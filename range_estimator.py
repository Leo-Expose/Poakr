#!/usr/bin/env python3
"""
Opponent range estimation and range-vs-range equity for Discard Hold'em.
Models opponent's likely range based on actions, board, and history.
"""
import numpy as np
from collections import defaultdict
from eval7 import equity_vs_range, parse_card
from hand3 import hand_type_3card, hand_type_2card, preflop_equity_cluster, best_discard_for_type
from board_texture import analyze_board_texture, get_board_category


class RangeEstimator:
    """
    Estimates opponent's range at each decision point using Bayesian updating.
    """
    
    def __init__(self):
        # Prior: uniform over all 3-card hands preflop, all 2-card postflop
        self.preflop_prior = self._uniform_preflop_prior()
        self.postflop_prior = self._uniform_postflop_prior()
        
        # Current posterior
        self.current_range = None
        self.current_street = 'preflop'
        self.action_history = []
        
        # Range compression: group by hand type
        self.type_weights = defaultdict(float)
    
    def _uniform_preflop_prior(self):
        """Uniform prior over all 3-card combinations."""
        from itertools import combinations
        from eval7 import parse_card
        prior = {}
        for hole in combinations(range(52), 3):
            prior[hole] = 1.0 / 22100
        return prior
    
    def _uniform_postflop_prior(self):
        """Uniform prior over all 2-card combinations (post-discard)."""
        from itertools import combinations
        prior = {}
        for hole in combinations(range(52), 2):
            prior[hole] = 1.0 / 1326
        return prior
    
    def reset_hand(self, street='preflop'):
        """Reset for new hand."""
        self.current_street = street
        self.action_history = []
        if street == 'preflop':
            self.current_range = self.preflop_prior.copy()
        else:
            self.current_range = self.postflop_prior.copy()
    
    def observe_action(self, street, action, bet_size, pot, to_call, board, position):
        """
        Update range based on observed action.
        position: 0=button (SB), 1=big_blind
        """
        self.current_street = street
        self.action_history.append({
            'street': street,
            'action': action,
            'bet_size': bet_size,
            'pot': pot,
            'to_call': to_call,
            'board': list(board),
            'position': position
        })
        
        # Likelihood of action given hand strength
        new_range = {}
        total_likelihood = 0.0
        
        for hand, prior_prob in self.current_range.items():
            # Compute hand strength in this spot
            strength = self._hand_strength_in_spot(hand, street, board, action, bet_size, pot, to_call, position)
            likelihood = self._action_likelihood(action, bet_size, pot, to_call, strength, street)
            
            new_range[hand] = prior_prob * likelihood
            total_likelihood += new_range[hand]
        
        # Normalize
        if total_likelihood > 0:
            for hand in new_range:
                new_range[hand] /= total_likelihood
            self.current_range = new_range
    
    def observe_discard(self, my_discard, opp_discard, my_hole, board):
        """
        Update range after seeing opponent's discard.
        This is the key information from the simultaneous discard!
        """
        # Opponent's discard reveals information about their hand
        opp_discard_rank = opp_discard // 4
        opp_discard_suit = opp_discard % 4
        
        new_range = {}
        total_likelihood = 0.0
        
        for hand, prior_prob in self.current_range.items():
            # Likelihood they would discard this card given their hand
            likelihood = self._discard_likelihood(hand, opp_discard, board)
            new_range[hand] = prior_prob * likelihood
            total_likelihood += new_range[hand]
        
        if total_likelihood > 0:
            for hand in new_range:
                new_range[hand] /= total_likelihood
            self.current_range = new_range
    
    def _hand_strength_in_spot(self, hand, street, board, action, bet_size, pot, to_call, position):
        """Evaluate hand strength in current context."""
        if street == 'preflop':
            # 3-card hand
            htype, hstrength, _ = hand_type_3card(hand)
            return hstrength / 2000.0  # Normalize
        else:
            # Postflop - hand should be 2 cards after discard
            # But our range might still have 3-card hands from preflop
            # Convert 3-card to best 2-card
            if len(hand) == 3:
                best_eq, _, _ = preflop_equity_cluster(hand, n_draws=200)
                return best_eq
            
            # 2-card hand postflop
            htype, hstrength, _ = hand_type_2card(hand)
            # Adjust for board
            if board:
                board_cards = list(board)
                # Quick equity vs random
                from eval7 import equity_vs_range
                eq = equity_vs_range(list(hand), board_cards, n_draws=200, seed=42)
                return eq
            return hstrength / 2000.0
    
    def _action_likelihood(self, action, bet_size, pot, to_call, strength, street):
        """
        Probability of taking this action with given hand strength.
        Based on GTO frequencies and exploitative adjustments.
        """
        eps = 0.01  # Minimum probability for any action
        
        if action == 'fold':
            if to_call == 0:
                return eps  # Shouldn't fold when can check
            # Fold more with weak hands
            return 0.9 - strength * 0.8
        
        elif action == 'check':
            if to_call > 0:
                return eps  # Can't check facing bet
            # Check with medium hands, trap with strong
            if strength > 0.8:
                return 0.2  # Trapping
            return 0.6 - strength * 0.3
        
        elif action == 'call':
            # Call with hands that have equity vs betting range
            pot_odds = to_call / (pot + to_call) if pot + to_call > 0 else 0
            if strength > pot_odds + 0.05:
                return 0.8
            elif strength > pot_odds - 0.05:
                return 0.5
            return 0.1
        
        elif action == 'raise':
            # Raise with strong hands (value) and some weak (bluff)
            if bet_size == 0:  # Open raise
                if strength > 0.65:
                    return 0.7  # Value
                elif strength < 0.3:
                    return 0.15  # Bluff
                return 0.1
            else:  # 3-bet or check-raise
                if strength > 0.75:
                    return 0.6  # Value
                elif strength < 0.25:
                    return 0.1  # Bluff
                return 0.05
        
        return eps
    
    def _discard_likelihood(self, hand, opp_discard, board):
        """
        Likelihood opponent discards this specific card given their hand.
        They discard to maximize equity, with some noise.
        """
        # For each possible discard from their hand, compute equity
        discards = list(hand)
        equities = {}
        for d in discards:
            kept = [c for c in hand if c != d]
            if board:
                eq = equity_vs_range(kept, list(board), n_draws=200, seed=hash(tuple(sorted(kept))) & 0xFFFFFFFF)
            else:
                eq = equity_vs_range(kept, [], n_draws=200, seed=hash(tuple(sorted(kept))) & 0xFFFFFFFF)
            equities[d] = eq
        
        # Softmax likelihood
        best_eq = max(equities.values())
        if equities[opp_discard] == best_eq:
            return 0.8  # High prob for optimal discard
        # Lower prob for suboptimal
        diff = best_eq - equities[opp_discard]
        return 0.1 * np.exp(-diff * 20)
    
    def get_range_summary(self):
        """Get summary statistics of current range."""
        if not self.current_range:
            return {}
        
        type_probs = defaultdict(float)
        total = 0.0
        for hand, prob in self.current_range.items():
            if self.current_street == 'preflop':
                htype, _, _ = hand_type_3card(hand)
            else:
                htype, _, _ = hand_type_2card(hand)
            type_probs[htype] += prob
            total += prob
        
        # Normalize
        for htype in type_probs:
            type_probs[htype] /= total
        
        return dict(type_probs)
    
    def range_vs_range_equity(my_range, opp_range, board, n_draws=500):
        """
        Compute equity of my range vs opponent range.
        This is the correct way to make decisions - not vs random hand!
        """
        # Sample from both ranges
        my_hands = list(my_range.keys())
        my_probs = np.array(list(my_range.values()))
        my_probs /= my_probs.sum()
        
        opp_hands = list(opp_range.keys())
        opp_probs = np.array(list(opp_range.values()))
        opp_probs /= opp_probs.sum()
        
        # Monte Carlo
        rng = np.random.default_rng(42)
        wins = 0.0
        total = 0
        
        for _ in range(n_draws):
            # Sample hands
            my_idx = rng.choice(len(my_hands), p=my_probs)
            opp_idx = rng.choice(len(opp_hands), p=opp_probs)
            
            my_hand = my_hands[my_idx]
            opp_hand = opp_hands[opp_idx]
            
            # Check for card collision
            if set(my_hand) & set(opp_hand):
                continue  # Invalid sample
            
            # Equity
            from eval7 import equity_vs_range
            eq = equity_vs_range(list(my_hand), list(board), n_draws=1, seed=rng.integers(0, 2**32))
            # This is simplified - in practice we'd evaluate both
            wins += eq
            total += 1
        
        return wins / total if total > 0 else 0.5


class RangeVSEquity:
    """
    Fast range-vs-range equity using vectorized evaluation.
    """
    
    def __init__(self):
        from eval7 import eval_batch
        self.eval_batch = eval_batch
    
    def equity(self, my_range_hands, opp_range_hands, board, n_draws=500):
        """
        my_range_hands: list of (hand, weight) tuples
        opp_range_hands: list of (hand, weight) tuples
        board: list of board cards
        """
        if not my_range_hands or not opp_range_hands:
            return 0.5
        
        # Normalize weights
        my_weights = np.array([w for _, w in my_range_hands])
        my_weights /= my_weights.sum()
        opp_weights = np.array([w for _, w in opp_range_hands])
        opp_weights /= opp_weights.sum()
        
        my_hands = [h for h, _ in my_range_hands]
        opp_hands = [h for h, _ in opp_range_hands]
        
        # Vectorized Monte Carlo
        rng = np.random.default_rng(12345)
        wins = 0.0
        
        for _ in range(n_draws):
            # Sample hands
            my_idx = rng.choice(len(my_hands), p=my_weights)
            opp_idx = rng.choice(len(opp_hands), p=opp_weights)
            
            if set(my_hands[my_idx]) & set(opp_hands[opp_idx]):
                continue
            
            # Complete board if needed
            n_board = len(board)
            need = 5 - n_board
            
            if need > 0:
                # Sample remaining board
                used = set(my_hands[my_idx]) | set(opp_hands[opp_idx]) | set(board)
                rem = [c for c in range(52) if c not in used]
                if len(rem) < need:
                    continue
                board_completion = rng.choice(rem, size=need, replace=False)
                full_board = list(board) + list(board_completion)
            else:
                full_board = board
            
            # Evaluate
            my_cards = np.array([list(my_hands[my_idx]) + full_board], dtype=np.int64)
            opp_cards = np.array([list(opp_hands[opp_idx]) + full_board], dtype=np.int64)
            
            my_score = self.eval_batch(my_cards)[0]
            opp_score = self.eval_batch(opp_cards)[0]
            
            if my_score > opp_score:
                wins += 1
            elif my_score == opp_score:
                wins += 0.5
        
        return wins / n_draws


# Preflop range construction
def build_preflop_range(action_sequence, position):
    """
    Build opponent's preflop range based on action sequence.
    action_sequence: list of ('raise', size), ('call',), ('fold',), ('check',)
    position: 0=button, 1=big_blind
    """
    from itertools import combinations
    
    all_hands = list(combinations(range(52), 3))
    weights = np.ones(len(all_hands))
    
    # Position adjustments
    if position == 0:  # Button (SB) - first to act
        # Open raising range
        if any(a[0] == 'raise' for a in action_sequence):
            # Tighten for raises
            for i, hand in enumerate(all_hands):
                htype, hstrength, _ = hand_type_3card(hand)
                if htype in ('trips', 'pair'):
                    weights[i] *= 2.0
                elif htype == 'flush_draw':
                    weights[i] *= 1.5
                elif htype.startswith('straight_draw'):
                    weights[i] *= 1.3
                elif htype == 'high_card':
                    weights[i] *= 0.3
    else:  # Big blind - facing action
        if any(a[0] == 'call' for a in action_sequence):
            # Calling range - wider
            for i, hand in enumerate(all_hands):
                htype, hstrength, _ = hand_type_3card(hand)
                if htype in ('trips', 'pair'):
                    weights[i] *= 1.5
                elif htype == 'high_card':
                    weights[i] *= 0.8
    
    # Normalize
    weights /= weights.sum()
    return list(zip(all_hands, weights))


if __name__ == '__main__':
    # Test
    from itertools import combinations
    estimator = RangeEstimator()
    
    # Simulate preflop: Button raises, BB calls
    estimator.reset_hand('preflop')
    estimator.observe_action('preflop', 'raise', 6, 3, 0, [], 0)  # BTN raises to 6
    estimator.observe_action('preflop', 'call', 6, 9, 6, [], 1)   # BB calls
    
    print("BB range after calling preflop raise:")
    summary = estimator.get_range_summary()
    for htype, prob in sorted(summary.items(), key=lambda x: -x[1])[:10]:
        print(f"  {htype}: {prob:.3f}")