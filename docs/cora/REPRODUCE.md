# Reproduce CORA in the organized repository

Run from `pokerbot/` (or the extracted package root). Preinstalled NumPy is required; no runtime installation. SciPy is used only by the separate offline guarantee lab. Local evidence used Python 3.13.16 / NumPy 2.3.5; actual target Python 3.11 execution remains pending.

## Integrity, build, and tests

```bash
python3 tools/maintenance/verify_workspace.py
python3 tools/cora/build_cora.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/cora -p 'test_*.py' -v
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -B releases/cora/v1/cora_bot.py < fixtures/cora/example_session.jsonl
```

The builder extracts the frozen v2 helpers, removes duplicate-hole inference and the previous adapter/main, embeds the canonical table, and adds CORA. It writes `releases/cora/current/cora_bot.py`, not the published v1 file. It currently reproduces the published SHA256 exactly. Runtime imports only standard Python/NumPy and reads no table file.

## Exact geometry/quotient and constrained runtime reruns

Run serially, never while timing a match experiment:

```bash
python3 tools/cora/microbench.py
python3 tools/cora/resource_cora.py
```

The microbench pins one CPU, applies a 1-GiB address-space limit, and checks 30 boards against the disjoint-pair oracle and dense model. The resource program tests the **frozen v1 standalone** on 400/1000-hand serialized-frame fixtures with/without the asserted lock contract. New output goes under `evidence/cora/reruns/`, leaving published `evidence/cora/benchmarks/` unchanged.

OS affinity/rlimits enforce CPU/address space; Python audit hooks ban write/socket/process operations. This is not the undisclosed official wire/process harness or a complete native-extension sandbox proof. Actual stdio is separately covered by a CLI unit test.

## Corrected frozen strategic confirmation

Longer test; do not edit algorithm/table/runtime sources or run another CPU-heavy process during it:

```bash
python3 -u tools/cora/experiment.py \
  --matches 8 --deals 50 --seed 121000 \
  --modes v1_info,v2_info,v2,posterior,full \
  --opponents OverFolder,CallingStation,Balanced,Aggressor,SelectiveBluffer,Trapper \
  --output confirmation_rerun.json
```

The runner snapshots current candidate source hashes at startup. Output goes under `evidence/cora/reruns/`. Existing confirmation is `evidence/cora/confirmation/confirmation_results.json`. After organization the table's path is `data/preflop/preflop.json`; its bytes are unchanged. Historical result keys keep the old path, resolved by the migration map.

Each candidate model is cold-started per match. Candidate duplicate inference is disabled; `_info` references enable their old inference. Only own cards, public board/action/outcome information is supplied to CORA. The six synthetic families share eight physical deal seeds, so inference must account for seed clusters.

Wall-clock guards can change sample counts/decisions across machines. Source hashes establish identity, not bit-identical seeded traces. These strategic matches are 100 hands, not official 400/1000-hand strategic validation.

## Offline table provenance

Canonical table: `data/preflop/preflop.json`; original generation log: `data/preflop/generation.log`. To generate a new sample table:

```bash
python3 tools/cora/make_preflop.py
```

This writes `data/preflop/preflop_regenerated.json`, never replacing the canonical input. Generation timing can change its hash even if estimates reproduce. Do not substitute new inputs into published evidence without a new provenance record.

## New guarantee lab

```bash
python3 tools/cora/guarantee_lab.py
python3 tests/cora/test_guarantees.py
```

Results: `evidence/guarantee_lab/`. This uses SciPy to propose minimax distributions and exact Fraction arithmetic to verify them. Variable-post, specific capped-score, and safe-river-credit research do not modify the frozen policy. See [guarantee docs](../guarantees/README.md).

## Packaging

```bash
python3 tools/cora/package_cora.py
```

Creates an organized source/evidence package under `releases/organized/`, with checksum manifest. Frozen original ZIPs remain under `releases/v1/`, `releases/v2/`, and `releases/cora/v1/`. No loose exports are written into the workspace root.
