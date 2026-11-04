# CORA — tested low-compute architecture, not a universal poker guarantee

**Status:** research candidate and self-contained **EXAMPLE-protocol** prototype. Previous v2 remains frozen. This is not yet an official competition submission.

## Executive result

The corrected architecture won **47 of 48** fresh-seed synthetic matches, versus **45/48** for duplicate-aware v2, **43/48** for duplicate-aware v1, and **38/48** for v2 without duplicate inference. CORA used **27.976 seconds of measured bot compute** over those 48 matches—**4.29× less than duplicate-aware v2**, **4.42× less than duplicate-disabled v2**, and about **22% less than v1**.

One CORA match still lost: OverFolder, seed index 3, **−19 chips**. There is no claim that we cannot lose every game. All **47 matches reaching the conditional win certificate finished positive**.

The strongest previous reference lost only three matches. CORA's two-win advantage is too small to establish general strategic superiority. The hard numerical claims are the measured resource reduction, exact combinatorial/representation results, and observed benchmark scores—not a tournament win probability.

One-time preflop table generation took **18.182 seconds** offline. Adding that once to CORA's measured 48-match processing gives **46.158 seconds**: still below v2-info's 119.993 seconds, but above v1's 35.759 seconds. The 22% advantage over v1 is an **online processing** result, not a lower-total-compute claim including cold preprocessing for this short batch. Offline work is not hidden.

## What changed fundamentally

The previous controller primarily estimated a scalar equity against a largely uniform opposing range. CORA builds a shared **payoff-and-action algebra**:

1. **Blocker-incidence river geometry:** score every possible two-card holding once, then compute every holding's exact disjoint-opponent percentile using card-incidence histograms and inclusion–exclusion. No quadratic candidate–opponent matrix.
2. **Public-action range inference:** retain a joint belief over possible opposing cards and 144 policy types. Public bets/checks/calls/folds and public win/tie/loss results supply evidence. No actual opposing hole cards are consumed.
3. **Exact behavioral quotient:** merge possible holdings only when their implemented action likelihoods and represented payoffs are identical. This reduces the state space without changing the modeled answer.
4. **Conditional match-point lock:** stop voluntary payments when the worst-case remaining forced cost cannot erase a positive raw-net lead. This converts an already provable match point into a cheap check/fold continuation.
5. **Sampled preflop amortization:** use an embedded 169-class table rather than repeat the same preflop sampling online. This is conventional amortization, not a novelty claim.

These are linked changes to representation, evidence processing, and terminal utility—not merely a larger rollout budget. Flop/turn sampling, an early-street selectivity adjustment, and one-response river valuation remain approximations. The early-street cap is 16 ms versus the v2 reference's 25 ms; table, deadline, and RNG-path differences mean the match results do not isolate every mathematical component's causal contribution. Speed-only exploration scored 13/24 versus v2's 15/24: making the old path cheaper alone did not improve wins.

**Novelty limit:** this is a new architecture in this project. Inclusion–exclusion, Bayesian conditioning, exact aggregation, and stopping certificates are established tools. Because the work was workspace-only, global originality has not been verified.

## Corrected frozen confirmation

- Seed block: **121000–121007**.
- Six synthetic families: OverFolder, CallingStation, Balanced, Aggressor, SelectiveBluffer, Trapper.
- Eight matches per family per configuration.
- **50 duplicate deals / 100 hands per strategic match**, swapped seats.
- Five configurations: **240 matches / 24,000 hands total**.
- Candidate policy/kernel/table/runtime hashes were frozen before launch and still match the final research sources.
- No strategy parameters were tuned on this confirmation.
- These are **100-hand strategic tests, not the official 400/1000-hand formats**. Longer-format execution is tested separately below.

| Configuration | Wins | Losses | Bot compute, s | Mean raw net/match | Recovered internal deadlines |
|---|---:|---:|---:|---:|---:|
| v1, duplicate inference enabled | 43 | 5 | 35.759 | 219.33 | 0 |
| v2, duplicate inference enabled | 45 | 3 | 119.993 | 337.77 | 135 |
| v2, duplicate inference disabled | 38 | 10 | 123.686 | 148.31 | 60 |
| CORA posterior alone | **47** | 1 | 78.379 | **397.48** | 458 |
| CORA full chain | **47** | 1 | **27.976** | 133.67 | 96 |

“Posterior alone” uses the cheap preflop/early path and corrected river inference, but not the early-street selectivity penalty or win lock. Thus the new range representation does not require the lock to obtain the observed win score. The full chain did **not** add wins over posterior alone on this seed block; it used **2.80× less compute** and reached 47 certificates.

### Family-level scores

| Opponent | v1 info | v2 info | v2 off | Posterior | Full |
|---|---:|---:|---:|---:|---:|
| OverFolder | 5/8 | 6/8 | 3/8 | 7/8 | 7/8 |
| CallingStation | 8/8 | 8/8 | 7/8 | 8/8 | 8/8 |
| Balanced | 8/8 | 8/8 | 7/8 | 8/8 | 8/8 |
| Aggressor | 7/8 | 7/8 | 6/8 | 8/8 | 8/8 |
| SelectiveBluffer | 8/8 | 8/8 | 8/8 | 8/8 | 8/8 |
| Trapper | 7/8 | 8/8 | 7/8 | 8/8 | 8/8 |

### Matched conversions and uncertainty

Full converted **9 v2-off losses**, **2 v2-info losses**, and **4 v1-info losses** into wins, with **zero dropped reference wins** on this particular block. Full and posterior won exactly the same matched cases.

The six families reuse the same eight deal seeds. Treating all 48 outcomes as independent Bernoulli trials would exaggerate confidence. A descriptive two-sided sign test on the **eight seed blocks**, ignoring zero-change blocks, yields:

- versus v2 off: p = .03125;
- versus v2 info: p = .5;
- versus v1 info: p = .5.

These are small, fixed-family benchmark comparisons, not league confidence guarantees. The latter two comparisons do not establish a population-level win advantage. Two adversarial families were introduced after exploration, but had already appeared in the earlier holdout; the corrected confirmation used **new deals**, not entirely unseen opponent families.

## Isolated exactness/speed benchmark

Thirty final boards, seed 2181. Run after confirmation, with **one-CPU affinity and 1-GiB address-space limit**, no concurrent benchmark:

| Quantity | Result |
|---|---:|
| Median complete river-kernel build | **4.368 ms** |
| Median additional quadratic disjoint-pair oracle | **68.510 ms** |
| Median physical-hand / quotient-state ratio | **12.230×** |
| Median dense / quotient response latency ratio | **21.806×** |
| Peak test-process RSS | **41.762 MiB** |

Every tested holding's percentile agreed with the direct disjoint-pair oracle within **1e−14**. Dense and compressed continuation/win masses agreed within **1e−13**. This is exactness of the geometry and represented model—not proof of the true opponent range or optimal play.

The quadratic timing excludes common score construction, whereas the complete kernel timing includes it. They are stated separately rather than pretending both are identical end-to-end implementations. The dense histogram implementation costs `O(N log N + D U)`, not unconditional `O(N log N)`; see [PROOFS.md](CORA_PROOFS.md).

## Constrained execution of the final standalone artifact

Final artifact: `cora_bot.py`, **69,786 bytes**.

SHA256:

```
5473fdf8975fe812c35cb87f4937bb516bb278f0a11b89daa9e935130bc5ae36
```

The worker imports this bundled file, runs a closed-loop synthetic game, serializes/parses normalized frames, and includes startup, every hand-end, and match-end costs. The fixture and opponent run in the same process, so external process time and peak RSS include their overhead.

| Workload | External process wall, s | Candidate booked processing, s | Peak RSS, MiB | Illegal replies | Recovered soft deadlines |
|---|---:|---:|---:|---:|---:|
| 400 hands, explicit lock contract | **4.684** | 2.957 | 41.512 | **0** | 19 |
| 1000 hands, explicit lock contract | **10.506** | 6.563 | 42.484 | **0** | 146 |
| 1000 hands, no lock contract | **24.997** | 18.201 | 42.820 | **0** | 231 |

All three completed without a process failure, hard clock kill, or exhausted usable processing bank. Each declared a 60-second bank; the controller retains a **15-second reserve**, so reported usable remaining budget is `45 − booked processing`. The worst tested no-lock case retained **26.799 usable seconds**, in addition to that reserve.

- One CPU and 1-GiB **address space** were enforced through OS affinity/rlimits.
- Runtime write attempts and socket/process creation were blocked with Python audit hooks; **zero forbidden attempts** were observed.
- This is **not** a full OS read-only/network-namespace equivalence proof; native extension behavior is not comprehensively covered by Python audit hooks.
- Frames exercised the bundled adapter through serialized in-process calls. Actual stdin/stdout was additionally tested in a separate CLI unit test. This is not the undisclosed official process/protocol lifecycle.
- Execution used **Python 3.13.16 / NumPy 2.3.5**. Python 3.11 grammar checks passed, but **actual Python 3.11 execution remains unvalidated**.
- These are three execution fixtures, not strategic win-rate samples or exhaustive worst-case clock proofs.

Recovered internal deadlines are deliberate soft interrupt recoveries, not competition-level forfeits. The bot can still lose a match while finishing legally.

## Hardening and no-cheating boundary

**23 current tests passed:** 14 mathematical/agent tests and 9 EXAMPLE transport tests. Coverage includes all-hand disjoint oracles, tie geometry, hero blockers, dense/quotient differential updates, normalized legal categorical probabilities, exact showdown masks, interrupted atomic updates, event replay, fresh private-state reset, and the conditional bound over 10,000 adversarial return sequences.

Transport tests cover request/hand-end replay, conflicting IDs, public money ledger mismatch, actor order, incomplete/closed betting rounds, changed private/public hand state, response application, explicit lock gating, match reset, nested private-field rejection, and actual stdin/stdout.

The standalone build deliberately **removes the old duplicate-hole inference implementation and old protocol entry point**. Its match session only permits duplicate mode `off`. It reads own hole cards, public board/actions/stacks/outcome, supplied legal actions, and public control/budget fields. It does not consume actual opposing cards, deal seeds, future boards, private benchmark state, a network service, or runtime table files. The preflop table is embedded. NumPy and standard Python suffice; no runtime installs.

The test harness necessarily owns all cards to simulate a game. That does not give them to the candidate. Candidate sources contain no fixture imports or stack-inspection mechanism.

## Important tradeoff and release gates

**No universal “no sacrifices” claim.** Full's mean raw net was **133.67**, versus posterior's **397.48**. Once a match point is certified, locking deliberately gives up surplus chip EV. Unknown capped-chip tie-break rules can make that harmful to tournament ranking. The lock certificate concerns primary raw-net match wins, not all tournament objectives.

Do not submit the prototype as official until these gates are resolved:

1. Actual modified rules, card/rank/payout mechanics, and legal-action meanings.
2. Official stdin/stdout schema, lifecycle, restart behavior, and clock accounting.
3. Primary scoring and capped-chip tie-break formula; verify all lock premises or keep it disabled.
4. Final-stage time bank and any blind/ante growth or mandatory fees.
5. Actual Python 3.11 + organizer NumPy execution.
6. Larger 400/1000-hand strategic tests and stronger adaptive, out-of-family competitors.

The target is strong practical performance with no prohibited information—not an invented guaranteed tournament victory.

## Evidence history and reproducibility

Older exploratory and holdout evidence is retained, not pooled with the corrected confirmation:

- Exploration: v2 15/24, full 23/24; pre-transactional sources and concurrent microbenchmark activity. Discovery only.
- First frozen block (91000): v2 off 29/48, posterior 41/48, full 44/48; stronger prior references 34/48 and 33/48. Later math audit found unnormalized clipped likelihoods and soft outcome conditioning. Archived before correction.
- Corrected confirmation (121000): final table above. Proper legal categorical probabilities and exact showdown masks. No tuning during the run.

Raw arrays, logs, source hashes, tests, scripts, and archived sources are in the package. See [REPRODUCE.md](CORA_REPRODUCE.md), [PROOFS.md](CORA_PROOFS.md), and [PROTOCOL_CORA_EXAMPLE.md](CORA_PROTOCOL_EXAMPLE.md).

Previous `runtime/bot.py` remains unchanged at SHA256 `27c303582022e1320e3cad286021c93526c345819567cd6380052c113d522bbb`. The previous audited v2 delivery has not been overwritten.
