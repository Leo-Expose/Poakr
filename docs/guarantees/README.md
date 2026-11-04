# Toward rigorous poker guarantees

> Update, 31 October: the supplied PDFs now specify Discard Hold’em. This page describes the earlier isolated lab. See [actual-game candidate](../discard/REPORT.md) and [PDF reconciliation](../organizer/RULES_RECONCILIATION.md). Its per-hand clipping contract is NOT the official match-level tie-break.


## The goal, stated precisely

We want cheap, auditable certificates that hold against **every opponent policy and every physically legal opposing holding/chance outcome**, inside a stated rule/state class. No finite-policy belief approximation is allowed to quietly substitute for that universal quantifier.

We distinguish:

1. **Numerical/representation correctness:** exact card geometry and a lossless represented quotient.
2. **Expected-value protection:** minimax against a class of opponents, averaged over the specified chance distribution.
3. **Pointwise score guarantee:** a stated continuation secures a score threshold on every allowed completion.
4. **Execution guarantee:** the process finishes legally within the real clock.
5. **Tournament victory:** qualification/final ranking, including tie-breaks and other matches.

A result at one level does not establish the next. The existing win lock is level 3 conditional on level 4 and its scoring/posting premises; it is not level 5.

## New implemented work

### A. Exact heterogeneous-cost certificate

`research/guarantee_lab/certificates.py` prepares future forced-cost suffix sums once, then answers rational-bound queries in constant time. It supports known upper bounds on changing blinds/antes/mandatory losses, rather than assuming every later hand costs the same big blind.

For completed score B, current paid C, and future per-hand loss bounds F_i:

```
raw lower bound = B − C − Σ F_i
```

For the **specifically defined** score `sum(clip(hand_net, −K, K))`:

```
capped lower bound = completed capped score − min(C,K) − Σ min(F_i,K)
```

The capped formula cannot use raw banked profit and is not a guess about the organizer's undisclosed chip tie-break. Both use exact rational arithmetic and a strict positive comparison (or another explicitly supplied threshold).

### B. Safe current-river settlement credit

`research/guarantee_lab/river_credit.py` examines **all 990 physically legal opposing pairs** in the standard final-board examples, not just posterior support.

Under final-board, correct-ranking, no-fee, equal-initial-stack, standard matched-payout/refund, and check/call-settlement premises:

- If the hero can tie but cannot lose to any legal pair, checking/calling through settlement guarantees current-hand net **at least zero**.
- If the hero strictly beats every legal pair, it guarantees at least the opponent's **already-paid contribution D**.

Then:

```
new raw lower bound = B + guaranteed current-hand net − Σ F_i
```

This can certify states the fold-based bound cannot. Verified examples:

| State | Old bound | New bound |
|---|---:|---:|
| Shared royal-flush board; B=10, C=50, future costs 3+5 | −48 | **+2** |
| Unique royal flush; B=−60, opponent already paid 70, future costs 3+5 | not a winning abandonment state | **+2** |

The second example certifies a comeback even before banked completed-hand net becomes positive.

**Required two-stage plan:** check/call through the current settlement, then free check/fold in later hands. Immediately folding the current hand would destroy the credit. This is deliberately **not wired into CORA's existing immediate-lock branch**.

### C. Constant-size symbolic turn proof

`research/guarantee_lab/turn_credit.py` identifies dominating quads on a **rainbow turn** under standard 52-card high-poker rules. The hero's pair and board pair exhaust rank R; both other public ranks must be lower than R.

No matter what the one remaining board card or opposing two cards are:

- the final board can contain at most two cards of one suit, so an opponent cannot make a flush/straight flush with two hole cards;
- no higher rank is already on the turn, so one river plus two opposing cards cannot create higher quads;
- all lower categories and lower quads lose to the hero.

The production research predicate does **not enumerate runouts**. Its example is `9c 9d` on `9h 9s 2c 3d`. Tests independently enumerate **1035 opposing pairs × 44 runouts = 45,540 physical worlds**, and every comparison strictly favors the hero. The same −60 banked / +70 guaranteed current / −8 future bound yields **+2**, now before the river is known.

It requires check/call through **turn and river settlement**, no rake/fees, correct standard ranking, equal-stack matching, standard matched-payout/refund semantics, and verified clock completion. It is not a proof for extra-board-card/wildcard/changed-category variants and is not integrated into the frozen bot.

### D. Exact minimax laboratory and impossibility witnesses

`research/guarantee_lab/kuhn.py` builds a three-card, one-bet poker game with 64 complete causal policies per player and six equally likely deals. Policy actions depend only on the player's own card and public history. There is no hidden-card peek or strategy fusion.

The lab enumerates **24,576 policy/deal payoffs**, solves primal and dual LPs using SciPy, reconstructs their strategies as rational probabilities, then verifies **every constraint with exact Fraction arithmetic**:

```
first-player minimax expected value = −1/18
primal/dual gap = 0 exactly
```

This value is for the toy game, not modified Hold'em.

There is also a concrete legal fixed-policy world where every first-player policy loses at least the ante. In a second witness, the same low/high deal is played twice with cards and seats swapped. The opponent uses the same own-card-only policy in both roles: bet/call the highest card, check/fold otherwise. Across **4096 independently chosen own policy pairs**, the best total is **zero**, not a strict win. Allowing separate policies in the two copies is more powerful than requiring one fixed policy, so this upper bound also covers such a fixed controller on this witness.

It proves that a promise to strictly win **every poker/duplicate-poker world** is false. It does not compute the value of the organizer's undisclosed game. More generally, an all-opponent/all-seat strict-win claim in a symmetric zero-sum game cannot hold for both opposing instances of the claimed strategy.

## Current evidence

`evidence/guarantee_lab/results.json` and `run.log` hold exact distributions, witnesses, example bounds, and scope. The final lab run took **0.414 seconds**, peak **77.96 MiB**, with one CPU and a 1-GiB address-space limit. This is an offline proof lab, not candidate runtime latency.

- **12 mathematical guarantee tests + 18 settlement-controller tests passed**, including exhaustive small adversarial returns, invalid/missing premises, cap semantics, exact minimax constraints, all-physical-peer river examples, and unsafe states.
- Combined CORA + guarantee suite: **53 tests passed**.
- Reorganized v2 suite: **34 tests passed**.
- The frozen CORA policy and its published benchmark scores have not changed.

## What remains unknown

Contracts in these modules are assertions for a verified adapter, not self-certifying facts. A caller lying about scoring, fees, ranking, legality, or clock survival invalidates the guarantee. Safe credits must be generated from trusted current own/public state, checked for hand/board/rule freshness, and never accepted as an unverified wire claim.

Official modified rules, scoring/cap semantics, clock/lifecycle, Python 3.11 execution, and larger adaptive-opponent tests remain release gates. The new certificates have not undergone official-protocol or tournament validation.

Implemented: [proof-aware settlement controller](CONTROLLER.md) / [implementation report](IMPLEMENTATION_REPORT.md).

Next: [proofs](THEOREMS.md), [roadmap](ROADMAP.md), [release gates](../RELEASE_GATES.md).
