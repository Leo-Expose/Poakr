#!/usr/bin/env python3
"""Fresh-seed strategy regression; frozen v1 vs v2, isolated models and public events.
Synthetic standard-Hold'em runner, not the official protocol or variant.
"""
import sys, json, time, random, argparse, statistics, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'bench'))
RUNTIME_SHA256=hashlib.sha256((ROOT/'runtime/bot.py').read_bytes()).hexdigest()
from runtime import bot as b
from engine.game import Game, GameConfig, HandState
from fullmatch import FullBot, OverFolder, CallingStation, Balanced, Aggressor


class CoreBot:
    def __init__(self,mode='board',bluff=True,seed=123):
        self.session=b.BotSession('match',settings=b.Settings(duplicate_mode=mode,proactive_bluff=bluff),seed=seed)
        self.hand_id='0'; self.hands_left=120; self.lead=0; self.seq=0
    def set_context(self,hand_id,hands_left,lead):
        self.hand_id=str(hand_id); self.hands_left=hands_left; self.lead=lead
    def decide(self,obs):
        mapping={}
        for old in obs['legal']:
            action=b.Action(old[0],min(obs['to_call']+obs['pot']*old[1],obs['my_stack']) if old[0]=='bet' else 0)
            mapping.setdefault(action,old)
        o=b.Observation(str(self.session.decisions),self.hand_id,tuple(sorted(obs['hole'])),tuple(obs['board']),obs['pot'],obs['to_call'],
                        obs['my_stack'],obs['opp_stack'],tuple(mapping),chip_lead=self.lead,hands_left=self.hands_left)
        action=self.session.act(o)
        assert action in mapping
        return mapping[action]
    def learn_public(self,history,seat,cfg):
        # Reconstruct only public chips/streets to calculate actual faced size,
        # including capped all-ins. No hole or future board cards are consulted.
        game=Game(cfg); st=HandState(cfg,[[],[]],[])
        for p,blind in ((0,cfg.sb),(1,cfg.bb)):
            st.stacks[p]-=blind; st.committed[p]+=blind; st.total_in[p]+=blind
        previous=None
        for street,p,act in history:
            if street!=st.street:
                st.pot+=sum(st.committed); st.committed=[0.,0.]; st.street=street; previous=None
            if p!=seat and previous is not None and previous[0]==seat and previous[1]=='bet':
                self.session.opponent.observe(self.seq,street+1,act[0],True,previous[2]); self.seq+=1
            pot=st.middle(); tc=max(0,st.to_call(p)); extra=0
            if act[0]=='bet': extra=max(0,min(tc+act[1]*pot,st.stacks[p])-tc)
            previous=(p,act[0],extra/max(1e-12,pot))
            game.apply(st,p,act)


def match(A,B,deals,seed):
    rng=random.Random(seed); net=0; cfg=GameConfig()
    # No unpublished opponent-hole/reveal data is given to either bot.
    for deal in range(deals):
        dealt=rng.sample(range(52),9)
        for copy in (0,1):
            idx=2*deal+copy; remaining=2*deals-idx
            if isinstance(A,CoreBot): A.set_context(idx,remaining,net)
            else:
                A.hand_id=idx; A.set_match_state(net,remaining/(2*deals))
            if isinstance(B,CoreBot): B.set_context(idx,remaining,-net)
            players=(A,B) if copy==0 else (B,A)
            value,history=Game(cfg,seed+idx).play_hand(dealt,*players)
            net+=value if copy==0 else -value
            A.learn_public(history,copy,cfg) if isinstance(A,CoreBot) else A.learn_public(history,copy)
            if isinstance(B,CoreBot): B.learn_public(history,1-copy,cfg)
    return net


def main():
    p=argparse.ArgumentParser(); p.add_argument('--matches',type=int,default=8); p.add_argument('--deals',type=int,default=60)
    p.add_argument('--seed',type=int,default=43000); p.add_argument('--release-check',action='store_true'); p.add_argument('--no-mirror',action='store_true'); p.add_argument('--output',default='matches_results.json'); args=p.parse_args()
    if Path(args.output).name!=args.output or not args.output.endswith('.json'):
        p.error('--output must be a plain .json filename; reruns never overwrite historical evidence')
    destination=ROOT/'evidence/v2/reruns'/args.output; destination.parent.mkdir(parents=True,exist_ok=True)
    results=[]
    configs=[('v2',True,True),('v2_no_bluff',True,False),('v2_no_info',False,True),('legacy_v1',True,True)]
    if args.release_check: configs=[('v2_release_board',True,False),('legacy_v1',True,True)]
    opponents=[('OverFolder',OverFolder),('CallingStation',CallingStation),('Balanced',Balanced),('Aggressor',Aggressor)]
    for label,dup,bluff in configs:
        for name,factory in opponents:
            nets=[]; info=0; own_time=0; timeouts=0; start=time.perf_counter()
            for i in range(args.matches):
                if label=='legacy_v1': A=FullBot(); A.reset()
                else:
                    A=CoreBot('board' if dup else 'off',bluff,seed=734)
                    A.session.bank.hands_total=2*args.deals
                B=factory(seed=args.seed+200+i)
                nets.append(match(A,B,args.deals,args.seed+i))
                if isinstance(A,CoreBot):
                    info+=A.session.info_decisions; own_time+=A.session.bank.spent; timeouts+=A.session.errors
                else: info+=A.info
            row=dict(config=label,opponent=name,nets=nets,wins=sum(x>0 for x in nets),draws=sum(x==0 for x in nets),
                     losses=sum(x<0 for x in nets),mean_chips=statistics.mean(nets),info_decisions=info,
                     own_compute_s=own_time,deadline_fallbacks=timeouts,wall_s=time.perf_counter()-start)
            results.append(row); print(json.dumps(row),flush=True)
    # Symmetric awareness check: both independent sessions can infer; no universal
    # one-sided information edge is expected, and finite results may be noisy.
    nets=[]
    for i in range(0 if args.no_mirror else args.matches):
        A=CoreBot(seed=734); B=CoreBot(seed=734)
        A.session.bank.hands_total=B.session.bank.hands_total=2*args.deals
        nets.append(match(A,B,args.deals,args.seed+2000+i))
    if nets: results.append(dict(config='v2',opponent='DuplicateAwareMirror',nets=nets,wins=sum(x>0 for x in nets),
                        draws=sum(x==0 for x in nets),losses=sum(x<0 for x in nets),mean_chips=statistics.mean(nets)))
    output=dict(matches=args.matches,deals=args.deals,seed=args.seed,results=results,runtime_sha256=RUNTIME_SHA256)
    destination.write_text(json.dumps(output,indent=2)); print('Saved',destination,flush=True)

if __name__=='__main__': main()
