"""Public-information red team. Local engine diagnostics, not tournament odds."""
import argparse
import hashlib
import json
import random
import runpy
import sys
import time
from itertools import combinations
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.discard.local_runner import Client,LocalMatch,Opponent
from research.discard_holdem.proofs import card,text_card
from research.discard_holdem.partial_eval import eval_made

PROFILES=('CallingStation','CheckFold','Shove','Aggressor','ValueNit','Trap','SmallBall','Switch')

class RedTeam(Opponent):
    """Own cards + public state only. No duplicate or future-board memory."""
    def __init__(self,kind,seed=91):
        super().__init__(kind,seed);self.hid=0
    def handle(self,msg):
        kind=msg['type']
        if kind=='new_hand':self.hid=msg['hand_id']
        if self.kind in ('CallingStation','CheckFold','Shove','Aggressor'):
            return super().handle(msg)
        if kind=='new_hand':self.hole=tuple(map(card,msg['hole_cards']))
        if kind=='discard_result':self.hole=tuple(map(card,msg['hole_cards']))
        if kind=='discard_request':
            board=tuple(map(card,msg['board']));pairs=list(combinations(self.hole,2))
            scores=eval_made(np.array([p+board for p in pairs],dtype=np.int64))
            keep=pairs[int(np.argmax(scores))]
            return dict(type='discard',card=text_card(next(c for c in self.hole if c not in keep)))
        if kind!='action_request':return None
        board=tuple(map(card,msg['board']));ranks=[c//4 for c in self.hole]
        if board:
            pairs=list(combinations(self.hole,2));scores=eval_made(np.array([p+board for p in pairs],dtype=np.int64))
            score=int(max(scores));cat=score>>20
            # Do not value a pair supplied entirely by the public board as a hole pair.
            hits=any(c//4 in ranks for c in board) or len(set(ranks))<len(ranks)
            premium=cat>=2 or (cat==1 and hits and max(ranks)>=8)
            playable=cat>=1 and hits
        else:
            premium=(len(set(ranks))<len(ranks) and max(ranks)>=8) or sum(r>=10 for r in ranks)>=2
            playable=len(set(ranks))<len(ranks) or max(ranks)>=10
        legal=msg['legal_actions'];owed=msg['to_call'];pot=msg['pot']
        mode=self.kind
        if mode=='Switch':mode='ValueNit' if (self.hid-1)//40%2==0 else 'SmallBall'
        raise_it=False;fold_it=False
        if mode=='ValueNit':
            raise_it=premium;fold_it=owed>0 and (not playable or owed>max(8,pot*.35) and not premium)
        elif mode=='Trap':
            raise_it=premium and (len(board)>=4 or owed>2)
            fold_it=owed>0 and not playable and owed>2
        elif mode=='SmallBall':
            raise_it=self.rng.random()<.8
            fold_it=owed>max(6,pot*.55) and not premium
        if fold_it and 'fold' in legal:return dict(type='action',action='fold')
        if raise_it and 'raise' in legal:
            amount=msg['min_raise'] if mode=='SmallBall' else msg['max_raise']
            return dict(type='action',action='raise',amount=amount)
        return dict(type='action',action='call' if owed else 'check')


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def run(bot_path,seeds,profiles,hands,out):
    out=Path(out)
    if out.exists():raise ValueError('fresh output required')
    klass=runpy.run_path(str(bot_path),run_name='redteam_candidate')['DiscardBot']
    rows=[];started=time.monotonic()
    for seed in seeds:
        for profile in profiles:
            hero=klass();other=RedTeam(profile,seed+57)
            # Alternate starting position across seeds; all seats alternate within matches.
            pos=seed%2;clients=[Client(hero),Client(other)] if pos==0 else [Client(other),Client(hero)]
            match=LocalMatch(*clients,hands=hands,seed=seed)
            result=match.run();net=match.net[pos]
            assert hero.completed==hands and hero.score==net and hero.errors==0 and hero.score_trusted
            assert match.invalid==0 and clients[pos].max_reply<5 and clients[pos].spent<match.bank_ms/1000
            row=dict(seed=seed,opponent=profile,candidate_position=pos,hands=hands,net=net,
                     raw_request_s=clients[pos].spent,max_reply_s=clients[pos].max_reply,
                     proofs=hero.proof_arms,reserve=hero.reserve,errors=hero.errors,
                     ledger_trusted=hero.score_trusted,notices=match.invalid)
            rows.append(row)
            print(json.dumps(row),flush=True)
            # Preserve partial completed results even if a later assertion fails.
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps(dict(candidate=str(bot_path.relative_to(ROOT)),candidate_sha256=sha(bot_path),
                    engine_sha256=sha(ROOT/'tools/discard/local_runner.py'),redteam_sha256=sha(Path(__file__)),
                    scope='in-process independent local engine; no OS sandbox or tournament-rate claim',
                    complete=False,rows=rows),indent=2)+'\n')
    data=json.loads(out.read_text());data.update(complete=True,wall_s=time.monotonic()-started,
        summary=dict(matches=len(rows),wins=sum(r['net']>0 for r in rows),draws=sum(r['net']==0 for r in rows),
                     losses=sum(r['net']<0 for r in rows),total_net=sum(r['net'] for r in rows),worst_net=min(r['net'] for r in rows)))
    out.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps(data['summary']),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bot',default='releases/discard/v1/bot.py')
    p.add_argument('--seeds',required=True);p.add_argument('--profiles',default=','.join(PROFILES));p.add_argument('--hands',type=int,default=400)
    p.add_argument('--output',required=True);a=p.parse_args()
    run((ROOT/a.bot).resolve(),[int(s) for s in a.seeds.split(',')],a.profiles.split(','),a.hands,ROOT/a.output)
