"""Protocol 1.0 Discard Hold'em candidate. PDF-backed; not organizer-certified.
No duplicate identification/inference, past private-card memory or file access.
Strategy estimates are model-relative, not minimax or pointwise guarantees.
"""
import json
import random
import time
from dataclasses import dataclass
from itertools import combinations
import numpy as np
from engine.numpy_eval import eval_batch
from research.discard_holdem.proofs import (
    RANKS, SUITS, card, text_card, parse_cards, default_discard,
    future_blinds, quads_turn, river_geometry,
)

STREETS=('preflop','flop','turn','river')
LENGTHS=(0,3,4,5)


def integer(value, low=0, high=10**9):
    if type(value) is not int or not low<=value<=high:raise ValueError('integer outside range')
    return value


@dataclass
class Replay:
    paid: list
    bets: list
    street: int
    actor: str
    raises: int
    delta: int
    acted: list
    closed: bool=False
    folded: str=None

    @property
    def pot(self):return sum(self.paid)


def replay(history,seat,target):
    """Independently reconstruct totals from public street-total action history.
    Blinds are implicit; amounts in history are TO amounts, not increments.
    """
    if seat not in ('button','big_blind') or target not in STREETS:raise ValueError('bad seat/street')
    if not isinstance(history,list) or len(history)>64:raise ValueError('bounded public history required')
    button=0 if seat=='button' else 1
    r=Replay([1,2] if button==0 else [2,1],[1,2] if button==0 else [2,1],0,
             'me' if button==0 else 'opp',1,2,[False,False])
    def advance(s):
        if s<r.street or (s!=r.street and not r.closed):raise ValueError('street advanced before betting closed')
        while r.street<s:
            r.street+=1;r.bets=[0,0];r.acted=[False,False];r.raises=0;r.delta=2
            r.actor='me' if button==1 else 'opp'
            r.closed=(max(r.paid)==200)
        if s>STREETS.index(target):raise ValueError('future history')
    for event in history:
        if not isinstance(event,dict) or r.folded:raise ValueError('history after fold')
        s=STREETS.index(event['street']);advance(s)
        actor=event['actor'];p=0 if actor=='me' else 1
        if actor not in ('me','opp') or actor!=r.actor or r.closed:raise ValueError('wrong history actor')
        kind=event['action'];owed=max(0,r.bets[1-p]-r.bets[p]);paid=0
        if kind=='fold':
            if owed==0:raise ValueError('free fold is illegal')
            r.folded=actor;r.closed=True
        elif kind=='check':
            if owed:raise ValueError('check facing a bet')
            r.acted[p]=True
        elif kind=='call':
            amount=integer(event['amount'],0,200)
            if owed<=0 or amount!=r.bets[1-p]:raise ValueError('call must be exact street TO amount')
            paid=amount-r.bets[p];r.bets[p]=amount;r.acted[p]=True
        elif kind=='raise':
            amount=integer(event['amount'],0,200)
            maximum=min(r.bets[p]+200-r.paid[p],r.bets[1-p]+200-r.paid[1-p])
            minimum=min(maximum,r.bets[1-p]+max(2,r.delta))
            if r.raises>=4 or max(r.paid)==200 or not minimum<=amount<=maximum or amount<=r.bets[1-p]:
                raise ValueError('illegal raise in history')
            r.delta=amount-r.bets[1-p];paid=amount-r.bets[p];r.bets[p]=amount
            r.raises+=1;r.acted=[False,False];r.acted[p]=True
        else:raise ValueError('unknown history action')
        r.paid[p]+=paid
        if max(r.paid)>200:raise ValueError('stack exceeded')
        if r.bets[0]==r.bets[1] and all(r.acted):r.closed=True
        r.actor='opp' if actor=='me' else 'me'
    advance(STREETS.index(target))
    return r


class DiscardBot:
    def __init__(self,samples=128,spend_to_cap=True):
        self.samples=integer(samples,1,4096)
        self.spend_to_cap=spend_to_cap
        self.rng=random.Random(734)
        self.ready=False;self.finished=False;self.score=0;self.score_trusted=True
        self.completed=0;self.errors=0;self.proof_arms=0;self.lock_actions=0
        self.hand_id=None;self.pending=False;self.locked=False
        self.certificate=None;self.cache={};self.last_history=[]
        self.own=();self.original=();self.dead=();self.board=()
        self.chosen_discard=None;self.last_result=None;self.geometry=None;self.expected_reply=None;self.reserve=None

    def _money(self,msg):
        a=integer(msg['my_stack'],0,200);b=integer(msg['opp_stack'],0,200)
        pot=integer(msg['pot'],0,400)
        if pot!=400-a-b:raise ValueError('nonconserving pot/stacks')
        return 200-a,200-b

    def _board(self,msg,counts):
        board=parse_cards(msg['board'],counts)
        if board[:len(self.board)]!=self.board or set(board)&(set(self.original)|set(self.dead)):
            raise ValueError('changed/colliding public board')
        self.board=board
        return board

    def _same_hand(self,msg):
        if integer(msg['hand_id'],1,self.total)!=self.hand_id:raise ValueError('wrong hand')

    def _remaining_cost(self):
        return future_blinds(self.seat,self.total-self.hand_id)

    def _equity(self,board):
        """Coupled-scenario fixed discard choices; never max-own per runout.
        Pre-discard peer max over pairs is a pessimistic clairvoyant envelope,
        not a simulated legal opponent. Actual strategy uses uniform deal models.
        Post-discard uniform retained-pair estimates omit discard-selection bias.
        """
        key=(self.own,board,self.dead)
        if key in self.cache:return self.cache[key]
        if len(board)==5 and self.geometry is not None:return self.geometry[2],self.own
        n=self.samples
        own_pairs=list(combinations(self.own,2))
        blocked=set(self.original)|set(board)|set(self.dead)
        deck=[c for c in range(52) if c not in blocked]
        pre=len(self.own)==3
        peer_count=3 if pre else 2
        need=5-len(board)
        worlds=np.array([self.rng.sample(deck,peer_count+need) for _ in range(n)],dtype=np.int64)
        boards=np.column_stack((np.tile(board,(n,1)),worlds[:,peer_count:]))
        peer_options=list(combinations(range(peer_count),2))
        peer=np.stack([worlds[:,ix] for ix in peer_options])
        peer_full=np.concatenate((peer,np.broadcast_to(boards,(len(peer_options),n,5))),axis=2)
        strongest=eval_batch(peer_full.reshape(-1,7)).reshape(len(peer_options),n).max(axis=0)
        own_full=np.stack([np.column_stack((np.tile(pair,(n,1)),boards)) for pair in own_pairs])
        scores=eval_batch(own_full.reshape(-1,7)).reshape(len(own_pairs),n)
        estimates=((scores>strongest)+.5*(scores==strongest)).mean(axis=1)
        best=int(np.argmax(estimates))
        result=(float(estimates[best]),own_pairs[best])
        # Per-hand cache: <= five board states; reset at the next hand.
        if len(self.cache)<12:self.cache[key]=result
        return result

    def _safe_action(self,msg):
        legal=msg.get('legal_actions',[])
        if 'check' in legal:return dict(type='action',action='check')
        if self.pending and 'call' in legal:return dict(type='action',action='call')
        if 'fold' in legal:return dict(type='action',action='fold')
        if 'call' in legal:return dict(type='action',action='call')
        # Valid protocol requests always supply a passive action.
        raise ValueError('no safe legal action')

    def _arm(self,paid,board,allow_river=True):
        if not self.score_trusted:return
        future=self._remaining_cost()
        if self.locked:
            if self.score-paid[0]-future<self.reserve:
                self.score_trusted=False;self.locked=False;self.certificate=None
            elif self.certificate is not None:
                lower=self.score-paid[0]-future
                self.certificate.update(abandonment_lower=lower,lower=self.reserve)
            return
        if self.pending:return
        lower=self.score-paid[0]-future
        if lower>0:
            self.reserve=min(lower,self.match_cap) if self.spend_to_cap else lower
            self.locked=True;self.certificate=dict(kind='margin-budget' if self.spend_to_cap else 'abandon',abandonment_lower=lower,lower=self.reserve);self.proof_arms+=1;return
        if len(self.own)!=2 or len(self.dead)!=2:return
        floor=None;kind=None;peers=None
        if len(board)==4 and quads_turn(self.own,board,self.dead):floor=paid[1];kind='dead-card-turn'
        elif len(board)==5 and allow_river:
            if self.geometry is None:self.geometry=river_geometry(self.own,board,self.dead)
            relation,peers,_=self.geometry
            if relation>=0:floor=paid[1] if relation>0 else 0;kind='all-physical-river'
        if floor is not None and self.score+floor-future>0:
            self.pending=True;self.floor=floor;self.anchor=board
            lower=self.score+floor-future
            self.reserve=min(lower,self.match_cap) if self.spend_to_cap else lower
            self.certificate=dict(kind=kind,abandonment_lower=lower,lower=self.reserve,peers=peers)
            self.proof_arms+=1

    def _verify_history(self,history):
        if not isinstance(history,list):raise ValueError('history missing')
        if self.last_history and history[:len(self.last_history)]!=self.last_history:
            raise ValueError('changed accepted history')
        if self.expected_reply is not None:
            index,event,_=self.expected_reply
            if len(history)<=index or any(history[index].get(k)!=v for k,v in event.items()):
                raise ValueError('submitted own response absent or changed without correction notice')
            self.expected_reply=None

    def handle(self,msg):
        reply=self._handle(msg)
        if reply is not None and msg.get('type')=='action_request':
            event=dict(street=msg['street'],actor='me',action=reply['action'])
            delta=0
            if reply['action']=='raise':event['amount']=reply['amount'];delta=reply['amount']-msg['my_bet']
            elif reply['action']=='call':event['amount']=msg['opp_bet'];delta=msg['to_call']
            self.expected_reply=(len(msg['history']),event,200-msg['my_stack']+delta)
        return reply

    def _handle(self,msg):
        if not isinstance(msg,dict):return None
        kind=msg.get('type')
        if kind=='init':
            if self.ready:raise ValueError('repeated init')
            if msg['protocol_version']!='1.0' or (msg['starting_stack'],msg['small_blind'],msg['big_blind'])!=(200,1,2):
                raise ValueError('unsupported protocol/rules')
            self.total=integer(msg['total_hands'],1,10000)
            self.match_cap=400 if self.total<=400 else 1000
            self.bank=integer(msg['time_bank_ms'],1)
            self.per_reply=integer(msg['per_response_ms'],1)
            self.ready=True;return None
        if kind=='match_end':self.finished=True;return None
        # Unknown future types/fields are ignored, as required by the protocol.
        if kind not in ('new_hand','action_request','discard_request','discard_result','hand_result','notice'):return None
        if not self.ready:raise ValueError('init required')
        if kind=='new_hand':
            if self.hand_id is not None:raise ValueError('unfinished previous hand')
            h=integer(msg['hand_id'],1,self.total)
            if h!=self.completed+1:raise ValueError('nonsequential hand')
            seat=msg['seat']
            if seat not in ('button','big_blind') or (msg['stack'],msg['opp_stack'])!=(200,200):raise ValueError('unsupported hand')
            if hasattr(self,'last_seat') and seat==self.last_seat:raise ValueError('seats did not alternate')
            self.hand_id=h;self.seat=seat;self.last_seat=seat
            self.original=parse_cards(msg['hole_cards'],(3,));self.own=self.original
            self.dead=();self.board=();self.cache={};self.chosen_discard=None;self.last_history=[];self.geometry=None;self.expected_reply=None
            return None
        if kind=='notice':
            # The next full history / discard_result is authoritative. Do not
            # book the submitted action as accepted, nor guess its correction.
            self.score_trusted=False;self.locked=False;self.certificate=None;self.expected_reply=None
            return None
        self._same_hand(msg)
        if kind=='discard_result':
            own_discard=card(msg['my_discard']);opp_discard=card(msg['opp_discard'])
            own=parse_cards(msg['hole_cards'],(2,))
            if own_discard not in self.original or set(own)!=(set(self.original)-{own_discard}):raise ValueError('discard mismatch')
            if opp_discard in set(self.original)|set(self.board):raise ValueError('colliding opposing discard')
            if len(self.dead) and self.dead!=(own_discard,opp_discard):raise ValueError('changed public discard')
            self.own=own;self.dead=(own_discard,opp_discard);self.cache={}
            return None
        if kind=='hand_result':
            board=self._board(msg,(0,3,4,5))
            own=parse_cards(msg['my_hole_cards'],(2,3))
            if set(own)!=set(self.own):raise ValueError('result changed own cards')
            target=STREETS[LENGTHS.index(len(board))]
            self._verify_history(msg['history'])
            r=replay(msg['history'],self.seat,target)
            if msg['result']=='fold':
                if r.folded not in ('me','opp'):raise ValueError('fold result without folded actor')
                expected=-r.paid[0] if r.folded=='me' else r.paid[1]
            elif msg['result']=='showdown':
                if len(board)!=5 or len(self.dead)!=2 or r.folded or not r.closed or r.paid[0]!=r.paid[1]:raise ValueError('incomplete showdown')
                peer=parse_cards(msg['opp_hole_cards'],(2,))
                if set(peer)&(set(self.original)|set(board)|set(self.dead)):raise ValueError('colliding revealed peer')
                scores=eval_batch(np.array([self.own+board,peer+board],dtype=np.int64))
                expected=(int(scores[0]>scores[1])-int(scores[0]<scores[1]))*r.paid[0]
            else:raise ValueError('unknown result')
            if (msg.get('opp_discard') is not None) != bool(self.dead) or (self.dead and card(msg['opp_discard'])!=self.dead[1]):
                raise ValueError('result changed the exposed discard')
            net=integer(msg['net'],-200,200)
            if net!=expected:raise ValueError('net disagrees with public ledger / showdown')
            if self.pending and (net<self.floor or (msg['result']=='fold' and r.folded=='me')):
                self.score_trusted=False;self.certificate=None
            self.score+=net;self.completed+=1
            if self.pending and self.score_trusted:self.locked=True
            self.pending=False;self.last_result=self.hand_id;self.hand_id=None
            return None
        left=integer(msg['time_left_ms'],0)
        if kind=='discard_request':
            incoming=parse_cards(msg['hole_cards'],(3,))
            if set(incoming)!=set(self.original) or len(self.own)!=3:raise ValueError('wrong discard holding')
            board=self._board(msg,(3,));paid=self._money(msg)
            if paid[0]!=paid[1]:raise ValueError('discard before matching flop wagers')
            if self.expected_reply is not None and paid[0]!=self.expected_reply[2]:
                raise ValueError('submitted action not reflected in discard stacks')
            cap_sealed=self.locked and self.score-paid[0]-self._remaining_cost()>=self.match_cap
            if (self.locked and not self.spend_to_cap) or cap_sealed or left<100 or self.per_reply<100:
                discarded=default_discard(msg['hole_cards'])
            else:
                _,keep=self._equity(board)
                discarded=text_card(next(c for c in self.original if c not in keep))
            self.chosen_discard=discarded
            return dict(type='discard',card=discarded)
        street=msg['street'];board=self._board(msg,(LENGTHS[STREETS.index(street)],))
        paid=self._money(msg);self._verify_history(msg['history']);r=replay(msg['history'],self.seat,street)
        my_bet=integer(msg['my_bet'],0,200);opp_bet=integer(msg['opp_bet'],0,200)
        if (r.paid!=list(paid) or r.bets!=[my_bet,opp_bet] or r.actor!='me' or r.closed):
            raise ValueError('request differs from accepted-action history')
        if self.last_history and msg['history'][:len(self.last_history)]!=self.last_history:raise ValueError('changed accepted history')
        self.last_history=list(msg['history'])
        owed=integer(msg['to_call'],0,200)
        if owed!=max(0,r.bets[1]-r.bets[0]):raise ValueError('wrong call price')
        if len(board)>=4 and (len(self.own)!=2 or len(self.dead)!=2):raise ValueError('post-discard information missing')
        legal=msg['legal_actions']
        if not isinstance(legal,list) or not legal or len(legal)>4 or len(set(legal))!=len(legal) or not set(legal)<={'fold','check','call','raise'}:
            raise ValueError('unknown legal action')
        passive={'check'} if owed==0 else {'fold','call'}
        if set(legal)-{'raise'}!=passive:raise ValueError('missing passive action')
        if integer(msg['raises_left'],0,4)!=4-r.raises:raise ValueError('raise count mismatch')
        if 'raise' in legal:
            maximum=min(r.bets[0]+200-paid[0],r.bets[1]+200-paid[1])
            minimum=min(maximum,r.bets[1]+max(2,r.delta))
            if (integer(msg['min_raise'],1,200),integer(msg['max_raise'],1,200))!=(minimum,maximum) or r.raises>=4 or max(paid)==200:
                raise ValueError('raise range mismatch')
        self._arm(paid,board,allow_river=left>100 and self.per_reply>=100)
        if self.pending:
            if board[:len(self.anchor)]!=self.anchor:raise ValueError('stale settlement proof')
            required='call' if owed else 'check'
            if required not in legal:raise ValueError('safe continuation unavailable')
            return dict(type='action',action=required)
        if self.locked:
            self.lock_actions+=1
            if not self.spend_to_cap or self.score-paid[0]-self._remaining_cost()>=self.match_cap:
                return self._safe_action(msg)
        budget=200 if not self.locked else min(200,self.score-self._remaining_cost()-self.reserve)
        if self.locked and budget<=paid[0]:return self._safe_action(msg)
        if owed and paid[0]+owed>budget:return dict(type='action',action='fold')
        if left<100 or self.per_reply<100:return self._safe_action(msg)
        q,_=self._equity(board)
        pot=msg['pot'];price=owed/(pot+owed) if owed else 0
        if owed and q<price+.025:return dict(type='action',action='fold')
        budget_max=msg.get('max_raise',0) if not self.locked else min(msg.get('max_raise',0),my_bet+budget-paid[0])
        if 'raise' in legal and budget_max>=msg['min_raise'] and q>(.72 if len(board)<4 else .76):
            minimum=msg['min_raise'];maximum=budget_max
            amount=max(minimum,min(maximum,msg['opp_bet']+max(2,int(.65*(pot+owed)))))
            return dict(type='action',action='raise',amount=amount)
        return dict(type='action',action='call' if owed else 'check')

    def fallback(self,msg):
        self.errors+=1
        self.score_trusted=False;self.locked=False;self.certificate=None
        if not isinstance(msg,dict):return None
        if msg.get('type')=='discard_request':
            values=msg.get('hole_cards',[])
            if len(values)==3:
                try:return dict(type='discard',card=default_discard(values))
                except (ValueError,IndexError,TypeError):pass
        if msg.get('type')=='action_request':
            try:return self._safe_action(msg)
            except (ValueError,TypeError):return None
        if msg.get('type')=='hand_result':
            # Continue legal gameplay if reconciliation failed, but never claim
            # a certified lead from an unverified result.
            if self.hand_id==msg.get('hand_id'):
                self.completed+=1;self.hand_id=None;self.pending=False
        return None


def discard_main():
    bot=DiscardBot()
    for line in __import__('sys').stdin:
        try:
            msg=json.loads(line)
        except (ValueError,TypeError):continue
        try:reply=bot.handle(msg)
        except (ValueError,KeyError,TypeError,IndexError,OverflowError):reply=bot.fallback(msg)
        if reply is not None:print(json.dumps(reply,separators=(',',':')),flush=True)
        if bot.finished:break
    return bot
