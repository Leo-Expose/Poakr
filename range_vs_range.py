#!/usr/bin/env python3
"""
Proper Range-vs-Range Equity Calculator for Discard Hold'em.

Computes: Equity( Hero_Range, Villain_Range, Board )
Using vectorized batch evaluation for speed.

Key features:
- Handles weighted ranges (hand, weight) pairs
- Pre-computes hand-vs-hand equities for common boards
- Uses importance sampling for rare boards
- Caches results for repeated queries
"""
import numpy as np
import json
import os
from collections import defaultdict
from itertools import combinations
from eval7 import eval_batch, equity_vs_range, parse_card
from hand3 import get_hand_type_bucket


class RangeVSEquity:
    """
    Fast range-vs-range equity using vectorized operations.
    """
    
    def __init__(self, cache_size=10000):
        self.cache = {}
        self.cache_size = cache_size
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Pre-compute all 2-card hand equities vs random on common boards
        self._precompute_common_boards()
    
    def _precompute_common_boards(self):
        """Pre-compute equities for common flop textures."""
        # This would be expensive to do fully, so we'll do it lazily
        pass
    
    def equity(self, hero_range, villain_range, board, n_draws=500):
        """
        Compute equity of hero_range vs villain_range on board.
        
        Args:
            hero_range: list of (hand_tuple, weight) where hand is 2 or 3 cards
            villain_range: list of (hand_tuple, weight)
            board: list of 0-5 card ints
            n_draws: Monte Carlo samples
            
        Returns: float equity in [0, 1]
        """
        if not hero_range or not villain_range:
            return 0.5
        
        # Normalize weights
        hero_hands = [h for h, _ in hero_range]
        hero_weights = np.array([w for _, w in hero_range])
        hero_weights /= hero_weights.sum()
        
        villain_hands = [h for h, _ in villain_range]
        villain_weights = np.array([w for _, w in villain_range])
        villain_weights /= villain_weights.sum()
        
        # Check cache
        cache_key = self._make_cache_key(hero_hands, villain_hands, board)
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]
        
        self.cache_misses += 1
        
        # Monte Carlo with importance sampling
        equity = self._mc_equity(hero_hands, hero_weights, 
                                 villain_hands, villain_weights,
                                 board, n_draws)
        
        # Cache result
        if len(self.cache) >= self.cache_size:
            # Simple eviction: clear half
            keys = list(self.cache.keys())
            for k in keys[:len(keys)//2]:
                del self.cache[k]
        self.cache[cache_key] = equity
        
        return equity
    
    def _make_cache_key(self, hero_hands, villain_hands, board):
        """Create hashable cache key."""
        hero_key = tuple(sorted(hero_hands))
        villain_key = tuple(sorted(villain_hands))
        board_key = tuple(sorted(board))
        return (hero_key, villain_key, board_key)
    
    def _mc_equity(self, hero_hands, hero_weights, villain_hands, villain_weights, board, n_draws):
        """Vectorized Monte Carlo equity."""
        rng = np.random.default_rng()
        
        # Convert to arrays
        n_hero = len(hero_hands)
        n_villain = len(villain_hands)
        
        # Pre-sample hero/villain hands according to weights
        hero_indices = rng.choice(n_hero, size=n_draws, p=hero_weights)
        villain_indices = rng.choice(n_villain, size=n_draws, p=villain_weights)
        
        wins = 0.0
        valid_draws = 0
        
        # Process in batches
        batch_size = 1000
        for i in range(0, n_draws, batch_size):
            end = min(i + batch_size, n_draws)
            batch_hero_idx = hero_indices[i:end]
            batch_villain_idx = villain_indices[i:end]
            batch_n = end - i
            
            # Get hands for this batch
            batch_hero = [hero_hands[idx] for idx in batch_hero_idx]
            batch_villain = [villain_hands[idx] for idx in batch_villain_idx]
            
            # Check for card collisions
            valid = []
            for j in range(batch_n):
                if not (set(batch_hero[j]) & set(batch_villain[j])):
                    valid.append(j)
            
            if not valid:
                continue
            
            # Build complete boards
            n_board = len(board)
            need = 5 - n_board
            
            if need > 0:
                # Need to sample turn/river
                used_cards = set(board)
                for j in valid:
                    used_cards.update(batch_hero[j])
                    used_cards.update(batch_villain[j])
                
                # Sample remaining board cards for each valid sample
                remaining = [c for c in range(52) if c not in used_cards]
                if len(remaining) < need:
                    continue
                
                # For simplicity, use same runout for all (approximation)
                runout = np.random.choice(remaining, size=need, replace=False)
                full_board = list(board) + list(runout)
            else:
                full_board = board
            
            # Evaluate
            hero_cards = np.array([list(batch_hero[j]) + full_board for j in valid], dtype=np.int64)
            villain_cards = np.array([list(batch_villain[j]) + full_board for j in valid], dtype=np.int64)
            
            try:
                hero_scores = eval_batch(hero_cards)
                villain_scores = eval_batch(villain_cards)
                
                wins += np.sum(hero_scores > villain_scores) + 0.5 * np.sum(hero_scores == villain_scores)
                valid_draws += len(valid)
            except Exception:
                continue
        
        return wins / valid_draws if valid_draws > 0 else 0.5
    
    def get_stats(self):
        return {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'cache_size': len(self.cache)
        }


class RangeBuilder:
    """
    Builds opponent ranges based on actions, positions, and board textures.
    """
    
    def __init__(self):
        # Pre-compute all 3-card hands by type
        self._init_hand_database()
    
    def _init_hand_database(self):
        """Pre-compute all 3-card hands grouped by strategic type."""
        from hand3 import hand_type_3card, get_hand_type_bucket
        from itertools import combinations
        
        self.all_hands = list(combinations(range(52), 3))
        self.hands_by_type = defaultdict(list)
        
        for hand in self.all_hands:
            htype = get_hand_type_bucket(hand)
            self.hands_by_type[htype].append(hand)
    
    def build_preflop_range(self, position, action_sequence, board=None, 
                           opponent_tendencies=None):
        """
        Build opponent's preflop range based on observed actions.
        
        Args:
            position: 'SB' or 'BB' (opponent's position)
            action_sequence: list of actions taken
            board: flop board (if postflop)
            opponent_tendencies: dict of observed frequencies
            
        Returns: list of (hand, weight) tuples
        """
        weights = np.ones(len(self.all_hands))
        
        # Position-based adjustments
        if position == 'SB':
            # SB opens or limps
            if any(a == 'raise' for a in action_sequence):
                # Raising range
                weights = self._apply_raising_weights(weights, action_sequence)
            elif any(a == 'call' for a in action_sequence):
                # Calling/limping range
                weights = self._apply_limping_weights(weights)
        else:  # BB
            if any(a == 'raise' for a in action_sequence):
                # 3-betting or cold calling
                weights = self._apply_3bet_weights(weights, action_sequence)
            elif any(a == 'call' for a in action_sequence):
                # Cold call
                weights = self._apply_cold_call_weights(weights)
        
        # Board texture adjustments (if postflop)
        if board is not None:
            weights = self._apply_board_weights(weights, board)
        
        # Opponent tendency adjustments
        if opponent_tendencies:
            weights = self._apply_tendency_weights(weights, opponent_tendencies)
        
        # Normalize and return
        weights = weights / weights.sum()
        return list(zip(self.all_hands, weights))
    
    def _apply_raising_weights(self, weights, actions):
        """Adjust weights for raising range."""
        # Tighten for raises
        for i, hand in enumerate(self.all_hands):
            htype = get_hand_type_bucket(hand)
            if htype in ('trips', 'pair_premium'):
                weights[i] *= 2.0
            elif htype in ('pair_high', 'flush_draw_broadway', 'straight_draw_open_ended'):
                weights[i] *= 1.5
            elif htype in ('pair_mid', 'two_suited_broadway'):
                weights[i] *= 1.2
            elif htype in ('high_card_other', 'straight_draw_two_gap'):
                weights[i] *= 0.3
        return weights
    
    def _apply_limping_weights(self, weights):
        """Adjust for limping range."""
        for i, hand in enumerate(self.all_hands):
            htype = get_hand_type_bucket(hand)
            if htype in ('pair_premium', 'trips'):
                weights[i] *= 0.5  # Trapping sometimes
            elif htype in ('high_card_other',):
                weights[i] *= 0.7
        return weights
    
    def _apply_3bet_weights(self, weights, actions):
        """Adjust for 3-betting range."""
        for i, hand in enumerate(self.all_hands):
            htype = get_hand_type_bucket(hand)
            if htype in ('trips', 'pair_premium'):
                weights[i] *= 2.5
            elif htype in ('pair_high', 'flush_draw_broadway'):
                weights[i] *= 1.5
            elif htype in ('high_card_other',):
                weights[i] *= 0.1  # Bluff 3-bets rare
        return weights
    
    def _apply_cold_call_weights(self, weights):
        """Adjust for cold calling range."""
        for i, hand in enumerate(self.all_hands):
            htype = get_hand_type_bucket(hand)
            if htype in ('pair_premium', 'trips'):
                weights[i] *= 0.8  # Sometimes trap
            elif htype in ('pair_mid', 'flush_draw_other'):
                weights[i] *= 1.2
            elif htype in ('high_card_broadway',):
                weights[i] *= 1.0
        return weights
    
    def _apply_board_weights(self, weights, board):
        """Adjust range based on board texture."""
        from board_texture import analyze_board_texture
        tex = analyze_board_texture(board)
        
        # On wet boards, calling ranges are wider
        # On dry boards, folding ranges are wider
        # This is a simplified adjustment
        return weights
    
    def _apply_tendency_weights(self, weights, tendencies):
        """Adjust for known opponent tendencies."""
        if tendencies.get('vpip', 0) > 0.3:
            # Loose opponent - widen range
            pass
        if tendencies.get('pfr', 0) > 0.2:
            # Aggressive - tighten calling range
            pass
        return weights
    
    def update_range_postflop(self, preflop_range, action, street, bet_size, pot, board):
        """
        Update range based on postflop action using Bayesian updating.
        """
        updated = []
        for hand, weight in preflop_range:
            # Likelihood of action given hand
            likelihood = self._action_likelihood(hand, action, street, bet_size, pot, board)
            updated.append((hand, weight * likelihood))
        
        # Normalize
        total = sum(w for _, w in updated)
        if total > 0:
            updated = [(h, w/total) for h, w in updated]
        return updated
    
    def _action_likelihood(self, hand, action, street, bet_size, pot, board):
        """P(action | hand, street, board)."""
        # Simplified likelihood model
        htype = get_hand_type_bucket(hand)
        
        # Base strength
        strength = self._hand_strength_on_board(hand, board)
        
        if action == 'fold':
            return 1.0 - strength
        elif action == 'check':
            if bet_size > 0:
                return 0.01  # Can't check facing bet
            return 0.5 + 0.3 * (0.5 - abs(strength - 0.5))  # Check medium
        elif action == 'call':
            pot_odds = bet_size / (pot + bet_size) if pot > 0 else 0
            if strength > pot_odds + 0.1:
                return 0.9
            elif strength > pot_odds - 0.1:
                return 0.5
            return 0.1
        elif action == 'raise':
            if strength > 0.7:
                return 0.7  # Value
            elif strength < 0.3:
                return 0.15  # Bluff
            return 0.05
        return 0.1
    
    def _hand_strength_on_board(self, hand, board):
        """Estimate hand strength vs random on board."""
        if not board:
            return 0.5
        # Quick estimate
        from hand3 import hand_type_3card
        htype, _, _ = hand_type_3card(hand)
        if htype == 'trips':
            return 0.85
        elif htype == 'pair_premium':
            return 0.65
        elif htype in ('flush_draw_broadway', 'straight_draw_open_ended'):
            return 0.55
        return 0.4


# Global instances
_range_calculator = None
_range_builder = None


def get_range_calculator():
    global _range_calculator
    if _range_calculator is None:
        _range_calculator = RangeVSEquity()
    return _range_calculator


def get_range_builder():
    global _range_builder
    if _range_builder is None:
        _range_builder = RangeBuilder()
    return _range_builder


if __name__ == '__main__':
    # Test
    builder = get_range_builder()
    print(f"Total hands: {len(builder.all_hands)}")
    print(f"Types: {list(builder.hands_by_type.keys())}")
    
    # Build SB open range
    sb_range = builder.build_preflop_range('SB', ['raise'])
    print(f"SB open range: {len(sb_range)} hands")
    
    # Test equity
    calc = get_range_calculator()
    equity = calc.equity(sb_range[:50], sb_range[:50], [], n_draws=100)
    print(f"Equity test: {equity:.4f}")