"""Offline-only capability probe. Never downloads or installs anything.
No champion import changes. OpenSpiel is NOT an allowed submission dependency.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def probe():
    result=dict(python=sys.version.split()[0],installed={},open_spiel_execution=False,
        target_game_adapter_implemented=False,target_game_validated=False,champion_changed=False,
        submission_dependency_allowed=False,install_attempted=False)
    for name in ('pyspiel','open_spiel'):
        try:spec=importlib.util.find_spec(name)
        except ModuleNotFoundError:spec=None
        result['installed'][name]=bool(spec)
    if not all(result['installed'].values()):
        result['status']='missing optional offline research dependency; no OpenSpiel algorithms executed'
        return result
    import pyspiel
    names=pyspiel.registered_names()
    result.update(open_spiel_execution=True,registered_games=len(names),
        kuhn_registered='kuhn_poker' in names,universal_poker_registered='universal_poker' in names,
        status='basic API probe only; no CFR training, target adapter or exploitability result')
    if result['kuhn_registered']:
        game=pyspiel.load_game('kuhn_poker')
        result['kuhn_num_players']=game.num_players()
        result['kuhn_initial_is_chance']=game.new_initial_state().is_chance_node()
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
    out=ROOT/a.output
    if out.exists():raise SystemExit('Fresh output path required')
    result=probe();out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
