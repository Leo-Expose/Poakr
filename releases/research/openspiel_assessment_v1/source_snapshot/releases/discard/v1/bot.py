#!/usr/bin/env python3
"""Discard Hold'em protocol 1.0 candidate. Organizer-runner certification pending.
Target Python 3.11; stdlib + NumPy only. No runtime file, network or process I/O.
"""
import sys, os
sys.dont_write_bytecode=True
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'

# SOURCE engine/numpy_eval.py
import numpy as np

# 10 straight patterns (bool 13-vec) + their high cards.  Wheel high = 3.
_STRAIGHTS = np.zeros((10, 13), np.bool_)
for _i, _top in enumerate(range(4, 13)):
    _STRAIGHTS[_i, _top - 4:_top + 1] = True
_STRAIGHTS[9, [0, 1, 2, 3, 12]] = True
_STRAIGHT_HIGH = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 3], np.int32)

_RANKS = np.arange(13, dtype=np.int32)[None, :]
_CAT = 20


def _top_n(mask, n):
    """
    mask: (N,W) bool — which columns are eligible (W = 13 for ranks, 4 for suits).
    Returns (N,n) int32 of the n HIGHEST-index eligible columns, descending.
    Empty slots are 0 (callers guarantee enough eligible columns).

    Key trick: key = eligible*1000 + column, sort descending.  Eligible columns
    always outrank ineligible ones, and among eligible, higher index first.
    """
    w = mask.shape[1]
    key = mask.astype(np.int32) * 1000 + np.arange(w, dtype=np.int32)[None, :]
    order = np.argsort(-key, axis=1, kind="stable")[:, :n]
    return order.astype(np.int32)


def eval_batch(cards):
    """
    cards: (N,7) integer array of card ids (rank*4 + suit).
    Returns (N,) int32 scores, higher is better.
    """
    c = np.asarray(cards)
    if c.ndim != 2 or c.shape[1] != 7:
        raise ValueError("cards must be (N,7)")
    N = c.shape[0]
    idx = np.arange(N)
    ranks = (c // 4).astype(np.int32)
    suits = (c % 4).astype(np.int32)

    # ---- rank multiplicities (N,13) ----
    cnt = np.zeros((N, 13), np.int8)
    for j in range(7):
        np.add.at(cnt, (idx, ranks[:, j]), 1)
    present = cnt > 0

    # ---- groups ----
    is4 = cnt == 4
    is3 = cnt == 3
    is_ge3 = cnt >= 3
    is2 = cnt == 2

    q = np.where(is4.any(1), _top_n(is4, 1)[:, 0], -1)

    t3 = np.where(is_ge3.any(1), _top_n(is_ge3, 1)[:, 0], -1)
    # second trip (full house from two trips)
    t3_rest = is_ge3.copy()
    rows = idx[t3 >= 0]
    t3_rest[rows, t3[t3 >= 0]] = False
    t3b = np.where(t3_rest.any(1), _top_n(t3_rest, 1)[:, 0], -1)

    p2 = is2.copy()
    p2a = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)
    rows = idx[p2a >= 0]
    p2[rows, p2a[p2a >= 0]] = False
    p2b = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)

    # ---- straight ----
    highs = np.full((N, 10), -1, np.int32)
    for k in range(10):
        ok = (present & _STRAIGHTS[k]).sum(1) == 5
        highs[:, k] = np.where(ok, _STRAIGHT_HIGH[k], -1)
    shigh = highs.max(1)

    # ---- flush ----
    suit_cnt = np.zeros((N, 4), np.int8)
    for j in range(7):
        np.add.at(suit_cnt, (idx, suits[:, j]), 1)
    has_flush = (suit_cnt >= 5).any(1)
    flush_suit = np.where(has_flush, _top_n(suit_cnt >= 5, 1)[:, 0], -1)

    # ---- straight flush ----
    sf_high = np.full(N, -1, np.int32)
    mrows = idx[has_flush]
    if len(mrows):
        fs = flush_suit[mrows]
        suit_rank = np.zeros((len(mrows), 13), np.bool_)
        for j in range(7):
            sel = suits[mrows, j] == fs
            suit_rank[np.arange(len(mrows))[sel], ranks[mrows, j][sel]] = True
        hs = np.full((len(mrows), 10), -1, np.int32)
        for k in range(10):
            ok = (suit_rank & _STRAIGHTS[k]).sum(1) == 5
            hs[:, k] = np.where(ok, _STRAIGHT_HIGH[k], -1)
        sf_high[mrows] = hs.max(1)
    is_sf = sf_high >= 0

    score = np.zeros(N, np.int64)

    # --- straight flush ---
    m = is_sf
    score[m] = (8 << _CAT) | sf_high[m]

    # --- quads ---
    m = (score == 0) & (q >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], q[m]] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (7 << _CAT) | (q[m] << 4) | kick

    # --- full house ---
    m = (score == 0) & (t3 >= 0) & ((p2a >= 0) | (t3b >= 0))
    if m.any():
        pair_rank = np.where(p2a >= 0, p2a, t3b)
        score[m] = (6 << _CAT) | (t3[m] << 4) | pair_rank[m]

    # --- flush ---
    m = (score == 0) & has_flush
    if m.any():
        r = idx[m]
        fs = flush_suit[m]
        sr = np.zeros((len(r), 13), np.bool_)
        for j in range(7):
            sel = suits[r, j] == fs
            sr[np.arange(len(r))[sel], ranks[r, j][sel]] = True
        top = _top_n(sr, 5)
        v = np.zeros(len(r), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = (5 << _CAT) | v

    # --- straight ---
    m = (score == 0) & (shigh >= 0)
    score[m] = (4 << _CAT) | shigh[m]

    # --- trips ---
    m = (score == 0) & (t3 >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], t3[m]] = True
        kick = _top_n(present & ~excl, 2)[idx[m]]
        score[m] = (3 << _CAT) | (t3[m] << 8) | (kick[:, 0] << 4) | kick[:, 1]

    # --- two pair ---
    m = (score == 0) & (p2a >= 0) & (p2b >= 0)
    if m.any():
        hi = np.maximum(p2a[m], p2b[m])
        lo = np.minimum(p2a[m], p2b[m])
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], hi] = True
        excl[idx[m], lo] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (2 << _CAT) | (hi << 8) | (lo << 4) | kick

    # --- one pair ---
    m = (score == 0) & (p2a >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], p2a[m]] = True
        kick = _top_n(present & ~excl, 3)[idx[m]]
        score[m] = (1 << _CAT) | (p2a[m] << 12) | (kick[:, 0] << 8) | (kick[:, 1] << 4) | kick[:, 2]

    # --- high card ---
    m = score == 0
    if m.any():
        top = _top_n(present[m], 5)
        v = np.zeros(m.sum(), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = v

    return score.astype(np.int32)





# SOURCE research/discard_holdem/proofs.py
from itertools import combinations
import numpy as np

RANKS = '23456789TJQKA'
SUITS = 'cdhs'  # internal encoding; NOT the organizer's discard tie-break order
DISCARD_ORDER = 'shdc'
WINDOWS = tuple(sum(1 << (4*r+s) for r in ranks) for s in range(4)
                for ranks in [*(tuple(range(h-4,h+1)) for h in range(4,13)),(12,0,1,2,3)])
RANK_MASKS = tuple(15 << (4*r) for r in range(13))


def card(text):
    if not isinstance(text,str) or len(text)!=2 or text[0] not in RANKS or text[1] not in SUITS:
        raise ValueError('invalid protocol card')
    return 4*RANKS.index(text[0])+SUITS.index(text[1])


def text_card(value):
    return RANKS[value//4]+SUITS[value%4]


def parse_cards(values, counts):
    if not isinstance(values,(list,tuple)) or len(values) not in counts:
        raise ValueError('bounded card list required')
    out=tuple(card(c) for c in values)
    if len(set(out))!=len(out):raise ValueError('duplicate cards')
    return out


def default_discard(values):
    return min(values,key=lambda c:(RANKS.index(c[0]),DISCARD_ORDER.index(c[1])))


def future_blinds(seat, remaining):
    if seat not in ('button','big_blind') or type(remaining) is not int or remaining<0:
        raise ValueError('known alternating seats and nonnegative hand count required')
    return (remaining//2)*3+(remaining%2)*(2 if seat=='button' else 1)


def quads_turn(hero, board, dead):
    """Sufficient all-peer/all-river rank certificate, <=13+40 mask checks.

    Higher quads need all four cards of a higher public rank. A known dead card
    obstructs them. A straight flush window needs at most three missing cards
    supplied by the river and two opponent cards; any blocked card obstructs it.
    All other categories lose to our quads. No runout enumeration at runtime.
    """
    hero,board,dead=tuple(hero),tuple(board),tuple(dead)
    if len(hero)!=2 or len(board)!=4 or len(dead)!=2:
        raise ValueError('post-discard turn and both public dead cards required')
    values=hero+board+dead
    if any(type(c) is not int or not 0<=c<52 for c in values) or len(set(values))!=8:
        raise ValueError('distinct normalized own/public cards required')
    rank=hero[0]//4
    if hero[1]//4!=rank or sum(c//4==rank for c in board)!=2:return False
    visible=sum(1<<c for c in board)
    blocked=sum(1<<c for c in hero+dead)
    for higher in range(rank+1,13):
        mask=RANK_MASKS[higher]
        if visible & mask and not blocked & mask:return False
    for window in WINDOWS:
        if (window & visible).bit_count()>=2 and not (window & blocked):return False
    return True


def river_geometry(hero,board,dead):
    """All physical retained pairs, including every low-probability holding.
    Return (minimum current net, number of physical pairs), or None if beatable.
    Dead cards constrain physical support, not a posterior selection model.
    """
    values=tuple(hero)+tuple(board)+tuple(dead)
    if len(hero)!=2 or len(board)!=5 or len(dead)!=2 or len(set(values))!=9:
        raise ValueError('complete post-discard physical state required')
    if any(type(c) is not int or not 0<=c<52 for c in values):raise ValueError('bad card')
    blocked=set(values)
    peers=np.array(list(combinations((c for c in range(52) if c not in blocked),2)),dtype=np.int64)
    boards=np.tile(board,(len(peers),1))
    peer_scores=eval_batch(np.column_stack((peers,boards)))
    own=int(eval_batch(np.array([tuple(hero)+tuple(board)],dtype=np.int64))[0])
    strongest=int(peer_scores.max())
    relation=(own>strongest)-(own<strongest)
    q=float(np.mean((own>peer_scores)+.5*(own==peer_scores)))
    return relation,len(peers),q


def river_floor(hero,board,dead,opponent_paid):
    if type(opponent_paid) is not int or not 0<=opponent_paid<=200:raise ValueError('bad paid')
    relation,n,_=river_geometry(hero,board,dead)
    return None if relation<0 else (opponent_paid if relation>0 else 0,n)


def match_cap_score(results):
    """Rulebook 8.3: sum clip(MATCH net,-C,C) / sum MATCH hand counts."""
    from fractions import Fraction
    numerator=denominator=0
    for net,hands,cap in results:
        if any(type(x) is not int for x in (net,hands,cap)) or hands<=0 or cap<=0:
            raise ValueError('integer match net and positive hands/cap required')
        numerator+=max(-cap,min(cap,net));denominator+=hands
    return Fraction(numerator,denominator) if denominator else Fraction(0)

# SOURCE research/discard_holdem/protocol.py
import json
import random
import time
from dataclasses import dataclass
from itertools import combinations
import numpy as np

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

if __name__=='__main__':
    discard_main()
