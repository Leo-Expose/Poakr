"""Package organized source/docs/evidence; refresh only the replaceable organized bundle; never rewrite frozen releases."""
import json,hashlib,zipfile,runpy,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT/'tools/maintenance/verify_workspace.py'),run_name='__main__')
out=ROOT/'releases/organized';out.mkdir(parents=True,exist_ok=True)
def tested_count(name):
    log=(ROOT/name).read_text()
    if not log.rstrip().endswith('OK'):raise RuntimeError('passing log required: '+name)
    return int(re.search(r'Ran (\d+) tests',log).group(1))

files={}
for directory in ('runtime','src','engine','policies','legacy','bench','research','tools','tests','docs','data','config','fixtures','evidence','vendor'):
    for p in sorted((ROOT/directory).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.md','.log','.jsonl','.txt','.pdf') and p.relative_to(ROOT).as_posix() != 'evidence/migration/organized_packaging.log':
            files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
files['README.md']=(ROOT/'README.md').read_bytes()
for p in (ROOT/'releases').rglob('*'):
    if p.is_file() and 'organized' not in p.parts and p.suffix in ('.py','.json','.zip','.md','.pdf','.log'):
        files[p.relative_to(ROOT).as_posix()]=p.read_bytes()
manifest=dict(release='organized-workspace-2026-11-02',official_ready=False,
              frozen_cora_policy_unchanged=True,new_guarantees_integrated=False,
              tests=dict(cora_and_guarantees=tested_count('evidence/openspiel/2026_11_02/tests_cora.log'),v2=tested_count('evidence/openspiel/2026_11_02/tests_v2.log'),discard=tested_count('evidence/openspiel/2026_11_02/tests_discard.log'),supplied_engine=tested_count('evidence/openspiel/2026_11_02/tests_organizer.log'),openspiel_objective_contract=tested_count('evidence/openspiel/2026_11_02/tests.log')),python_execution='3.13.16; actual 3.11 pending',
              files={n:dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest()) for n,b in sorted(files.items())})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
files['releases/organized/manifest.json']=(out/'manifest.json').read_bytes()
archive=out/'pokerbot_workspace.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for n,b in sorted(files.items()):
        info=zipfile.ZipInfo('pokerbot/'+n,date_time=(2026,11,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        info.external_attr=(0o755 if n.endswith("tools/discard/resource_launcher.py") else 0o644)<<16;z.writestr(info,b)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for n,b in files.items():assert z.read('pokerbot/'+n)==b
print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,files=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest()),indent=2))
