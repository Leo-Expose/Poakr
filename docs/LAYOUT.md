# Layout and preservation policy

## Immutable versus live

**Published binaries/archives:** `releases/v1/`, `releases/v2/`, `releases/cora/v1/`. Do not overwrite. The v2 runtime in `runtime/bot.py` is also frozen. Historical ZIPs contain the original pre-organization layout.

**Live build outputs:** `releases/cora/current/`; organized source packages in `releases/organized/`; optional v2 rebuilds in `releases/v2/rebuilt/`. These are not silently substituted for published evidence.

**Frozen CORA measurements:** `evidence/cora/confirmation/`, `holdout/`, `exploration/`, `benchmarks/`, and historical test logs. Old source-name strings inside results are preserved. The migration map resolves them; do not rewrite old hashes/results to look current.

**New reruns:** `evidence/cora/reruns/`, `evidence/v2/reruns/`, and `evidence/legacy_bench/reruns/`. The match/microbench/resource tools write here. Record new results separately, with their exact tested source/artifact identity.

**Guarantee research:** `research/guarantee_lab/`, `tools/cora/guarantee_lab.py`, `tests/cora/test_guarantees.py` and `test_settlement.py`, `evidence/guarantee_lab/`, `docs/guarantees/`. It is not imported by the frozen standalone policy.

**Data:** `data/preflop/preflop.json` is the exact table used by the published confirmation. Regeneration writes `preflop_regenerated.json`, not the canonical table. Generation timing/provenance and old heuristic assets are separate.

**Source separation:** `research/` remains the importable CORA package; `tools/` contains entry scripts; `tests/` contains tests; `docs/` contains human-facing documentation. `bench/` remains the historical comparison program namespace so dependent imports stay stable.

## Migration record

`evidence/migration/path_map.json` records old and new file paths and pre-move hashes. Active tools/docs were updated after movement; their hashes may differ by path fixes. Runtime, CORA kernel/controller/adapter, the canonical table, and published ZIP/executable bytes remain unchanged. Archived source copies are not rewritten.

The earlier CORA report mislabeled string length as byte length: the executable is **69,794 UTF-8 bytes**, not 69,786 bytes. The latter is its Unicode character count. Hash and execution identity were correct. Active docs/build logging are corrected; historical reports inside frozen archives remain unchanged.

## Working rules

1. Run from repository root, unless a tool documents otherwise.
2. Do not tune a source while its frozen confirmation is running.
3. Never pool discovery and confirmation runs without explicit labels.
4. A policy change requires a new release and fresh evidence; a path-only migration does not change old benchmark outcomes.
5. Never write generated files into the workspace root or source directories.
6. Use modern source/docs/data formats; no runtime installs or external lookups.
7. New mathematical assertions need quantified scope, assumptions, an executable check, and counterexamples at the boundary.
8. Read `docs/RELEASE_GATES.md` before attempting any official submission.

**Reference-controller snapshot:** `releases/guarantees/v1/` is an immutable research archive/manifest, not an organizer-ready or full-policy submission. Rebuilt v2 reports/packages use `releases/v2/rebuilt/`, never the historical published paths.

## Actual-game extension, 31 October 2026

`research/discard_holdem/`, `tools/discard/`, `tests/discard/`, `evidence/discard/`, and `docs/discard/` are the separate protocol-1.0 Discard Hold’em implementation. Original supplied PDFs and extraction provenance live in `docs/organizer/`. `releases/discard/current/` is a live build; `releases/discard/v1/` is an immutable candidate plus frozen evidence. No historical two-card bot was relabeled or modified. The workspace bundle is not an upload; only the new single `bot.py` / root-level `bot.py` submission ZIP has the requested shape.

## Supplied-engine extension, 2 November 2026

- `vendor/organizer/`: untouched extracted starter files, original combined Markdown and provenance manifest.
- `docs/organizer/attachments/`: all three PDFs, including the1-November statement; extracted Markdown is a convenience.
- `tests/organizer/`, `evidence/organizer_runner/`: conformance tests, two direct CLI runs, four externally measured/resource-constrained runs, fresh118-test logs.
- `tools/discard/resource_launcher.py`, `validate_supplied_engine.py`: external instrumentation only, not submission code. Launcher needs executable permissions (`chmod +x` after extraction if needed).
- `docs/discard/SUPPLIED_ENGINE_VALIDATION.md`, `docs/organizer/CLOCK_CLARIFICATION.md`: current evidence and unsent responsible clarification.
- `releases/discard/validated_2026_11_02/`: supplemental hashed attestation for unchangedv1; no artificial policy-version bump or rewrite of frozenv1.

`releases/organized/` is a refreshed, replaceable whole-workspace bundle, not an immutable policy release or official upload. Frozen original manifests/research ZIPs remain immutable.

## Champion-hardening research, iteration1

- `research/discard_holdem/{adaptive,partial_eval}.py`: experimental public-action range guard and current made-rank helper, separate from unchanged protocol/proofs.
- `tools/discard/{redteam,compare_redteam}.py`: public-information opponents, fixed seeds and automatic promotion verdict.
- `tests/discard/test_adaptive.py`, `evidence/discard/redteam_2026_11_02/`:11newtests, plan, frozen trial identity,96matches, complete rows and failed-gate verdict.
- `releases/discard/experimental/`: live experimental build, not recommended upload.
- `releases/discard/experiments/range_guard_v1/`: immutable research snapshot of rejected-for-promotion challenger; never overwrite.
- `docs/discard/ROBUSTNESS_ITERATION_1.md`: latest hardening report. V1 remains the working champion; no strategy-version promotion.

## OpenSpiel/objective investigation

- `docs/openspiel/`: sourced assessment, exact claim boundaries and integration plan.
- `research/openspiel_bridge/`: own exact small-game objective audit and immutable discard-information contract; not a registered/full OpenSpiel game.
- `tools/openspiel/`: no-install dependency probe and independent exact audit/royal witness. No OpenSpiel dependency is added to the bot.
- `tests/openspiel/`, `evidence/openspiel/2026_11_02/`:14new tests, missing-dependency record, exact rational certificates,903-pair witness and fresh143-test suite logs.

OpenSpiel was reviewed online at the user's request; it is not installed/executed. V1 and the rejected challenger remain unchanged.
