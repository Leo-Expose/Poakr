#!/usr/bin/env python3
"""
Multi-street planning and pot control for Discard Hold'em.
Thinks ahead to future streets, manages SPR, plans bluffs/value.
"""
import numpy as np
from eval7 import equity_vs_range, parse_card
from hand3 import hand_type_2card, preflop_equity_cluster
from board_texture import analyze_board_texture, get_board_category


class StreetPlanner:
    """
    Plans multi-street strategy based on current hand, board, stacks, and ranges.
    """
    
    def __init__(self, my_hole, board, my_stack, opp_stack, pot, 
                 my_range_estimator, opp_range_estimator):
        self.my_hole = my_hole
        self.board = board
        self.my_stack = my_stack
        self.opp_stack = opp_stack
        self.pot = pot
        self.my_range_est = my_range_estimator
        self.opp_range_est = opp_range_estimator
        
        self.eff_stack = min(my_stack, opp_stack)
        self.spr = self.eff_stack / pot if pot > 0 else float('inf')
        self.street = self._get_street()
        
        # Hand categorization
        if len(my_hole) == 3:
            self.my_type, self.my_strength, _ = hand_type_3card(my_hole)
        else:
            self.my_type, self.my_strength, _ = hand_type_2card(my_hole)
        
        # Board texture
        self.board_texture = analyze_board_texture(board)
        self.board_category = get_board_category(board)
        
        # Range advantages
        self.range_advantage = self._compute_range_advantage()
        self.nut_advantage = self._compute_nut_advantage()
    
    def _get_street(self):
        if not self.board:
            return 'preflop'
        elif len(self.board) == 3:
            return 'flop'
        elif len(self.board) == 4:
            return 'turn'
        else:
            return 'river'
    
    def _compute_range_advantage(self):
        """Who has more equity on average?"""
        # Simplified: compare hand type distributions
        my_summary = self.my_range_est.get_range_summary()
        opp_summary = self.opp_range_est.get_range_summary()
        
        strong_types = ['trips', 'pair', 'flush_draw']
        my_strong = sum(my_summary.get(t, 0) for t in strong_types)
        opp_strong = sum(opp_summary.get(t, 0) for t in strong_types)
        
        return my_strong - opp_strong
    
    def _compute_nut_advantage(self):
        """Who has more nutted hands?"""
        my_summary = self.my_range_est.get_range_summary()
        opp_summary = self.opp_range_est.get_range_summary()
        
        my_nuts = my_summary.get('trips', 0) * 0.5 + my_summary.get('pair', 0) * 0.3
        opp_nuts = opp_summary.get('trips', 0) * 0.5 + opp_summary.get('pair', 0) * 0.3
        
        return my_nuts - opp_nuts
    
    def should_bet(self, my_equity, facing_bet=False):
        """
        Decide whether to bet/raise based on multi-street considerations.
        Returns: (should_bet, bet_size_fraction, reason)
        """
        if facing_bet:
            return self._should_call_raise(my_equity)
        
        # Initiative: we can bet
        if self.street == 'preflop':
            return self._preflop_bet_decision(my_equity)
        
        # Postflop
        if self.range_advantage > 0.1:
            # We have range advantage - bet wider
            if my_equity > 0.45:
                size = self._value_bet_size(my_equity)
                return True, size, "range_advantage_value"
            elif my_equity < 0.35 and self.board_category in ('dry', 'paired'):
                size = self._bluff_size()
                return True, size, "range_advantage_bluff"
        
        if self.nut_advantage > 0.15:
            # We have nut advantage - polarize
            if my_equity > 0.7:
                size = self._value_bet_size(my_equity)
                return True, size, "nut_advantage_value"
            elif my_equity < 0.3 and self.spr > 4:
                size = self._bluff_size()
                return True, size, "nut_advantage_bluff"
        
        # No clear advantage - check back medium hands
        if 0.45 < my_equity < 0.65:
            return False, 0, "pot_control"
        
        # Weak hand - check/fold
        return False, 0, "give_up"
    
    def _should_call_raise(self, my_equity):
        """Decision facing a bet."""
        pot_odds = 0  # Would be passed in real implementation
        required_equity = pot_odds * 1.1  # Slightly higher due to rake/implied odds
        
        if my_equity > required_equity + 0.1:
            # Clear call/raise
            if my_equity > 0.7 and self.nut_advantage > 0.1:
                return True, self._raise_size(my_equity), "strong_raise"
            return True, 0, "call"
        elif my_equity > required_equity - 0.05:
            return True, 0, "marginal_call"
        else:
            # Consider bluff raise
            if self.board_category == 'dry' and my_equity < 0.25 and self.spr > 3:
                return True, self._bluff_raise_size(), "bluff_raise"
            return False, 0, "fold"
    
    def _preflop_bet_decision(self, my_equity):
        """Preflop specific logic with 3 cards."""
        if my_equity > 0.6:
            return True, 0.5, "strong_open"  # 3x BB
        elif my_equity > 0.45:
            return True, 0.33, "standard_open"  # 2.5x BB
        elif my_equity > 0.35:
            return True, 0.25, "steal"  # 2x BB
        return False, 0, "fold"
    
    def _value_bet_size(self, equity):
        """Value bet sizing based on equity, SPR, board texture."""
        if self.spr > 10:
            base = 0.66  # Deep: larger bets
        elif self.spr > 5:
            base = 0.5
        else:
            base = 0.33  # Short: smaller bets
        
        # Adjust for board
        if self.board_texture['wet']:
            base *= 1.2  # Charge draws
        elif self.board_category == 'dry':
            base *= 0.8  # Smaller on dry
        
        # Adjust for equity
        if equity > 0.8:
            base *= 1.3
        elif equity > 0.65:
            base *= 1.1
        
        return min(1.0, base)  # Cap at pot
    
    def _bluff_size(self):
        """Bluff sizing."""
        if self.spr > 8:
            return 0.66
        elif self.spr > 4:
            return 0.5
        return 0.4
    
    def _raise_size(self, equity):
        """Raise size facing bet."""
        if equity > 0.8:
            return 3.0  # 3x bet
        elif equity > 0.65:
            return 2.5
        return 2.0
    
    def _bluff_raise_size(self):
        return 2.5
    
    def plan_future_streets(self, my_equity, action_taken):
        """
        Returns plan for future streets: {street: (action, size, condition)}
        """
        plan = {}
        
        if self.street == 'flop':
            if action_taken == 'bet' and my_equity > 0.6:
                plan['turn'] = ('bet', 0.66, 'continue_value')
                plan['river'] = ('bet', 0.5, 'value_or_give_up')
            elif action_taken == 'bet' and my_equity < 0.4:
                plan['turn'] = ('bet', 0.75, 'barrel_bluff')
                plan['river'] = ('check', 0, 'give_up_unless_improved')
            elif action_taken == 'check':
                plan['turn'] = ('probe_bet', 0.4, 'if_checked_to')
        
        elif self.street == 'turn':
            if action_taken == 'bet' and my_equity > 0.6:
                plan['river'] = ('bet', 0.5, 'value')
            elif action_taken == 'bet' and my_equity < 0.4:
                plan['river'] = ('bet', 0.75, 'triple_barrel_if_scare')
            elif action_taken == 'call':
                plan['river'] = ('check_call', 0, 'bluff_catch')
        
        return plan
    
    def implied_odds(self, my_equity, draw_type=None):
        """
        Calculate implied odds for calling with draws.
        """
        if draw_type is None:
            # Infer from hand
            if self.my_type.startswith('straight_draw') or self.my_type == 'flush_draw':
                draw_type = self.my_type
        
        if not draw_type:
            return 0
        
        # Probability of hitting
        if 'flush' in draw_type:
            hit_prob = 0.19  # ~9 outs
        elif 'open_ended' in draw_type:
            hit_prob = 0.17  # 8 outs
        elif 'one_gap' in draw_type:
            hit_prob = 0.13  # 6 outs
        else:
            hit_prob = 0.09  # 4 outs
        
        # Average win when hit (depends on board)
        if self.board_texture['wet']:
            win_when_hit = 0.7  # Often get paid less on wet boards
        else:
            win_when_hit = 0.85  # Get paid more on dry boards
        
        # Implied value
        implied_value = hit_prob * win_when_hit * self.eff_stack
        return implied_value


def geometric_sizing(pot, stack, target_ratio=0.5):
    """
    Geometric bet sizing: bet same fraction each street to put opponent all-in by river.
    """
    if pot == 0:
        return stack
    
    streets_left = 2  # turn + river
    # Solve: pot * (1 + r)^streets = stack
    r = (stack / pot) ** (1.0 / streets_left) - 1
    return min(pot * r, stack)


if __name__ == '__main__':
    # Test
    print("StreetPlanner module loaded")
    print("Use with actual range estimators in game")