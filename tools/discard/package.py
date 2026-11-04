"""Freeze the PDF-backed candidate and its honest evidence; never overwrite v1."""
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'releases/discard/v1'
if OUT.exists():raise SystemExit('Discard candidate v1 already exists; do not overwrite a frozen version.')
source=ROOT/'releases/discard/current/bot.py'
code=source.read_bytes();digest=hashlib.sha256(code).hexdigest()
assert len(code)<5_000_000
log=(ROOT/'evidence/discard/tests.log').read_text()
assert log.rstrip().endswith('OK') and int(re.search(r'Ran (\d+) tests',log)[1])==21
names=['constrained_400.json','constrained_1000.json','constrained_400_shove.json','constrained_400_aggressor.json','loss_witness_16.json']
rows=[]
for name in names:
    row=json.loads((ROOT/'evidence/discard'/name).read_text());rows.append(row)
    assert row['standalone_sha256']==digest and row['invalid_responses']==0
    meta=row['runtime_metadata']
    assert meta['errors']==0 and meta['score_trusted'] and not meta['forbidden_attempts']
    assert meta['completed']==row['hands'] and meta['score']==row['net']
    assert row['candidate_request_wall_s']<row['time_bank_ms']/1000 and row['candidate_max_reply_s']<5 and meta['ready_s']<5
assert rows[-1]['net']==-229  # retain the failure, do not market universal victory
OUT.mkdir(parents=True)
(OUT/'bot.py').write_bytes(code)
with zipfile.ZipFile(OUT/'submission.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    info=zipfile.ZipInfo('bot.py',date_time=(2026,10,31,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16
    z.writestr(info,code)
with zipfile.ZipFile(OUT/'submission.zip') as z:
    assert z.namelist()==['bot.py'] and z.read('bot.py')==code and z.testzip() is None
(OUT/'evidence').mkdir()
(OUT/'docs/discard').mkdir(parents=True)
shutil.copytree(ROOT/'docs/organizer',OUT/'docs/organizer')
for name in names+['tests.log']:shutil.copyfile(ROOT/'evidence/discard'/name,OUT/'evidence'/name)
for name in ('REPORT.md','GUARANTEES.md'):shutil.copyfile(ROOT/'docs/discard'/name,OUT/'docs/discard'/name)
paths=[ROOT/'engine/numpy_eval.py',*list((ROOT/'research/discard_holdem').glob('*.py')),
       *list((ROOT/'tools/discard').glob('*.py')),*list((ROOT/'tests/discard').glob('*.py'))]
manifest=dict(release='discard-holdem-pdf-candidate-v1',date='2026-10-31',protocol_version='1.0',
              official_ready=False,organizer_runner_validated=False,problem_statement_present=False,
              python_execution='3.13.16',python_311_execution_verified=False,
              duplicate_inference=False,published_legacy_algorithms_unchanged=True,
              universal_initial_state_nonloss=False,new_variant_tests=21,
              bot_bytes=len(code),bot_sha256=digest,
              submission_zip_sha256=hashlib.sha256((OUT/'submission.zip').read_bytes()).hexdigest(),
              source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)},
              supplied_pdf_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'docs/organizer/attachments').glob('*.pdf')},
              frozen_files={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.rglob('*')) if p.is_file()})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(directory=str(OUT),bot_sha256=digest,bot_bytes=len(code),
                     submission_zip_bytes=(OUT/'submission.zip').stat().st_size,official_ready=False),indent=2))
