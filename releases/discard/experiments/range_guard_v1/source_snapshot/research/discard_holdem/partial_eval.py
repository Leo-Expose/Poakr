"""Exact current made-hand rank for 5/6/7 physical cards.
Derived from our existing NumPy evaluator; no external bot source.
Used only for heuristic range modelling, NEVER proof support truncation.
"""
import numpy as np

# 10 straight patterns (bool 13-vec) + their high cards.  Wheel high = 3.
_STRAIGHTS = np.zeros((10, 13), np.bool_)
for _i, _top in enumerate(range(4, 13)):
    _STRAIGHTS[_i, _top - 4:_top + 1] = True
_STRAIGHTS[9, [0, 1, 2, 3, 12]] = True
_STRAIGHT_HIGH = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 3], np.int32)

_RANKS = np.arange(13, dtype=np.int32)[None, :]
_CAT = 20


def _top_n(mask, n):
    """
    mask: (N,W) bool — which columns are eligible (W = 13 for ranks, 4 for suits).
    Returns (N,n) int32 of the n HIGHEST-index eligible columns, descending.
    Empty slots are 0 (callers guarantee enough eligible columns).

    Key trick: key = eligible*1000 + column, sort descending.  Eligible columns
    always outrank ineligible ones, and among eligible, higher index first.
    """
    w = mask.shape[1]
    key = mask.astype(np.int32) * 1000 + np.arange(w, dtype=np.int32)[None, :]
    order = np.argsort(-key, axis=1, kind="stable")[:, :n]
    return order.astype(np.int32)


def eval_made(cards):
    """
    cards: (N,7) integer array of card ids (rank*4 + suit).
    Returns (N,) int32 scores, higher is better.
    """
    c = np.asarray(cards)
    if c.ndim != 2 or c.shape[1] not in (5,6,7):
        raise ValueError("cards must have 5, 6 or 7 columns")
    N = c.shape[0]
    idx = np.arange(N)
    ranks = (c // 4).astype(np.int32)
    suits = (c % 4).astype(np.int32)

    # ---- rank multiplicities (N,13) ----
    cnt = np.zeros((N, 13), np.int8)
    for j in range(c.shape[1]):
        np.add.at(cnt, (idx, ranks[:, j]), 1)
    present = cnt > 0

    # ---- groups ----
    is4 = cnt == 4
    is3 = cnt == 3
    is_ge3 = cnt >= 3
    is2 = cnt == 2

    q = np.where(is4.any(1), _top_n(is4, 1)[:, 0], -1)

    t3 = np.where(is_ge3.any(1), _top_n(is_ge3, 1)[:, 0], -1)
    # second trip (full house from two trips)
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
    for j in range(c.shape[1]):
        np.add.at(suit_cnt, (idx, suits[:, j]), 1)
    has_flush = (suit_cnt >= 5).any(1)
    flush_suit = np.where(has_flush, _top_n(suit_cnt >= 5, 1)[:, 0], -1)

    # ---- straight flush ----
    sf_high = np.full(N, -1, np.int32)
    mrows = idx[has_flush]
    if len(mrows):
        fs = flush_suit[mrows]
        suit_rank = np.zeros((len(mrows), 13), np.bool_)
        for j in range(c.shape[1]):
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
    score[m] = (8 << _CAT) | sf_high[m]

    # --- quads ---
    m = (score == 0) & (q >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], q[m]] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (7 << _CAT) | (q[m] << 4) | kick

    # --- full house ---
    m = (score == 0) & (t3 >= 0) & ((p2a >= 0) | (t3b >= 0))
    if m.any():
        pair_rank = np.where(p2a >= 0, p2a, t3b)
        score[m] = (6 << _CAT) | (t3[m] << 4) | pair_rank[m]

    # --- flush ---
    m = (score == 0) & has_flush
    if m.any():
        r = idx[m]
        fs = flush_suit[m]
        sr = np.zeros((len(r), 13), np.bool_)
        for j in range(c.shape[1]):
            sel = suits[r, j] == fs
            sr[np.arange(len(r))[sel], ranks[r, j][sel]] = True
        top = _top_n(sr, 5)
        v = np.zeros(len(r), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = (5 << _CAT) | v

    # --- straight ---
    m = (score == 0) & (shigh >= 0)
    score[m] = (4 << _CAT) | shigh[m]

    # --- trips ---
    m = (score == 0) & (t3 >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], t3[m]] = True
        kick = _top_n(present & ~excl, 2)[idx[m]]
        score[m] = (3 << _CAT) | (t3[m] << 8) | (kick[:, 0] << 4) | kick[:, 1]

    # --- two pair ---
    m = (score == 0) & (p2a >= 0) & (p2b >= 0)
    if m.any():
        hi = np.maximum(p2a[m], p2b[m])
        lo = np.minimum(p2a[m], p2b[m])
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], hi] = True
        excl[idx[m], lo] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (2 << _CAT) | (hi << 8) | (lo << 4) | kick

    # --- one pair ---
    m = (score == 0) & (p2a >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], p2a[m]] = True
        kick = _top_n(present & ~excl, 3)[idx[m]]
        score[m] = (1 << _CAT) | (p2a[m] << 12) | (kick[:, 0] << 8) | (kick[:, 1] << 4) | kick[:, 2]

    # --- high card ---
    m = score == 0
    if m.any():
        top = _top_n(present[m], 5)
        v = np.zeros(m.sum(), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = v

    return score.astype(np.int32)

