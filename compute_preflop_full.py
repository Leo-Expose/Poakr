#!/usr/bin/env python3
"""
Precompute preflop equity for ALL 3-card hands in Discard Hold'em.
"""
import itertools
import numpy as np
import json
from eval7 import equity_vs_range

# All 52 cards
ALL_CARDS = [r * 4 + s for r in range(13) for s in range(4)]

# Generate all unique 3-card combinations (22,100)
all_3card_hands = list(itertools.combinations(ALL_CARDS, 3))
print(f"Total 3-card hands: {len(all_3card_hands)}")

def hand_str(hole):
    ranks = "23456789TJQKA"
    suits = "shdc"
    return " ".join(f"{ranks[c//4]}{suits[c%4]}" for c in hole)

results = {}
batch_size = 100

for batch_start in range(0, len(all_3card_hands), batch_size):
    batch = all_3card_hands[batch_start:batch_start + batch_size]
    
    for hole in batch:
        # For each possible discard, compute equity vs random 2-card hand
        best_eq = 0.0
        for discard_idx in range(3):
            kept = [hole[j] for j in range(3) if j != discard_idx]
            eq = equity_vs_range(kept, [], n_draws=300, seed=hash(tuple(sorted(kept))) & 0xFFFFFFFF)
            if eq > best_eq:
                best_eq = eq
        
        results[tuple(sorted(hole))] = best_eq
    
    if batch_start % 2000 == 0:
        print(f"  Processed {batch_start + len(batch)}/{len(all_3card_hands)}")

# Save full table
output = {hand_str(hole): eq for hole, eq in results.items()}
with open('/home/leo/Documents/Poker/pokerbot/preflop_3card_equity_full.json', 'w') as f:
    json.dump(output, f)

print("\nDone! Saved full table.")
print(f"Total hands: {len(results)}")

# Print statistics
eqs = list(results.values())
print(f"Min equity: {min(eqs):.4f}")
print(f"Max equity: {max(eqs):.4f}")
print(f"Mean equity: {np.mean(eqs):.4f}")
print(f"Median equity: {np.median(eqs):.4f}")

# Top/bottom
sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
print("\nTop 10:")
for hole, eq in sorted_results[:10]:
    print(f"  {hand_str(hole)}: {eq:.4f}")

print("\nBottom 10:")
for hole, eq in sorted_results[-10:]:
    print(f"  {hand_str(hole)}: {eq:.4f}")