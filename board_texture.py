#!/usr/bin/env python3
"""
Board texture analysis for Discard Hold'em.
Provides utilities for evaluating board connectivity, flush/straight draws, etc.
"""
import numpy as np
from eval7 import parse_card


def analyze_board_texture(board_cards):
    """
    Analyze board texture for bet sizing and strategy decisions.
    Returns dict with texture metrics.
    """
    if not board_cards:
        return {
            'wet': False,
            'flush_draw': False,
            'straight_draw': False,
            'paired': False,
            'trips': False,
            'broadway': 0,
            'connected': 0,
            'texture_score': 0.0
        }
    
    ranks = [c // 4 for c in board_cards]
    suits = [c % 4 for c in board_cards]
    
    # Count ranks
    rank_counts = {}
    for r in ranks:
        rank_counts[r] = rank_counts.get(r, 0) + 1
    
    # Paired board
    paired = any(c >= 2 for c in rank_counts.values())
    trips = any(c >= 3 for c in rank_counts.values())
    
    # Flush draw
    suit_counts = {}
    for s in suits:
        suit_counts[s] = suit_counts.get(s, 0) + 1
    flush_draw = max(suit_counts.values()) >= 3 if len(board_cards) >= 3 else False
    flush_possible = max(suit_counts.values()) >= 2
    
    # Straight draw / connectedness
    unique_ranks = sorted(set(ranks))
    straight_draw = False
    connected = 0
    for i in range(len(unique_ranks) - 1):
        gap = unique_ranks[i+1] - unique_ranks[i]
        if gap <= 2:
            connected += 1
        if gap <= 3 and len(unique_ranks) >= 3:
            straight_draw = True
    
    # Broadway cards (T-A = ranks 8-12)
    broadway = sum(1 for r in ranks if r >= 8)
    
    # Texture score: 0 = dry, 1 = very wet
    texture_score = 0.0
    if trips:
        texture_score += 0.5  # Trips boards are tricky but not "drawy"
    elif paired:
        texture_score += 0.2
    if flush_draw:
        texture_score += 0.3
    elif flush_possible:
        texture_score += 0.15
    if straight_draw:
        texture_score += 0.25
    if connected >= 2:
        texture_score += 0.2
    if broadway >= 2:
        texture_score += 0.1
    
    # Wet boards have draws, dry boards are paired/high card
    wet = texture_score > 0.4
    
    dry = not wet and not trips and not paired and not flush_draw and not straight_draw
    
    return {
        'wet': wet,
        'dry': dry,
        'flush_draw': flush_draw,
        'flush_possible': flush_possible,
        'straight_draw': straight_draw,
        'paired': paired,
        'trips': trips,
        'broadway': broadway,
        'connected': connected,
        'texture_score': min(1.0, texture_score)
    }


def get_board_category(board_cards):
    """
    Categorize board for strategy:
    - 'dry': paired, no draws
    - 'semi_wet': some draws but not many
    - 'wet': multiple draws possible
    - 'trips': trips on board
    - 'straight_flush': straight/flush possible
    """
    texture = analyze_board_texture(board_cards)
    
    if texture['trips']:
        return 'trips'
    if texture['flush_draw'] and texture['straight_draw']:
        return 'straight_flush'
    if texture['wet']:
        return 'wet'
    if texture['paired'] or texture['flush_possible'] or texture['straight_draw']:
        return 'semi_wet'
    return 'dry'


def estimate_opponent_range(board_cards, action_history, street):
    """
    Estimate opponent's likely range based on board and action.
    Returns equity adjustment factor.
    """
    texture = analyze_board_texture(board_cards)
    
    # Base adjustment
    adj = 0.0
    
    # On wet boards, opponent's calling range is wider
    if texture['wet']:
        adj -= 0.05  # We need more equity to value bet
    # On dry boards, opponent folds more
    elif texture['dry']:
        adj += 0.05  # We can bluff more
    
    # Paired boards: opponent has trips more often
    if texture['paired'] and not texture['trips']:
        adj -= 0.03
    
    return adj


def river_bluff_candidates(hole_cards, board_cards):
    """
    Identify good bluff candidates on river based on blockers.
    Returns list of (card_to_discard, bluff_score) tuples.
    Handles both 3-card (pre-discard) and 2-card (post-discard) hands.
    """
    hole = [parse_card(c) for c in hole_cards]
    board = [parse_card(c) for c in board_cards]
    
    results = []
    for i, discard in enumerate(hole):
        kept = [hole[j] for j in range(len(hole)) if j != i]
        
        # Blockers: cards that block opponent's value hands
        blocker_score = 0.0
        discard_rank = discard // 4
        discard_suit = discard % 4
        
        # Block top pair
        for bc in board:
            if bc // 4 == discard_rank:
                blocker_score += 0.15
        
        # Block flush
        board_suits = [c % 4 for c in board]
        if board_suits.count(discard_suit) >= 3:
            blocker_score += 0.25
        elif board_suits.count(discard_suit) >= 2:
            blocker_score += 0.1
        
        # Block straight
        board_ranks = sorted(set(c // 4 for c in board))
        for r in board_ranks:
            if abs(r - discard_rank) <= 2:
                blocker_score += 0.05
        
        # Unblock bluffs (we don't block missed draws we'd bluff with)
        # This is complex, simplified for now
        
        results.append((discard, blocker_score))
    
    return sorted(results, key=lambda x: -x[1])


# Test
if __name__ == '__main__':
    # Test board textures
    test_boards = [
        ["As", "Kd", "7h"],  # Dry
        ["9s", "8s", "7s"],  # Very wet (flush + straight)
        ["Td", "Td", "2c"],  # Paired dry
        ["Js", "Ts", "9h"],  # Wet (straight draw)
        ["As", "Ah", "Ad"],  # Trips
    ]
    
    for b in test_boards:
        cards = [parse_card(c) for c in b]
        tex = analyze_board_texture(cards)
        cat = get_board_category(cards)
        print(f"Board: {b} -> Category: {cat}, Texture: {tex['texture_score']:.2f}, Wet: {tex['wet']}")