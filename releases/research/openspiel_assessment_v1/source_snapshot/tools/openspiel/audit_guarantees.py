"""Run own exact objective audit + actual-variant shared-royal rank witness.
No OpenSpiel dependency, no strategy modification, no installed packages.
"""
import argparse
import hashlib
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from research.openspiel_bridge.objectives import audit_objectives
from research.discard_holdem.proofs import card,text_card,river_geometry


def royal_witness():
    hero=tuple(map(card,['2c','3d']));board=tuple(map(card,['Ts','Js','Qs','Ks','As']));dead=tuple(map(card,['4h','7h']))
    relation,pairs,q=river_geometry(hero,board,dead)
    spec=importlib.util.spec_from_file_location('witness_supplied_engine',ROOT/'vendor/organizer/Starter_Kit/engine.py')
    vendor=importlib.util.module_from_spec(spec);spec.loader.exec_module(vendor)
    own=vendor.best_hand(list(map(text_card,hero)),list(map(text_card,board)))
    remaining=[c for c in range(52) if c not in hero+board+dead]
    tested=0
    for peer in combinations(remaining,2):
        assert vendor.best_hand(list(map(text_card,peer)),list(map(text_card,board)))==own
        tested+=1
    assert relation==0 and pairs==tested==903 and q==.5 and own==(8,14)
    return dict(hero=['2c','3d'],board=['Ts','Js','Qs','Ks','As'],public_discards=['4h','7h'],
        physical_retained_peer_pairs=tested,all_pairs_tie=True,rank_relation=relation,
        supplied_engine_agrees=True,hand_rank=list(own),
        opponent_policy='always check/call; discard any legal private card; never fold',
        upper_bound_for_hero_hand_net=0,
        argument='At matched showdown both play the royal board and net0; hero folding loses its contribution. Equal reset stacks let the opponent match every legal wager. Repeat legal royal-board duplicate deals: total net cannot be positive.',
        scope='Strict-win counterexample for the actual variant. Does NOT by itself disprove every hypothetical universal nonloss strategy.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    out=ROOT/a.output
    if out.exists():raise SystemExit('Fresh output path required')
    start=time.perf_counter();result=dict(own_kuhn_objective_audit=audit_objectives(),actual_variant_royal_witness=royal_witness(),
        open_spiel_executed=False,champion_changed=False,scope='Exact small-game audit and actual-variant rank witness; no full Discard minimax/exploitability solution')
    result['wall_s']=time.perf_counter()-start
    paths=['research/openspiel_bridge/objectives.py','research/guarantee_lab/kuhn.py','research/discard_holdem/proofs.py','tools/openspiel/audit_guarantees.py','vendor/organizer/Starter_Kit/engine.py','releases/discard/v1/bot.py']
    result['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
