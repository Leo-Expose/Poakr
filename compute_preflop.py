#!/usr/bin/env python3
"""
Precompute preflop equity for all 3-card hands in Discard Hold'em.
Each hand is evaluated assuming both players discard optimally after flop.
This runs offline and generates a lookup table for the bot.
"""
import itertools
import numpy as np
from eval7 import equity_vs_range, parse_card

# All 52 cards
ALL_CARDS = [r * 4 + s for r in range(13) for s in range(4)]

# Generate all unique 3-card combinations (22,100)
all_3card_hands = list(itertools.combinations(ALL_CARDS, 3))
print(f"Total 3-card hands: {len(all_3card_hands)}")

# For each 3-card hand, compute equity vs random 3-card hand
# This is expensive, so we'll do a sample first
results = {}

def hand_str(hole):
    ranks = "23456789TJQKA"
    suits = "shdc"
    return " ".join(f"{ranks[c//4]}{suits[c%4]}" for c in hole)

# First, let's compute for a representative sample
sample_size = 1000
sample_indices = np.random.choice(len(all_3card_hands), sample_size, replace=False)

print("Computing sample equities...")
for i, idx in enumerate(sample_indices):
    hole = all_3card_hands[idx]
    
    # For each possible discard, compute equity vs random 2-card hand
    best_eq = 0.0
    for discard_idx in range(3):
        kept = [hole[j] for j in range(3) if j != discard_idx]
        eq = equity_vs_range(kept, [], n_draws=500, seed=hash(tuple(sorted(kept))) & 0xFFFFFFFF)
        if eq > best_eq:
            best_eq = eq
    
    results[hole] = best_eq
    
    if i % 100 == 0:
        print(f"  {i}/{sample_size} - {hand_str(hole)}: {best_eq:.4f}")

# Sort by equity
sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)

print("\nTop 20 3-card hands:")
for hole, eq in sorted_results[:20]:
    print(f"  {hand_str(hole)}: {eq:.4f}")

print("\nBottom 20 3-card hands:")
for hole, eq in sorted_results[-20:]:
    print(f"  {hand_str(hole)}: {eq:.4f}")

# Save to file
import json
output = {
    hand_str(hole): eq for hole, eq in results.items()
}
with open('/home/leo/Documents/Poker/pokerbot/preflop_3card_equity.json', 'w') as f:
    json.dump(output, f)

print("\nSaved sample to preflop_3card_equity.json")