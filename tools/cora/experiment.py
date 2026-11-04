"""Workspace-only staged ablations, public data only, all duplicate inference off."""
import sys,json,time,random,argparse,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'bench'))
SOURCE_HASHES={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ('research/kernels.py','research/agent.py','runtime/bot.py','data/preflop/preflop.json')}
from research.agent import Agent,load_preflop
from bench.matches_v2 import CoreBot
from bench.fullmatch import OverFolder,CallingStation,Balanced,Aggressor,FullBot
from types import SimpleNamespace
from engine.game import Game,GameConfig
from engine.equity import equity_vs_range,pot_odds


class LegacyBridge:
    def __init__(self,hands_total):
        self.full=FullBot();self.full.reset();self.total=hands_total
        self.session=SimpleNamespace(bank=SimpleNamespace(spent=0.),decisions=0,errors=0)
    def set_context(self,hand,hands_left,net):
        self.full.hand_id=hand;self.full.set_match_state(net,hands_left/self.total)
    def decide(self,obs):
        start=time.perf_counter()
        try:
            self.session.decisions+=1;return self.full.decide(obs)
        finally:self.session.bank.spent+=time.perf_counter()-start
    def learn_public(self,history,seat,cfg):
        start=time.perf_counter()
        try:self.full.learn_public(history,seat)
        finally:self.session.bank.spent+=time.perf_counter()-start


class SelectiveBluffer:
    def __init__(self,seed=0): self.r=random.Random(seed)
    def decide(self,obs):
        legal=obs['legal'];eq=equity_vs_range(obs['hole'],obs['board'],n_draws=120,seed=self.r.randrange(1<<30))
        bets=[a for a in legal if a[0]=='bet']; po=pot_odds(obs['to_call'],obs['pot'])
        if obs['to_call']==0:
            if bets and eq<.35 and self.r.random()<.45: return min(bets,key=lambda a:abs(a[1]-1))
            return ('check',) if ('check',) in legal else legal[0]
        return ('call',) if eq>po+.05 else (('fold',) if ('fold',) in legal else legal[0])


class Trapper:
    def __init__(self,seed=0): self.r=random.Random(seed)
    def decide(self,obs):
        legal=obs['legal'];eq=equity_vs_range(obs['hole'],obs['board'],n_draws=120,seed=self.r.randrange(1<<30))
        bets=[a for a in legal if a[0]=='bet']; po=pot_odds(obs['to_call'],obs['pot'])
        if obs['to_call']==0:
            if bets and .62<eq<.82 and self.r.random()<.5: return min(bets,key=lambda a:abs(a[1]-.5))
            return ('check',) if ('check',) in legal else legal[0]
        if bets and eq>.88: return min(bets,key=lambda a:abs(a[1]-1))
        return ('call',) if eq>po else (('fold',) if ('fold',) in legal else legal[0])


def run(A,B,deals,seed):
    rng=random.Random(seed);cfg=GameConfig();net=0.;locked_at=None
    for d in range(deals):
        dealt=rng.sample(range(52),9)
        for copy in (0,1):
            hand=2*d+copy; left=2*deals-hand
            A.set_context(hand,left,net)
            seat=copy
            players=(A,B) if copy==0 else (B,A)
            value,history=Game(cfg,seed+hand).play_hand(dealt,*players)
            own_net=value if copy==0 else -value
            if isinstance(A,Agent):
                folded=any(act[0]=='fold' for street,p,act in history)
                last=max((s for s,p,a in history),default=-1)
                nboard=cfg.n_board if not folded else sum(cfg.board_by_street[:last+1])
                outcome=None if folded else (1 if own_net>0 else -1 if own_net<0 else 0)
                # Only ACTUALLY PUBLIC board prefix and win/tie/loss are passed.
                A.finish_public(history,seat,cfg,tuple(dealt[4:4+nboard]),outcome)
                if A.locked and locked_at is None: locked_at=hand
                assert len(A.session.duplicate.history)==0
            else: A.learn_public(history,seat,cfg)
            net+=own_net
    if isinstance(A,Agent) and A.locked: assert net>0,('violated win certificate',net)
    return net,locked_at


def main():
    p=argparse.ArgumentParser();p.add_argument('--matches',type=int,default=8);p.add_argument('--deals',type=int,default=60)
    p.add_argument('--seed',type=int,default=71000);p.add_argument('--modes',default='v2,fast,kernel,inference,full')
    p.add_argument('--opponents',default='OverFolder,CallingStation,Balanced,Aggressor')
    p.add_argument('--output',default='exploratory_results.json');args=p.parse_args()
    pre=load_preflop(ROOT/'data/preflop/preflop.json')
    registry=dict(OverFolder=OverFolder,CallingStation=CallingStation,Balanced=Balanced,Aggressor=Aggressor,
                  SelectiveBluffer=SelectiveBluffer,Trapper=Trapper)
    (ROOT/'evidence/cora/reruns').mkdir(parents=True,exist_ok=True)
    results=[];status=ROOT/'evidence/cora/reruns'/args.output
    for mode in args.modes.split(','):
        for name in args.opponents.split(','):
            nets=[];locked=[];own_seconds=0.;requests=0;kbuild=0;posterior=0;errors=0;begin=time.perf_counter()
            for i in range(args.matches):
                if mode=='v1_info': A=LegacyBridge(2*args.deals)
                elif mode in ('v2','v2_info'):
                    A=CoreBot(mode='board' if mode=='v2_info' else 'off',bluff=False,seed=734);A.session.bank.hands_total=2*args.deals
                else: A=Agent(mode,seed=734,hands_total=2*args.deals,preflop=pre)
                B=registry[name](seed=args.seed+200+i)
                net,lock=run(A,B,args.deals,args.seed+i);nets.append(net);locked.append(lock)
                own_seconds+=A.session.bank.spent
                if isinstance(A,Agent):
                    requests+=A.requests;kbuild+=A.kernel_builds;posterior+=A.posterior_actions;errors+=A.errors
                else:requests+=A.session.decisions;errors+=A.session.errors
            row=dict(mode=mode,opponent=name,nets=nets,wins=sum(x>0 for x in nets),draws=sum(x==0 for x in nets),
                     losses=sum(x<0 for x in nets),mean_net=statistics.mean(nets),locks=locked,
                     own_seconds=own_seconds,requests=requests,kernel_builds=kbuild,posterior_actions=posterior,
                     timeouts=errors,wall_s=time.perf_counter()-begin)
            results.append(row);print(json.dumps(row),flush=True)
            data=dict(matches=args.matches,deals=args.deals,seed=args.seed,duplicate_inference_in_candidate=False,baseline_duplicate_modes={m:('board' if m in ('v2_info','v1_info') else 'off') for m in args.modes.split(',')},
                      sources=SOURCE_HASHES,results=results)
            status.write_text(json.dumps(data,indent=2))

if __name__=='__main__':main()
