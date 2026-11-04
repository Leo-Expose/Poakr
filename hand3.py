#!/usr/bin/env python3
"""
Complete 3-card hand categorization and analysis for Discard Hold'em.
Proper hand types, equity clusters, and strategic properties.
"""
import itertools
import os
import json
import numpy as np
from eval7 import equity_vs_range, parse_card, card_str


# All cards
ALL_CARDS = [r * 4 + s for r in range(13) for s in range(4)]
RANKS = "23456789TJQKA"
SUITS = "shdc"


def hand_type_3card(hole):
    """
    Classify a 3-card hand into strategic type.
    Returns: (type_name, strength_score, details_dict)
    """
    ranks = sorted([c // 4 for c in hole], reverse=True)
    suits = [c % 4 for c in hole]
    rank_str = "".join(RANKS[r] for r in ranks)
    
    # Count ranks
    from collections import Counter
    rc = Counter(ranks)
    sc = Counter(suits)
    
    # Three of a kind
    if 3 in rc.values():
        trip_rank = max(r for r, c in rc.items() if c == 3)
        return ("trips", 1000 + trip_rank, {"trip_rank": trip_rank})
    
    # Pair
    if 2 in rc.values():
        pair_rank = max(r for r, c in rc.items() if c == 2)
        kicker = max(r for r, c in rc.items() if c == 1)
        suited = 1 if len(sc) == 2 else 0  # Pair + suited kicker
        return ("pair", 500 + pair_rank * 13 + kicker + suited * 0.5, 
                {"pair_rank": pair_rank, "kicker": kicker, "suited": suited})
    
    # Three suited (flush draw)
    if len(sc) == 1:
        return ("flush_draw", 300 + ranks[0] * 13 + ranks[1],
                {"high": ranks[0], "mid": ranks[1], "low": ranks[2]})
    
    # Straight draws
    gaps = [ranks[i] - ranks[i+1] for i in range(2)]
    max_gap = max(gaps)
    min_gap = min(gaps)
    is_connected = max_gap <= 3
    is_1gap = max_gap <= 2 and min_gap <= 1
    is_2gap = max_gap <= 3 and min_gap <= 2
    
    # Broadway potential
    broadway_count = sum(1 for r in ranks if r >= 8)
    
    if is_connected:
        straight_type = "open_ended" if gaps == [1, 1] else "one_gap" if 2 in gaps else "two_gap"
        return (f"straight_draw_{straight_type}", 200 + ranks[0] * 13 + ranks[1] + broadway_count * 5,
                {"high": ranks[0], "type": straight_type, "broadway": broadway_count})
    
    # Two suited
    if len(sc) == 2:
        suited_ranks = []
        for s, cnt in sc.items():
            if cnt == 2:
                suited_ranks = sorted([r for r, s2 in zip(ranks, suits) if s2 == s], reverse=True)
        return ("two_suited", 100 + (suited_ranks[0] * 13 + suited_ranks[1]) if suited_ranks else 0,
                {"high": ranks[0], "suited_high": suited_ranks[0] if suited_ranks else ranks[0],
                 "suited_low": suited_ranks[1] if suited_ranks else ranks[1]})
    
    # High card
    return ("high_card", ranks[0] * 13 + ranks[1],
            {"high": ranks[0], "mid": ranks[1], "low": ranks[2], "broadway": broadway_count})


def hand_type_2card(hole):
    """Classify 2-card hand (post-discard)."""
    ranks = sorted([c // 4 for c in hole], reverse=True)
    suited = hole[0] % 4 == hole[1] % 4
    gap = ranks[0] - ranks[1]
    
    if ranks[0] == ranks[1]:
        return ("pair", 1000 + ranks[0], {"pair_rank": ranks[0]})
    if suited and gap <= 3:
        return ("suited_connector", 500 + ranks[0] * 13 + ranks[1], {"high": ranks[0], "gap": gap})
    if suited:
        return ("suited", 300 + ranks[0] * 13 + ranks[1], {"high": ranks[0], "low": ranks[1]})
    if gap <= 3:
        return ("connector", 200 + ranks[0] * 13 + ranks[1], {"high": ranks[0], "gap": gap})
    if ranks[0] >= 10:  # T+
        return ("broadway", 150 + ranks[0] * 13 + ranks[1], {"high": ranks[0], "low": ranks[1]})
    return ("high_card", ranks[0] * 13 + ranks[1], {"high": ranks[0], "low": ranks[1]})


def get_hand_type_bucket(hole):
    """Map 3-card hand to strategic bucket for CFR strategy lookup."""
    htype, hstrength, details = hand_type_3card(hole)
    ranks = sorted([c // 4 for c in hole], reverse=True)
    
    if htype == 'trips':
        return 'trips'
    elif htype == 'pair':
        pair_rank = details['pair_rank']
        if pair_rank >= 10:  # T+
            return 'pair_premium'
        elif pair_rank >= 7:
            return 'pair_high'
        return 'pair_mid'
    elif htype == 'flush_draw':
        if ranks[0] >= 10:
            return 'flush_draw_broadway'
        return 'flush_draw_other'
    elif htype.startswith('straight_draw'):
        return htype
    elif htype == 'two_suited':
        if ranks[0] >= 10:
            return 'two_suited_broadway'
        return 'two_suited_other'
    else:
        if ranks[0] >= 10:
            return 'high_card_broadway'
        return 'high_card_other'


def best_discard_for_type(hole):
    """
    Given a 3-card hand, determine optimal discard for each hand type.
    Returns dict of {discard_idx: (kept_type, kept_strength, discard_rank, discard_suit)}
    """
    results = {}
    for i in range(3):
        kept = [hole[j] for j in range(3) if j != i]
        ktype, kstrength, kdetails = hand_type_2card(kept)
        discarded = hole[i]
        results[i] = {
            "kept_type": ktype,
            "kept_strength": kstrength,
            "details": kdetails,
            "discarded_rank": discarded // 4,
            "discarded_suit": discarded % 4
        }
    return results


def preflop_equity_cluster(hole, n_draws=1000):
    """
    Compute equity for each discard option, return best.
    Also returns equity distribution across discard options.
    """
    equities = {}
    for i in range(3):
        kept = [hole[j] for j in range(3) if j != i]
        eq = equity_vs_range(kept, [], n_draws=n_draws, 
                           seed=hash(tuple(sorted(kept))) & 0xFFFFFFFF)
        equities[i] = eq
    
    best_idx = max(equities, key=equities.get)
    return equities[best_idx], equities, best_idx


def compute_hand3_cluster_equities():
    """
    Group all 3-card hands by type and compute average equity per cluster.
    """
    clusters = {}
    all_hands = list(itertools.combinations(ALL_CARDS, 3))
    
    for hole in all_hands:
        htype, hstrength, hdetails = hand_type_3card(hole)
        if htype not in clusters:
            clusters[htype] = []
        # Get best equity
        best_eq, _, _ = preflop_equity_cluster(hole, n_draws=500)
        clusters[htype].append(best_eq)
    
    # Compute stats
    stats = {}
    for htype, eqs in clusters.items():
        stats[htype] = {
            "count": len(eqs),
            "mean_eq": np.mean(eqs),
            "std_eq": np.std(eqs),
            "min_eq": np.min(eqs),
            "max_eq": np.max(eqs),
            "median_eq": np.median(eqs)
        }
    
    return stats


# Precomputed cluster stats - loaded from file if available
CLUSTER_STATS = {}
_cluster_stats_path = os.path.join(os.path.dirname(__file__), 'cluster_stats.json')
if os.path.exists(_cluster_stats_path):
    with open(_cluster_stats_path, 'r') as f:
        CLUSTER_STATS = json.load(f)
    print(f"Loaded {len(CLUSTER_STATS)} hand type clusters", file=__import__('sys').stderr)
else:
    # Fallback defaults
    CLUSTER_STATS = {
        "trips": {"mean_eq": 0.85, "std_eq": 0.05},
        "pair": {"mean_eq": 0.62, "std_eq": 0.08},
        "flush_draw": {"mean_eq": 0.56, "std_eq": 0.06},
        "straight_draw_open_ended": {"mean_eq": 0.58, "std_eq": 0.07},
        "straight_draw_one_gap": {"mean_eq": 0.52, "std_eq": 0.07},
        "straight_draw_two_gap": {"mean_eq": 0.48, "std_eq": 0.08},
        "two_suited": {"mean_eq": 0.45, "std_eq": 0.06},
        "high_card": {"mean_eq": 0.38, "std_eq": 0.07}
    }


def get_cluster_threshold(htype, percentile=0.5):
    """Get equity threshold for a hand type at given percentile."""
    if htype not in CLUSTER_STATS:
        return 0.5
    stats = CLUSTER_STATS[htype]
    # Approximate percentile from normal distribution
    from scipy import stats as scipy_stats
    z = scipy_stats.norm.ppf(percentile)
    return stats['mean_eq'] + z * stats['std_eq']


# Export cluster stats for strategy
def get_cluster_threshold(htype, percentile=0.5):
    """Get equity threshold for a hand type at given percentile."""
    if CLUSTER_STATS is None:
        init_cluster_stats()
    if htype not in CLUSTER_STATS:
        return 0.5
    stats = CLUSTER_STATS[htype]
    # Approximate percentile from normal distribution
    from scipy import stats as scipy_stats
    z = scipy_stats.norm.ppf(percentile)
    return stats['mean_eq'] + z * stats['std_eq']


# Hand type hierarchy for strategy
HAND_TYPE_ORDER = [
    "trips",
    "pair",
    "flush_draw",
    "straight_draw_open_ended",
    "straight_draw_one_gap",
    "straight_draw_two_gap",
    "two_suited",
    "high_card"
]

HAND_TYPE_RANK = {ht: i for i, ht in enumerate(HAND_TYPE_ORDER)}


def compare_hand_types(ht1, ht2):
    """Compare two hand types (-1 if ht1 < ht2, 0 if equal, 1 if ht1 > ht2)."""
    return (HAND_TYPE_RANK.get(ht1, 99) > HAND_TYPE_RANK.get(ht2, 99)) - \
           (HAND_TYPE_RANK.get(ht1, 99) < HAND_TYPE_RANK.get(ht2, 99))


if __name__ == '__main__':
    # Test
    test_hands = [
        [parse_card(c) for c in ["As", "Ah", "Ad"]],  # Trips
        [parse_card(c) for c in ["As", "Ah", "Kd"]],  # Pair
        [parse_card(c) for c in ["As", "Ks", "Qs"]],  # Flush draw
        [parse_card(c) for c in ["Ts", "9s", "8h"]],  # Straight draw
        [parse_card(c) for c in ["As", "Kd", "Qh"]],  # Two suited
        [parse_card(c) for c in ["As", "7d", "2h"]],  # High card
    ]
    
    for hole in test_hands:
        htype, hstrength, hdetails = hand_type_3card(hole)
        print(f"{' '.join(card_str(c) for c in hole)}: {htype} (strength={hstrength})")
        discards = best_discard_for_type(hole)
        for i, d in discards.items():
            print(f"  Discard {card_str(hole[i])} -> keep {d['kept_type']} ({d['kept_strength']})")
        best_eq, all_eq, best_idx = preflop_equity_cluster(hole, n_draws=1000)
        print(f"  Equities: {all_eq}, best: discard {best_idx} ({best_eq:.4f})")
        print()