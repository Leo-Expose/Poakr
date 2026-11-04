from pathlib import Path
import hashlib,json,shutil
R=Path('/home/user/pokerbot');H=R.parent;moves={}
if (R/'evidence/migration/path_map.json').exists():raise SystemExit('One-time migration already recorded; refusing replay.')
def move(a,b):
 a=Path(a);b=Path(b)
 if not a.exists():return
 b.parent.mkdir(parents=True,exist_ok=True)
 old=hashlib.sha256(a.read_bytes()).hexdigest() if a.is_file() else None
 shutil.move(str(a),str(b));moves[str(a.relative_to(H))]=dict(new=str(b.relative_to(H)),sha256=old)
for name in ['README.md','ARCHITECTURE.md','READINESS.md','PROTOCOL_EXAMPLE.md','VALIDATION.md']:move(R/name,R/'docs/v2'/name)
for name in ['REPORT.md','PROOFS.md','REPRODUCE.md','PROTOCOL_CORA_EXAMPLE.md']:move(R/'research'/name,R/'docs/cora'/name)
for name in ['CORA_REPORT.md','CORA_PROOFS.md','CORA_REPRODUCE.md','CORA_PROTOCOL_EXAMPLE.md']:move(H/name,R/'docs/archive/cora_v1_exports'/name)
for name in ['build_cora.py','experiment.py','make_preflop.py','microbench.py','package_cora.py','resource_cora.py']:move(R/'research'/name,R/'tools/cora'/name)
for name in ['test_research.py','test_stream.py']:move(R/'research'/name,R/'tests/cora'/name)
move(R/'research/preflop.json',R/'data/preflop/preflop.json');move(R/'research/preflop.log',R/'data/preflop/generation.log')
move(R/'research/example_cora.jsonl',R/'fixtures/cora/example_session.jsonl')
move(R/'research/cora_bot.py',R/'releases/cora/v1/cora_bot.py');move(R/'research/manifest.json',R/'releases/cora/v1/manifest.json')
move(H/'cora_bot_example.py',R/'releases/cora/v1/cora_bot_example.py');move(H/'cora_research.zip',R/'releases/cora/v1/cora_research.zip')
move(H/'pokerbot_v2_audited.zip',R/'releases/v2/pokerbot_v2_audited.zip');move(R/'releases/manifest.json',R/'releases/v2/manifest.json')
move(H/'pokerbot_hardened.zip',R/'releases/v1/pokerbot_hardened.zip')
move(R/'research/archive',R/'evidence/archive/cora')
for p in list((R/'research').iterdir()):
 if p.suffix not in ('.json','.log'):continue
 n=p.name
 category=('confirmation' if n.startswith(('confirmation','summary')) else 'exploration' if n.startswith('exploratory') else 'holdout' if n.startswith(('holdout','strong_baselines')) else 'benchmarks' if n.startswith(('microbench','resource')) else 'tests' if n in ('tests.log','stream_tests.log') else 'smoke' if n.startswith('smoke') else 'inventory')
 move(p,R/'evidence/cora'/category/n)
for p in list((R/'tests').iterdir()):
 if p.suffix in ('.json','.log'):move(p,R/'evidence/v2'/p.name)
for p in list((R/'bench').iterdir()):
 if p.suffix in ('.json','.log'):move(p,R/'evidence/legacy_bench'/p.name)
(R/'evidence/migration').mkdir(parents=True,exist_ok=True)
(R/'evidence/migration/path_map.json').write_text(json.dumps(moves,indent=2))
# Update live tooling, NOT algorithms, frozen artifacts, or historical results.
repl={}
for old,row in moves.items():
 if old.startswith('pokerbot/') and row['new'].startswith('pokerbot/'):
  repl[old[len('pokerbot/'):]]=row['new'][len('pokerbot/'):]
for p in list((R/'tools/cora').glob('*.py'))+list((R/'tests/cora').glob('*.py'))+list((R/'bench').glob('*.py')):
 if p.name=='package_cora.py':continue
 s=p.read_text()
 for a,b in sorted(repl.items(),key=lambda x:-len(x[0])):s=s.replace(a,b)
 if p.parent in (R/'tools/cora',R/'tests/cora'):s=s.replace('Path(__file__).resolve().parent.parent','Path(__file__).resolve().parents[2]')
 if p.name=='experiment.py':s=s.replace("ROOT/'research'/args.output","ROOT/'evidence/cora/reruns'/args.output").replace("results=[];status=", "(ROOT/'evidence/cora/reruns').mkdir(parents=True,exist_ok=True)\n    results=[];status=")
 if p.name=='build_cora.py':s=s.replace("out=ROOT/'releases/cora/v1/cora_bot.py';out.write_text(code)","out=ROOT/'releases/cora/current/cora_bot.py';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(code)")
 if p.name in ('microbench.py','resource_cora.py'):
  s=s.replace("ROOT/'evidence/cora/benchmarks/", "ROOT/'evidence/cora/reruns/")
  s=s.replace("ROOT=Path(__file__).resolve().parents[2]", "ROOT=Path(__file__).resolve().parents[2];(ROOT/'evidence/cora/reruns').mkdir(parents=True,exist_ok=True)")
 if p.name=='matches_v2.py':s=s.replace("ROOT/'tests'/args.output", "ROOT/'evidence/v2'/args.output")
 if p.name=='package_v2.py':
  s=s.replace("ROOT/'VALIDATION.md'", "ROOT/'releases/v2/rebuilt/VALIDATION.md'")
  for n in ['README.md','READINESS.md','VALIDATION.md','ARCHITECTURE.md','PROTOCOL_EXAMPLE.md']:s=s.replace("'"+n+"'", "'docs/v2/"+n+"'")
  s=s.replace("ROOT/'releases/v2/manifest.json'", "ROOT/'releases/v2/rebuilt/manifest.json'")
  s=s.replace("include.append('releases/v2/manifest.json')", "include.append('releases/v2/rebuilt/manifest.json')")
  s=s.replace("path=ROOT.parent/'pokerbot_v2_audited.zip'", "path=ROOT/'releases/v2/rebuilt/pokerbot_v2_audited.zip'")
  s=s.replace("ROOT=Path(__file__).resolve().parent.parent", "ROOT=Path(__file__).resolve().parent.parent\n(ROOT/'releases/v2/rebuilt').mkdir(parents=True,exist_ok=True)")
 p.write_text(s)
# Track migration without rewriting frozen source-name keys in old evidence.
for n in ['research/kernels.py','research/agent.py','runtime/bot.py']:
 assert hashlib.sha256((R/n).read_bytes()).hexdigest()==json.loads((R/'evidence/cora/confirmation/confirmation_results.json').read_text())['sources'][n]
for category in ['confirmation','exploration','holdout','benchmarks','tests','smoke','inventory']:(R/'evidence/cora'/category).mkdir(parents=True,exist_ok=True)
print('Migrated',len(moves),'entries; frozen algorithm hashes unchanged.')
