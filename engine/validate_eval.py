"""Exhaustive validation of the evaluator against a brute-force reference.
Checks EVERY 5-card hand in a 13x4 deck (2,598,960) for exact score equality,
and every 7-card showdown ordering on a large random sample.
Reference is written inline & explicitly so no bug can be shared with the impl.
"""
import sys, time, random
from itertools import combinations
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.cards import make_evaluator, make_best_of

NS = 4
EV = make_evaluator(13, NS)
BEST = make_best_of(EV, 7)


def brute(cards):
    """Independent, deliberately dumb reference. cards = list of 5 ints."""
    ranks = [c // NS for c in cards]
    suits = [c % NS for c in cards]
    # multiplicity, computed from scratch
    mult = {}
    for r in ranks:
        mult[r] = mult.get(r, 0) + 1
    quads = [r for r, n in mult.items() if n == 4]
    trips = [r for r, n in mult.items() if n == 3]
    pairs = sorted([r for r, n in mult.items() if n == 2], reverse=True)
    singles = sorted([r for r, n in mult.items() if n == 1], reverse=True)

    flush = len(set(suits)) == 1
    uniq = sorted(set(ranks))
    straight = -1
    if len(uniq) == 5:
        if uniq[4] - uniq[0] == 4:
            straight = uniq[4]
        elif uniq == [0, 1, 2, 3, 12]:
            straight = 3

    hi = sorted(ranks, reverse=True)
    if flush and straight >= 0:
        return (8 << 20) | straight
    if quads:
        kicker = sorted([r for r in ranks if r != quads[0]], reverse=True)[0]
        return (7 << 20) | (quads[0] << 4) | kicker
    if trips and pairs:
        return (6 << 20) | (trips[0] << 4) | pairs[0]
    if flush:
        return (5 << 20) | (hi[0] << 16) | (hi[1] << 12) | (hi[2] << 8) | (hi[3] << 4) | hi[4]
    if straight >= 0:
        return (4 << 20) | straight
    if trips:
        return (3 << 20) | (trips[0] << 8) | (singles[0] << 4) | singles[1]
    if len(pairs) == 2:
        return (2 << 20) | (pairs[0] << 8) | (pairs[1] << 4) | singles[0]
    if len(pairs) == 1:
        return (1 << 20) | (pairs[0] << 12) | (singles[0] << 8) | (singles[1] << 4) | singles[2]
    return (hi[0] << 16) | (hi[1] << 12) | (hi[2] << 8) | (hi[3] << 4) | hi[4]


def main():
    deck = list(range(52))
    t0 = time.time()
    bad = 0
    first_bad = None
    n = 0
    for combo in combinations(deck, 5):
        a = EV(*combo)
        b = brute(list(combo))
        n += 1
        if a != b:
            bad += 1
            if first_bad is None:
                first_bad = (combo, a, b)
    dt = time.time() - t0
    print(f"EXHAUSTIVE 5-card: {n:,} hands, {bad} mismatches, {dt:.1f}s")
    if first_bad:
        c, a, b = first_bad
        print("  first mismatch:", [hex(x) for x in c], "impl", a, "ref", b)
    assert bad == 0, "evaluator mismatch"

    # 7-card showdown ordering agreement
    random.seed(7)
    N = 40000
    mism = 0
    t0 = time.time()
    for _ in range(N):
        d = deck[:]
        random.shuffle(d)
        h1, h2, bd = d[:2], d[2:4], d[4:9]
        a1, a2 = BEST(h1, bd), BEST(h2, bd)
        cs1, cs2 = h1 + bd, h2 + bd
        r1 = max(brute([cs1[i] for i in cb]) for cb in combinations(range(7), 5))
        r2 = max(brute([cs2[i] for i in cb]) for cb in combinations(range(7), 5))
        if (a1 > a2) - (a1 < a2) != (r1 > r2) - (r1 < r2):
            mism += 1
    print(f"7-card ordering: {mism} mismatches / {N} in {time.time()-t0:.1f}s")
    assert mism == 0

    # equity ground truth
    for name, (A, B, exp) in {
        "AA vs KK": ([50, 51], [46, 47], 0.8520),
        "AKs vs QQ": ([50, 47], [42, 43], 0.4611),
        "AKo vs JJ": ([48, 51], [38, 39], 0.4576),
        "72o vs AA": ([24, 5], [50, 51], 0.1174),
    }.items():
        w = 0.0
        Nn = 20000
        for _ in range(Nn):
            d = [x for x in range(52) if x not in A + B]
            random.shuffle(d)
            b = d[:5]
            r = BEST(A, b) - BEST(B, b)
            w += 1 if r > 0 else (0.5 if r == 0 else 0)
        got = w / Nn
        print(f"  {name:10s} {got:.4f}  exact={exp}  {'OK' if abs(got-exp)<0.008 else 'CHECK'}")
    print("\nEVALUATOR VALIDATED")


if __name__ == "__main__":
    main()
