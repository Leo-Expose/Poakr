#!/usr/bin/env python3
"""
Simultaneous Discard Game Theory for Discard Hold'em.

After the flop, both players simultaneously choose 1 of 3 cards to discard.
This is a Bayesian game where each player knows their own 3 cards + the flop,
but not the opponent's 3 cards. The discard choice affects the resulting 2-card
hand that plays the remaining streets.

Key insight: The discard is NOT just "keep best 2 cards". It's strategic:
- Block opponent's outs
- Disguise hand strength
- Manipulate opponent's range estimation
- Create bluffing opportunities on later streets
"""
import numpy as np
from itertools import combinations
from eval7 import equity_vs_range, parse_card
from hand3 import hand_type_3card, best_discard_for_type, preflop_equity_cluster
from range_estimator import RangeEstimator


class DiscardGame:
    """
    Models the simultaneous discard as a Bayesian game.
    Computes optimal mixed strategy for discarding.
    """
    
    def __init__(self, my_hole, board, opp_range_estimator):
        """
        my_hole: list of 3 card ids (our 3 cards)
        board: list of 3 card ids (flop)
        opp_range_estimator: RangeEstimator with opponent's preflop range
        """
        self.my_hole = my_hole
        self.board = board
        self.opp_estimator = opp_range_estimator
        
        # Our possible discards (0, 1, 2)
        self.my_actions = [0, 1, 2]
        
        # Precompute our equity for each discard vs opponent's range
        self.my_equities = {}  # my_action -> equity
        self._compute_my_equities()
        
        # Precompute opponent's likely discards for each hand in their range
        self.opp_discard_dist = self._compute_opp_discard_distribution()
    
    def _compute_my_equities(self):
        """Compute our equity for each discard option vs opponent's range."""
        opp_range = self.opp_estimator.current_range
        
        for action in self.my_actions:
            kept = [self.my_hole[j] for j in range(3) if j != action]
            eq = self._equity_vs_range(kept, opp_range, self.board)
            self.my_equities[action] = eq
    
    def _equity_vs_range(self, my_kept, opp_range, board):
        """Equity of our 2-card hand vs opponent's range."""
        if not opp_range:
            return equity_vs_range(my_kept, board, n_draws=500, seed=42)
        
        # Sample from opponent's range
        opp_hands = list(opp_range.keys())
        opp_weights = np.array(list(opp_range.values()))
        opp_weights /= opp_weights.sum()
        
        rng = np.random.default_rng(hash(tuple(my_kept)) & 0xFFFFFFFF)
        wins = 0.0
        total = 0
        
        for _ in range(200):
            opp_idx = rng.choice(len(opp_hands), p=opp_weights)
            opp_hand = opp_hands[opp_idx]
            
            # Check collision
            if set(my_kept) & set(opp_hand):
                continue
            
            # Opponent will also discard optimally
            opp_best_eq, _, _ = preflop_equity_cluster(opp_hand, n_draws=100)
            # This is recursive - simplified for now
            opp_kept = self._best_kept_for_opp(opp_hand)
            
            eq = equity_vs_range(my_kept, board, n_draws=1, seed=rng.integers(0, 2**32))
            # Actually need head-to-head
            full_board = self._simulate_runout(my_kept + list(opp_kept) + board)
            # Simplified
            wins += eq
            total += 1
        
        return wins / total if total > 0 else 0.5
    
    def _best_kept_for_opp(self, opp_hand):
        """Opponent's best 2-card hand (simplified: max equity vs random)."""
        best_eq = -1
        best_kept = None
        for i in range(3):
            kept = [opp_hand[j] for j in range(3) if j != i]
            eq = equity_vs_range(kept, self.board, n_draws=200, seed=hash(tuple(sorted(kept))))
            if eq > best_eq:
                best_eq = eq
                best_kept = kept
        return best_kept
    
    def _simulate_runout(self, known_cards):
        """Simulate turn/river."""
        used = set(known_cards)
        rem = [c for c in range(52) if c not in used]
        rng = np.random.default_rng()
        return rng.choice(rem, size=2, replace=False)
    
    def _compute_opp_discard_distribution(self):
        """
        For each hand in opponent's range, what discard would they choose?
        Returns: dict of hand -> {discard_action: probability}
        """
        dist = {}
        for hand, prob in self.opp_estimator.current_range.items():
            # Opponent chooses discard to maximize their equity
            opp_equities = {}
            for opp_action in [0, 1, 2]:
                kept = [hand[j] for j in range(3) if j != opp_action]
                eq = equity_vs_range(kept, self.board, n_draws=300, seed=hash(tuple(sorted(kept))))
                opp_equities[opp_action] = eq
            
            # Softmax over equities (with temperature)
            best_eq = max(opp_equities.values())
            probs = {}
            temp = 0.02  # Low temperature = near-deterministic
            for a, eq in opp_equities.items():
                probs[a] = np.exp((eq - best_eq) / temp)
            total = sum(probs.values())
            for a in probs:
                probs[a] /= total
            
            dist[hand] = probs
        
        return dist
    
    def exploit_opp_discard_tell(self, observed_opp_discard):
        """
        Update opponent range based on their observed discard.
        This is the KEY information gain from the simultaneous discard!
        """
        new_range = {}
        total = 0.0
        
        for hand, prior_prob in self.opp_estimator.current_range.items():
            # Likelihood they'd discard this card
            if hand in self.opp_discard_dist:
                likelihood = self.opp_discard_dist[hand].get(observed_opp_discard, 0.01)
            else:
                # Compute on the fly
                opp_equities = {}
                for opp_action in [0, 1, 2]:
                    kept = [hand[j] for j in range(3) if j != opp_action]
                    eq = equity_vs_range(kept, self.board, n_draws=200, seed=hash(tuple(sorted(kept))))
                    opp_equities[opp_action] = eq
                best_eq = max(opp_equities.values())
                likelihood = 0.8 if opp_equities[observed_opp_discard] == best_eq else 0.1
            
            new_range[hand] = prior_prob * likelihood
            total += new_range[hand]
        
        if total > 0:
            for hand in new_range:
                new_range[hand] /= total
        
        self.opp_estimator.current_range = new_range
    
    def optimal_mixed_strategy(self):
        """
        Compute optimal mixed strategy for our discard.
        Uses game theory: we want to maximize minimum equity (maximin)
        or exploit known opponent tendencies.
        """
        # Simple: if one discard dominates, use it
        best_action = max(self.my_equities, key=self.my_equities.get)
        best_eq = self.my_equities[best_action]
        
        # Check if we should mix (e.g., for deception)
        second_best = max(v for k, v in self.my_equities.items() if k != best_action)
        
        # If equities are close, mix for balance
        if best_eq - second_best < 0.02:
            # Mix between top 2
            actions = sorted(self.my_equities, key=self.my_equities.get, reverse=True)[:2]
            probs = {a: 0.5 for a in actions}
            return probs
        
        # Otherwise pure strategy
        return {best_action: 1.0}
    
    def get_discard_info_value(self):
        """
        How much information does our discard reveal to opponent?
        Lower is better (more deceptive).
        """
        # If we always discard the same card type, opponent learns our hand type
        htype, _, _ = hand_type_3card(self.my_hole)
        if htype in ('trips', 'pair'):
            # These have obvious discards (the kicker/odd card)
            return 0.8  # High information leak
        elif htype == 'flush_draw':
            # Discard off-suit card - reveals we had flush draw
            return 0.6
        return 0.3  # Low info for straight draws/high card


def solve_discard_game(my_hole, board, opp_range, n_iterations=100):
    """
    Solve the simultaneous discard game using fictitious play.
    Returns optimal mixed strategy for both players.
    """
    # Discretize opponent range into types
    opp_types = defaultdict(list)
    for hand, prob in opp_range.items():
        htype, _, _ = hand_type_3card(hand)
        opp_types[htype].append((hand, prob))
    
    # Normalize within each type
    for htype in opp_types:
        total = sum(p for _, p in opp_types[htype])
        opp_types[htype] = [(h, p/total) for h, p in opp_types[htype]]
    
    # Our strategy: distribution over {0, 1, 2}
    my_strategy = {0: 1/3, 1: 1/3, 2: 1/3}
    opp_strategy = {htype: {0: 1/3, 1: 1/3, 2: 1/3} for htype in opp_types}
    
    for iteration in range(n_iterations):
        # Best response to opponent strategy
        my_utilities = {a: 0.0 for a in [0, 1, 2]}
        
        for my_action in [0, 1, 2]:
            my_kept = [my_hole[j] for j in range(3) if j != my_action]
            
            for htype, hands in opp_types.items():
                for opp_hand, opp_prob in hands:
                    # Opponent's mixed strategy for this hand type
                    for opp_action, opp_act_prob in opp_strategy[htype].items():
                        opp_kept = [opp_hand[j] for j in range(3) if j != opp_action]
                        
                        # Equity
                        eq = equity_vs_range(my_kept, opp_kept, board, n_draws=100, seed=42)
                        my_utilities[my_action] += eq * opp_prob * opp_act_prob
        
        # Update our strategy (smooth best response)
        best_action = max(my_utilities, key=my_utilities.get)
        for a in my_strategy:
            my_strategy[a] = 0.9 * my_strategy[a] + 0.1 * (1.0 if a == best_action else 0.0)
        
        # Renormalize
        total = sum(my_strategy.values())
        for a in my_strategy:
            my_strategy[a] /= total
    
    return my_strategy


# Fast heuristic for actual play
def choose_discard_gto(my_hole, board, opp_range_estimator, pot, street='flop'):
    """
    GTO-inspired discard choice with exploitation.
    """
    # First, get pure equity-maximizing discard
    best_eq, all_eq, best_idx = preflop_equity_cluster(my_hole, n_draws=500)
    
    # Check if we should deviate for strategic reasons
    htype, hstrength, _ = hand_type_3card(my_hole)
    
    # Get opponent range summary
    opp_summary = opp_range_estimator.get_range_summary()
    opp_strong = opp_summary.get('trips', 0) + opp_summary.get('pair', 0)
    
    # Strategic adjustments:
    if htype == 'trips':
        # Always discard the kicker (obvious, no choice)
        return best_idx
    
    if htype == 'pair':
        # Usually discard kicker, but sometimes discard pair card to disguise
        if opp_strong > 0.3 and pot > 20:
            # Opponent likely strong, disguise by discarding pair card
            # Find which card is the pair
            ranks = [c // 4 for c in my_hole]
            from collections import Counter
            rc = Counter(ranks)
            pair_rank = max(r for r, c in rc.items() if c == 2)
            pair_indices = [i for i, c in enumerate(my_hole) if c // 4 == pair_rank]
            if pair_indices and np.random.random() < 0.1:
                return pair_indices[0]  # Discard one of the pair!
        return best_idx
    
    if htype == 'flush_draw':
        # Discard off-suit card (standard)
        # But if board has flush draw, consider discarding suited card to block
        board_suits = [c % 4 for c in board]
        my_suits = [c % 4 for c in my_hole]
        if len(set(board_suits)) == 1:  # Monotone board
            # Block their flush
            suited_idx = [i for i, s in enumerate(my_suits) if s == board_suits[0]]
            if suited_idx:
                return suited_idx[0]
        return best_idx
    
    if htype.startswith('straight_draw'):
        # Standard: discard the card that doesn't help straight
        return best_idx
    
    # High card: sometimes discard high card to disguise
    if htype == 'high_card' and pot > 30:
        if np.random.random() < 0.15:
            # Discard highest card occasionally
            high_idx = max(range(3), key=lambda i: my_hole[i] // 4)
            return high_idx
    
    return best_idx


if __name__ == '__main__':
    # Test
    my_hole = [parse_card(c) for c in ["As", "Ks", "Qs"]]
    board = [parse_card(c) for c in ["Js", "Ts", "2h"]]
    
    print(f"My hole: {' '.join(['As', 'Ks', 'Qs'])}")
    print(f"Board: {' '.join(['Js', 'Ts', '2h'])}")
    
    htype, hstrength, _ = hand_type_3card(my_hole)
    print(f"Hand type: {htype}")
    
    best_eq, all_eq, best_idx = preflop_equity_cluster(my_hole, n_draws=1000)
    print(f"Equities: {all_eq}")
    print(f"Best discard: {best_idx} (eq={best_eq:.4f})")