#!/usr/bin/env python3
"""
Tournament-aware strategy for Pokerbots competition.

Stage 1 (Swiss Qualifier): 400 hands, capped at ±400 chips per match
- 6 rounds, ~200 duplicate deals (400 hands)
- Match points: 1 for Win, 0.5 for Draw, 0 for Loss
- Tie-breakers: capped chips per hand formula

Stage 2 (Top 32 Finals): 1000 hands, capped at ±1000 chips per match
- Full round-robin, ~500 duplicate deals
- Scores reset

Key insight: The CAP changes optimal strategy!
- In Stage 1: Each hand max impact = 400/400 = 1 chip per hand average
- In Stage 2: Each hand max impact = 1000/1000 = 1 chip per hand average
- But variance matters more in Stage 2 due to more hands

Optimal play:
- When ahead by > cap: Play safe (WinLock)
- When behind by > cap: High variance needed
- Near cap boundary: Adjust variance
"""

import numpy as np


class TournamentContext:
    """
    Manages tournament state and adjusts strategy based on stage,
    match score, and cap.
    """
    
    def __init__(self, stage=1, match_cap=400, total_hands=400):
        self.stage = stage
        self.match_cap = match_cap
        self.total_hands = total_hands
        
        # Match state
        self.match_net = 0
        self.hands_played = 0
        self.opp_match_net = 0
        
        # Round state (for Swiss)
        self.round = 1
        self.match_points = 0.0
        self.opp_match_points = 0.0
    
    def update_hand(self, net, hand_id):
        """Update after each hand."""
        self.match_net += net
        self.hands_played = hand_id
    
    def get_match_state(self):
        """
        Returns: 'winning_big', 'winning', 'tied', 'losing', 'losing_big'
        """
        remaining = self.total_hands - self.hands_played
        max_possible_swing = remaining * 50  # Realistic max per hand
        
        if self.match_net > self.match_cap - 50:
            return 'winning_big'
        elif self.match_net > 50:
            return 'winning'
        elif self.match_net > -50:
            return 'tied'
        elif self.match_net > -self.match_cap + 50:
            return 'losing'
        else:
            return 'losing_big'
    
    def should_reduce_variance(self):
        """True if we should play safe (reduce variance)."""
        state = self.get_match_state()
        if state == 'winning_big':
            return True
        # Also reduce variance if we're close to cap
        if abs(self.match_net) > self.match_cap * 0.7:
            return True
        return False
    
    def should_increase_variance(self):
        """True if we should play high variance (catch up)."""
        state = self.get_match_state()
        if state == 'losing_big':
            return True
        # If behind and few hands left
        remaining = self.total_hands - self.hands_played
        if self.match_net < -100 and remaining < 50:
            return True
        return False
    
    def get_variance_multiplier(self):
        """
        Returns multiplier for bet sizing and bluff frequency.
        > 1.0 = more aggressive, < 1.0 = more passive
        """
        if self.should_reduce_variance():
            return 0.6  # Play tight, smaller bets, fewer bluffs
        elif self.should_increase_variance():
            return 1.4  # Play loose, larger bets, more bluffs
        return 1.0  # Neutral
    
    def get_bluff_frequency_adj(self):
        """Adjustment to base bluff frequency."""
        mult = self.get_variance_multiplier()
        if mult < 1.0:
            return 0.5  # Half bluffs when protecting lead
        elif mult > 1.0:
            return 1.5  # More bluffs when behind
        return 1.0
    
    def get_call_threshold_adj(self):
        """Adjustment to call threshold (pot odds multiplier)."""
        if self.should_reduce_variance():
            return 1.1  # Need better odds to call
        elif self.should_increase_variance():
            return 0.9  # Call lighter
        return 1.0


class MatchPhaseDetector:
    """
    Detects which phase of the match we're in and adjusts strategy.
    """
    
    PHASES = ['early', 'middle', 'late', 'endgame']
    
    def __init__(self, total_hands):
        self.total_hands = total_hands
    
    def get_phase(self, hand_id):
        """Get current phase based on hand number."""
        progress = hand_id / self.total_hands
        if progress < 0.25:
            return 'early'
        elif progress < 0.5:
            return 'middle'
        elif progress < 0.75:
            return 'late'
        return 'endgame'
    
    def get_phase_adjustments(self, hand_id):
        """Returns strategy adjustments for current phase."""
        phase = self.get_phase(hand_id)
        
        if phase == 'early':
            # Early: Play solid, gather info, build image
            return {
                'tightness': 1.1,
                'bluff_freq': 0.8,
                'value_bet_thresh': 1.05,
                'call_thresh': 1.05
            }
        elif phase == 'middle':
            # Middle: Exploit tendencies, standard play
            return {
                'tightness': 1.0,
                'bluff_freq': 1.0,
                'value_bet_thresh': 1.0,
                'call_thresh': 1.0
            }
        elif phase == 'late':
            # Late: Increase aggression, pressure opponents
            return {
                'tightness': 0.9,
                'bluff_freq': 1.2,
                'value_bet_thresh': 0.95,
                'call_thresh': 0.95
            }
        else:  # endgame
            # Endgame: Maximum exploitation, WinLock awareness
            return {
                'tightness': 0.85,
                'bluff_freq': 1.3,
                'value_bet_thresh': 0.9,
                'call_thresh': 0.9
            }


# Preflop adjustments based on tournament context
def get_tournament_preflop_adjustments(tournament_ctx, phase_adj):
    """
    Returns adjustments to preflop thresholds based on tournament state.
    """
    var_mult = tournament_ctx.get_variance_multiplier()
    
    return {
        'raise_threshold_adj': (var_mult - 1.0) * 0.1,  # +/- 0.1
        'call_threshold_adj': (1.0 / var_mult - 1.0) * 0.05,
        'bluff_raise_freq': 0.15 * tournament_ctx.get_bluff_frequency_adj(),
        'bluff_3bet_freq': 0.1 * tournament_ctx.get_bluff_frequency_adj(),
    }


if __name__ == '__main__':
    # Test
    ctx = TournamentContext(stage=1, match_cap=400, total_hands=400)
    ctx.match_net = 300
    ctx.hands_played = 200
    print(f"State: {ctx.get_match_state()}")
    print(f"Variance mult: {ctx.get_variance_multiplier()}")
    
    detector = MatchPhaseDetector(400)
    print(f"Phase 100: {detector.get_phase(100)}")
    print(f"Phase 300: {detector.get_phase(300)}")
    print(f"Late adj: {detector.get_phase_adjustments(300)}")