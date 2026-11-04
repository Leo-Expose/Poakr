# Pokerbot v2 — measured validation, including regressions

## Verdict

A substantially safer, configurable engineering core is implemented and tested.
**It is not a perfected strategy or an official submission.** The final holdout
favored the preserved v1 in match wins; v2 had higher average chips. Do not replace
match-point evidence with a chip-profit story.

Official custom mechanics, protocol/lifecycle, fair-play interpretation, finals
bank and tie-break cap remain unknown. `docs/v2/READINESS.md` tracks every area explicitly.

## Frozen-release identity

`runtime/bot.py` SHA-256: `27c303582022e1320e3cad286021c93526c345819567cd6380052c113d522bbb`.

The final unit, resource, exhaustive-frequency and fresh-seed strategy checks use
this release. Older exploratory results are separate and not relabeled as release
evidence. The runtime uses stdlib + NumPy, with no source-package imports.

## Correctness and engineering tests

- **34/34 unittest cases passed**, including independent evaluator
  comparisons, configured variants, exact equity, collisions, public-terminal
  memory, malformed reveals, request replay/conflicts, match resets, watchdog
  restoration, depleted budgets, strict parsing and standalone read-only execution.
- Standard seven-card evaluator versus independent five-subset reference:
  **1,200 random hands, zero mismatches**.
- Generic configured evaluator versus independent reference:
  **800 hands across eight rule configurations, zero mismatches**.
- Exact known-hand flop, turn and river equity checked against independent
  enumeration. Also tested exact preflop equity in a small configured deck.
- **All 2,598,960 standard five-card combinations** reproduce the
  independently known category frequencies. This is frequency validation, not an
  exhaustive seven-card score/tiebreak differential proof.
- Resumable Monte Carlo retains its alpha-spending look count; exact-enumeration
  timeout cannot leak biased prefix equity.
- Python 3.11 grammar check passed. **Execution used Python 3.13.16**, not 3.11;
  the actual required interpreter remains a release gate.

## Constrained-runtime stress

A separate child process was pinned to one permitted CPU, given a **1 GiB virtual
address-space cap**, and denied network/process creation/file-write operations
via Python audit hooks. This is not an OS-level replica of the official sandbox.
Only one synthetic decision per street was requested; real request counts depend
on the variant and action history.

| Hands | Requests / legal responses | Wall time | Peak RSS | Per-decision deadline interruptions |
|---|---:|---:|---:|---:|
| 400 | 1600 / 1600 | 8.99s | 38.21 MiB | 2 |
| 1000 | 4000 / 4000 | 23.29s | 38.48 MiB | 150 |

Both runs used a 60-second configured bank and retained a 25% planned reserve.
No forbidden operation was attempted and no worker crashed. Deadline interruption
is not a match forfeit: completed Monte Carlo batches may support a decision;
otherwise a supplied legal fallback is selected. Some exact computations can be
abandoned. Accuracy/strength under every possible workload is not established.
Host waiting time and kill semantics still need verification. The 1,000-hand
stress uses 60 seconds conservatively; the announcement does not specify the
actual finals allowance.

## Final fresh-seed strategy holdout

Six matches per opponent, 60 duplicate pairs / 120 hands per match, deal seeds
53000–53005. Synthetic standard-Hold'em policies, not equilibrium opponents.
`v2_release_board` enables replay inference with proactive bluff/risk dial off;
**the default unconfigured adapter leaves replay inference off** until integration
checks authorize it.

| Opponent | Board-enabled v2 wins | v1 wins | v2 mean chips | v1 mean chips |
|---|---:|---:|---:|---:|
| OverFolder | 1/6 | 3/6 | -57.5 | -83.8 |
| CallingStation | 6/6 | 6/6 | +501.3 | +328.5 |
| Balanced | 4/6 | 4/6 | +202.7 | +47.4 |
| Aggressor | 5/6 | 5/6 | +392.5 | +59.5 |

**v2: 16/24 wins. v1: 18/24 wins.** These small samples do not establish
superiority in either direction. The over-folder is a clear unresolved policy
weakness, and v2 lost more matches to it on this holdout. Preserving the baseline
and reporting the regression is preferable to shipping an unsupported “upgrade.”

The benchmark drives `BotSession.act` through a chip-action adapter and feeds
public action histories, including actual capped bet sizing. It never feeds
unrevealed runout or opponent-hole cards into memory. It asserts legality. It
measures the decision core, **not the official wire protocol**. Reported own-compute
time excludes benchmark public-history reconstruction and transport overhead.
Timing-dependent sample caps mean repeated runs need not be bit-identical.

## Earlier exploratory v2 pilot — separate evidence

Seeds 43000–43005, six 60-pair matches per opponent:

- v2 with board inference and proactive bluff: **18/24 wins**.
- v2 with board inference, proactive bluff disabled: **18/24**.
- v2 without duplicate inference: **14/24**.
- Frozen v1 baseline: **16/24**.
- Duplicate-aware mirror: 4/6 wins, mean +236.5 chips, noisy six-match diagnostic.
  Both bots have isolated memory. This is not evidence of a universal advantage
  when both players track, nor proof that mirror bias is absent.

The proactive-bluff pilot did not add wins; it remains off by default. The risk
dial remains off based on its weak earlier evidence. The final seed set is not
silently combined with the exploratory pilot to create a more flattering result.

## Open strategy work

The random-opponent equity model is not a conditional opponent calling/betting
range. Selective betting, trap-heavy behavior, adaptive opponents, future betting,
match-risk utility and the actual capped chip tie-break remain unresolved. No
finite synthetic suite proves optimal poker play. Bigger independent holdouts and
actual-variant tests are required before strategy selection.

## Reproduce

```bash
python3 bench/build_release.py
python3 -m unittest discover -s tests -v
python3 bench/exhaustive_v2.py
python3 bench/resource_v2.py
python3 bench/matches_v2.py --matches 6 --deals 60 --seed 53000 \
  --release-check --no-mirror --output release_matches_results.json
python3 bench/package_v2.py
```

See `docs/v2/PROTOCOL_EXAMPLE.md` for fixtures and `docs/v2/READINESS.md` for the complete audit.
The release contains both the v2 integration candidate and the preserved v1.
No claims of guaranteed wins, universal no-forfeit safety, organizer approval,
research novelty or “everything perfected” are made.
