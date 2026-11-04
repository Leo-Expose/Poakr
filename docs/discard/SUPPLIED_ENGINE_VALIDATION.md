# Supplied-engine validation of unchanged Discard v1

**2 November 2026 — local evidence, not tournament certification.**

## Conclusion

The newly supplied **1-November Problem Statement** and starter-kit implementation are compatible with the frozen Discard v1 candidate. No policy or candidate-byte change was required. Six full clock-enabled matches completed with zero notices. Ten new conformance tests plus the existing 108 tests pass (118 total). This removes the missing-statement / missing-starter-runner gates, not the Python3.11, real host sandbox, final-limit or strategic-strength gates.

Upload-shaped artifact: `releases/discard/v1/submission.zip`, containing only root `bot.py`; or `releases/discard/v1/bot.py` (30,730 bytes). SHA-256 of bot: `2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907`. Original v1 manifest, evidence and documentation remain immutable historical snapshots. A supplemental attestation lives in `releases/discard/validated_2026_11_02/`.

## Inputs and provenance

- [Problem Statement](../organizer/attachments/8a894a3d-946f-40e9-b7ab-7c4e01eb0d4c.pdf), 8 pages, 1 November; SHA-256 `4d140e948c8266a44c2f253b0b9b736fada9f0896a6a3a6558465398b8bb8206`.
- [Rule reconciliation](../organizer/RULES_RECONCILIATION.md) links all three PDFs and their extracted text.
- `vendor/organizer/Starter_Kit/`: four files extracted from the supplied combined Markdown. Source/file identities: `vendor/organizer/manifest.json`. Engine SHA-256 `7a44eb0ef7518e1343779d2a46163549e380b228d8f583f1d0478adf4fd64ad6`.
- Vendor Python and starter policies were not edited. This reconstruction is verified against the supplied Markdown, **not against an independently supplied original ZIP**. The actual tournament host may differ.

The statement confirms fixed positional cards within a duplicate pair, alternating bots between those positions, four aggressions including BB, minimum TO raises, simultaneous exposed discard even after preflop all-in, best-five ranking and fold-before-discard results retaining all three private cards. No duplicate identity/inference is enabled in the candidate.

## Two direct supplied-CLI runs

No source instrumentation, no `--no-time-limits`, no resource wrapper. Evidence: `evidence/organizer_runner/v1/`.

| Stage | Opponent | Seed | Candidate position | Completed | Raw net | Notices |
|---|---|---:|:---:|---:|---:|---:|
|1|Starter|221000|A|400/400|+543|0|
|2|Random|231000|A|1000/1000|+1670|0|

Both summaries report 0.00 charged seconds. **That is not actual zero compute.** The engine's fixed startup grace window also exempts early responses; [clock clarification draft](../organizer/CLOCK_CLARIFICATION.md). These runs establish baseline protocol completion under the supplied CLI, not resource confinement.

## Four independently measured, resource-constrained runs

`tools/discard/validate_supplied_engine.py` imports the untouched engine and temporarily substitutes an external Bot subclass to timestamp complete stdout lines. `tools/discard/resource_launcher.py` loads the unchanged candidate/opponent under CPU affinity `[0]`, 1-GiB address-space limits and single-thread library settings. The wrapper emits a separate stderr probe, never extra protocol information or hidden cards. Engine clocks stay enabled. These runs are **instrumented supplied-engine runs**, distinguished from the unmodified CLI above.

| Fixture / candidate position | Seed | Hands | Net | Raw request sum | Max reply | Ready after loading | Peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
|Starter / A|241000|400|+624|2.218408 s|0.068450 s|0.061585 s|29.34 MiB|
|Random / B|251000|400|+610|1.195479 s|0.067451 s|0.069118 s|29.07 MiB|
|Starter / B|261000|1000|+1440|8.519273 s|0.065674 s|0.065722 s|29.69 MiB|
|Same candidate / A|271000|1000|+212|10.621562 s|0.210070 s|0.192292 s|30.15 MiB|

These measured candidates served respectively 1608,1109,4140,4860 requests (302,171,785,882 discards). Whole instrumented match times: 2.735344,1.556524,10.214180,22.671637 seconds. Every row completed all hands with zero notices, zero candidate accounting errors, a trusted score ledger and no forbidden audited operation attempts. Candidate certified initial floors were respectively 20,152,16,175; each final score exceeded its floor. This is fixture evidence, not a universal state-coverage proof.

The **other identical candidate in the mirror match lost −212**, with no certificate armed. It also completed with zero notices/errors and a trusted ledger. This directly refutes any claim that this candidate never loses from the initial state. Do not count one selected mirror side as an independent strength win.

Exact JSON, engine logs and captured stderr probes are in `evidence/organizer_runner/measured/<fixture>/`. They record candidate, opponent, engine, launcher and measurement-driver hashes. The strict raw request sums include the first loading delay; all were below the 60/150-second banks, all observed replies below five seconds. Peak RSS numbers concern these processes only. Audit hooks/affinity/address-space limits are **not** read-only mounts, network namespaces, native-code isolation or complete OS sandbox validation. Local execution remains **Python3.13.16**; Python3.11 was not available.

## Regression tests

Fresh logs: `evidence/organizer_runner/tests/`.

| Suite | Tests | Result |
|---|---:|---|
|Supplied-engine conformance|10|PASS|
|Discard protocol/proofs|21|PASS|
|Preserved CORA/guarantee|53|PASS|
|Preserved v2|34|PASS|
|Total|118|PASS|

New checks execute all five Problem Statement examples: full contributions and +140/−140 payout, four-aggression cap, all-in discard/concurrent request ordering and +200/−200 payout, fold before discard with three-card private result, kickers/playing the board. Other checks cover parser corrections, deterministic fallback suit order, duplicate layout, current startup-clock behavior, exact vendor provenance, and **2,000 independently sampled seven-card ranks** compared with the supplied evaluator (exact rank tuples). The rank comparison is not exhaustive over all seven-card combinations.

## Reproduce without changing frozen evidence

From workspace root, with allowed dependencies already installed:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/organizer -v
python3 tools/maintenance/verify_workspace.py
# On the actual target, substitute python3.11 where available:
python3 vendor/organizer/Starter_Kit/engine.py releases/discard/v1/bot.py vendor/organizer/Starter_Kit/bot.py --seed 221000 --log-dir fresh_direct_400
chmod +x tools/discard/resource_launcher.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 tools/discard/validate_supplied_engine.py --stage 2 --seed 261000 --candidate-position B --label fresh_stage2_starter
```

Use fresh labels/output directories. The measured driver refuses to overwrite a label. The random opponent is globally unseeded: a deck seed does **not** reproduce its action sequence. No claim of deterministic random-opponent net reproduction is made.

## Remaining gates and strength limits

1. Actual Python3.11 and organizer NumPy/image execution; grammar compatibility is not execution.
2. Actual OS-enforced sandbox and host timing, plus final provisional limits/caps.
3. Organizer clarification of the startup charging discrepancy; draft has **not been sent**.
4. Stronger adaptive opponents and a larger independent holdout. Starter/random wins and mirror play do not estimate tournament win rate or solve poker.
5. Normal stages use 400/1000 hands and inferred candidate caps400/1000. A custom `--stage 2 --hands 400` has a stage cap1000 but candidate inference400; such custom stage/hand combinations are outside this validation. Future protocol support for an explicit cap should be preferred if supplied.
6. Team registration, eligibility and actual valid portal upload; none performed here.

The mathematical guarantee remains **conditional floor preservation in verified state classes**, not universal initial-state nonloss, strict victory, or immunity to forfeit. [Precise guarantees](GUARANTEES.md).
