# Reproduce CORA

Run commands from the extracted project root (`CORA/`). Only standard Python and preinstalled NumPy are needed. Do not install dependencies at runtime. Local evidence used Python 3.13.16 / NumPy 2.3.5; target Python 3.11 still needs execution qualification.

## Build and correctness

```bash
python3 research/build_cora.py
python3 research/test_research.py
python3 research/test_stream.py
python3 -B research/cora_bot.py < research/example_cora.jsonl
```

The builder extracts the unchanged v2 evaluator, budget, policy, and validation helpers, removes duplicate-hole inference and the old adapter/main, embeds the sampled preflop table, and adds the research kernel/controller/EXAMPLE adapter. The runtime file does not import the project package or load a table file. Bytecode cache writes are disabled by the standalone entry file.

Building under another Python version may change grammar/unparse behavior in future builders; compare actual hashes rather than assuming byte identity. The current builder preserves source lines rather than using AST unparse.

## Exact geometry and quotient benchmark

Run in isolation, not during match timing:

```bash
python3 research/microbench.py
```

This Linux script pins one CPU, applies a 1-GiB address-space limit, evaluates 30 boards, asserts direct quadratic-oracle and dense/quotient agreement, and writes `research/microbench_results.json`. Timings vary with system load.

## Frozen corrected confirmation

This is a longer test. Do not edit kernel/agent/table/runtime sources during it or run another CPU-heavy benchmark alongside it:

```bash
python3 -u research/experiment.py \
  --matches 8 --deals 50 --seed 121000 \
  --modes v1_info,v2_info,v2,posterior,full \
  --opponents OverFolder,CallingStation,Balanced,Aggressor,SelectiveBluffer,Trapper \
  --output confirmation_rerun.json
```

It snapshots loaded candidate source hashes at startup. Use a different output filename to preserve the delivered evidence. Each mode starts a cold match-local model. Candidate duplicate inference is disabled; the two `_info` references enable their previous board-copy inference. Only public final-board prefixes and public win/tie/loss outcomes are passed to CORA.

This compares synthetic policies, not top tournament competitors. The eight physical deal seeds repeat across the six opponent families, so confidence analyses must use seed clusters rather than pretend all 48 results are independent.

Sampling budgets are wall-clock guarded. Seeded runs therefore need not be bit-identical across machines/interpreters: deadline timing can change sample counts and subsequent decisions. A hash match establishes source identity, not identical stochastic traces.

## Final standalone under constrained resources

After confirmation finishes:

```bash
python3 research/resource_cora.py
```

The parent runs three isolated child processes: 400 hands with the asserted lock contract, 1000 with it, and 1000 without it. Children enforce one CPU and 1-GiB virtual address space; a Python audit hook rejects runtime writes, socket creation/connections, and process spawning. Bytecode writes are disabled. They import the built single-file candidate, drive serialized public frames through it in a closed-loop fixture, count legality and soft deadlines, include hand/match-end costs, and record the exact standalone SHA256.

This is not a full OS network/read-only container proof or the official process harness. Do not infer Python 3.11 execution from a grammar check or 1000-hand tournament strength from one resource fixture.

## Files and provenance

- `confirmation_results.json`, `summary_results.json`, `confirmation.log`: corrected frozen evidence.
- `microbench_results.json`, `resource_results.json`, associated logs: final isolated measurements.
- `tests.log`, `stream_tests.log`: current 14+9 correctness results.
- `preflop.json`, `make_preflop.py`, `preflop.log`: offline sampled table/provenance.
- `archive/before_normalized_policy/`: exact older kernel/agent and older holdout/reference results before the categorical/showdown correction.
- Other archived exploratory sources/results: discovery-stage evidence, explicitly not final corrected confirmation.
- `manifest.json` in the release: file hashes and evidence scope.

The old v2 runtime is included for reproducible comparisons and stays frozen. The standalone candidate contains no duplicate-hole inference implementation. Legacy/benchmark sources are test fixtures, not runtime imports.
