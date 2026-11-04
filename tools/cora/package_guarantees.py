"""Freeze research v1 once; never rewrite an existing snapshot.
The archive is a reference overlay, NOT a complete/official poker submission.
"""
import hashlib
import json
import re
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'releases/guarantees/v1'
ARCHIVE = OUT/'proof_controller_research.zip'
if ARCHIVE.exists() or (OUT/'manifest.json').exists():
    raise SystemExit('Research v1 is already frozen. Use a separately reviewed version, not an overwrite.')
OUT.mkdir(parents=True, exist_ok=True)

def test_count(name):
    log = (ROOT/name).read_text()
    if not log.rstrip().endswith('OK'):
        raise RuntimeError('passing log required: '+name)
    return int(re.search(r'Ran (\d+) tests',log).group(1))

assert test_count('evidence/guarantee_lab/tests.log') == 12
assert test_count('evidence/guarantee_lab/settlement_tests.log') == 18
benchmark = json.loads((ROOT/'evidence/guarantee_lab/settlement_results.json').read_text())
for name, digest in benchmark['source_sha256'].items():
    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest, name
for row in benchmark['results']:
    assert row['final_raw'] == 2 and not row['forbidden_attempts']
files = {}
for directory in ('research/guarantee_lab','docs/guarantees','evidence/guarantee_lab'):
    for p in sorted((ROOT/directory).rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.md','.json','.log'):
            files[p.relative_to(ROOT).as_posix()] = p.read_bytes()
for name in ('research/kernels.py','runtime/bot.py','tests/cora/test_guarantees.py',
             'tests/cora/test_settlement.py','tools/cora/guarantee_lab.py','tools/cora/settlement_bench.py',
             'tools/cora/package_guarantees.py','docs/RELEASE_GATES.md'):
    files[name] = (ROOT/name).read_bytes()
files['README.md'] = b'''# Proof-aware poker controller research v1\n\nThis is an isolated, source-pinned reference overlay, not a complete poker policy\nor an organizer-compatible submission. Standard verified synthetic rules only.\nStart at docs/guarantees/CONTROLLER.md and IMPLEMENTATION_REPORT.md.\n\nRun from this directory with NumPy and SciPy already installed:\n\n    OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s tests/cora -p 'test_*.py' -v\n    python3 tools/cora/settlement_bench.py\n\nThis snapshot contains 30 guarantee/controller tests. The broader workspace\nreported 53 CORA/guarantee plus 34 v2 tests; the unrelated tests are not included\nhere. Actual execution used Python 3.13.16; required Python 3.11 is unverified.\nThere are no runtime installs/network calls. The turn path uses only stdlib;\nthe cold river proof uses NumPy; the offline toy minimax lab uses SciPy.\n\nHost facts and rules need verification by a real adapter. No universal strict\ninitial-state victory, official time-bank survival, or tournament claim is made.\nThe ZIP is immutable; reruns on an extracted copy do not change this archive.\n'''
manifest = dict(release='proof-controller-research-v1',official_ready=False,
                complete_poker_policy=False,published_bots_changed=False,
                tests=dict(mathematical=12,controller=18),python_execution='3.13.16',
                python_311_execution_verified=False,
                files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in sorted(files.items())})
manifest_bytes = (json.dumps(manifest,indent=2)+'\n').encode()
(OUT/'manifest.json').write_bytes(manifest_bytes)
files['releases/guarantees/v1/manifest.json'] = manifest_bytes
with zipfile.ZipFile(ARCHIVE,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,data in sorted(files.items()):
        entry = zipfile.ZipInfo('pokerbot_guarantees/'+name,date_time=(2026,10,15,0,0,0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o644 << 16
        z.writestr(entry,data)
with zipfile.ZipFile(ARCHIVE) as z:
    assert z.testzip() is None
    for name,data in files.items(): assert z.read('pokerbot_guarantees/'+name) == data
print(json.dumps(dict(archive=str(ARCHIVE),bytes=ARCHIVE.stat().st_size,files=len(files),
                     sha256=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()),indent=2))
