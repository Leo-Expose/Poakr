"""Freeze supplemental validation, not a new policy version. Never overwrite."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'releases/discard/validated_2026_11_02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if OUT.exists():raise SystemExit('Refusing to overwrite supplemental attestation')
bot=ROOT/'releases/discard/v1/bot.py'
assert sha(bot)=='2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907'
assert bot.read_bytes()==(ROOT/'releases/discard/current/bot.py').read_bytes()
paths={}
for name in ('docs/discard/SUPPLIED_ENGINE_VALIDATION.md','docs/organizer/CLOCK_CLARIFICATION.md',
             'docs/organizer/RULES_RECONCILIATION.md','docs/RELEASE_GATES.md',
             'tools/discard/resource_launcher.py','tools/discard/validate_supplied_engine.py',
             'tests/organizer/test_supplied_engine.py','vendor/organizer/manifest.json',
             'docs/organizer/attachments/manifest.json'):
    paths[name]=ROOT/name
for p in sorted((ROOT/'evidence/organizer_runner').rglob('*')):
    if p.is_file() and (p.name=='measurements.json' or p.parent.name=='tests'):
        paths[p.relative_to(ROOT).as_posix()]=p
# Manifest pins raw evidence too, without needlessly duplicating all match logs.
evidence={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'evidence/organizer_runner').rglob('*')) if p.is_file()}
for name,p in paths.items():
    dst=OUT/'snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
readme=OUT/'README.md'
readme.write_text('''# Supplemental validation — 2 November 2026

This is evidence for the **unchanged Discard v1 candidate**, not a new policy.
Use the original `releases/discard/v1/bot.py` or `submission.zip` for the upload-shaped artifact. Do not upload this validation folder or the full workspace bundle.

Six full supplied-engine matches passed with clocks enabled and zero notices: two direct CLI, four externally measured/resource-constrained. All118 tests pass. The identical opposing candidate loses212 in the1000-hand mirror, so this is not a universal nonloss or tournament-strength claim.

Read snapshot/docs/discard/SUPPLIED_ENGINE_VALIDATION.md and snapshot/docs/organizer/CLOCK_CLARIFICATION.md. Internal documentation links describe the original workspace layout; use the full organized bundle for those linked sources. The clock clarification is a draft, not sent. ActualPython3.11 and OS-enforced host sandbox remain untested.

manifest.json hashes this immutable snapshot, the original candidate/artifact, and the separately preserved raw evidence. Existingv1 files are not rewritten. Measurements and audit probes are external tools, not submission code.
''')
frozen={p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
m=dict(validation='discard-v1-supplied-engine-2026-11-02',policy_changed=False,official_ready=False,
       candidate=dict(path='releases/discard/v1/bot.py',bytes=bot.stat().st_size,sha256=sha(bot)),
       submission_sha256=sha(bot.parent/'submission.zip'),
       python_execution='3.13.16',python_311_execution_verified=False,full_os_sandbox_verified=False,
       tests=dict(supplied_engine=10,discard=21,cora_and_guarantees=53,v2=34,total=118),
       direct_cli_full_matches=2,instrumented_full_matches=4,clocks_enabled=True,
       mirror_other_candidate_net=-212,clock_report_sent=False,
       frozen_files=frozen,evidence_files=evidence)
(OUT/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
print(json.dumps(dict(folder=str(OUT),files=len(frozen),manifest_sha256=sha(OUT/'manifest.json')),indent=2))
