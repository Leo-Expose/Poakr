"""Research architecture: public action kernels + payoff geometry + solvency lock.
Mock-engine bridge below is NOT the official stdin/stdout protocol.
No opponent hole cards or duplicate-hole inference are used.
"""
from __future__ import annotations
import json,time,math,random
from pathlib import Path
from collections import OrderedDict
import numpy as np
from runtime import bot as core
from research.kernels import RiverKernel,PolicyMixture,WinLock


class Agent:
    def __init__(self,mode='full',seed=734,hands_total=120,preflop=None):
        self.mode=mode
        self.session=core.BotSession('research',settings=core.Settings(duplicate_mode='off',proactive_bluff=False),
                                     hands_total=hands_total,seed=seed)
        self.models=PolicyMixture(); self.free=np.full((4,2),1.5); self.nfree=np.zeros(4,int)
        self.hand_id='0'; self.hands_left=hands_total; self.lead=0.; self.locked=False
        self.kernel_cache=OrderedDict(); self.belief=None; self.events_seen=0; self.learn_seen=0
        self.hole=None; self.board=None; self.rng=random.Random(seed); self.preflop=preflop or {}
        self.requests=0; self.lock_actions=0; self.kernel_builds=0; self.river_actions=0; self.posterior_actions=0
        self.errors=0
    def set_context(self,hand_id,hands_left,lead):
        new=str(hand_id)!=self.hand_id
        if new:
            self.belief=None; self.events_seen=0; self.learn_seen=0; self.hole=None; self.board=None
        self.hand_id=str(hand_id); self.hands_left=hands_left; self.lead=float(lead)
    def _kernel(self,board):
        key=tuple(sorted(board))
        if key not in self.kernel_cache:
            self.kernel_cache[key]=RiverKernel(key); self.kernel_builds+=1
            while len(self.kernel_cache)>4: self.kernel_cache.popitem(last=False)
        self.kernel_cache.move_to_end(key); return self.kernel_cache[key]
    @staticmethod
    def public_events(history,cfg):
        # Replay ONLY publicly visible money/actions, never dealing/hole cards.
        stacks=[cfg.stack-cfg.sb,cfg.stack-cfg.bb]; committed=[cfg.sb,cfg.bb]; pot=0.; street=-1; raises=0
        events=[]
        for s,p,act in history:
            if s!=street:
                pot+=sum(committed); committed=[0.,0.]; street=s; raises=0
            tc=max(0.,committed[1-p]-committed[p]); middle=pot+sum(committed)
            price=min(tc,stacks[p])/(middle-max(0.,tc-stacks[p])+min(tc,stacks[p])) if middle+tc>0 else 0.
            can_raise=raises<cfg.max_raises and stacks[p]>tc and stacks[1-p]>0
            events.append((s+1,p,act[0],tc>0,price,can_raise))
            if act[0]=='call': pay=min(tc,stacks[p])
            elif act[0]=='bet': pay=min(tc+middle*act[1],stacks[p]); raises+=1
            else: pay=0.
            stacks[p]-=pay; committed[p]+=pay
        return events
    def _observe_belief(self,history,seat,cfg):
        events=self.public_events(history,cfg)
        for event_id,(street,who,kind,faced,price,can_raise) in enumerate(events[self.events_seen:],self.events_seen):
            if street==3 and who!=seat:
                self.belief.observe(kind,faced,price,can_raise,event_id=event_id)
        self.events_seen=len(events)
    def _selectivity(self,street):
        if self.nfree[street]<8: return 0.
        a,b=self.free[street]; mean=a/(a+b); sd=math.sqrt(a*b/((a+b)**2*(a+b+1)))
        upper=min(1.,mean+2*sd)
        # Early-street approximation, explicitly NOT an exact range certificate.
        return .24*min(1.,self.nfree[street]/16)*max(0.,(.50-upper)/.50)
    def _eq(self,obs,deadline):
        if not obs.board:
            a,b=obs.hole; ra,rb=a//4,b//4
            key=(max(ra,rb),min(ra,rb),int(a%4==b%4))
            if key in self.preflop:
                q=self.preflop[key]
                return core.EquityResult(q,max(0,q-.018),min(1,q+.018),16384,False,'offline-amortized')
        return self.session.equity.estimate(obs.hole,obs.board,None,self.session.policy.thresholds(obs),deadline)
    def _river_action(self,obs,raises=0,max_raises=4):
        eq=self.belief.equity(); call,pot,po=obs.price()
        passive=core.safe_action(obs.legal); best=passive; best_ev=0. if call else eq*pot
        for action in obs.legal:
            if action.kind=='call': ev=eq*(pot+call)-call
            elif action.kind=='check': ev=eq*pot
            elif action.kind=='fold': ev=0.
            else:
                pay=min(action.pay,obs.my_stack,obs.opp_stack+obs.to_call)
                extra=max(0,pay-call)
                opponent_price=extra/(pot+call+2*extra) if pot+call+2*extra else 0.
                can_reraise=raises+1<max_raises and obs.my_stack>action.pay and obs.opp_stack>extra
                cont,win=self.belief.response(opponent_price,can_reraise)
                # One-response river EV. Later re-raises are handled on new
                # requests, but their future effect is not solved in this value.
                ev=(1-cont)*pot+win*(pot+call+2*extra)-cont*(call+extra)
            if ev>best_ev+1e-9: best,best_ev=action,ev
        return best
    def decide(self,raw):
        start=time.perf_counter(); self.requests+=1
        mapping={}
        for old in raw['legal']:
            a=core.Action(old[0],min(raw['to_call']+raw['pot']*old[1],raw['my_stack']) if old[0]=='bet' else 0.)
            mapping.setdefault(a,old)
        obs=core.Observation(str(self.requests),self.hand_id,tuple(sorted(raw['hole'])),tuple(raw['board']),raw['pot'],raw['to_call'],
                             raw['my_stack'],raw['opp_stack'],tuple(mapping),chip_lead=self.lead,hands_left=self.hands_left)
        self.hole=obs.hole; self.board=obs.board
        try:
            obs.validate(self.session.rules)
            paid=max(0.,raw['cfg'].stack-obs.my_stack)
            abandon=next((a for a in obs.legal if a.kind in ('check','fold')),None)
            if self.locked and abandon is None:
                raise core.ValidationError('abandonment contract violated after certificate')
            if self.mode=='full' and abandon is not None and (self.locked or WinLock.certified(self.lead,paid,self.hands_left,max(raw['cfg'].sb,raw['cfg'].bb))):
                self.locked=True; self.lock_actions+=1; action=abandon
            elif self.session.bank.remaining()<.005 or len(obs.legal)==1:
                action=core.safe_action(obs.legal)
            elif len(obs.board)==5 and self.mode in ('kernel','posterior','inference','full'):
                with core.decision_guard(min(.04,self.session.bank.remaining())):
                    kernel=self._kernel(obs.board)
                    if self.belief is None:
                        self.belief=self.models.begin(kernel,obs.hole)
                    if self.mode!='kernel': self._observe_belief(raw['history'],raw['position'],raw['cfg'])
                    if self.mode=='kernel':
                        ids,z,payoff,outcome=kernel.view(obs.hole); q=float(payoff.mean())
                        action=self.session.policy.choose(obs,core.EquityResult(q,q,q,len(ids),True,'river-exact'),False,self.session.bank.hands_total)
                    else:
                        raises=sum(s==raw['street'] and a[0]=='bet' for s,p,a in raw['history'])
                        action=self._river_action(obs,raises,raw['cfg'].max_raises); self.posterior_actions+=1
                    self.river_actions+=1
            else:
                budget=min(.016,self.session.bank.budget(self.hands_left,.016))
                self.session.equity.partial=None
                try:
                    with core.decision_guard(max(.0005,budget)):
                        eq=self._eq(obs,time.perf_counter()+budget)
                except core.ComputationExpired:
                    eq=self.session.equity.partial; self.errors+=1
                if eq is not None and obs.to_call>0 and self.mode in ('inference','full'):
                    # Apply only to voluntary bets, not blind posting pressure.
                    history=raw['history']
                    if history and history[-1][0]==raw['street'] and history[-1][1]!=raw['position'] and history[-1][2][0]=='bet':
                        penalty=self._selectivity(raw['street']+1)
                        q=max(0.,eq.value-penalty)
                        eq=core.EquityResult(q,max(0,eq.low-penalty),max(0,eq.high-penalty),eq.samples,False,'action-calibrated-approx')
                action=self.session.policy.choose(obs,eq,False,self.session.bank.hands_total)
            assert action in mapping
            return mapping[action]
        except core.ComputationExpired:
            self.errors+=1; return mapping[core.safe_action(obs.legal)]
        finally: self.session.bank.charge(time.perf_counter()-start)
    def finish_public(self,history,seat,cfg,public_board,outcome):
        start=time.perf_counter()
        try:
            events=self.public_events(history,cfg)
            # Stats learn a first free action per street per hand, not repeated
            # re-raises as independent samples. No hidden holding is read.
            seen=set()
            for street,who,kind,faced,price,can_raise in events:
                if who==seat or faced or kind not in ('check','bet') or street in seen: continue
                seen.add(street); self.nfree[street]+=1
                self.free[street,int(kind=='check')]+=1
            if self.mode in ('posterior','inference','full') and self.hole is not None and len(public_board)==5 and any(e[0]==3 and e[1]!=seat for e in events):
                with core.decision_guard(min(.04,max(.0005,self.session.bank.remaining()))):
                    if self.belief is None: self.belief=self.models.begin(self._kernel(public_board),self.hole)
                    self._observe_belief(history,seat,cfg); self.belief.finish(outcome)
        except core.ComputationExpired: self.errors+=1
        finally: self.session.bank.charge(time.perf_counter()-start)


def load_preflop(path):
    data=json.loads(Path(path).read_text())
    return {(hi,lo,s):q for hi,lo,s,q in data['rows']}
