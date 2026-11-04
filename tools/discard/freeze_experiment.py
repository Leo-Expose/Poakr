"""Freeze rejected-for-promotion range-guard research, never overwrite."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'releases/discard/experiments/range_guard_v1'
EVIDENCE=ROOT/'evidence/discard/redteam_2026_11_02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if OUT.exists():raise SystemExit('Refusing to overwrite frozen experiment')
verdict=json.loads((EVIDENCE/'verdict.json').read_text())
assert not verdict['promoted'] and not verdict['gates']['no_worse_worst_match']
freeze=json.loads((EVIDENCE/'experimental_freeze.json').read_text())
for name,digest in freeze['files'].items():assert sha(ROOT/name)==digest,name
OUT.mkdir(parents=True)
shutil.copyfile(ROOT/'releases/discard/experimental/bot.py',OUT/'bot.py')
for name in ('plan.json','experimental_freeze.json','verdict.json'):
    shutil.copyfile(EVIDENCE/name,OUT/name)
for name in list(freeze['files'])+['research/discard_holdem/protocol.py','research/discard_holdem/proofs.py','engine/numpy_eval.py','tools/discard/build.py','tools/discard/compare_redteam.py']:
    dst=OUT/'source_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)
(OUT/'README.md').write_text('''# Range-guard experiment v1 — NOT PROMOTED

This immutable research candidate is NOT the working champion or recommended submission. Champion remains `releases/discard/v1/bot.py` in the full workspace.

All32fresh holdout fixtures won for both versions. Experiment earns8598chips versus7232, but weakest result7versus12 fails the predeclared gate. No experimental supplied-engine/resource validation was attempted after that failure. ActualPython3.11 remains untested.

Read the full [hardening report](../../../../docs/discard/ROBUSTNESS_ITERATION_1.md). Plan/freeze/verdict and source snapshots are preserved here. Complete runtime/test dependencies and raw matches are in the full organized workspace bundle; source_snapshot is for provenance, not a separate standalone project. Only bot.py is self-contained, but its research status must not be confused with validated recommendation.

manifest.json hashes these immutable files and separately preserved raw evidence. Do not overwrite this experiment or tune to the now-public holdout and call it fresh.
''')
m=dict(experiment='range-guard-v1',promoted=False,official_ready=False,policy_changed_from_champion=True,
       candidate_sha256=sha(OUT/'bot.py'),champion_sha256=sha(ROOT/'releases/discard/v1/bot.py'),
       supplied_engine_experimental_validation=False,python_311_execution_verified=False,os_sandbox_verified=False,
       frozen_files={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()},
       evidence_files={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(EVIDENCE.rglob('*')) if p.is_file()})
(OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(folder=str(OUT),manifest_sha256=sha(OUT/'manifest.json')),indent=2))
