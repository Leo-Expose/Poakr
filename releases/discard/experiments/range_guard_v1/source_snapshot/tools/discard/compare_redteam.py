"""Apply predeclared red-team gates; do not silently relax a failed gate."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'evidence/discard/redteam_2026_11_02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
freeze=json.loads((OUT/'experimental_freeze.json').read_text())
for name,digest in freeze['files'].items():assert sha(ROOT/name)==digest,name
base=json.loads((OUT/'holdout_v1.json').read_text());trial=json.loads((OUT/'holdout_experimental.json').read_text())
assert base['complete'] and trial['complete']
assert base['candidate_sha256']=='2de972289c37024c9283d8c29b273c694a2f229d67309ac347cfb7cfff7bb907'
assert trial['candidate_sha256']==freeze['files']['releases/discard/experimental/bot.py']
assert base['redteam_sha256']==trial['redteam_sha256']==freeze['files']['tools/discard/redteam.py']
assert [(r['seed'],r['opponent']) for r in base['rows']]==[(r['seed'],r['opponent']) for r in trial['rows']]
for p in OUT.glob('*_v1.json'):
    d=json.loads(p.read_text())
    for row in d['rows']:
        assert row['errors']==0 and row['notices']==0 and row['ledger_trusted']
        if row['reserve'] is not None:assert row['net']>=row['reserve']
for p in OUT.glob('*_experimental.json'):
    d=json.loads(p.read_text())
    for row in d['rows']:
        assert row['errors']==0 and row['notices']==0 and row['ledger_trusted']
        if row['reserve'] is not None:assert row['net']>=row['reserve']
test_log=(OUT/'tests_discard.log').read_text()
assert 'Ran 32 tests' in test_log and test_log.rstrip().endswith('OK')
a,b=base['summary'],trial['summary']
gates=dict(new_and_existing_discard_tests_pass=True,at_least_baseline_wins=b['wins']>=a['wins'],higher_total_net=b['total_net']>a['total_net'],
           no_worse_worst_match=b['worst_net']>=a['worst_net'],all_recorded_floors_preserved=True,
           all_protocol_ledgers_valid=True,frozen_source_identities=True)
profiles=[]
for name in dict.fromkeys(r['opponent'] for r in base['rows']):
    x=[r['net'] for r in base['rows'] if r['opponent']==name];y=[r['net'] for r in trial['rows'] if r['opponent']==name]
    profiles.append(dict(opponent=name,baseline_nets=x,experimental_nets=y,baseline_total=sum(x),experimental_total=sum(y),
        baseline_capped_total=sum(max(-400,min(400,n)) for n in x),experimental_capped_total=sum(max(-400,min(400,n)) for n in y)))
verdict=dict(baseline=a,experimental=b,gates=gates,eligible_for_next_validation_gate=all(gates.values()),promoted=False,
    champion='releases/discard/v1/bot.py',
    explanation='Experimental worst holdout net is7 versus baseline12; predeclared worst-result gate fails. Keep v1. Larger net is not perfect play.',
    supplied_engine_experimental_validation='Not attempted: preceding strength gate failed; original v1 supplied-engine evidence remains valid.',
    paired_net_better=sum(y['net']>x['net'] for x,y in zip(base['rows'],trial['rows'])),
    paired_net_equal=sum(y['net']==x['net'] for x,y in zip(base['rows'],trial['rows'])),
    paired_net_worse=sum(y['net']<x['net'] for x,y in zip(base['rows'],trial['rows'])),profiles=profiles,
    baseline_capped_total=sum(p['baseline_capped_total'] for p in profiles),experimental_capped_total=sum(p['experimental_capped_total'] for p in profiles),
    scope='fixed small local diagnostic holdout; not tournament odds, universal nonloss, minimax, or OS/runtime certification')
(OUT/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n')
print(json.dumps(verdict,indent=2))
