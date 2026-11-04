#!/usr/bin/env python3
"""
Precompute and save cluster statistics for 3-card hands.
Run once, then import the saved stats.
"""
import itertools
import numpy as np
import json
from eval7 import equity_vs_range
from hand3 import hand_type_3card, preflop_equity_cluster


ALL_CARDS = [r * 4 + s for r in range(13) for s in range(4)]
all_hands = list(itertools.combinations(ALL_CARDS, 3))

print(f"Computing cluster stats for {len(all_hands)} hands...")

clusters = {}
for i, hole in enumerate(all_hands):
    htype, hstrength, hdetails = hand_type_3card(hole)
    if htype not in clusters:
        clusters[htype] = []
    best_eq, _, _ = preflop_equity_cluster(hole, n_draws=300)
    clusters[htype].append(best_eq)
    
    if i % 5000 == 0:
        print(f"  {i}/{len(all_hands)}")

stats = {}
for htype, eqs in clusters.items():
    stats[htype] = {
        "count": len(eqs),
        "mean_eq": float(np.mean(eqs)),
        "std_eq": float(np.std(eqs)),
        "min_eq": float(np.min(eqs)),
        "max_eq": float(np.max(eqs)),
        "median_eq": float(np.median(eqs))
    }
    print(f"  {htype}: {stats[htype]['count']} hands, mean_eq={stats[htype]['mean_eq']:.4f}")

with open('/home/leo/Documents/Poker/pokerbot/cluster_stats.json', 'w') as f:
    json.dump(stats, f)

print("Saved cluster_stats.json")