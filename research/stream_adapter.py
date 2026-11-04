"""CORA EXAMPLE adapter. Standard fixed-stack heads-up only; NOT official grammar.
No opponent hole-card fields are consumed. History amounts are actual chips paid.
The hard win lock is enabled only under an explicitly asserted scoring/posting
contract. Opaque/missing contract => inference without the lock.
"""
import sys,json,time,hashlib,argparse
from types import SimpleNamespace
from collections import OrderedDict
from runtime import bot as core
from research.agent import Agent


class CoraAdapter:
    def __init__(self,preflop,seed=734,boot_cost=0):
        self.preflop=preflop;self.seed=seed;self.boot_cost=boot_cost
        self.agent=None;self.cfg=None;self.match_id=None;self.responses=OrderedDict();self.seen_matches=set();self.finished=OrderedDict();self.snapshot=None
    @property
    def bank(self): return self.agent.session.bank if self.agent else None
    def _history(self,values):
        if not isinstance(values,list) or len(values)>256: raise core.ValidationError('bounded public history required')
        st=[self.cfg.stack-self.cfg.sb,self.cfg.stack-self.cfg.bb];comm=[self.cfg.sb,self.cfg.bb];pot=0.;street=0;finished=False;expected=0;raises=0;acted=[False,False];closed=False
        result=[]
        for ev in values:
            if not isinstance(ev,dict) or finished: raise core.ValidationError('invalid public event')
            s=core.integer(ev.get('street'),'street',0,3);who=core.integer(ev.get('actor'),'actor',0,1)
            if s<street: raise core.ValidationError('history regression')
            if s!=street:
                if s!=street+1 or not closed:raise core.ValidationError('incomplete public history')
                pot+=sum(comm);comm=[0.,0.];street=s;expected=1;raises=0;acted=[False,False];closed=False
            if closed or st[who]<=0:raise core.ValidationError('action after closed round/all-in')
            if who!=expected:raise core.ValidationError('out-of-turn public action')
            expected=1-who
            tc=max(0.,comm[1-who]-comm[who]);middle=pot+sum(comm)
            action=ev.get('action')
            if not isinstance(action,dict): raise core.ValidationError('history action required')
            kind=action.get('kind')
            if kind=='bet':
                pay=core.number(action.get('pay'),'history pay')
                if not tc<pay<=st[who] or middle<=0 or raises>=self.cfg.max_raises or st[1-who]<=0: raise core.ValidationError('invalid history bet')
                old=('bet',(pay-tc)/middle);raises+=1
            elif kind=='call':
                if tc<=0: raise core.ValidationError('invalid history call')
                pay=min(tc,st[who]);old=('call',)
            elif kind=='check':
                if tc>0: raise core.ValidationError('invalid history check')
                pay=0.;old=('check',)
            elif kind=='fold': pay=0.;old=('fold',);finished=True
            else: raise core.ValidationError('unknown history action')
            result.append((s-1,who,old));st[who]-=pay;comm[who]+=pay;acted[who]=True
            closed=(acted[expected] and comm[who]<=comm[expected]) or (min(st)==0 and comm[0]==comm[1])
        self.ledger=(st,comm,pot,street,finished,expected,closed)
        return result
    @staticmethod
    def _wire_prefix(history):
        return tuple((e['street'],e['actor'],e['action']['kind'],e['action'].get('pay',0)) for e in history)
    def handle(self,obj):
        if not isinstance(obj,dict): raise core.ValidationError('object message required')
        kind=obj.get('type')
        allowed={'start_match':{'type','match_id','starting_stack','sb','bb','max_raises','hands_total','timebank_s','raw_net_abandonment_contract'},'decision':{'type','match_id','request_id','hand_id','hole','board','pot','to_call','my_stack','opp_stack','hands_left','banked_net','seat','legal','history','time_left_s'},'hand_end':{'type','match_id','hand_id','seat','board','outcome','history','time_left_s'},'status':{'type','match_id','time_left_s'},'end_match':{'type','match_id'}}
        if kind not in allowed or set(obj)-allowed[kind]: raise core.ValidationError('unknown message fields')
        # Reject unknown nested fields before hashing. No hidden-card fields may
        # influence either policy input or retry handling.
        if kind in ('decision','hand_end'):
            history=obj.get('history')
            if not isinstance(history,list) or len(history)>256:raise core.ValidationError('bounded history required')
            for ev in history:
                if not isinstance(ev,dict) or set(ev)!={'street','actor','action'}:raise core.ValidationError('history field schema')
                action=ev['action']
                if not isinstance(action,dict) or set(action)!=({'kind','pay'} if action.get('kind')=='bet' else {'kind'}):raise core.ValidationError('history action schema')
        if kind=='decision':
            legal=obj.get('legal')
            if not isinstance(legal,list):raise core.ValidationError('legal list required')
            for action in legal:
                if not isinstance(action,dict) or set(action)!=({'kind','pay'} if action.get('kind')=='bet' else {'kind'}):raise core.ValidationError('legal action schema')
        mid=core.identifier(obj.get('match_id'),'match_id')
        if kind=='start_match':
            if self.agent is not None or mid in self.seen_matches: raise core.ValidationError('invalid match reset')
            stack=core.number(obj.get('starting_stack'),'starting_stack',.01)
            sb=core.number(obj.get('sb'),'sb',.01);bb=core.number(obj.get('bb'),'bb',sb)
            if bb>=stack: raise core.ValidationError('unsupported blind all-in setup')
            raises=core.integer(obj.get('max_raises',4),'max_raises',0,16)
            total=core.integer(obj.get('hands_total'),'hands_total',1,100000)
            bank=core.number(obj.get('timebank_s'),'timebank_s',.01)
            contract=obj.get('raw_net_abandonment_contract',False)
            if not isinstance(contract,bool): raise core.ValidationError('contract must be bool')
            # Contract: scores are raw own completed-hand net profit; stack resets
            # per hand; fixed declared blinds are all forced charges; legal
            # check/fold abandonment is always available; no future blind growth.
            self.cfg=SimpleNamespace(stack=stack,sb=sb,bb=bb,max_raises=raises)
            self.agent=Agent('full' if contract else 'inference',self.seed,total,self.preflop)
            self.agent.session.bank.total=bank;self.agent.session.bank.charge(self.boot_cost);self.boot_cost=0
            self.match_id=mid;return None
        if self.agent is None or mid!=self.match_id: raise core.ValidationError('no active matching session')
        if 'time_left_s' in obj: self.bank.update_host(core.number(obj['time_left_s'],'time_left_s'))
        if kind=='status': return None
        if kind=='end_match':
            self.seen_matches.add(mid)
            if len(self.seen_matches)>256: raise core.ValidationError('match registry limit')
            self.agent=None;self.match_id=None;self.responses.clear();self.finished.clear();self.snapshot=None;return None
        if kind=='decision':
            rid=core.identifier(obj.get('request_id'),'request_id')
            fingerprint=hashlib.sha256(json.dumps({k:v for k,v in obj.items() if k!='time_left_s'},sort_keys=True,allow_nan=False).encode()).hexdigest()
            if rid in self.responses:
                old,reply=self.responses[rid]
                if old!=fingerprint: raise core.ValidationError('conflicting request ID')
                return reply
            obs=core.observation_from_json(obj,core.Rules());obs.validate(core.Rules())
            if obs.hands_left is None or not 1<=obs.hands_left<=self.bank.hands_total: raise core.ValidationError('hands_left required/bounded')
            if obs.hand_id in self.finished: raise core.ValidationError('decision after hand end')
            seat=core.integer(obj.get('seat'),'seat',0,1)
            net=core.number(obj.get('banked_net'),'banked_net',-1e12)
            history=self._history(obj.get('history'))
            stacks,comm,pot,street,finished,expected,closed=self.ledger
            phase=core.Rules().board_lengths.index(len(obs.board))
            if finished or phase<street or phase>street+1:raise core.ValidationError('inconsistent decision phase')
            if phase>street:
                if not closed or min(stacks)<=0:raise core.ValidationError('premature street/request after all-in')
                pot+=sum(comm);comm=[0.,0.];expected=1
            elif closed:raise core.ValidationError('request after closed round')
            if seat!=expected:raise core.ValidationError('out-of-turn request')
            expected_values=(stacks[seat],stacks[1-seat],pot+sum(comm),max(0.,comm[1-seat]-comm[seat]))
            actual_values=(obs.my_stack,obs.opp_stack,obs.pot,obs.to_call)
            if any(abs(a-b)>1e-7 for a,b in zip(actual_values,expected_values)):raise core.ValidationError('public money ledger mismatch')
            if self.snapshot is not None and self.snapshot[0]==obs.hand_id:
                _,hole,board,position,prefix=self.snapshot
                if hole!=obs.hole or position!=seat or not set(board)<=set(obs.board) or self._wire_prefix(obj['history'])[:len(prefix)]!=prefix:raise core.ValidationError('private/public hand state changed or response not applied')
            mapping={}
            for action in obs.legal:
                if action.kind=='bet':
                    if obs.pot<=0: raise core.ValidationError('zero-pot bet unsupported in example')
                    old=('bet',(action.pay-obs.to_call)/obs.pot)
                else: old=(action.kind,)
                mapping[old]=action
            raw=dict(hole=list(obs.hole),board=list(obs.board),pot=obs.pot,to_call=obs.to_call,my_stack=obs.my_stack,
                     opp_stack=obs.opp_stack,legal=list(mapping),history=history,position=seat,
                     street=core.Rules().board_lengths.index(len(obs.board))-1,cfg=self.cfg)
            self.agent.set_context(obs.hand_id,obs.hands_left,net)
            old=self.agent.decide(raw)
            reply=core.action_response(rid,mapping[old]);self.responses[rid]=(fingerprint,reply)
            action=reply['action'];prefix=self._wire_prefix(obj['history'])+((phase,seat,action['kind'],action.get('pay',0)),)
            self.snapshot=(obs.hand_id,obs.hole,obs.board,seat,prefix)
            while len(self.responses)>512: self.responses.popitem(last=False)
            return reply
        if kind=='hand_end':
            hid=core.identifier(obj.get('hand_id'),'hand_id')
            fingerprint=hashlib.sha256(json.dumps({k:v for k,v in obj.items() if k!='time_left_s'},sort_keys=True,allow_nan=False).encode()).hexdigest()
            if hid in self.finished:
                if self.finished[hid]!=fingerprint: raise core.ValidationError('conflicting hand end')
                return None
            seat=core.integer(obj.get('seat'),'seat',0,1)
            if hid!=self.agent.hand_id:
                # A hand may end before we received any decision. Forget prior
                # private state; never treat its old hole cards as current data.
                self.agent.set_context(hid,1,0)
            outcome=obj.get('outcome')
            if outcome is not None and (isinstance(outcome,bool) or outcome not in (-1,0,1)):
                raise core.ValidationError('outcome must be win/tie/loss or null for no showdown')
            board=core.Rules().cards(obj.get('board'))
            if len(board) not in core.Rules().board_lengths: raise core.ValidationError('invalid public end board')
            history=self._history(obj.get('history'))
            stacks,comm,pot,street,finished,expected,closed=self.ledger
            if (outcome is None and not finished) or (outcome is not None and (finished or len(board)!=5 or not closed or (street!=3 and min(stacks)>0))):raise core.ValidationError('inconsistent hand completion')
            if self.snapshot is not None and self.snapshot[0]==hid:
                _,hole,previous,position,prefix=self.snapshot
                if position!=seat or set(hole)&set(board) or not set(previous)<=set(board) or self._wire_prefix(obj['history'])[:len(prefix)]!=prefix:raise core.ValidationError('inconsistent completed hand')
            self.agent.finish_public(history,seat,self.cfg,board,outcome)
            self.snapshot=None
            self.finished[hid]=fingerprint
            while len(self.finished)>1600:self.finished.popitem(last=False)
            return None
        raise core.ValidationError('unknown control type')
    def fallback(self,obj):
        if not isinstance(obj,dict) or obj.get('type')!='decision' or self.agent is None: return None
        try:
            if core.identifier(obj.get('match_id'),'match_id')!=self.match_id: return None
            rid=core.identifier(obj.get('request_id'),'request_id')
            if rid in self.responses: return None
            legal=core.legal_from_json(obj.get('legal'))
            return core.action_response(rid,core.safe_action(legal))
        except (ValueError,TypeError): return None


def cora_main(preflop,boot_cost=0,argv=None):
    parser=argparse.ArgumentParser(description='CORA research EXAMPLE protocol, standard Holdem only')
    parser.add_argument('--seed',type=int,default=734);args=parser.parse_args(argv)
    adapter=CoraAdapter(preflop,args.seed,boot_cost)
    for line in core.read_bounded_lines(sys.stdin):
        begin=time.perf_counter();old_bank=adapter.bank;old_spent=old_bank.spent if old_bank else 0.;obj=None
        try:
            if line is None: raise core.ValidationError('oversized line')
            if not line.strip(): continue
            obj=core.strict_json(line);reply=adapter.handle(obj)
        except Exception as exc:
            sys.stderr.write('input_error:'+type(exc).__name__+'\n');reply=adapter.fallback(obj)
        try:
            if reply is not None:
                sys.stdout.write(json.dumps(reply,separators=(',',':'),allow_nan=False)+'\n');sys.stdout.flush()
        finally:
            bank=adapter.bank if adapter.bank is not None else old_bank
            if bank:
                already=max(0.,bank.spent-old_spent) if bank is old_bank else 0.
                # Agent bodies already account their own compute. Add only the
                # remaining parse/transport overhead, never double-charge it.
                bank.charge(max(0.,time.perf_counter()-begin-already))
