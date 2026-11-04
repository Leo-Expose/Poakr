# Discard Hold’em protocol-1.0 retry — 31 October 2026

## What changed with the supplied PDFs

The previous bots solved a different two-card mock game. The new candidate implements the actual **three-card / exposed-discard game and the supplied stdin/stdout protocol**. Old CORA/v2 files, archives, benchmark claims and the earlier reference controller remain unchanged. Their win rates are not evidence for this variant.

The supplied rules resolve the deadline year, standard post-discard ranking, action schema, reset stacks, caps, finals bank and charged clocks. [Reconciliation and original PDFs](../organizer/RULES_RECONCILIATION.md).

**Candidate:** `releases/discard/current/bot.py`, 30,730 bytes, stdlib + NumPy, no runtime workspace imports/table files/installs. SHA-256 `2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907`. A source-pinned copy and top-level `bot.py` ZIP are frozen under `releases/discard/v1/`. They are **candidates, not organizer-certified submissions**.

## Implemented

- Complete known protocol lifecycle: init, new hand, action, discard request/result, terminal accounting, notice and match end. Unknown types/fields are ignored. Only request replies reach stdout; each is flushed.
- Three-card pre-discard policy and one committed two-card discard choice. Both public dead cards block future samples, retained peer pairs and rank proofs. Even preflop all-ins still answer the flop discard request.
- Independent replay of accepted public actions: street-total TO amounts, 1/2 blinds, initial BB raise count, min raises, four-aggression cap, stacks/pot, seat order and own response confirmation. Never book a submitted reply as accepted merely because it was printed.
- Raw hand net checked against public contribution history and independently evaluated revealed showdown. A correction notice or discrepancy withdraws certification; the candidate does not rely on engine corrections.
- New constant-size dead-card turn-quads certificate, including nonrainbow boards and dead-card-blocked higher quads. Independent exhaustive tests cover **79,464 physical worlds** across two examples.
- All **903** physical peer pairs on the river; reuse the rank pass for uniform-pair strategy equity, avoiding a second Monte Carlo calculation.
- Exact alternating future blind bounds; pending check/call through settlement; then a cap-seeking commitment ceiling that **does not erode the initial certified score floor**. This is not a claim of optimal cap-score strategy.
- Single-file build and independent local protocol engine, with both interpretations of duplicate card/seat mapping. No duplicate inference or hidden actual-card/runout access.

See [proofs and precise limitations](GUARANTEES.md).

## Tests

**108 tests passed:** 21 new Discard Hold’em tests + 53 preserved CORA/guarantee tests + 34 v2 tests. No old strategic result was relabeled for the new game.

New checks include suit-order fallback, match-level clipping, every alternating blind suffix through 1000 hands, TO accounting, BB’s option after limping, raise limits, exposed dead cards, mandatory all-in discards, unknown-field compatibility, submitted-action reconciliation, low-bank legal responses, pending settlement, coupled fixed discard choices, bounded spend, eight short local diagnostic matches and actual single-file stdio.

## Full serialized local fixtures

Every row used the **exact candidate SHA above**, an independent local engine, real stdin/stdout, one-CPU child affinity and a 1-GiB address-space limit. Python audit hooks found zero attempted writes/network/process creation. File reads by Python/library loading are not a proof of OS-enforced sandbox isolation. Source performs no explicit file I/O.

| Opponent | Hands | Raw net | Serialized candidate request time | Whole local match | Peak child RSS |
|---|---:|---:|---:|---:|---:|
| CallingStation | 400 | +513 | 4.763 s | 5.026 s | 34.15 MiB |
| Selective | 1000 | +26 | 7.340 s | 7.727 s | 34.11 MiB |
| Shove | 400 | +191 | 0.418 s | 0.501 s | 34.36 MiB |
| Aggressor | 400 | +94 | 0.661 s | 0.734 s | 34.12 MiB |
| Shove | 16 | -229 | 0.262 s | 0.298 s | 34.14 MiB |

The four full-length fixtures won; the **16-hand diagnostic lost −229** before a certificate armed. This is explicit evidence against claiming this candidate never loses. These few artificial-opponent runs are not a win-rate estimate, tournament-strength holdout, or equilibrium proof. Different lengths/seeds/layouts are not independent equivalent trials and must not be pooled into a flattering “success rate.”

Across all rows: zero illegal replies, zero adapter errors, trusted terminal ledger through completion, and zero forbidden audit attempts. Startup readiness was below 0.12 seconds; maximum reply was below 0.16 seconds. The 400/1000 fixtures used 60/150-second banks; all stayed within those banks, 5-second response/startup limits and 180/450-second whole-match limits. Serialized timing conservatively includes child startup in the first request; it does not understate that contribution.

The 400-hand shove fixture also exercises mandatory all-in discards. Raw results and metadata are in `evidence/discard/*.json`. Intermediate, differently hashed prototypes are under `evidence/discard/archive/pre_reserve_floor/` and are not current evidence.

## Strategy limitations, not hidden behind the proofs

The ordinary policy is a low-compute baseline, not a general poker solution. Coupled Monte Carlo compares three fixed own-pair choices on identical hypothetical worlds and selects one pair by its mean—not the impossible best pair after each future runout. For pre-discard opponents, a maximum over their hypothetical pairs is a pessimistic clairvoyant envelope, not a simulated legal strategy. Uniform deals and uniform post-discard retained pairs do not model action/discard selection bias. Sampling and maximizing noisy means are not exact expectation or confidence certificates. No sampled estimate authorizes a pointwise lock.

The cap-seeking continuation protects the original guaranteed floor; it can still earn less than the passive baseline would have earned on a particular realized path. The 1000-hand net +26 is not hidden behind its fast runtime or the earlier intermediate prototype’s larger profit.

## What still prevents an official-ready claim

1. The **Problem Statement scheduled for 1 November** is absent; it can override variant mechanics.
2. The **organizer starter-kit runner** is absent. Our complete local engine is not that runner.
3. Actual **Python 3.11 execution** and organizer NumPy remain untested; local interpreter is **3.13.16**. AST grammar compatibility passes.
4. OS-level sandbox isolation, native-library behavior and hostile scheduling are not proven by audit hooks or finite timing samples.
5. Provisional caps/clocks and the duplicate-layout example need final confirmation. No duplicate inference is enabled, so that layout ambiguity does not drive decisions.
6. Stronger adaptive-opponent tests and a larger independently frozen holdout are still needed. No universal initial-state win/nonloss or global novelty claim is made.

## Reproduce

From repository root; dependencies must already be installed:

```bash
python3 tools/discard/build.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/discard -p 'test_*.py' -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/discard/local_runner.py --hands 400 --opponent CallingStation --wire --sandbox --seed 173000 --output rerun_400.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/discard/local_runner.py --hands 1000 --opponent Selective --wire --sandbox --seed 181000 --layout swapped_seat_cards --output rerun_1000.json
python3 tools/maintenance/verify_workspace.py
```

Choose fresh output names. `--sandbox` means the documented affinity/address-space/audit worker, **not OS sandbox certification**. Do not upload the full workspace/research ZIP: the candidate artifact is the single `bot.py` or the candidate ZIP containing it at the top level.
