# Remaining-work implementation report

## Delivered

The isolated proof-aware controller and integer-tick ledger are implemented. No published gameplay algorithm changed. The module computes its own current credit, consumes fresh action tokens, keeps pending check/call continuation through payout, and only then abandons later hands. It detects replay/conflict, altered cards/rules, missing calls, wrong prices, malformed payout/scoreboard and exceeded future-cost premises.

**87 tests passed: 53 CORA/guarantee + 34 v2.** The 53 include 12 mathematical guarantee and 18 new controller tests. Controller tests include 375 independent accounting cases and 480 bounded complete financial paths. The existing symbolic turn card check still covers 45,540 physical worlds.

## Constrained measurements

Both workers were pinned to one CPU with a 1-GiB address-space cap. Python audit hooks rejected runtime writes/network/process creation; neither worker attempted a forbidden operation. This is **not OS-level isolation evidence**. Execution was Python 3.13.16, not the required 3.11.

| Path | Arming | Selection median / p95 | Peak RSS | Whole child process |
|---|---:|---:|---:|---:|
| turn | 0.060 ms | 2.372 / 2.476 µs | 16.23 MiB | 0.093 s |
| river | 74.727 ms | 2.330 / 3.986 µs | 31.34 MiB | 0.177 s |

Each selection measurement is 10,000 reads of the **same unchanged validated state**, not 10,000 consecutive live actions. Whole-child time includes this microbenchmark and a synthetic four-hand ledger trace. The turn path loads no NumPy and does no runout enumeration. The cold river path loads NumPy and builds the physical-peer kernel. Neither selection path enumerates cards.

Both traces bank an actual ledger loss of −60, finish the guaranteed +70 current hand, then lose at most 3 and 5 in later hands: **final raw +2**. No arbitrary initial scoreboard injection is used. This does not imply that such a winning state can be forced from an initial deal.

Exact values, source SHA-256 identities, trace actions and scope are in `evidence/guarantee_lab/settlement_results.json`; full logs are adjacent. Times are measurements, not worst-case scheduler/traffic proofs.

## Maintenance closed

- v2 builder writes `releases/v2/rebuilt/bot.py`, leaving frozen runtime untouched; rebuilt bytes match the frozen SHA.
- v2 rebuilt package includes the newly generated rebuilt validation report, not the historical report; ZIP entry hashes and report inclusion were verified.
- v2 match, resource and exhaustive reruns write `evidence/v2/reruns/`; old fullmatch reruns use `evidence/legacy_bench/reruns/`.
- Match output filenames cannot traverse into historical paths. A negative-path test and a tiny relocated v2 match smoke passed.
- Frozen v2 runtime now has an explicit integrity pin in the workspace verifier.
- Original source/standalone/release ZIP integrity remains verified. Current grammar passes Python 3.11 parsing.
- Guarantee standalone test log was refreshed; current combined logs remain the full-suite authority.

## Still blocked or deliberately not claimed

1. Official modified game, score/cap, protocol, accepted-action and clock/lifecycle semantics are missing. We cannot validate an organizer adapter or submit an honest official-ready bot without them.
2. Actual Python 3.11 is absent in this workspace environment. Grammar parsing is not execution validation. No network/download/runtime installation was used.
3. OS-enforced read-only/network-isolated testing and official host time-bank behavior remain unverified.
4. This is a partial research overlay; full-policy integration, stronger adaptive-opponent tests and a new independent gameplay holdout have **not** been performed. Frozen CORA results are not new-controller strength evidence.
5. No universal strict initial-state victory, tournament qualification, globally novel research, or universal no-forfeit claim is made.

See [controller design and quantified scope](CONTROLLER.md), [remaining roadmap](ROADMAP.md), and [official gates](../RELEASE_GATES.md).
