# Proof-aware settlement controller — research v1

## Status and quantified scope

Implemented in `research/guarantee_lab/settlement.py`. This is a **separate reference overlay**, not a full poker strategy, an organizer adapter, or a replacement for the frozen CORA/v2 bots. It accepts no wire-supplied guarantee, score balance, or credit object. It generates its own credit from trusted current own/public cards and an independently accumulated contribution ledger.

The scope is a finite, heads-up standard 52-card high game with two private cards per player, equal fixed hand-start stacks, integer money ticks, matched-stake payouts and uncalled refunds, no rake/fees, verified future forced-cost bounds, verified free abandonment, and successful legal execution without forfeit. The optional score is specifically the sum of symmetrically clipped per-hand net, not an assumed organizer formula. Every contract is a **trusted adapter assertion**, not a fact established by this module.

## State machine

| State | Behavior |
|---|---|
| `WATCH` | No certificate active; `choose()` returns `None` for an ordinary policy. |
| `SETTLE_SAFE_HAND` | Never fold or raise. Check when free; call the exact ledger-derived price otherwise. The turn proof remains pending through the river. |
| `ABANDON` | Check when free, otherwise fold. Recompute the exact remaining-loss margin and verify subsequent forced contributions fit the schedule. |
| `DONE` | All scheduled hands have settled. A certified run retains a positive validated final margin. An unarmed run makes no victory claim. |
| `INVALID` | Remove the certificate and raise `UnsafeState`. Do not substitute an unsafe fold for a pending settlement. A real adapter must catch/reconcile this state; this is not a no-crash/forfeit guarantee. |

`try_arm()` first tests the ordinary current-paid abandonment bound. If that is already positive, immediate abandonment is valid. Otherwise it tests safe turn/river settlement credit. A settlement credit never authorizes an immediate fold. Switching from settlement to abandonment requires a validated terminal payout, not just an action response, a river reveal, or a claimed win.

## Ledger and trust boundary

`TickLedger` starts with zero banked score and derives both raw and clipped score from terminal payouts. There is no API for injecting a banked −60/+100 claim. The tests create those balances through earlier paid actions and verified payouts.

- All amounts are nonnegative built-in integer ticks; floating values, booleans and negative payments are rejected.
- Each hand resets to the same configured stack. Payments cannot exceed that stack.
- Hand IDs are fresh, at most 128 characters, and the match has a fixed hand count.
- Match-wide event sequences must be exactly the next ledger revision. Replays, skipped events and different-hand events are rejected atomically.
- Own cards are fixed; the board only extends known cards, with no collisions. Card inputs are bounded lists/tuples.
- Terminal payout lists contain exactly two values. They must match the stated result and conserve the total contribution pool.
- Optional host raw/clipped scoreboards must equal the independently accumulated score before settlement can commit.
- Separate intermediate refunds are **not supported**. They belong in terminal payouts. Side pots, unequal stacks, unrefundable dead-money conventions, rake and different payoff formulas require a different verified adapter/model.

The host/adapter still supplies the truth of actual accepted actions, terminal results, card visibility, action availability, and rules. Accounting checks cannot prove an honest host, authenticate a message, or infer hidden cards. Python private attributes/frozen dataclasses are not a security boundary against hostile in-process code.

## Binding and action lifecycle

A `Request` binds the hand ID, ledger revision, rule version, own holding, current board, call price and normalized legal actions. It must be constructed from verified adapter facts, **not passed straight from an arbitrary JSON message**. The call price must equal the contribution difference. A `Decision` can only be confirmed if it still equals the freshly computed decision for that exact request.

A confirmed own action consumes its decision point. Another selection requires a new trusted public event. Old tokens expire after calls, checks, card reveals, payments and new hands. Changing rule configuration requires a new verified controller; an armed controller does not silently carry its proof into different rules.

`confirm()` is called **only after the host accepts the exact action**. It does not perform I/O. A failed or ambiguous write must be reconciled with host state rather than guessed into the ledger. Opponent payments, public board extensions and terminal events likewise enter only through trusted local adapter code.

`choose(..., deadline_recovery=True)` uses the same check/call or abandonment selection. It performs no card enumeration. It is not a timer, OS scheduling bound, transport implementation, or promise to finish within an unspecified host time bank.

## Composition argument

Let completed score be B, the current safe-hand minimum net be G, and the verified future abandonment cost bounds be F_i. Before arming, require `B + G − sum(F_i) > threshold`, using exact arithmetic and the correct raw/clipped scoreboard.

1. The current card proof covers every physical opposing holding, and for the supported turn pattern every river.
2. Check/call continuation under equal-stack matched/refunded payouts realizes current net at least G. Accepted payout is checked against this minimum and the applicable result/board/contribution conditions.
3. Only after that payout does the controller enter abandonment. Every later hand loses at most its actual forced contribution, bounded by F_i; free checks and opponent folds cannot worsen that bound.
4. Each legal settlement preserves the suffix-bound invariant. At match completion the suffix is zero and the actual computed score exceeds the threshold.

For the clipped contract, monotonic clipping gives current score at least `min(G,K)` and later losses at most `min(F_i,K)`. Raw and clipped B are separate accumulators. The source uses the existing exact `BoundSchedule` for these expressions. O(1) queries mean a constant count of arithmetic operations; integer/rational bit cost depends on configured money magnitudes.

This is conditional on the actual rule/adapter/clock premises continuing to hold. Detecting a premise violation withdraws the claim; it does not retroactively prove the earlier premise true or guarantee a safe response under an unknown protocol.

## Test scope

`tests/cora/test_settlement.py` has **18 tests**, in addition to the 12 existing mathematical guarantee tests.

- **375** independent accounting cases: contributions 0..4 × contributions 0..4 × five terminal result types × three cap modes. These cover ties, matched transfers, folds and uncalled refunds; they are accounting cases, not claims that every arbitrary contribution/result tuple is a legally reached game state.
- All five integer opponent river bet sizes in a residual-stack-4 betting round. With a check/call hero, the opponent checks or bets, the hero responds, and the round closes.
- **480 complete synthetic financial paths**: five river sizes × four future-post sizes × six later-post sizes × four optional-check/fold paths. Independent score oracle gives final raw `−60 + (70 + bet) − post2 − post3 >= 2`.
- The initial −60 deficit is derived from an earlier real ledger loss, not injected as a score claim.
- Pending-hand no-fold behavior, deadline recovery, river shared-royal ties, peer folds, immediate locks, cap/raw differences, altered decisions, request replay, missing calls, price mismatches, rule changes, payout errors, omitted river, skipped controller settlement and exceeded future costs.
- The separate card test still exhausts **45,540** opposing-pair/river worlds for the supported turn example.

These are bounded prototype tests, not exhaustive full Hold’em strategy trees or organizer-protocol tests. No new full-policy strength/holdout result is claimed.

## Reproduce

From the project root with dependencies already present:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/cora -p 'test_settlement.py' -v
python3 tools/cora/settlement_bench.py
python3 tools/maintenance/verify_workspace.py
```

See [implementation report](IMPLEMENTATION_REPORT.md), [theorems](THEOREMS.md), and [release gates](../RELEASE_GATES.md). Actual Python 3.11 execution and OS-enforced sandbox/official protocol validation remain open.
