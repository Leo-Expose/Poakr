"""
Fast 7-card hand evaluator (numba), used ONLY for offline training throughput.
Semantics are IDENTICAL to engine.cards (verified differentially, see validate_eval).

Card id = rank*4 + suit, rank 0..12 (2..A), suit 0..3.

Rank counts are kept in an explicit int8[13] array — this is the key fix over the
bit-packing attempt: a present rank is NOT the same as a tripled rank, and a
naive 'set both bits' encoding collapses 1/2/3-of-a-kind into one value, which
then silently empties the kicker lists. Explicit counts are both correct and,
at 13 entries, cheap even in numba.
"""
import numpy as np
from numba import njit

CAT = 20


@njit(cache=True)
def _score7(cards):
    """cards: int64[7]. Returns int64 score, higher is better."""
    cnt = np.zeros(13, np.int8)
    suits = np.zeros(4, np.int8)
    rank_mask = np.int64(0)
    # suit_rank_mask[s] = bitmask of ranks present in suit s
    srm = np.zeros(4, np.int64)

    for i in range(7):
        c = cards[i]
        r = c // 4
        s = c % 4
        cnt[r] += 1
        suits[s] += 1
        rank_mask |= np.int64(1) << np.int64(r)
        srm[s] |= np.int64(1) << np.int64(r)

    # ---- straight high (wheel included) ----
    nd = 0
    t = rank_mask
    while t:
        t &= t - 1
        nd += 1
    sh = -1
    if nd >= 5:
        for top in range(12, 3, -1):
            need = np.int64(0x1F) << np.int64(top - 4)
            if (rank_mask & need) == need:
                sh = top
                break
        if sh < 0:
            wheel = np.int64(0x100F)  # bits 0,1,2,3 and 12
            if (rank_mask & wheel) == wheel:
                sh = 3

    # ---- flush suit (if any) ----
    fs = -1
    for s in range(4):
        if suits[s] >= 5:
            fs = s
            break

    # ---- groups, scanning high rank to low ----
    q = -1
    t3a = -1
    t3b = -1
    p2a = -1
    p2b = -1
    for r in range(12, -1, -1):
        c = cnt[r]
        if c == 4:
            q = r
        elif c == 3:
            if t3a < 0:
                t3a = r
            elif t3b < 0:
                t3b = r
        elif c == 2:
            if p2a < 0:
                p2a = r
            elif p2b < 0:
                p2b = r

    # ---- straight flush ----
    if fs >= 0:
        fm = srm[fs]
        s_sh = -1
        for top in range(12, 3, -1):
            need = np.int64(0x1F) << np.int64(top - 4)
            if (fm & need) == need:
                s_sh = top
                break
        if s_sh < 0:
            wheel = np.int64(0x100F)
            if (fm & wheel) == wheel:
                s_sh = 3
        if s_sh >= 0:
            return (8 << CAT) | s_sh

    # ---- quads ----
    if q >= 0:
        for r in range(12, -1, -1):
            if r != q and cnt[r] > 0:
                return (7 << CAT) | (q << 4) | r
        return (7 << CAT) | (q << 4)

    # ---- full house (trips+pair, or two trips where the lower becomes the pair) ----
    if t3a >= 0:
        if p2a >= 0:
            return (6 << CAT) | (t3a << 4) | p2a
        if t3b >= 0:
            return (6 << CAT) | (t3a << 4) | t3b

    # ---- flush ----
    if fs >= 0:
        v = 0
        taken = 0
        for r in range(12, -1, -1):
            if (srm[fs] >> np.int64(r)) & 1:
                v |= r << (16 - 4 * taken)
                taken += 1
                if taken == 5:
                    break
        return (5 << CAT) | v

    # ---- straight ----
    if sh >= 0:
        return (4 << CAT) | sh

    # ---- trips ----
    if t3a >= 0:
        k0 = -1
        k1 = -1
        for r in range(12, -1, -1):
            if r == t3a or cnt[r] == 0:
                continue
            if k0 < 0:
                k0 = r
            elif k1 < 0:
                k1 = r
                break
        if k1 < 0:
            k1 = 0
        return (3 << CAT) | (t3a << 8) | (k0 << 4) | k1

    # ---- two pair ----
    if p2a >= 0 and p2b >= 0:
        hi = p2a if p2a > p2b else p2b
        lo = p2b if p2a > p2b else p2a
        for r in range(12, -1, -1):
            if r != hi and r != lo and cnt[r] > 0:
                return (2 << CAT) | (hi << 8) | (lo << 4) | r
        return (2 << CAT) | (hi << 8) | (lo << 4)

    # ---- one pair ----
    if p2a >= 0:
        ks = np.zeros(3, np.int64)
        n = 0
        for r in range(12, -1, -1):
            if r == p2a or cnt[r] == 0:
                continue
            ks[n] = r
            n += 1
            if n == 3:
                break
        while n < 3:
            ks[n] = 0
            n += 1
        return (1 << CAT) | (p2a << 12) | (ks[0] << 8) | (ks[1] << 4) | ks[2]

    # ---- high card ----
    v = 0
    taken = 0
    for r in range(12, -1, -1):
        if (rank_mask >> np.int64(r)) & 1:
            v |= r << (16 - 4 * taken)
            taken += 1
            if taken == 5:
                break
    return v


@njit(cache=True)
def eval_hands(cards_a, cards_b):
    """Two 7-card hands -> (score_a, score_b)."""
    sa = _score7(cards_a)
    sb = _score7(cards_b)
    return sa, sb


@njit(cache=True)
def eval_one(cards):
    return _score7(cards)


@njit(cache=True, nogil=True)
def equity_vs_range(hole, board, n_board, draws, rng_state):
    """
    Monte-carlo equity of `hole` vs a uniform random 2-card hand, given `n_board`
    board cards already dealt. Ties count 0.5. `rng_state` is an int64 seed that
    is advanced internally (xorshift). Returns win-share in [0,1].
    """
    used = np.zeros(52, np.bool_)
    for i in range(2):
        used[hole[i]] = True
    for i in range(n_board):
        used[board[i]] = True

    rem = np.empty(52, np.int64)
    nr = 0
    for c in range(52):
        if not used[c]:
            rem[nr] = c
            nr += 1

    a = np.empty(7, np.int64)
    b = np.empty(7, np.int64)
    for i in range(2):
        a[i] = hole[i]
    for i in range(n_board):
        a[2 + i] = board[i]
        b[2 + i] = board[i]

    wins = 0.0
    state = rng_state
    if state == 0:
        state = 88172645463325252
    for _ in range(draws):
        # xorshift64
        state ^= (state << np.int64(13))
        state ^= (state >> np.int64(7))
        state ^= (state << np.int64(17))

        i1 = int(state % nr)
        state ^= (state << np.int64(13)); state ^= (state >> np.int64(7)); state ^= (state << np.int64(17))
        i2 = int(state % (nr - 1))
        if i2 >= i1:
            i2 += 1
        b[0] = rem[i1]
        b[1] = rem[i2]

        # remaining board cards, drawn without replacement from the rest
        k = nr - 2
        pool = np.empty(nr, np.int64)
        w = 0
        for j in range(nr):
            if j != i1 and j != i2:
                pool[w] = rem[j]
                w += 1
        for t in range(5 - n_board):
            state ^= (state << np.int64(13)); state ^= (state >> np.int64(7)); state ^= (state << np.int64(17))
            idx = int(state % k)
            a[2 + n_board + t] = pool[idx]
            b[2 + n_board + t] = pool[idx]
            pool[idx] = pool[k - 1]
            k -= 1

        sa = _score7(a)
        sb = _score7(b)
        if sa > sb:
            wins += 1.0
        elif sa == sb:
            wins += 0.5
    return wins / draws
