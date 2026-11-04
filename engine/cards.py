"""
Card primitives AGNOSTIC to deck geometry.

card = rank * n_suits + suit,  rank in [0,n_ranks), suit in [0,n_suits)

The same code serves 52-card Hold'em, short deck, 58-card, 4-board, 1-hole...
Nothing downstream needs a rewrite when the real rules land.
"""

HIGH, PAIR, TWOPAIR, TRIPS, STRAIGHT, FLUSH, FULLHOUSE, QUADS, STRAIGHTFLUSH = range(9)
_NAMES = ["High", "Pair", "TwoPair", "Trips", "Straight", "Flush", "FullHouse", "Quads", "StraightFlush"]


def category_name(score):
    return _NAMES[(score >> 20) & 0xF]


def make_evaluator(n_ranks, n_suits, full_beats_flush=True, wheel_low=True):
    """
    Returns eval5(c0,c1,c2,c3,c4) -> int score (higher wins), pure integer math.

    Score = category << 20 | tiebreakers packed 4 bits each (descending).
    """
    CAT = 20
    _ = [0] * n_ranks  # template

    # straight masks, longest-first ordering by high card
    masks = []
    for top in range(4, n_ranks):
        m = ((1 << 5) - 1) << (top - 4)
        masks.append((top, m))
    if wheel_low and n_ranks >= 5:
        # A-2-3-4-5 ("wheel"): ranks {0,1,2,3} plus the ace at n_ranks-1
        masks.append((3, 0b1111 | (1 << (n_ranks - 1))))
    masks.sort(key=lambda t: -t[0])

    C_FULL, C_FLUSH = (FULLHOUSE, FLUSH) if full_beats_flush else (FLUSH, FULLHOUSE)

    def eval5(c0, c1, c2, c3, c4):
        r0 = c0 // n_suits; r1 = c1 // n_suits; r2 = c2 // n_suits
        r3 = c3 // n_suits; r4 = c4 // n_suits

        cnt = [0] * n_ranks
        cnt[r0] += 1; cnt[r1] += 1; cnt[r2] += 1; cnt[r3] += 1; cnt[r4] += 1

        # ordered ranks by (count desc, rank desc)
        q = []; t = []; p = []; k = []
        for r in range(n_ranks - 1, -1, -1):
            c = cnt[r]
            if c == 4: q.append(r)
            elif c == 3: t.append(r)
            elif c == 2: p.append(r)
            elif c == 1: k.append(r)

        # distinct-rank bitmask; popcount == number of distinct ranks
        rm = (1 << r0) | (1 << r1) | (1 << r2) | (1 << r3) | (1 << r4)
        n_distinct = bin(rm).count("1")

        is_flush = (c0 % n_suits == c1 % n_suits == c2 % n_suits == c3 % n_suits == c4 % n_suits)

        # straight
        sh = -1
        if n_distinct == 5:
            for top, m in masks:
                if (rm & m) == m:
                    sh = top
                    break

        if q:
            return (QUADS << CAT) | (q[0] << 4) | (t[0] if t else (p[0] if p else k[0]))
        if is_flush and sh >= 0:
            return (STRAIGHTFLUSH << CAT) | sh
        if t:
            if p:
                return (C_FULL << CAT) | (t[0] << 4) | p[0]
            return (TRIPS << CAT) | (t[0] << 8) | (k[0] << 4) | (k[1] if len(k) > 1 else 0)
        if is_flush:
            rs = sorted((r0, r1, r2, r3, r4), reverse=True)
            return (C_FLUSH << CAT) | (rs[0] << 16) | (rs[1] << 12) | (rs[2] << 8) | (rs[3] << 4) | rs[4]
        if sh >= 0:
            return (STRAIGHT << CAT) | sh
        if len(p) == 2:
            hi, lo = p[0], p[1]
            return (TWOPAIR << CAT) | (hi << 8) | (lo << 4) | k[0]
        if len(p) == 1:
            kk = k
            return (PAIR << CAT) | (p[0] << 12) | (kk[0] << 8) | (kk[1] << 4) | kk[2]
        rs = sorted((r0, r1, r2, r3, r4), reverse=True)
        return (HIGH << CAT) | (rs[0] << 16) | (rs[1] << 12) | (rs[2] << 8) | (rs[3] << 4) | rs[4]

    eval5.n_ranks = n_ranks
    eval5.n_suits = n_suits
    return eval5


def make_best_of(eval5, n_cards_total):
    """best_of(hole, board) -> score, over all 5-subsets of hole+board."""
    from itertools import combinations
    combos = list(combinations(range(n_cards_total), 5))

    def best(hole, board):
        cards = list(hole) + list(board)
        bs = -1
        for a, b, c, d, e in combos:
            s = eval5(cards[a], cards[b], cards[c], cards[d], cards[e])
            if s > bs:
                bs = s
        return bs

    best.combos = combos
    return best


def make_deck(n_ranks, n_suits):
    return list(range(n_ranks * n_suits))
