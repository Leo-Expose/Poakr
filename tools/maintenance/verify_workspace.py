"""Verify relocated frozen inputs/releases without rewriting historical evidence."""
from pathlib import Path
import hashlib,json,ast,zipfile
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
map_=json.loads((ROOT/'evidence/migration/path_map.json').read_text())
def resolve_historical(name):
    p=ROOT/name
    if p.exists():return p
    old='pokerbot/'+name
    if old in map_:return ROOT.parent/map_[old]['new']
    for prefix,row in sorted(map_.items(),key=lambda x:-len(x[0])):
        if old.startswith(prefix+'/'):return ROOT.parent/(row['new']+old[len(prefix):])
    raise FileNotFoundError(name)
confirmation=json.loads((ROOT/'evidence/cora/confirmation/confirmation_results.json').read_text())
for name,digest in confirmation['sources'].items():assert sha(resolve_historical(name))==digest,name
assert sha(ROOT/'runtime/bot.py')=='27c303582022e1320e3cad286021c93526c345819567cd6380052c113d522bbb','frozen v2 runtime'
expected='5473fdf8975fe812c35cb87f4937bb516bb278f0a11b89daa9e935130bc5ae36'
for name in ('releases/cora/v1/cora_bot.py','releases/cora/v1/cora_bot_example.py','releases/cora/current/cora_bot.py'):
    p=ROOT/name
    if p.exists():assert sha(p)==expected,name
for row in json.loads((ROOT/'evidence/cora/benchmarks/resource_results.json').read_text()):assert row['standalone_sha256']==expected
archives=[]
for old,row in map_.items():
    if old.endswith('.zip'):
        p=ROOT.parent/row['new'];assert sha(p)==row['sha256'],old
        with zipfile.ZipFile(p) as z:assert z.testzip() is None
        archives.append(str(p.relative_to(ROOT)))
research_archive=ROOT/'releases/guarantees/v1/proof_controller_research.zip'
if research_archive.exists():
    with zipfile.ZipFile(research_archive) as z:
        assert z.testzip() is None
        m=json.loads(z.read('pokerbot_guarantees/releases/guarantees/v1/manifest.json'))
        assert json.loads((ROOT/'releases/guarantees/v1/manifest.json').read_text())==m
        for name,row in m['files'].items():
            data=z.read('pokerbot_guarantees/'+name)
            assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],name
discard_manifest=ROOT/'releases/discard/v1/manifest.json'
if discard_manifest.exists():
    m=json.loads(discard_manifest.read_text());folder=discard_manifest.parent
    assert sha(folder/'bot.py')=='2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907'
    for name,digest in m['frozen_files'].items():assert sha(folder/name)==digest,name
    with zipfile.ZipFile(folder/'submission.zip') as z:
        assert z.namelist()==['bot.py'] and z.testzip() is None
        assert z.read('bot.py')==(folder/'bot.py').read_bytes()
supplement=ROOT/'releases/discard/validated_2026_11_02/manifest.json'
if supplement.exists():
    m=json.loads(supplement.read_text())
    assert sha(ROOT/m['candidate']['path'])==m['candidate']['sha256']
    assert sha(ROOT/'releases/discard/v1/submission.zip')==m['submission_sha256']
    for name,digest in m['frozen_files'].items():assert sha(supplement.parent/name)==digest,name
    for name,digest in m['evidence_files'].items():assert sha(ROOT/name)==digest,name
experiment=ROOT/'releases/discard/experiments/range_guard_v1/manifest.json'
if experiment.exists():
    m=json.loads(experiment.read_text())
    assert not m['promoted'] and sha(experiment.parent/'bot.py')==m['candidate_sha256']
    assert sha(ROOT/'releases/discard/v1/bot.py')==m['champion_sha256']
    for name,digest in m['frozen_files'].items():assert sha(experiment.parent/name)==digest,name
    for name,digest in m['evidence_files'].items():assert sha(ROOT/name)==digest,name
open_research=ROOT/'releases/research/openspiel_assessment_v1/manifest.json'
if open_research.exists():
    m=json.loads(open_research.read_text())
    assert not m['open_spiel_executed'] and not m['champion_changed']
    assert sha(ROOT/'releases/discard/v1/bot.py')==m['champion_sha256']
    for name,digest in m['frozen_files'].items():assert sha(open_research.parent/name)==digest,name
vendor=ROOT/'vendor/organizer/manifest.json'
if vendor.exists():
    m=json.loads(vendor.read_text())
    for name,digest in m['files'].items():assert sha(vendor.parent/'Starter_Kit'/name)==digest,name
    assert sha(vendor.parent/'combined_files.md')==m['source_sha256']
for name,row in json.loads((ROOT/'docs/organizer/attachments/manifest.json').read_text()).items():
    assert sha(ROOT/'docs/organizer/attachments'/name)==row['sha256'],name
for p in ROOT.rglob('*.py'):
    if '__pycache__' not in p.parts:ast.parse(p.read_text(),feature_version=(3,11))
print(json.dumps(dict(frozen_source_hashes_verified=True,frozen_standalone_sha256=expected,
                     frozen_zip_hashes_verified=archives,grammar_target='3.11',python_311_execution_verified=False),indent=2))
