"""
Ultra-fast 7-card hand evaluator in pure NumPy.
Card id = rank*4 + suit, rank 0..12 (2..A), suit 0..3.
Score: category << 20 | tiebreakers (4 bits each, descending).
Categories: 8=SF, 7=Quads, 6=FH, 5=Flush, 4=Straight, 3=Trips, 2=TwoPair, 1=Pair, 0=High
"""
import numpy as np

CAT = 20

# 10 straight patterns (bool 13-vec) + their high cards. Wheel high = 3 (5-high straight).
_STRAIGHTS = np.zeros((10, 13), np.bool_)
for _i, _top in enumerate(range(4, 13)):
    _STRAIGHTS[_i, _top - 4:_top + 1] = True
_STRAIGHTS[9, [0, 1, 2, 3, 12]] = True
_STRAIGHT_HIGH = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 3], np.int32)


def _top_n(mask, n):
    """mask: (N,W) bool. Returns (N,n) int32 of n HIGHEST eligible columns, descending."""
    w = mask.shape[1]
    key = mask.astype(np.int32) * 1000 + np.arange(w, dtype=np.int32)[None, :]
    order = np.argsort(-key, axis=1, kind="stable")[:, :n]
    return order.astype(np.int32)


def eval_batch(cards):
    """
    cards: (N,7) integer array of card ids (rank*4 + suit).
    Returns (N,) int32 scores, higher is better.
    """
    c = np.asarray(cards)
    if c.ndim != 2 or c.shape[1] != 7:
        raise ValueError("cards must be (N,7)")
    N = c.shape[0]
    idx = np.arange(N)
    ranks = (c // 4).astype(np.int32)
    suits = (c % 4).astype(np.int32)

    # ---- rank multiplicities (N,13) ----
    cnt = np.zeros((N, 13), np.int8)
    for j in range(7):
        np.add.at(cnt, (idx, ranks[:, j]), 1)
    present = cnt > 0

    # ---- groups ----
    is4 = cnt == 4
    is3 = cnt == 3
    is_ge3 = cnt >= 3
    is2 = cnt == 2

    q = np.where(is4.any(1), _top_n(is4, 1)[:, 0], -1)

    t3 = np.where(is_ge3.any(1), _top_n(is_ge3, 1)[:, 0], -1)
    t3_rest = is_ge3.copy()
    rows = idx[t3 >= 0]
    t3_rest[rows, t3[t3 >= 0]] = False
    t3b = np.where(t3_rest.any(1), _top_n(t3_rest, 1)[:, 0], -1)

    p2 = is2.copy()
    p2a = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)
    rows = idx[p2a >= 0]
    p2[rows, p2a[p2a >= 0]] = False
    p2b = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)

    # ---- straight ----
    highs = np.full((N, 10), -1, np.int32)
    for k in range(10):
        ok = (present & _STRAIGHTS[k]).sum(1) == 5
        highs[:, k] = np.where(ok, _STRAIGHT_HIGH[k], -1)
    shigh = highs.max(1)

    # ---- flush ----
    suit_cnt = np.zeros((N, 4), np.int8)
    for j in range(7):
        np.add.at(suit_cnt, (idx, suits[:, j]), 1)
    has_flush = (suit_cnt >= 5).any(1)
    flush_suit = np.where(has_flush, _top_n(suit_cnt >= 5, 1)[:, 0], -1)

    # ---- straight flush ----
    sf_high = np.full(N, -1, np.int32)
    mrows = idx[has_flush]
    if len(mrows):
        fs = flush_suit[mrows]
        suit_rank = np.zeros((len(mrows), 13), np.bool_)
        for j in range(7):
            sel = suits[mrows, j] == fs
            suit_rank[np.arange(len(mrows))[sel], ranks[mrows, j][sel]] = True
        hs = np.full((len(mrows), 10), -1, np.int32)
        for k in range(10):
            ok = (suit_rank & _STRAIGHTS[k]).sum(1) == 5
            hs[:, k] = np.where(ok, _STRAIGHT_HIGH[k], -1)
        sf_high[mrows] = hs.max(1)
    is_sf = sf_high >= 0

    score = np.zeros(N, np.int64)

    # --- straight flush ---
    m = is_sf
    score[m] = (8 << CAT) | sf_high[m]

    # --- quads ---
    m = (score == 0) & (q >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], q[m]] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (7 << CAT) | (q[m] << 4) | kick

    # --- full house ---
    m = (score == 0) & (t3 >= 0) & ((p2a >= 0) | (t3b >= 0))
    if m.any():
        pair_rank = np.where(p2a >= 0, p2a, t3b)
        score[m] = (6 << CAT) | (t3[m] << 4) | pair_rank[m]

    # --- flush ---
    m = (score == 0) & has_flush
    if m.any():
        r = idx[m]
        fs = flush_suit[m]
        sr = np.zeros((len(r), 13), np.bool_)
        for j in range(7):
            sel = suits[r, j] == fs
            sr[np.arange(len(r))[sel], ranks[r, j][sel]] = True
        top = _top_n(sr, 5)
        v = np.zeros(len(r), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = (5 << CAT) | v

    # --- straight ---
    m = (score == 0) & (shigh >= 0)
    score[m] = (4 << CAT) | shigh[m]

    # --- trips ---
    m = (score == 0) & (t3 >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], t3[m]] = True
        kick = _top_n(present & ~excl, 2)[idx[m]]
        score[m] = (3 << CAT) | (t3[m] << 8) | (kick[:, 0] << 4) | kick[:, 1]

    # --- two pair ---
    m = (score == 0) & (p2a >= 0) & (p2b >= 0)
    if m.any():
        hi = np.maximum(p2a[m], p2b[m])
        lo = np.minimum(p2a[m], p2b[m])
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], hi] = True
        excl[idx[m], lo] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (2 << CAT) | (hi << 8) | (lo << 4) | kick

    # --- one pair ---
    m = (score == 0) & (p2a >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], p2a[m]] = True
        kick = _top_n(present & ~excl, 3)[idx[m]]
        score[m] = (1 << CAT) | (p2a[m] << 12) | (kick[:, 0] << 8) | (kick[:, 1] << 4) | kick[:, 2]

    # --- high card ---
    m = score == 0
    if m.any():
        top = _top_n(present[m], 5)
        v = np.zeros(m.sum(), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = v

    return score.astype(np.int32)


def eval5_batch(cards):
    """
    Evaluate 5-card hands. cards: (N,5) -> (N,) scores.
    """
    c = np.asarray(cards)
    if c.ndim != 2 or c.shape[1] != 5:
        raise ValueError("cards must be (N,5)")
    N = c.shape[0]
    idx = np.arange(N)
    ranks = (c // 4).astype(np.int32)
    suits = (c % 4).astype(np.int32)

    # ---- rank multiplicities (N,13) ----
    cnt = np.zeros((N, 13), np.int8)
    for j in range(5):
        np.add.at(cnt, (idx, ranks[:, j]), 1)
    present = cnt > 0

    # ---- groups ----
    is4 = cnt == 4
    is3 = cnt == 3
    is_ge3 = cnt >= 3
    is2 = cnt == 2

    q = np.where(is4.any(1), _top_n(is4, 1)[:, 0], -1)

    t3 = np.where(is_ge3.any(1), _top_n(is_ge3, 1)[:, 0], -1)
    t3_rest = is_ge3.copy()
    rows = idx[t3 >= 0]
    t3_rest[rows, t3[t3 >= 0]] = False
    t3b = np.where(t3_rest.any(1), _top_n(t3_rest, 1)[:, 0], -1)

    p2 = is2.copy()
    p2a = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)
    rows = idx[p2a >= 0]
    p2[rows, p2a[p2a >= 0]] = False
    p2b = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)

    # ---- straight ----
    highs = np.full((N, 10), -1, np.int32)
    for k in range(10):
        ok = (present & _STRAIGHTS[k]).sum(1) == 5
        highs[:, k] = np.where(ok, _STRAIGHT_HIGH[k], -1)
    shigh = highs.max(1)

    # ---- flush ----
    suit_cnt = np.zeros((N, 4), np.int8)
    for j in range(5):
        np.add.at(suit_cnt, (idx, suits[:, j]), 1)
    has_flush = (suit_cnt >= 5).any(1)
    flush_suit = np.where(has_flush, _top_n(suit_cnt >= 5, 1)[:, 0], -1)

    # ---- straight flush ----
    sf_high = np.full(N, -1, np.int32)
    mrows = idx[has_flush]
    if len(mrows):
        fs = flush_suit[mrows]
        suit_rank = np.zeros((len(mrows), 13), np.bool_)
        for j in range(5):
            sel = suits[mrows, j] == fs
            suit_rank[np.arange(len(mrows))[sel], ranks[mrows, j][sel]] = True
        hs = np.full((len(mrows), 10), -1, np.int32)
        for k in range(10):
            ok = (suit_rank & _STRAIGHTS[k]).sum(1) == 5
            hs[:, k] = np.where(ok, _STRAIGHT_HIGH[k], -1)
        sf_high[mrows] = hs.max(1)
    is_sf = sf_high >= 0

    score = np.zeros(N, np.int64)

    # --- straight flush ---
    m = is_sf
    score[m] = (8 << CAT) | sf_high[m]

    # --- quads ---
    m = (score == 0) & (q >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], q[m]] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (7 << CAT) | (q[m] << 4) | kick

    # --- full house ---
    m = (score == 0) & (t3 >= 0) & ((p2a >= 0) | (t3b >= 0))
    if m.any():
        pair_rank = np.where(p2a >= 0, p2a, t3b)
        score[m] = (6 << CAT) | (t3[m] << 4) | pair_rank[m]

    # --- flush ---
    m = (score == 0) & has_flush
    if m.any():
        r = idx[m]
        fs = flush_suit[m]
        sr = np.zeros((len(r), 13), np.bool_)
        for j in range(5):
            sel = suits[r, j] == fs
            sr[np.arange(len(r))[sel], ranks[r, j][sel]] = True
        top = _top_n(sr, 5)
        v = np.zeros(len(r), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = (5 << CAT) | v

    # --- straight ---
    m = (score == 0) & (shigh >= 0)
    score[m] = (4 << CAT) | shigh[m]

    # --- trips ---
    m = (score == 0) & (t3 >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], t3[m]] = True
        kick = _top_n(present & ~excl, 2)[idx[m]]
        score[m] = (3 << CAT) | (t3[m] << 8) | (kick[:, 0] << 4) | kick[:, 1]

    # --- two pair ---
    m = (score == 0) & (p2a >= 0) & (p2b >= 0)
    if m.any():
        hi = np.maximum(p2a[m], p2b[m])
        lo = np.minimum(p2a[m], p2b[m])
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], hi] = True
        excl[idx[m], lo] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (2 << CAT) | (hi << 8) | (lo << 4) | kick

    # --- one pair ---
    m = (score == 0) & (p2a >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], p2a[m]] = True
        kick = _top_n(present & ~excl, 3)[idx[m]]
        score[m] = (1 << CAT) | (p2a[m] << 12) | (kick[:, 0] << 8) | (kick[:, 1] << 4) | kick[:, 2]

    # --- high card ---
    m = score == 0
    if m.any():
        top = _top_n(present[m], 5)
        v = np.zeros(m.sum(), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = v

    return score.astype(np.int32)


def equity_vs_range(hole, board, n_draws=500, seed=0):
    """
    Monte Carlo equity: P(win) + 0.5*P(tie) vs uniform random 2-card hand.
    hole: list of 2 card ids (rank*4 + suit)
    board: list of 0-5 card ids
    """
    hole = list(hole)
    board = list(board)
    known = set(hole) | set(board)
    rem = np.array([c for c in range(52) if c not in known], np.int64)
    n_board = len(board)
    need = 5 - n_board
    if len(rem) < 2 + need:
        return 0.5

    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    n = n_draws
    take = 2 + need
    keys = rng.random((n, len(rem)))
    idx = np.argpartition(keys, take - 1, axis=1)[:, :take]
    picked = rem[idx]

    opp = picked[:, :2]
    newcards = picked[:, 2:]

    my = np.empty((n, 7), np.int64)
    op = np.empty((n, 7), np.int64)
    my[:, :2] = hole
    op[:, :2] = opp
    if n_board:
        my[:, 2:2 + n_board] = board
        op[:, 2:2 + n_board] = board
    my[:, 2 + n_board:] = newcards
    op[:, 2 + n_board:] = newcards

    sm = eval_batch(my)
    so = eval_batch(op)
    wins = (sm > so).sum() + 0.5 * (sm == so).sum()
    return float(wins) / n


def card_str(c):
    """Convert card id to string like 'As', 'Td', etc."""
    rank = "23456789TJQKA"[c // 4]
    suit = "shdc"[c % 4]
    return rank + suit


def parse_card(s):
    """Parse card string like 'As' to card id."""
    rank = "23456789TJQKA".index(s[0])
    suit = "shdc".index(s[1])
    return rank * 4 + suit


# Preflop equity cache for 3-card hands (Discard Hold'em)
# We'll compute this on first use
_preflop_equity_cache = {}


def preflop_equity_3card(hole3, n_draws=2000, seed=42):
    """
    Equity of a 3-card hand vs random 3-card hand, assuming both discard optimally.
    This is an approximation - we assume both players will discard their worst card.
    """
    key = tuple(sorted(hole3))
    if key in _preflop_equity_cache:
        return _preflop_equity_cache[key]

    # For each possible discard, compute equity vs random 2-card hand
    best_eq = 0.0
    for i in range(3):
        kept = [hole3[j] for j in range(3) if j != i]
        eq = equity_vs_range(kept, [], n_draws=n_draws, seed=seed + i * 1000)
        if eq > best_eq:
            best_eq = eq

    _preflop_equity_cache[key] = best_eq
    return best_eq