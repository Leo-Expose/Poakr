# Champion hardening — iteration 1

**2 November 2026. Verdict: keep frozen v1; experimental challenger NOT promoted.**

## What “wins no matter what” can mean honestly

Strict victory against every opponent and legal deal is impossible: a shared royal-flush board with an opponent who always checks/calls gives no winning showdown and makes folding unprofitable. The [precise guarantee document](GUARANTEES.md) proves this actual-variant witness. This does not establish impossibility of every hypothetical universal nonloss strategy, but **our candidate already has concrete losses**, including the identical copy losing 212 in the supplied-engine mirror.

The useful objective is robust practical strength with independently checked conditional guarantees. We will not silently replace that with a promise of perfect play, no forfeit, universal nonloss, or tournament qualification.

## Work completed

1. Built eight public-information red-team profiles: CallingStation, CheckFold, Shove, Aggressor, ValueNit, Trap, SmallBall and Switch (changes style every 40 hands).
2. Declared development seeds 301000/301001 and fresh holdout seeds 401000–401003, 400 hands per match; source/promotion gates preserved in `evidence/discard/redteam_2026_11_02/plan.json`.
3. Built one experimental challenger, froze its strategy/source identities before the holdout, and did not retune after seeing holdout results.
4. Completed **96 full local matches / 38,400 hands**:16 development and32 holdout matches for each of two versions. Starting bot position alternates across seeds; duplicate positional cards remain fixed with alternating bots. No duplicate inference is used by the policies.
5. All 96 completed with zero illegal replies, zero candidate accounting errors, trusted ledgers, and final net at least the candidate's recorded initial certified floor. All 96 armed a certificate. This is finite evidence, not coverage of all legal worlds or opponents.
6. **129 tests pass**: 32 Discard (21 existing + 11 new),10 supplied-engine,53 preserved CORA/guarantee,34 v2. New tests include3,000 exact current-rank comparisons across 5/6/7 cards against the supplied evaluator, public-only modelling, tied-score invariance, final-reply accounting, bounded probes, low-bank and certificate exclusions, and inherited pending-settlement/reserve regressions.

All new match runs use the **independent local engine in-process**, not the organizer CLI or OS sandbox. They must not be pooled with the earlier supplied-engine timing/resource validation. Maximum observed candidate computation sum was 3.267460 s per 400-hand local fixture; maximum individual computation 0.015801 s. These exclude wire/launch costs and are not target-host speed guarantees.

## The experiment

`research/discard_holdem/adaptive.py` subclasses the existing protocol/proof implementation:

- **Public-action range guard:** aggregate observed raises/opportunities by preflop/postflop; downweight some uniformly sampled hands when facing aggression from a selective opponent. Weights stay positive and shrink toward the original estimate. This is a heuristic, **not a calibrated posterior or equilibrium range**.
- **Current information only:** candidate opponent-strength modelling uses the currently exposed board, not each sampled future runout. An exact 5/6/7-card made-rank helper supports this. No past revealed private-card collection or duplicate matching.
- **Bounded cheap-steal probe:** after sufficient observed cheap-price fold responses, at most one probe per hand, extra commitment at most 4 chips. The plug-in lower estimate is not an anytime/adaptive confidence theorem. Switching opponents can defeat this inference.
- **Proof firewall:** original `_arm`, `_verify_history`, pending settlement, safe action, future-blind bound and fallback methods are inherited unchanged. Cheap probes cannot override pending settlement, a locked reserve, low-bank recovery or withdrawn trust. The original wrapper records the FINAL outgoing reply so subsequent accepted-history validation remains correct.
- All physical river proof support remains intact. Heuristic weights never truncate or authorize exact certificate support.

The strategy still uses approximate sampled equity, simplified ranges and a non-equilibrium opponent model. Adding adaptation is not automatically an improvement.

## All development results

| Version | Matches | Wins /draws /losses | Sum raw net | Weakest match |
|---|---:|---:|---:|---:|
|Frozen v1|16|16 /0 /0|+4,832|+19|
|Experiment|16|16 /0 /0|+4,365|+5|

The experiment was worse on this development aggregate. We preserved the one-trial experiment and ran the already declared holdout without retuning it. This is not a search over holdout results.

## Fresh holdout results

| Version | Matches | Wins /draws /losses | Sum raw net | Sum clipped match net, C400 | Weakest match |
|---|---:|---:|---:|---:|---:|
|Frozen v1|32|32 /0 /0|+7,232|+6,310|+12|
|Experiment|32|32 /0 /0|+8,598|+7,317|+7|

The experimental raw total is 18.9% larger on this particular holdout; its clipped total is 16.0% larger. Official tie-break aggregation would divide each clipped total by 12,800 hands. These descriptive differences are **not estimates of a tournament improvement rate**. Both versions received the same diagnostic match points. The experiment's paired net was better in 18 matches, equal in 5 and worse in 9. A different action policy can consume RNG and branch through hands differently; this is a matched-deck comparison, not identical trajectories or an optimal counterfactual.

| Opponent | v1 total, 4 matches | Experimental total | Experimental minus v1 |
|---|---:|---:|---:|
|CallingStation|+2,169|+2,169|0|
|CheckFold|+1,088|+1,701|+613|
|Shove|+715|+724|+9|
|Aggressor|+350|+351|+1|
|ValueNit|+1,306|+1,383|+77|
|Trap|+929|+1,683|+754|
|SmallBall|+359|+378|+19|
|Switch|+316|+209|−107|

The worst experimental result was +7 against Aggressor, seed401002. Its Switch aggregate deteriorated. Neither these profiles nor four seeds per profile cover sophisticated adaptive best responses or independently authored strong opponents. A 48/48 diagnostic record for either version across development+holdout does not erase the earlier actual-variant losses or establish universal nonloss.

## Promotion decision

Predeclared gates required:

- existing/new tests, ledger validity, original floor preservation and frozen source identity: **PASS**;
- at least baseline holdout wins: **PASS** (32 versus 32);
- greater total holdout net: **PASS** (+8,598 versus +7,232);
- no worse weakest holdout match: **FAIL** (+7 versus +12).

**Do not relax the failed gate after seeing the results. V1 remains the working champion.** This conservative rule is an engineering selection rule, not a statistically proven robustness ordering: a 5-chip difference alone does not prove v1 globally stronger. The challenger is worth research, but is neither uniformly better nor cleared for replacement.

Per the plan, experimental supplied-engine/resource validation was **not attempted**, since the preceding strength gate failed. Earlier v1 [supplied-engine evidence](SUPPLIED_ENGINE_VALIDATION.md) remains unchanged. Do not claim the experiment inherits those runtime measurements or that it passed the organizer runner.

## Artifacts and reproduction

- Working champion: `releases/discard/v1/bot.py`,SHA-256 `2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907`; original submission ZIP unchanged.
- Experimental bot: 42,797 bytes,SHA-256 `e133f9c2e740f3d9c28ec294515d3d52c7ac631ebe62a5f82d7fee0e6314e139`. Live build: `releases/discard/experimental/`; frozen research snapshot: `releases/discard/experiments/range_guard_v1/`. **Not the recommended submission.**
- Full per-match rows, seeds, source hashes, logs, plan, freeze, tests and verdict: `evidence/discard/redteam_2026_11_02/`.
- Tools: `tools/discard/redteam.py`, `compare_redteam.py`; model source: `research/discard_holdem/adaptive.py`, `partial_eval.py`; tests: `tests/discard/test_adaptive.py`.

Run with allowed dependencies already installed; no runtime installs:

```bash
python3 tools/discard/build.py --experimental
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/discard -v
# Fresh output names required; original evidence must not be overwritten.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/discard/redteam.py --seeds 401000,401001,401002,401003 --output evidence/discard/fresh_baseline.json
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/discard/redteam.py --bot releases/discard/experimental/bot.py --seeds 401000,401001,401002,401003 --output evidence/discard/fresh_experimental.json
python3 tools/discard/compare_redteam.py
python3 tools/maintenance/verify_workspace.py
```

`compare_redteam.py` checks the original pinned experiment; changing the strategy requires a new experiment and fresh holdout, not overwriting the freeze. `build.py` without `--experimental` still reconstructs byte-identical v1. Actual Python 3.11, OS sandbox, final limits and organizer clock clarification remain open. No organizer contact/upload occurred.

## Next defensible direction

A stronger opponent family (including policy-aware adaptive opponents and head-to-head play), more independent seeds and a match-win/downside objective are more useful than claiming “perfect.” A new experiment should separate range-guard and cheap-steal ablations, explicitly test style-switch recovery, and use a new held-out set. Retuning to these now-public holdout seeds would invalidate another fresh-holdout claim.
