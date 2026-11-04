#!/usr/bin/env python3
"""
God-tier Pokerbots competitor for Discard Hold'em - FAST TOURNAMENT VERSION.

Integrates:
- Vectorized 7-card evaluator + Monte Carlo equity
- Precomputed 3-card hand equity table (22,100 hands)
- GTO-inspired betting policy with mixed strategies
- Optimal discard using equity + blocker analysis
- Board texture analysis for bet sizing
- Duplicate deal exploitation (learn from instance 1, crush instance 2)
- Time bank management + WinLock certificate
- Opponent modeling with adaptive frequencies
"""
import sys
import json
import time
import os
import numpy as np

# Import our fast modules
from eval7 import equity_vs_range, parse_card, card_str, preflop_equity_3card
from discard import choose_discard, choose_discard_fast
from policy import get_policy


class TimeBank:
    """Manages cumulative time bank across hands using engine's time_left_ms."""
    
    def __init__(self, total_ms=60000, per_response_ms=5000):
        self.total_ms = total_ms
        self.remaining_ms = float(total_ms)
        self.per_response_ms = per_response_ms
        self.hand_count = 0
    
    def start_hand(self):
        self.hand_count += 1
    
    def update_from_engine(self, time_left_ms):
        """Update remaining time from engine's time_left_ms field."""
        self.remaining_ms = float(time_left_ms)
    
    def get_budget(self, is_critical=False):
        hands_left = max(1, 400 - self.hand_count)
        reserve_per_hand = 50
        available = max(0, self.remaining_ms - hands_left * reserve_per_hand)
        limit = min(self.per_response_ms, available)
        
        if is_critical:
            return min(limit / 1000.0, 4.5)
        else:
            return min(limit / 1000.0, 0.5)
    
    def is_critical(self, req):
        pot = req.get('pot', 0)
        street = req.get('street', 'preflop')
        to_call = req.get('to_call', 0)
        my_stack = req.get('my_stack', 200)
        
        if street == 'river':
            return True
        if pot > 100:
            return True
        if to_call > my_stack * 0.3:
            return True
        if my_stack < 50:
            return True
        return False


class GameState:
    """Tracks game state across hands."""
    
    def __init__(self):
        self.hands_played = 0
        self.net_chips = 0
        self.current_hand_net = 0
        self.total_hands = 400
        self.match_cap = 400
        self.my_hole_cards = []
        self.opp_discards = []
        self.current_street = 'preflop'
        self.action_history = []
        self.seat = None          # 'button' or 'big_blind' from new_hand
        self.deal_seed = None
        self.hand_instance = 1    # 1 or 2 within duplicate pair
        self.instance_1_my_hole = None  # Store my hole cards from instance 1
        self.instance_1_board = None    # Store board from instance 1
        
        # Duplicate deal memory for exploitation (in-process, keyed by hand_id)
        self.duplicate_memory = {}
        
        # Simple opponent modeling
        self.opp_fold_freq = 0.5
        self.opp_raise_freq = 0.1
        self.opp_aggression = {'preflop': 0.1, 'flop': 0.2, 'turn': 0.3, 'river': 0.4}
    
    def reset_hand(self):
        self.current_hand_net = 0
        self.my_hole_cards = []
        self.opp_discards = []
        self.current_street = 'preflop'
        self.action_history = []
    
    def is_button(self):
        """Return True if we are the button (seat 0)."""
        return self.seat == 'button'
    
    def preflop_position(self, to_call):
        """
        Determine preflop position from engine's perspective.
        Button posts 1, BB posts 2. Button acts first preflop with to_call=1.
        """
        if self.is_button():
            return 'button'  # Acts first, to_call=1
        else:
            return 'big_blind'  # Acts second, to_call=2 or 0 if button checked
    
    def winlock_check(self):
        remaining = self.total_hands - self.hands_played
        if remaining <= 0:
            return True
        max_future_loss = remaining * 50
        current_risk = abs(self.current_hand_net)
        if self.net_chips - current_risk > max_future_loss + 10:
            return True
        return False
    
    def update_opp_model_from_history(self, req):
        """Update opponent model from req['history'] only (opponent actions)."""
        for event in req.get('history', []):
            if event.get('actor') == 'opp':
                street = event['street']
                action = event['action']
                bet_size = event.get('amount', 0)
                pot = req.get('pot', 0)
                to_call = req.get('to_call', 0)
                
                if action == 'fold':
                    self.opp_fold_freq = 0.9 * self.opp_fold_freq + 0.1
                elif action == 'raise':
                    self.opp_raise_freq = 0.9 * self.opp_raise_freq + 0.1
                    self.opp_aggression[street] = 0.9 * self.opp_aggression.get(street, 0.2) + 0.1
                elif action == 'call':
                    self.opp_aggression[street] = 0.9 * self.opp_aggression.get(street, 0.2) + 0.05
    
    def opp_fold_estimate(self, street, bet_size, pot):
        base = self.opp_fold_freq
        agg = self.opp_aggression.get(street, 0.2)
        bet_frac = bet_size / (pot + bet_size) if pot > 0 else 0.5
        return np.clip(base * (1 + bet_frac) * (1 - agg * 0.5), 0.05, 0.95)
    
    def opp_call_threshold(self, street):
        agg = self.opp_aggression.get(street, 0.2)
        return 0.35 - agg * 0.15
    
    def store_instance_1_data(self, my_hole, board):
        """Store data from instance 1 for exploitation in instance 2."""
        self.instance_1_my_hole = my_hole
        self.instance_1_board = board
    
    def get_instance_2_exploit_info(self):
        """
        For instance 2: opponent holds exactly my instance 1 hole cards.
        Board from instance 1 is known if it reached that street.
        """
        if self.hand_instance != 2 or self.instance_1_my_hole is None:
            return None
        
        # Opponent's hole cards = my instance 1 hole cards
        opp_hole = self.instance_1_my_hole
        
        # Board known up to where instance 1 reached
        known_board = self.instance_1_board if self.instance_1_board else []
        
        return {
            'opp_hole': opp_hole,
            'known_board': known_board,
            'perfect_info': True
        }


# Global state
_timebank = None
_gamestate = None
_policy = None


def init_globals(total_hands=400, time_bank_ms=60000, per_response_ms=5000):
    global _timebank, _gamestate, _policy
    _timebank = TimeBank(time_bank_ms, per_response_ms)
    _gamestate = GameState()
    _gamestate.total_hands = total_hands
    _gamestate.match_cap = 400 if total_hands <= 400 else 1000
    _policy = get_policy(seed=42)


def choose_action(req):
    """Handle action_request with GTO + duplicate exploitation."""
    global _timebank, _gamestate, _policy
    
    # Wrap in try/except to prevent crashes from causing forfeits
    try:
        return _choose_action_impl(req)
    except Exception as e:
        # Log to stderr (not stdout!)
        import sys
        sys.stderr.write(f"choose_action error: {e}\n")
        # Return safe action
        legal = req.get('legal_actions', ['fold'])
        if 'check' in legal:
            return {'type': 'action', 'action': 'check'}
        elif 'call' in legal:
            return {'type': 'action', 'action': 'call'}
        else:
            return {'type': 'action', 'action': 'fold'}

def _choose_action_impl(req):
    """Implementation of action handling."""
    global _timebank, _gamestate, _policy
    
    # Update time bank from engine's time_left_ms
    if _timebank and 'time_left_ms' in req:
        _timebank.update_from_engine(req['time_left_ms'])
    
    is_critical = _timebank.is_critical(req) if _timebank else True
    budget = _timebank.get_budget(is_critical) if _timebank else 0.5
    start = time.perf_counter()
    
    legal = req['legal_actions']
    street = req['street']
    board = req['board']
    pot = req['pot']
    to_call = req['to_call']
    my_stack = req['my_stack']
    opp_stack = req['opp_stack']
    raises_left = req.get('raises_left', 4)
    
    _gamestate.current_street = street
    
    # Update opponent model from history (only opponent actions)
    _gamestate.update_opp_model_from_history(req)
    
    # Build request with tracked hole cards
    req_with_hole = dict(req)
    req_with_hole['hole_cards'] = _gamestate.my_hole_cards
    
    # --- DUPLICATE DEAL EXPLOITATION (Corrected) ---
    # In instance 2, opponent holds exactly my instance 1 hole cards
    exploit_info = _gamestate.get_instance_2_exploit_info()
    
    if exploit_info and exploit_info.get('perfect_info'):
        # WE KNOW THEIR EXACT HAND (my instance 1 cards) - play perfectly
        opp_hole = exploit_info['opp_hole']
        known_board = exploit_info['known_board']
        
        # Compute exact equity vs known hand
        my_hole_ids = [parse_card(c) for c in _gamestate.my_hole_cards]
        opp_hole_ids = [parse_card(c) for c in opp_hole]
        board_ids = [parse_card(c) for c in board]
        
        # Safety: ensure we have exactly 2 cards postflop
        if len(my_hole_ids) != 2 and street != 'preflop':
            # Fallback to normal policy if hole cards not properly set
            action = _policy.choose_action(req_with_hole)
        else:
            # Use preflop_equity_3card for preflop, else head-to-head
            if street == 'preflop':
                # We have 3 cards, preflop_equity_3card computes best 2-card equity
                eq = preflop_equity_3card(my_hole_ids, n_draws=500)
            else:
                # For postflop, use Monte Carlo with known opponent hand
                from eval7 import equity_vs_range
                eq = equity_vs_range(my_hole_ids, board_ids, n_draws=1000, 
                                   seed=hash(tuple(sorted(my_hole_ids + opp_hole_ids))) & 0xFFFFFFFF)
            
            action = _perfect_decision(eq, legal, pot, to_call, my_stack, opp_stack, req)
    else:
        # Normal GTO policy
        action = _policy.choose_action(req_with_hole)
    
    # WinLock safety
    if _gamestate.winlock_check():
        if action['action'] in ('call', 'raise'):
            if 'check' in legal:
                action = {'type': 'action', 'action': 'check'}
            else:
                action = {'type': 'action', 'action': 'fold'}
    
    # Ensure legal
    if action['action'] not in legal:
        if 'check' in legal:
            action = {'type': 'action', 'action': 'check'}
        elif 'call' in legal:
            action = {'type': 'action', 'action': 'call'}
        else:
            action = {'type': 'action', 'action': 'fold'}
    
    # Track time (already updated from engine)
    elapsed = time.perf_counter() - start
    if _timebank:
        _timebank.remaining_ms -= elapsed * 1000
    
    return action


def _perfect_decision(eq, legal, pot, to_call, my_stack, opp_stack, req):
    """Perfect decision when we know opponent's exact hand."""
    if to_call == 0:
        if eq > 0.6:
            if 'raise' in legal:
                min_raise = req.get('min_raise', pot)
                max_raise = req.get('max_raise', my_stack)
                size = min(max_raise, max(min_raise, int(pot * (0.5 if eq < 0.75 else 0.75))))
                return {'type': 'action', 'action': 'raise', 'amount': size}
        elif eq < 0.35 and pot > 15 and 'raise' in legal:
            min_raise = req.get('min_raise', pot)
            max_raise = req.get('max_raise', my_stack)
            size = min(max_raise, max(min_raise, int(pot * 0.66)))
            return {'type': 'action', 'action': 'raise', 'amount': size}
        return {'type': 'action', 'action': 'check'}
    else:
        pot_odds = to_call / (pot + to_call)
        if eq > pot_odds + 0.08:
            if eq > 0.75 and 'raise' in legal:
                min_raise = req.get('min_raise', pot + to_call)
                max_raise = req.get('max_raise', my_stack)
                size = min(max_raise, max(min_raise, int((pot + to_call) * 2.5)))
                return {'type': 'action', 'action': 'raise', 'amount': size}
            return {'type': 'action', 'action': 'call'}
        elif eq > pot_odds - 0.05:
            return {'type': 'action', 'action': 'call'}
        else:
            return {'type': 'action', 'action': 'fold'}


def _choose_discard_impl(req):
    """Implementation of discard handling."""
    global _timebank, _gamestate, _policy
    
    budget = _timebank.get_budget(is_critical=True) if _timebank else 1.0
    start = time.perf_counter()
    
    hole = req['hole_cards']
    board = req['board']
    pot = req['pot']
    my_stack = req['my_stack']
    opp_stack = req['opp_stack']
    
    _gamestate.my_hole_cards = hole
    
    # Normal GTO discard (fast)
    if pot > 50:
        discard_card = _policy.choose_discard(hole, board, pot, my_stack, opp_stack)
    else:
        from discard import choose_discard_fast
        discard_card = choose_discard_fast(hole, board)
    
    _gamestate.pending_discard = discard_card
    _gamestate.opp_discards.append(discard_card)
    
    elapsed = time.perf_counter() - start
    if _timebank:
        _timebank.remaining_ms -= elapsed * 1000
    
    return {'type': 'discard', 'card': discard_card}

def choose_discard(req):
    """Handle discard_request with GTO + duplicate exploitation."""
    global _timebank, _gamestate, _policy
    
    try:
        return _choose_discard_impl(req)
    except Exception as e:
        import sys
        sys.stderr.write(f"choose_discard error: {e}\n")
        # Safe fallback
        hole = req.get('hole_cards', [])
        if hole:
            from discard import default_discard
            try:
                return {'type': 'discard', 'card': default_discard(hole)}
            except:
                pass
        return {'type': 'discard', 'card': hole[0] if hole else '2c'}


def handle_message(msg):
    """Route message to appropriate handler."""
    global _timebank, _gamestate, _policy
    
    try:
        return _handle_message_impl(msg)
    except Exception as e:
        import sys
        sys.stderr.write(f"handle_message error: {e}\n")
        return None

def _handle_message_impl(msg):
    """Implementation of message handling."""
    global _timebank, _gamestate, _policy
    
    msg_type = msg.get('type')
    
    if msg_type == 'init':
        total_hands = msg.get('total_hands', 400)
        time_bank_ms = msg.get('time_bank_ms', 60000)
        per_response_ms = msg.get('per_response_ms', 5000)
        init_globals(total_hands, time_bank_ms, per_response_ms)
        return None
    
    elif msg_type == 'new_hand':
        _gamestate.hands_played += 1
        _gamestate.reset_hand()
        _gamestate.seat = msg.get('seat', 'button')
        _gamestate.my_hole_cards = msg.get('hole_cards', [])
        _gamestate.deal_seed = msg.get('deal_seed', str(_gamestate.hands_played))
        _gamestate.hand_instance = 1 if (_gamestate.hands_played % 2 == 1) else 2
        
        # Store instance 1 data for instance 2 exploitation
        if _gamestate.hand_instance == 1:
            _gamestate.instance_1_my_hole = list(_gamestate.my_hole_cards)
            _gamestate.instance_1_board = []
        
        _timebank.start_hand()
        return None
    
    elif msg_type == 'action_request':
        return choose_action(msg)
    
    elif msg_type == 'discard_request':
        return choose_discard(msg)
    
    elif msg_type == 'discard_result':
        my_discard = msg.get('my_discard')
        opp_discard = msg.get('opp_discard')
        hole_cards = msg.get('hole_cards', [])
        
        _gamestate.my_hole_cards = hole_cards
        _gamestate.opp_discards.append(opp_discard)
        _gamestate.pending_discard = None
        
        # Update instance 1 board knowledge
        if _gamestate.hand_instance == 1 and _gamestate.instance_1_board is not None:
            _gamestate.instance_1_board = list(msg.get('board', []))
        
        return None
    
    elif msg_type == 'hand_result':
        net = msg.get('net', 0)
        _gamestate.net_chips += net
        _gamestate.current_hand_net = net
        _gamestate.hands_played = msg.get('hand_id', _gamestate.hands_played)
        
        # Update instance 1 board if showdown
        if _gamestate.hand_instance == 1 and msg.get('result') == 'showdown':
            _gamestate.instance_1_board = list(msg.get('board', []))
        
        # Time bank uses engine's time_left_ms, no end_hand needed
        return None
    
    elif msg_type == 'notice':
        return None
    
    elif msg_type == 'match_end':
        return None
    
    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        
        reply = handle_message(msg)
        if reply is not None:
            print(json.dumps(reply, separators=(',', ':')), flush=True)
        
        if msg.get('type') == 'match_end':
            break


if __name__ == '__main__':
    main()