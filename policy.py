"""
GTO-inspired betting policy with mixed strategies, opponent modeling, and adaptive exploitation.
Designed for Discard Hold'em with 3-card preflop, discard after flop, 4-raise cap.
"""
import numpy as np
import random
import json
import os
from eval7 import equity_vs_range, parse_card, card_str, preflop_equity_3card
from discard import made_hand_strength, choose_discard, choose_discard_fast
from board_texture import analyze_board_texture, get_board_category, estimate_opponent_range, river_bluff_candidates
from hand3 import hand_type_3card, get_hand_type_bucket
from tournament import TournamentContext, MatchPhaseDetector, get_tournament_preflop_adjustments
from range_vs_range import get_range_calculator, get_range_builder


# Load precomputed preflop equity table
_preflop_equity_table = {}
_preflop_table_path = os.path.join(os.path.dirname(__file__), 'preflop_equity.json')
if os.path.exists(_preflop_table_path):
    with open(_preflop_table_path, 'r') as f:
        _preflop_equity_table = json.load(f)
    print(f"Loaded {len(_preflop_equity_table)} preflop equities", file=__import__('sys').stderr)


# Load CFR preflop strategy
_cfr_preflop = {}
_cfr_path = os.path.join(os.path.dirname(__file__), 'cfr_preflop.json')
if os.path.exists(_cfr_path):
    with open(_cfr_path, 'r') as f:
        _cfr_preflop = json.load(f)
    print(f"Loaded {len(_cfr_preflop)} CFR preflop strategies", file=__import__('sys').stderr)


def hand_key(hole_cards):
    """Normalize hand to canonical rank-sorted string key (matches preflop_equity.json)."""
    # Sort by rank (2-A), then by suit (shdc) for canonical ordering
    rank_order = {'2': 0, '3': 1, '4': 2, '5': 3, '6': 4, '7': 5, '8': 6, '9': 7, 'T': 8, 'J': 9, 'Q': 10, 'K': 11, 'A': 12}
    suit_order = {'s': 0, 'h': 1, 'd': 2, 'c': 3}
    cards_sorted = sorted(hole_cards, key=lambda c: (rank_order[c[0]], suit_order[c[1]]))
    return " ".join(cards_sorted)


def preflop_equity_3card(hole_cards, n_draws=800):
    """Equity of 3-card hand vs random 3-card hand (both discard optimally)."""
    key = hand_key(hole_cards)
    if key in _preflop_equity_table:
        return _preflop_equity_table[key]
    
    # Fallback to Monte Carlo if not in table
    hole_ids = [parse_card(c) for c in hole_cards]
    best = 0.0
    for i in range(3):
        kept = [hole_ids[j] for j in range(3) if j != i]
        eq = equity_vs_range(kept, [], n_draws=n_draws, seed=hash(tuple(sorted(kept))) & 0xFFFFFFFF)
        if eq > best:
            best = eq
    
    return best


def get_cfr_preflop_strategy(hole_cards, position, history):
    """
    Get CFR-based preflop strategy for given hand, position, and history.
    Returns dict of {action_name: probability}.
    """
    # Get hand type bucket
    hole_ids = [parse_card(c) for c in hole_cards]
    hand_type = get_hand_type_bucket(hole_ids)
    
    # Convert history to action names
    action_map = {0: 'CHECK', 1: 'RAISE_3X', 2: 'FOLD', 3: 'CALL', 4: 'RAISE_9X', 5: 'RAISE_22X'}
    history_names = [action_map.get(a, str(a)) for a in history]
    
    key = f"{position}|{hand_type}|{history_names}"
    
    if key in _cfr_preflop:
        return _cfr_preflop[key]
    
    # Fallback to simple heuristics
    return None


def sample_cfr_action(cfr_strategy, legal_actions):
    """Sample action from CFR strategy, constrained to legal actions."""
    if not cfr_strategy:
        return None
    
    # Filter to legal actions
    action_map_rev = {'CHECK': 'check', 'RAISE_3X': 'raise', 'FOLD': 'fold', 
                      'CALL': 'call', 'RAISE_9X': 'raise', 'RAISE_22X': 'raise'}
    
    legal_probs = {}
    total = 0.0
    for cfr_action, prob in cfr_strategy.items():
        mapped = action_map_rev.get(cfr_action)
        if mapped and mapped in legal_actions:
            legal_probs[mapped] = legal_probs.get(mapped, 0) + prob
            total += prob
    
    if total == 0:
        return None
    
    # Normalize
    for a in legal_probs:
        legal_probs[a] /= total
    
    # Sample
    r = np.random.random()
    cum = 0.0
    for a in legal_actions:
        if a in legal_probs:
            cum += legal_probs[a]
            if r <= cum:
                return a
    return legal_actions[-1]


class OpponentModel:
    """Simple opponent modeling for exploitation."""
    
    def __init__(self):
        self.history = []  # List of (street, action, bet_size, pot_odds, board_texture)
        self.fold_freq = 0.5
        self.raise_freq = 0.0
        self.call_freq = 0.5
        self.aggression_by_street = {0: 0.1, 1: 0.2, 2: 0.3, 3: 0.4}  # Preflop, flop, turn, river
        self.showdown_hands = []  # (hand_strength, action_sequence)
        self.total_hands = 0
    
    def observe_action(self, street, action, bet_size, pot, to_call, board):
        self.history.append({
            'street': street,
            'action': action,
            'bet_size': bet_size,
            'pot': pot,
            'to_call': to_call,
            'board': list(board)
        })
        
        if action == 'fold':
            self.fold_freq = 0.9 * self.fold_freq + 0.1
        elif action == 'raise':
            self.raise_freq = 0.9 * self.raise_freq + 0.1
        elif action == 'call':
            self.call_freq = 0.9 * self.call_freq + 0.1
        
        # Update street aggression
        if action in ('raise', 'bet'):
            self.aggression_by_street[street] = 0.9 * self.aggression_by_street[street] + 0.1
    
    def observe_showdown(self, hand_strength, action_seq):
        self.showdown_hands.append((hand_strength, action_seq))
        self.total_hands += 1
    
    def get_fold_estimate(self, street, bet_size, pot):
        """Estimate opponent fold probability to a bet of bet_size into pot."""
        base_fold = self.fold_freq
        # Adjust for street aggression
        agg = self.aggression_by_street.get(street, 0.2)
        # Larger bets get more folds
        bet_frac = bet_size / (pot + bet_size) if pot > 0 else 0.5
        fold_prob = base_fold * (1 + bet_frac) * (1 - agg * 0.5)
        return np.clip(fold_prob, 0.05, 0.95)
    
    def get_call_threshold(self, street):
        """Estimate minimum equity opponent needs to call."""
        # More aggressive opponents call lighter
        agg = self.aggression_by_street.get(street, 0.2)
        return 0.35 - agg * 0.15  # Range ~0.2 to 0.35


class BettingPolicy:
    """
    GTO-inspired policy with:
    - Equity-based thresholds
    - Mixed strategies (randomization)
    - Opponent exploitation
    - Bluffing with blockers
    - Pot odds / implied odds
    - SPR awareness
    - Board texture analysis
    - Tournament-aware strategy (Swiss caps, RR scoring)
    """
    
    def __init__(self, seed=42, tournament_ctx=None):
        self.rng = random.Random(seed)
        self.np_rng = np.random.default_rng(seed)
        self.opp = OpponentModel()
        
        # Tournament context
        self.tournament_ctx = tournament_ctx
        self.phase_detector = MatchPhaseDetector(400) if tournament_ctx else None
        
        # Base strategy parameters (tuned for Discard Hold'em)
        self.preflop_raise_threshold = 0.55  # Raise top ~45% of 3-card hands
        self.preflop_call_threshold = 0.40   # Call with ~60% of hands vs raise
        self.flop_bet_threshold = 0.50       # Bet top 50% of range on flop
        self.flop_checkraise_threshold = 0.65
        self.turn_bet_threshold = 0.55
        self.river_bet_threshold = 0.50
        self.river_bluff_threshold = 0.30    # Bluff bottom 30% when checked to
        self.bluff_freq = 0.25               # Target bluff frequency
        
        # Mixed strategy randomization
        self.mix_epsilon = 0.05  # Minimum probability for any legal action
    
    
    def _get_tournament_adjustments(self, hand_id=None):
        """Get current tournament adjustments."""
        if not self.tournament_ctx:
            return {
                'variance_mult': 1.0,
                'bluff_freq_mult': 1.0,
                'call_thresh_mult': 1.0,
                'tightness': 1.0,
                'phase_adj': {}
            }
        
        var_mult = self.tournament_ctx.get_variance_multiplier()
        bluff_mult = self.tournament_ctx.get_bluff_frequency_adj()
        call_mult = self.tournament_ctx.get_call_threshold_adj()
        
        phase_adj = {}
        if self.phase_detector and hand_id:
            phase_adj = self.phase_detector.get_phase_adjustments(hand_id)
        
        return {
            'variance_mult': var_mult,
            'bluff_freq_mult': bluff_mult,
            'call_thresh_mult': call_mult,
            'tightness': phase_adj.get('tightness', 1.0),
            'phase_adj': phase_adj
        }
    
    def _get_adjusted_threshold(self, base_threshold, adjustment_type, hand_id=None):
        """Get threshold adjusted for tournament context."""
        adj = self._get_tournament_adjustments(hand_id)
        
        if adjustment_type == 'preflop_raise':
            return base_threshold * adj['tightness'] + (adj['variance_mult'] - 1.0) * 0.1
        elif adjustment_type == 'preflop_call':
            return base_threshold * adj['call_thresh_mult']
        elif adjustment_type == 'flop_bet':
            return base_threshold * adj['tightness']
        elif adjustment_type == 'turn_bet':
            return base_threshold * adj['tightness']
        elif adjustment_type == 'river_bet':
            return base_threshold * adj['tightness']
        elif adjustment_type == 'river_bluff':
            return base_threshold / adj['bluff_freq_mult']
        elif adjustment_type == 'bluff_freq':
            return base_threshold * adj['bluff_freq_mult']
        
        return base_threshold
    
    def spr(self, pot, my_stack, to_call=0):
        p = pot + to_call
        return my_stack / p if p > 0 else float('inf')
    
    def pot_odds(self, to_call, pot):
        total = pot + to_call
        return to_call / total if total > 0 else 0.0
    
    def _equity_with_board(self, hole_cards, board, n_draws=400):
        """Get equity vs range given current board."""
        if not board:
            return preflop_equity_3card(hole_cards, n_draws=n_draws)
        
        hole_ids = [parse_card(c) for c in hole_cards]
        board_ids = [parse_card(c) for c in board]
        
        # For 3-card preflop, we need to consider we'll discard one after flop
        if len(board) == 3:
            # Estimate by taking best 2-card equity
            best_eq = 0.0
            for i in range(3):
                kept = [hole_ids[j] for j in range(3) if j != i]
                eq = equity_vs_range(kept, board_ids, n_draws=n_draws, 
                                   seed=hash((tuple(sorted(kept)), tuple(board_ids))) & 0xFFFFFFFF)
                if eq > best_eq:
                    best_eq = eq
            return best_eq
        else:
            # Post-discard: we have 2 cards
            # For now assume we kept our best 2
            kept = hole_ids[:2]  # Simplified
            return equity_vs_range(kept, board_ids, n_draws=n_draws,
                                 seed=hash((tuple(sorted(kept)), tuple(board_ids))) & 0xFFFFFFFF)

    def _range_vs_range_equity(self, my_range, opp_range, board, n_draws=300):
        """
        Compute equity of our range vs opponent's range on board.
        Uses vectorized range-vs-range calculator.
        """
        if not my_range or not opp_range:
            return 0.5
        
        calc = get_range_calculator()
        return calc.equity(my_range, opp_range, board, n_draws=n_draws)

    def _build_my_range(self, hole_cards, board, street):
        """Build our current range based on our actions and hand."""
        builder = get_range_builder()
        
        # For now, return a simplified range based on our hand
        # In practice, this would be built from our actual strategy
        hole_ids = [parse_card(c) for c in hole_cards]
        htype = get_hand_type_bucket(hole_ids)
        
        # Our range is concentrated around our hand type
        my_range = []
        for hand in builder.hands_by_type.get(htype, []):
            my_range.append((hand, 1.0))
        
        # Add some nearby types for balance
        if htype == 'pair_premium':
            for hand in builder.hands_by_type.get('pair_high', []):
                my_range.append((hand, 0.5))
        elif htype == 'flush_draw_broadway':
            for hand in builder.hands_by_type.get('flush_draw_other', []):
                my_range.append((hand, 0.3))
        
        return my_range
    
    def _estimate_opp_range(self, req, street):
        """Estimate opponent's range based on actions and board."""
        builder = get_range_builder()
        
        # Get opponent position
        position = 'BB' if req.get('seat') == 'button' else 'SB'
        
        # Build action sequence
        action_seq = []
        for h in req.get('history', []):
            if h['street'] == street:
                action_seq.append(h['action'])
        
        # Opponent tendencies from our model
        tendencies = {
            'vpip': self.opp.raise_freq + self.opp.call_freq,
            'pfr': self.opp.raise_freq,
            'agg': self.opp.aggression_by_street.get(street, 0.2)
        }
        
        opp_range = builder.build_preflop_range(
            position, action_seq, 
            board=req.get('board') if street != 'preflop' else None,
            opponent_tendencies=tendencies
        )
        
        return opp_range

    def _mixed_action(self, legal_actions, preferred, weights=None):
        """Select action with mixed strategy (minimum epsilon for all legal)."""
        if weights is None:
            weights = {}
        
        # Base weights
        probs = {a: self.mix_epsilon for a in legal_actions}
        
        # Boost preferred action
        if preferred in legal_actions:
            probs[preferred] += 0.7
        
        # Apply custom weights
        for a, w in weights.items():
            if a in probs:
                probs[a] += w
        
        # Normalize
        total = sum(probs.values())
        probs = {a: p/total for a, p in probs.items()}
        
        # Sample
        r = self.rng.random()
        cum = 0.0
        for a in legal_actions:
            cum += probs[a]
            if r <= cum:
                return a
        return legal_actions[-1]
    
    def geometric_sizing(self, pot, eff_stack, streets_left=2):
        """
        Geometric bet sizing: same fraction each street to get all-in by river.
        Solves: pot * (1 + r)^streets = eff_stack
        """
        if pot <= 0:
            return eff_stack
        r = (eff_stack / pot) ** (1.0 / streets_left) - 1
        return min(pot * r, eff_stack)
    
    def _raise_amount(self, legal_actions, req, eq, is_bluff=False, street=None):
        """Determine raise size using geometric sizing + equity/SPR adjustments."""
        if 'raise' not in legal_actions:
            return None
        
        pot = req['pot']
        my_stack = req['my_stack']
        opp_stack = req['opp_stack']
        min_raise = req.get('min_raise', pot + req['to_call'])
        max_raise = req.get('max_raise', my_stack)
        to_call = req.get('to_call', 0)
        
        eff_stack = min(my_stack, opp_stack + to_call)
        spr_val = self.spr(pot, my_stack, to_call)
        
        # Determine streets remaining
        if street is None:
            street = req.get('street', 'flop')
        streets_left = {'flop': 2, 'turn': 1, 'river': 0}.get(street, 1)
        
        if streets_left > 0:
            # Geometric sizing as baseline
            geo_size = self.geometric_sizing(pot, eff_stack, streets_left)
            geo_frac = geo_size / pot if pot > 0 else 1.0
        else:
            geo_frac = 1.0  # River: can go all-in
        
        # Adjust based on equity and bluffing
        if is_bluff:
            # Bluff sizing: larger when SPR high, smaller when SPR low
            if spr_val > 10:
                eq_adj = 1.2  # Can bet bigger with deep stacks
            elif spr_val > 5:
                eq_adj = 1.0
            else:
                eq_adj = 0.7
            target_frac = geo_frac * eq_adj
        else:
            # Value sizing: scale with equity
            if eq > 0.8:
                eq_adj = 1.3
            elif eq > 0.7:
                eq_adj = 1.15
            elif eq > 0.6:
                eq_adj = 1.0
            elif eq > 0.5:
                eq_adj = 0.85
            else:
                eq_adj = 0.7
            target_frac = geo_frac * eq_adj
        
        # Board texture adjustments (if available)
        board = req.get('board', [])
        if board:
            from board_texture import analyze_board_texture
            tex = analyze_board_texture([parse_card(c) for c in board])
            if tex['wet']:
                target_frac *= 1.15  # Charge draws more
            elif tex.get('dry', False):
                target_frac *= 0.85  # Smaller on dry boards
        
        target = req['opp_bet'] + int(target_frac * (pot + to_call))
        amount = max(min_raise, min(max_raise, target))
        
        # Round to nearest big blind (2 chips)
        amount = round(amount / 2) * 2
        return max(min_raise, min(max_raise, amount))
    
    def _get_float_adjustment(self, board, street):
        """Get float/delay adjustment to bet threshold."""
        bet_thresh = 0.5
        
        try:
            # Placeholder for float detection logic
            # If we detect opponent floating, we should bet thinner for value
            # and bluff less on later streets
            pass
        except Exception:
            pass
        
        return bet_thresh
    
    def choose_action(self, req):
        """Main decision function for action_request."""
        legal = req['legal_actions']
        street = req['street']
        hole = req['hole_cards']
        board = req['board']
        pot = req['pot']
        to_call = req['to_call']
        my_stack = req['my_stack']
        opp_stack = req['opp_stack']
        raises_left = req.get('raises_left', 4)
        
        # Get equity
        n_draws = 300 if street == 'preflop' else 400
        eq = self._equity_with_board(hole, board, n_draws=n_draws)
        
        # Get made hand strength if postflop
        mhs = made_hand_strength([parse_card(c) for c in hole], [parse_card(c) for c in board]) if board else None
        
        spr_val = self.spr(pot, my_stack, to_call)
        odds = self.pot_odds(to_call, pot)
        
        # Opponent modeling adjustments
        opp_fold_est = self.opp.get_fold_estimate(
            {'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}[street],
            pot * 0.5, pot
        ) if to_call == 0 else 0
        opp_call_thresh = self.opp.get_call_threshold({'preflop': 0, 'flop': 1, 'turn': 2, 'river': 3}[street])
        
        # --- PRELOP ---
        if street == 'preflop':
            # We have 3 cards, will discard 1 after flop
            # Use CFR-based strategy
            
            # Tournament adjustments
            hand_id = req.get('hand_id', 0)
            raise_thresh = self._get_adjusted_threshold(self.preflop_raise_threshold, 'preflop_raise', hand_id)
            call_thresh = self._get_adjusted_threshold(self.preflop_call_threshold, 'preflop_call', hand_id)
            bluff_freq = self._get_adjusted_threshold(self.bluff_freq, 'bluff_freq', hand_id)
            
            # Determine position from seat and to_call
            # Button posts 1, BB posts 2. Button acts first with to_call=1.
            seat = req.get('seat', 'button')
            if seat == 'button':
                position = 'button'
            else:
                position = 'big_blind'
            
            # Convert history to our format
            history = []
            for h in req.get('history', []):
                if h['street'] == 'preflop':
                    act = h['action']
                    if act == 'check':
                        history.append(0)
                    elif act == 'raise':
                        # Map raise sizes to CFR codes: 3x->1, 9x->4, 22x->5
                        amount = h.get('amount', 0)
                        if amount <= 6:
                            history.append(1)   # RAISE_3X
                        elif amount <= 18:
                            history.append(4)   # RAISE_9X
                        else:
                            history.append(5)   # RAISE_22X
                    elif act == 'fold':
                        history.append(2)
                    elif act == 'call':
                        history.append(3)
            
            # Get CFR strategy
            cfr_strat = get_cfr_preflop_strategy(req['hole_cards'], position, history)
            sampled_action = sample_cfr_action(cfr_strat, legal) if cfr_strat else None
            
            if sampled_action:
                if sampled_action == 'raise':
                    # Determine raise amount based on position and history
                    if position == 'button' and to_call == 1:
                        # Button open raise: 3x BB = 6 chips
                        amt = min(req.get('max_raise', my_stack), max(req.get('min_raise', 6), 6))
                    elif position == 'big_blind' and history == [0]:
                        # BB raise after button check: 3x BB = 6 chips
                        amt = min(req.get('max_raise', my_stack), max(req.get('min_raise', 6), 6))
                    elif position == 'big_blind' and history == [1]:
                        # BB 3-bet: 9x BB = 18 chips
                        amt = min(req.get('max_raise', my_stack), max(req.get('min_raise', 18), 18))
                    elif position == 'button' and history == [1, 4]:
                        # Button 4-bet: 22x BB = 44 chips
                        amt = min(req.get('max_raise', my_stack), max(req.get('min_raise', 44), 44))
                    elif position == 'button' and history == [0, 1]:
                        # Button raise after BB raise: 9x BB = 18 chips
                        amt = min(req.get('max_raise', my_stack), max(req.get('min_raise', 18), 18))
                    else:
                        amt = self._raise_amount(legal, req, eq)
                    
                    if amt:
                        return {'type': 'action', 'action': 'raise', 'amount': amt}
                
                elif sampled_action == 'check':
                    return {'type': 'action', 'action': 'check'}
                
                elif sampled_action == 'call':
                    return {'type': 'action', 'action': 'call'}
                
                elif sampled_action == 'fold':
                    return {'type': 'action', 'action': 'fold'}
            
            # Fallback to equity-based if CFR not available
            if to_call == 1:  # Button (button) acting first, to_call=1
                if eq > raise_thresh:
                    if 'raise' in legal:
                        amt = self._raise_amount(legal, req, eq)
                        if amt:
                            return {'type': 'action', 'action': 'raise', 'amount': amt}
                if 'raise' in legal and self.rng.random() < bluff_freq:
                    amt = self._raise_amount(legal, req, eq, is_bluff=True)
                    if amt:
                        return {'type': 'action', 'action': 'raise', 'amount': amt}
                return {'type': 'action', 'action': 'check'}
            
            else:  # BB facing raise (to_call > 1)
                if eq > call_thresh:
                    if eq > 0.65 and 'raise' in legal and raises_left > 1:
                        if self.rng.random() < 0.4:
                            amt = self._raise_amount(legal, req, eq)
                            if amt:
                                return {'type': 'action', 'action': 'raise', 'amount': amt}
                    return {'type': 'action', 'action': 'call'}
                
                if eq > 0.35 and 'raise' in legal and raises_left > 1:
                    if self.rng.random() < bluff_freq * 0.5:
                        amt = self._raise_amount(legal, req, eq, is_bluff=True)
                        if amt:
                            return {'type': 'action', 'action': 'raise', 'amount': amt}
                
                return {'type': 'action', 'action': 'fold'}
        
        # --- POSTFLOP (after discard, we have 2 cards) ---
        # For simplicity, treat our 3 cards as if we kept best 2
        # The discard phase will actually choose which 2 to keep
        
        # Tournament adjustments
        hand_id = req.get('hand_id', 0)
        bet_thresh_adj = self._get_tournament_adjustments(hand_id)
        bluff_freq = self._get_adjusted_threshold(self.bluff_freq, 'bluff_freq', hand_id)
        river_bluff_thresh = self._get_adjusted_threshold(self.river_bluff_threshold, 'river_bluff', hand_id)
        
        # Board texture analysis
        board_cards_parsed = [parse_card(c) for c in board] if board else []
        board_texture = analyze_board_texture(board_cards_parsed)
        board_category = get_board_category(board_cards_parsed)
        range_adj = estimate_opponent_range(board_cards_parsed, req.get('history', []), street)
        
        # Adjust equity based on board texture
        # On wet boards, our equity vs calling range is lower
        # On dry boards, we can bluff more
        adj_eq = eq + range_adj
        
        # Bet sizing fractions by street with tournament adjustments
        base_bet_thresh = {
            'flop': self._get_adjusted_threshold(self.flop_bet_threshold, 'flop_bet', hand_id),
            'turn': self._get_adjusted_threshold(self.turn_bet_threshold, 'turn_bet', hand_id),
            'river': self._get_adjusted_threshold(self.river_bet_threshold, 'river_bet', hand_id)
        }.get(street, 0.5)
        
        # On wet boards, bet thinner for value (more calls)
        # On dry boards, bet wider for value (more folds)
        if board_texture['wet']:
            bet_thresh = base_bet_thresh - 0.05
        elif board_category == 'dry':
            bet_thresh = base_bet_thresh + 0.03
        else:
            bet_thresh = base_bet_thresh
        
        # Value bet
        if adj_eq > bet_thresh and 'raise' in legal:
            # Check if we should slowplay
            if adj_eq > 0.8 and spr_val > 5 and self.rng.random() < 0.2:
                return {'type': 'action', 'action': 'check'}
            amt = self._raise_amount(legal, req, adj_eq)
            if amt:
                return {'type': 'action', 'action': 'raise', 'amount': amt}
            
            # Bluff
            # On river, use polarized range (strong hands + bluffs)
            # On earlier streets, use merged range
            if street == 'river':
                # Fallback to heuristic (CFR removed)
                bluff_thresh = river_bluff_thresh
                # On river, bluff with blockers
                if adj_eq < bluff_thresh and 'raise' in legal:
                    # Check blocker value for river bluff
                    bluff_candidates = river_bluff_candidates(hole, board)
                    if bluff_candidates and bluff_candidates[0][1] > 0.15:
                        if opp_fold_est > 0.35 and self.rng.random() < bluff_freq:
                            amt = self._raise_amount(legal, req, adj_eq, is_bluff=True)
                            if amt:
                                return {'type': 'action', 'action': 'raise', 'amount': amt}
            else:
                bluff_thresh = 0.35
                if adj_eq < bluff_thresh and 'raise' in legal:
                    # Semi-bluff with draws
                    if board_texture['flush_draw'] or board_texture['straight_draw']:
                        if opp_fold_est > 0.3 and self.rng.random() < bluff_freq * 1.5:
                            amt = self._raise_amount(legal, req, adj_eq, is_bluff=True)
                            if amt:
                                return {'type': 'action', 'action': 'raise', 'amount': amt}
                    # Pure bluff on dry boards
                    elif board_category == 'dry':
                        if opp_fold_est > 0.45 and self.rng.random() < bluff_freq:
                            amt = self._raise_amount(legal, req, adj_eq, is_bluff=True)
                            if amt:
                                return {'type': 'action', 'action': 'raise', 'amount': amt}
            
            return {'type': 'action', 'action': 'check'}
        
        else:  # Facing bet
            # Required equity to call with tournament adjustment
            required_eq = odds
            call_mult = self._get_tournament_adjustments(hand_id)['call_thresh_mult']
            
            # Board texture adjustments
            if board_texture['wet']:
                required_eq += 0.03  # Opponent's range stronger on wet boards
            elif board_category == 'dry':
                required_eq -= 0.02  # Opponent bluffs more on dry boards
            
            # Adjust for implied odds
            if spr_val > 5 and street != 'river':
                required_eq *= 0.85  # Can call lighter with implied odds
            # Adjust for opponent tendencies and tournament
            required_eq = max(required_eq, opp_call_thresh * 0.8) * call_mult
            
            if adj_eq > required_eq + 0.05:  # Clear call
                # Consider raise
                if 'raise' in legal and raises_left > 0:
                    raise_thresh = {
                        'flop': self.flop_checkraise_threshold,
                        'turn': 0.70,
                        'river': 0.75
                    }.get(street, 0.7)
                    
                    if adj_eq > raise_thresh:
                        # Value raise
                        if self.rng.random() < 0.7:
                            amt = self._raise_amount(legal, req, adj_eq)
                            if amt:
                                return {'type': 'action', 'action': 'raise', 'amount': amt}
                    elif adj_eq > 0.5 and self.rng.random() < 0.15:
                        # Semi-bluff raise
                        amt = self._raise_amount(legal, req, adj_eq, is_bluff=True)
                        if amt:
                            return {'type': 'action', 'action': 'raise', 'amount': amt}
                
                return {'type': 'action', 'action': 'call'}
            
            elif adj_eq > required_eq - 0.05:  # Marginal call
                # Mixed strategy
                call_prob = 0.5 + (adj_eq - required_eq + 0.05) * 5
                call_prob = np.clip(call_prob, 0.1, 0.9)
                if self.rng.random() < call_prob:
                    return {'type': 'action', 'action': 'call'}
                else:
                    return {'type': 'action', 'action': 'fold'}
            
            else:  # Clear fold
                # Very rarely bluff-raise as pure bluff
                if 'raise' in legal and raises_left > 0 and street == 'river':
                    if adj_eq < 0.2 and opp_fold_est > 0.6 and self.rng.random() < 0.05:
                        amt = self._raise_amount(legal, req, adj_eq, is_bluff=True)
                        if amt:
                            return {'type': 'action', 'action': 'raise', 'amount': amt}
                return {'type': 'action', 'action': 'fold'}
    
    def choose_discard(self, hole_cards, board, pot, my_stack, opp_stack):
        """Choose which of 3 cards to discard after flop."""
        # Use fast heuristic for speed, Monte Carlo for important spots
        n_draws = 200 if pot > 50 else 100
        # hole_cards is already the 3 cards from req
        return choose_discard(hole_cards, board, pot, my_stack, opp_stack, n_draws=n_draws)
    
    def observe_action(self, street, action, bet_size, pot, to_call, board):
        self.opp.observe_action(street, action, bet_size, pot, to_call, board)
    
    def observe_showdown(self, my_hole, opp_hole, board, action_seq):
        """Called at showdown to update opponent model."""
        from eval7 import parse_card
        from eval7 import eval5_batch
        my_ids = [parse_card(c) for c in my_hole]
        opp_ids = [parse_card(c) for c in opp_hole]
        board_ids = [parse_card(c) for c in board]
        
        # Evaluate opponent's hand strength
        from itertools import combinations
        combos = list(combinations(opp_ids + board_ids, 5))
        if combos:
            scores = eval5_batch(np.array(combos, dtype=np.int64))
            best = scores.max()
        else:
            best = 0
        cat = (best >> 20) & 0xF
        hs = cat / 8.0  # Normalize to [0,1]
        
        self.opp.observe_showdown(hs, action_seq)


# Global policy instance (persists across hands in a match)
_policy_instance = None


def get_policy(seed=42):
    global _policy_instance
    if _policy_instance is None:
        _policy_instance = BettingPolicy(seed)
    return _policy_instance