"""
Optimal discard strategy for Discard Hold'em.
After flop, both players simultaneously discard 1 of their 3 hole cards.
We want to maximize our equity while blocking opponent's outs.
"""
import numpy as np
from eval7 import eval_batch, equity_vs_range, card_str, parse_card


def hand_category(score):
    """Extract hand category from score (8=SF down to 0=High)."""
    return (score >> 20) & 0xF


def made_hand_strength(hole, board):
    """Quick made-hand strength in [0,1] using best 5-card category + kickers."""
    if not board:
        return None
    from itertools import combinations
    from eval7 import eval5_batch
    cards = list(hole) + list(board)
    combos = list(combinations(cards, 5))
    if not combos:
        return 0.0
    scores = eval5_batch(np.array(combos, dtype=np.int64))
    best = scores.max()
    cat = (best >> 20) & 0xF
    tie = best & 0xFFFFF
    return (cat + tie / 0x100000) / 9.0


def discard_equity(hole3, board, discards, n_draws=400):
    """
    Compute equity for each possible discard choice.
    hole3: list of 3 card ids
    board: list of 3 card ids (flop)
    discards: list of card ids to consider discarding
    Returns: dict {discard_card: equity}
    """
    results = {}
    for d in discards:
        kept = [c for c in hole3 if c != d]
        eq = equity_vs_range(kept, board, n_draws=n_draws, seed=hash((tuple(sorted(kept)), tuple(board))) & 0xFFFFFFFF)
        results[d] = eq
    return results


def blocker_value(hole3, board, discard_card, n_draws=300):
    """
    How much does discarding this card BLOCK opponent's outs?
    Simulate: if opponent had this card, how much would their equity drop?
    """
    kept = [c for c in hole3 if c != discard_card]
    # Opponent's equity if they DON'T have this card (normal)
    eq_normal = equity_vs_range(kept, board, n_draws=n_draws, seed=1000)
    
    # We can't easily simulate opponent having the card without knowing their range.
    # Instead, use a proxy: cards that complete draws on board.
    # For simplicity, return the rank/suit blocking potential.
    rank = discard_card // 4
    suit = discard_card % 4
    
    # Blocking value: higher for cards that hit board texture
    block_score = 0.0
    # Board cards
    for bc in board:
        if bc // 4 == rank:
            block_score += 0.05  # Blocking a pair/trips
        if bc % 4 == suit:
            block_score += 0.02  # Blocking flush draw
    
    return block_score


def choose_discard(hole_cards, board, pot, my_stack, opp_stack, n_draws=400):
    """
    Choose optimal discard from 3 hole cards.
    Returns the card id to discard.
    """
    # Parse hole cards
    hole3 = [parse_card(c) for c in hole_cards]
    board_cards = [parse_card(c) for c in board]
    
    # Get equity for each discard option
    equities = discard_equity(hole3, board_cards, hole3, n_draws=n_draws)
    
    # Add blocker value
    best_card = None
    best_score = -1
    
    for d in hole3:
        eq = equities[d]
        block = blocker_value(hole3, board_cards, d, n_draws=min(n_draws, 200))
        # Weight: primarily equity, secondarily blockers
        score = eq + block * 0.1
        if score > best_score:
            best_score = score
            best_card = d
    
    return card_str(best_card)


def choose_discard_fast(hole_cards, board):
    """
    Ultra-fast heuristic discard for time-pressured situations.
    """
    hole3 = [parse_card(c) for c in hole_cards]
    board_cards = [parse_card(c) for c in board]
    
    # Heuristic: keep the two cards that make the best 5-card hand with board
    from itertools import combinations
    best_keep = None
    best_score = -1
    
    for keep in combinations(hole3, 2):
        cards = list(keep) + board_cards
        # Quick evaluation: count pairs, flush draws, straight draws
        ranks = [c // 4 for c in cards]
        suits = [c % 4 for c in cards]
        
        score = 0
        # Pairs/trips
        from collections import Counter
        rc = Counter(ranks)
        for r, cnt in rc.items():
            if cnt >= 2:
                score += cnt * 10
        # Flush draw
        sc = Counter(suits)
        for s, cnt in sc.items():
            if cnt >= 4:
                score += 20
            elif cnt >= 3:
                score += 5
        # Straight draw potential
        unique_ranks = sorted(set(ranks))
        for i in range(len(unique_ranks) - 2):
            if unique_ranks[i+2] - unique_ranks[i] <= 4:
                score += 3
        
        if score > best_score:
            best_score = score
            best_keep = set(keep)
    
    # Discard the one not in best_keep
    for c in hole3:
        if c not in best_keep:
            return card_str(c)
    
    return card_str(hole3[0])