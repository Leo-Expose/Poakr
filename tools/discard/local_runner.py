"""Independent local PDF-1.0 engine, NOT organizer starter-kit software.
No hidden peer cards/future board are sent in requests. Simultaneous discard
requests precede both results. Supports both unresolved duplicate-layout readings.
"""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
import json
import random
import time
import hashlib
import subprocess
import selectors
from itertools import combinations
from engine.cards import make_evaluator,make_best_of
from research.discard_holdem.proofs import text_card,card
from research.discard_holdem.protocol import DiscardBot

FIVE=make_evaluator(13,4)
SEVEN=make_best_of(FIVE,7)


class Client:
    def __init__(self,bot):
        self.bot=bot;self.spent=0.;self.requests=0;self.max_reply=0.;self.invalid=0
    def send(self,msg):
        start=time.perf_counter();reply=self.bot.handle(msg);elapsed=time.perf_counter()-start
        if msg['type'] in ('action_request','discard_request'):
            self.spent+=elapsed;self.requests+=1;self.max_reply=max(self.max_reply,elapsed)
        else:assert reply is None
        return reply
    def close(self):pass


class WireClient(Client):
    def __init__(self,path,sandbox=False):
        self.spent=0.;self.requests=0;self.max_reply=0.;self.invalid=0;self.boot_s=None
        start=time.perf_counter()
        command=[sys.executable,'-B',str(path)]
        if sandbox:
            code='''import os,sys,time,resource,runpy,json
start=time.perf_counter()
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
forbidden=[]
def audit(event,args):
    if event.startswith(('socket.','subprocess.')) or event in ('os.system','os.fork','os.posix_spawn'):
        forbidden.append(event);raise RuntimeError('forbidden '+event)
    if event=='open':
        _,mode,flags=args
        if (isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            forbidden.append(event);raise RuntimeError('runtime write forbidden')
sys.addaudithook(audit)
ns=runpy.run_path(sys.argv[1],run_name='discard_candidate')
ready=time.perf_counter()-start
bot=ns['discard_main']()
print(json.dumps(dict(benchmark_metadata=True,errors=bot.errors,proofs=bot.proof_arms,score_trusted=bot.score_trusted,score=bot.score,completed=bot.completed,ready_s=ready,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,affinity=list(os.sched_getaffinity(0)),address_space_limit_bytes=1<<30,forbidden_attempts=forbidden,python=sys.version.split()[0])),file=sys.stderr,flush=True)
'''
            command=[sys.executable,'-B','-c',code,str(path)]
        self.sandbox=sandbox;self.metadata=None
        self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,bufsize=0)
        self.selector=selectors.DefaultSelector();self.selector.register(self.process.stdout,selectors.EVENT_READ)
        # Readiness sentinel is an ordinary request, included in later totals.
        # Startup is measured as the first reply minus its computation; the
        # official host's launch-ready boundary itself cannot be observed here.
        self.start=start
    def send(self,msg):
        start=time.perf_counter()
        self.process.stdin.write((json.dumps(msg,separators=(',',':'))+'\n').encode());self.process.stdin.flush()
        if msg['type'] not in ('action_request','discard_request'):return None
        self.requests+=1
        if not self.selector.select(5):raise RuntimeError('single reply deadline exceeded')
        line=self.process.stdout.readline()
        elapsed=time.perf_counter()-start
        if not line:raise RuntimeError('candidate EOF: '+self.process.stderr.read().decode())
        self.spent+=elapsed;self.max_reply=max(self.max_reply,elapsed)
        if self.boot_s is None:self.boot_s=time.perf_counter()-self.start
        return json.loads(line)
    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=5)
        extra=self.process.stdout.read()
        stderr=self.process.stderr.read()
        if self.sandbox:
            self.metadata=json.loads(stderr)
            assert self.metadata['benchmark_metadata'] and not self.metadata['forbidden_attempts'] and self.metadata['errors']==0
        else:assert not stderr,stderr
        assert self.process.returncode==0 and not extra,(extra,stderr)
        self.selector.close()


class Opponent:
    """Own-state-only diagnostic policies, not equilibrium opponents."""
    def __init__(self,kind,seed=91):self.kind=kind;self.rng=random.Random(seed)
    def handle(self,msg):
        kind=msg['type']
        if kind=='new_hand':self.hole=tuple(card(c) for c in msg['hole_cards'])
        if kind=='discard_result':self.hole=tuple(card(c) for c in msg['hole_cards'])
        if kind=='discard_request':
            flop=tuple(card(c) for c in msg['board'])
            best=max(combinations(self.hole,2),key=lambda h:FIVE(*(h+flop)))
            return dict(type='discard',card=text_card(next(c for c in self.hole if c not in best)))
        if kind!='action_request':return None
        legal=msg['legal_actions'];owed=msg['to_call'];pot=msg['pot']
        raise_it=False;fold_it=False
        if self.kind=='Shove':raise_it=True
        elif self.kind=='Aggressor':raise_it=self.rng.random()<.65
        elif self.kind=='Selective':
            board=tuple(card(c) for c in msg['board'])
            ranks=[c//4 for c in self.hole]
            pair=len(set(ranks))<len(ranks) or any(c//4 in ranks for c in board)
            strength=pair or max(ranks)>=10
            fold_it=owed>0 and (not strength or owed>max(4,pot*.6) and not pair)
            raise_it=strength and self.rng.random()<.35
        elif self.kind=='OverFolder':fold_it=owed>2 and self.rng.random()<.8
        elif self.kind not in ('CallingStation','CheckFold'):raise ValueError('unknown diagnostic opponent')
        if self.kind=='CheckFold':fold_it=owed>0
        if fold_it and 'fold' in legal:return dict(type='action',action='fold')
        if raise_it and 'raise' in legal:
            amount=msg['max_raise'] if self.kind=='Shove' else max(msg['min_raise'],min(msg['max_raise'],msg['opp_bet']+max(2,pot)))
            return dict(type='action',action='raise',amount=amount)
        return dict(type='action',action='call' if owed else 'check')


class LocalMatch:
    def __init__(self,a,b,hands=400,seed=20261031,layout='fixed_seat_cards',strict=True):
        if hands%2:raise ValueError('local duplicate fixture requires even hands')
        if layout not in ('fixed_seat_cards','swapped_seat_cards'):raise ValueError('unknown layout')
        self.clients=[a,b];self.hands=hands;self.seed=seed;self.layout=layout;self.strict=strict
        self.bank_ms=60000 if hands<=400 else 150000
        self.net=[0,0];self.discards=0;self.actions=0;self.invalid=0;self.terminal=0
        self.allin_discards=0;self.max_history=0;self.requests_log=[]
    def message(self,p,msg):
        return self.clients[p].send(msg)
    def hist(self,p,history):
        return [dict(e,actor='me' if e['actor']==p else 'opp') for e in history]
    def board_text(self,board):return list(map(text_card,board))
    def play_hand(self,hid,holes,board):
        button=0 if hid%2 else 1
        original=[tuple(h) for h in holes];remaining=list(original);dead=[None,None]
        paid=[1,2] if button==0 else [2,1]
        history=[];folded=None
        for p in (0,1):
            self.message(p,dict(type='new_hand',hand_id=hid,seat='button' if p==button else 'big_blind',
                               hole_cards=self.board_text(holes[p]),stack=200,opp_stack=200))
        for street_index,street in enumerate(('preflop','flop','turn','river')):
            visible=board[:(0,3,4,5)[street_index]]
            bets=list(paid) if street_index==0 else [0,0]
            raises=1 if street_index==0 else 0
            last_delta=2;acted=[False,False];actor=button if street_index==0 else 1-button
            if max(paid)<200:
                while True:
                    p=actor;other=1-p
                    owed=max(0,bets[other]-bets[p])
                    legal=['fold','call'] if owed else ['check']
                    maximum=min(bets[p]+200-paid[p],bets[other]+200-paid[other])
                    minimum=min(maximum,bets[other]+max(2,last_delta))
                    if raises<4 and max(paid)<200:legal.append('raise')
                    req=dict(type='action_request',hand_id=hid,street=street,board=self.board_text(visible),pot=sum(paid),
                             my_bet=bets[p],opp_bet=bets[other],to_call=owed,my_stack=200-paid[p],opp_stack=200-paid[other],
                             legal_actions=legal,raises_left=4-raises,history=self.hist(p,history),
                             time_left_ms=max(0,int(self.bank_ms-1000*self.clients[p].spent)))
                    if 'raise' in legal:req.update(min_raise=minimum,max_raise=maximum)
                    reply=self.message(p,req);self.actions+=1
                    valid=isinstance(reply,dict) and reply.get('type')=='action' and reply.get('action') in legal
                    if valid and reply['action']=='raise':
                        value=reply.get('amount');valid=type(value) is int and minimum<=value<=maximum
                    if not valid:
                        self.invalid+=1;self.clients[p].invalid+=1
                        if self.strict:raise AssertionError(('illegal action',req,reply))
                        reply=dict(type='action',action='fold' if owed else 'check')
                    action=reply['action'];event=dict(street=street,actor=p,action=action)
                    if action=='fold':folded=p
                    elif action=='check':acted[p]=True
                    elif action=='call':
                        amount=bets[other];paid[p]+=amount-bets[p];bets[p]=amount
                        event['amount']=amount;acted[p]=True
                    else:
                        amount=reply['amount'];last_delta=amount-bets[other]
                        paid[p]+=amount-bets[p];bets[p]=amount;raises+=1
                        acted=[False,False];acted[p]=True;event['amount']=amount
                    history.append(event);self.max_history=max(self.max_history,len(history))
                    if folded is not None or (bets[0]==bets[1] and all(acted)):break
                    actor=other
            if folded is not None:break
            if street_index==1:
                choices=[]
                # Neither result is sent until BOTH requests have answered.
                for p in (0,1):
                    reply=self.message(p,dict(type='discard_request',hand_id=hid,hole_cards=self.board_text(original[p]),
                                             board=self.board_text(visible),pot=sum(paid),my_stack=200-paid[p],opp_stack=200-paid[1-p],
                                             time_left_ms=max(0,int(self.bank_ms-1000*self.clients[p].spent))))
                    valid=isinstance(reply,dict) and reply.get('type')=='discard' and reply.get('card') in self.board_text(original[p])
                    if not valid:raise AssertionError(('illegal discard',reply))
                    choices.append(card(reply['card']));self.discards+=1
                if max(paid)==200:self.allin_discards+=2
                for p in (0,1):
                    dead[p]=choices[p];remaining[p]=tuple(c for c in original[p] if c!=dead[p])
                for p in (0,1):
                    self.message(p,dict(type='discard_result',hand_id=hid,my_discard=text_card(dead[p]),
                                        opp_discard=text_card(dead[1-p]),hole_cards=self.board_text(remaining[p])))
        if folded is not None:
            net= -paid[0] if folded==0 else paid[1]
            result='fold'
        else:
            a=SEVEN(remaining[0],board);b=SEVEN(remaining[1],board)
            net=((a>b)-(a<b))*paid[0]
            assert paid[0]==paid[1]
            visible=board;result='showdown'
        for p in (0,1):
            delta=net if p==0 else -net;self.net[p]+=delta
            self.message(p,dict(type='hand_result',hand_id=hid,result=result,net=delta,board=self.board_text(visible),
                                my_hole_cards=self.board_text(remaining[p]),
                                opp_hole_cards=self.board_text(remaining[1-p]) if result=='showdown' else None,
                                opp_discard=text_card(dead[1-p]) if dead[1-p] is not None else None,
                                history=self.hist(p,history)))
        self.terminal+=1
    def run(self):
        start=time.perf_counter()
        init=dict(type='init',protocol_version='1.0',total_hands=self.hands,starting_stack=200,small_blind=1,big_blind=2,
                  time_bank_ms=self.bank_ms,per_response_ms=5000)
        for p in (0,1):self.message(p,init)
        rng=random.Random(self.seed)
        for pair in range(self.hands//2):
            dealt=rng.sample(range(52),11);a=tuple(dealt[:3]);b=tuple(dealt[3:6]);board=tuple(dealt[6:])
            self.play_hand(2*pair+1,[a,b],board)
            # Fixed cards at physical seats swaps each bot's private cards;
            # swapped cards at physical seats retains each bot's private cards.
            self.play_hand(2*pair+2,[b,a] if self.layout=='fixed_seat_cards' else [a,b],board)
        for p in (0,1):self.message(p,dict(type='match_end',reason='complete'))
        for client in self.clients:client.close()
        return dict(hands=self.hands,seed=self.seed,duplicate_layout=self.layout,net=self.net[0],
                    invalid_responses=self.invalid,discard_replies=self.discards,allin_discard_replies=self.allin_discards,
                    actions=self.actions,max_history=self.max_history,wall_s=time.perf_counter()-start,
                    candidate_request_wall_s=self.clients[0].spent,candidate_max_reply_s=self.clients[0].max_reply,
                    candidate_requests=self.clients[0].requests,time_bank_ms=self.bank_ms,
                    candidate_errors=getattr(getattr(self.clients[0],'bot',None),'errors',None),
                    candidate_proofs=getattr(getattr(self.clients[0],'bot',None),'proof_arms',None),
                    candidate_ledger_trusted=getattr(getattr(self.clients[0],'bot',None),'score_trusted',None),
                    scope='independent local PDF-derived runner; NOT organizer starter kit')


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--hands',type=int,default=400)
    p.add_argument('--opponent',default='CallingStation');p.add_argument('--seed',type=int,default=20261031)
    p.add_argument('--layout',default='fixed_seat_cards');p.add_argument('--wire',action='store_true');p.add_argument('--sandbox',action='store_true')
    p.add_argument('--output',default='local_match.json');args=p.parse_args()
    if Path(args.output).name!=args.output:raise ValueError('plain output filename required')
    path=ROOT/'releases/discard/current/bot.py'
    a=WireClient(path,args.sandbox) if args.wire else Client(DiscardBot())
    b=Client(Opponent(args.opponent))
    result=LocalMatch(a,b,args.hands,args.seed,args.layout).run()
    if not args.wire:
        assert a.bot.completed==args.hands and a.bot.score==result['net']
        assert a.bot.errors==0 and a.bot.score_trusted
    if args.wire and args.sandbox:
        result['runtime_metadata']=a.metadata
        assert a.metadata['score']==result['net'] and a.metadata['completed']==args.hands and a.metadata['score_trusted']
        assert a.metadata['ready_s']<5
    assert a.spent < a.requests*5 and a.spent < result['time_bank_ms']/1000 and a.max_reply<5
    result.update(opponent=args.opponent,wire=args.wire,standalone_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    out=ROOT/'evidence/discard';out.mkdir(parents=True,exist_ok=True)
    (out/args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
