#!/usr/bin/env python3
"""Pokerbot v2: configurable core + EXAMPLE JSONL adapter (not official protocol).
Runtime: Python 3.11, stdlib + NumPy, no installs/network/runtime file writes.
"""
from __future__ import annotations
import os, time
PROGRAM_START=time.perf_counter()
# Honor 1-vCPU constraints before NumPy loads its numerical backend.
for _thread_key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_thread_key]='1'

# SOURCE: fast_eval.py
import numpy as np
_STRAIGHTS = np.zeros((10, 13), np.bool_)
for _i, _top in enumerate(range(4, 13)):
    _STRAIGHTS[_i, _top - 4:_top + 1] = True
_STRAIGHTS[9, [0, 1, 2, 3, 12]] = True           # wheel A-5
_STRAIGHT_HIGH = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 3], np.int32)
_RANKS13 = np.arange(13, dtype=np.int32)[None, :]
_CATSHIFT = 20


def _top_n(mask, n):
    w = mask.shape[1]
    key = mask.astype(np.int32) * 1000 + np.arange(w, dtype=np.int32)[None, :]
    order = np.argsort(-key, axis=1, kind="stable")[:, :n]
    return order.astype(np.int32)


def fast_eval_batch(cards):
    """
    cards: (N,7) int card ids (rank*4+suit).  Returns (N,) int32 scores.
    Higher is better.  Category << 20 | tiebreakers 4 bits each.
    """
    c = np.asarray(cards)
    if c.ndim != 2 or c.shape[1] != 7:
        raise ValueError("cards must be (N,7)")
    N = c.shape[0]
    idx = np.arange(N)
    ranks = (c // 4).astype(np.int32)
    suits = (c % 4).astype(np.int32)

    cnt = np.zeros((N, 13), np.int8)
    for j in range(7):
        np.add.at(cnt, (idx, ranks[:, j]), 1)
    present = cnt > 0

    is4 = cnt == 4
    is_ge3 = cnt >= 3
    is2 = cnt == 2

    q = np.where(is4.any(1), _top_n(is4, 1)[:, 0], -1)
    t3 = np.where(is_ge3.any(1), _top_n(is_ge3, 1)[:, 0], -1)
    t3_rest = is_ge3.copy()
    rows = idx[t3 >= 0]
    t3_rest[rows, t3[t3 >= 0]] = False
    t3b = np.where(t3_rest.any(1), _top_n(t3_rest, 1)[:, 0], -1)

    p2 = is2.copy()
    p2a = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)
    rows = idx[p2a >= 0]
    p2[rows, p2a[p2a >= 0]] = False
    p2b = np.where(p2.any(1), _top_n(p2, 1)[:, 0], -1)

    highs = np.full((N, 10), -1, np.int32)
    for k in range(10):
        ok = (present & _STRAIGHTS[k]).sum(1) == 5
        highs[:, k] = np.where(ok, _STRAIGHT_HIGH[k], -1)
    shigh = highs.max(1)

    suit_cnt = np.zeros((N, 4), np.int8)
    for j in range(7):
        np.add.at(suit_cnt, (idx, suits[:, j]), 1)
    has_flush = (suit_cnt >= 5).any(1)
    flush_suit = np.where(has_flush, _top_n(suit_cnt >= 5, 1)[:, 0], -1)

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

    m = is_sf
    score[m] = (8 << _CATSHIFT) | sf_high[m]

    m = (score == 0) & (q >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], q[m]] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (7 << _CATSHIFT) | (q[m] << 4) | kick

    m = (score == 0) & (t3 >= 0) & ((p2a >= 0) | (t3b >= 0))
    if m.any():
        pair_rank = np.where(p2a >= 0, p2a, t3b)
        score[m] = (6 << _CATSHIFT) | (t3[m] << 4) | pair_rank[m]

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
        score[m] = (5 << _CATSHIFT) | v

    m = (score == 0) & (shigh >= 0)
    score[m] = (4 << _CATSHIFT) | shigh[m]

    m = (score == 0) & (t3 >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], t3[m]] = True
        kick = _top_n(present & ~excl, 2)[idx[m]]
        score[m] = (3 << _CATSHIFT) | (t3[m] << 8) | (kick[:, 0] << 4) | kick[:, 1]

    m = (score == 0) & (p2a >= 0) & (p2b >= 0)
    if m.any():
        hi = np.maximum(p2a[m], p2b[m])
        lo = np.minimum(p2a[m], p2b[m])
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], hi] = True
        excl[idx[m], lo] = True
        kick = _top_n(present & ~excl, 1)[idx[m], 0]
        score[m] = (2 << _CATSHIFT) | (hi << 8) | (lo << 4) | kick

    m = (score == 0) & (p2a >= 0)
    if m.any():
        excl = np.zeros((N, 13), np.bool_)
        excl[idx[m], p2a[m]] = True
        kick = _top_n(present & ~excl, 3)[idx[m]]
        score[m] = (1 << _CATSHIFT) | (p2a[m] << 12) | (kick[:, 0] << 8) | (kick[:, 1] << 4) | kick[:, 2]

    m = score == 0
    if m.any():
        top = _top_n(present[m], 5)
        v = np.zeros(m.sum(), np.int64)
        for i in range(5):
            v |= top[:, i].astype(np.int64) << (16 - 4 * i)
        score[m] = v

    return score.astype(np.int32)

# SOURCE: core.py
import math
import time
import random
import signal
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections import OrderedDict
from itertools import combinations
from typing import Optional
import numpy as np

CATEGORIES = ('high', 'pair', 'two_pair', 'trips', 'straight', 'flush',
              'full_house', 'quads', 'straight_flush')

class ValidationError(ValueError):
    pass


def number(value, name, minimum=0.0):
    # Bounded magnitudes prevent overflow in pot arithmetic even for hostile JSON.
    if isinstance(value,bool) or not isinstance(value,(int,float)):
        raise ValidationError('invalid '+name)
    try:
        out=float(value)
    except (OverflowError,ValueError):
        raise ValidationError('invalid '+name) from None
    if not math.isfinite(out) or not minimum<=out<=1e12:
        raise ValidationError('invalid '+name)
    return out


def integer(value, name, minimum=0, maximum=1_000_000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValidationError('invalid ' + name)
    return value


def identifier(value, name):
    if isinstance(value,bool) or not isinstance(value,(str,int)) or not str(value).strip() or len(str(value))>128:
        raise ValidationError('invalid ' + name)
    return str(value)


class ComputationExpired(TimeoutError):
    pass


@contextmanager
def decision_guard(seconds):
    """POSIX main-thread watchdog; never replace a pre-existing host timer.
    NumPy C kernels may delay signal delivery until they return; bounded batches
    remain essential. Unsupported platforms/threads use deadline checks only.
    """
    armed=False; old_handler=None
    def expired(signum,frame): raise ComputationExpired('decision budget elapsed')
    try:
        if seconds>0 and hasattr(signal,'setitimer') and signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0):
            old_handler=signal.getsignal(signal.SIGALRM)
            try:
                signal.signal(signal.SIGALRM,expired)
                signal.setitimer(signal.ITIMER_REAL,seconds)
                armed=True
            except ValueError: pass  # not the main interpreter thread
        yield
    finally:
        if armed:
            signal.setitimer(signal.ITIMER_REAL,0)
            signal.signal(signal.SIGALRM,old_handler)


@dataclass(frozen=True)
class Rules:
    ranks: str = '23456789TJQKA'
    suits: str = 'cdhs'
    hole_count: int = 2
    board_by_street: tuple = (3, 1, 1)
    category_order: tuple = CATEGORIES
    wheel: bool = True
    exact_hole_used: Optional[int] = None
    # Override for unusual straight sequences: tuple of (rank-index tuple, high).
    straight_patterns: Optional[tuple] = None

    def __post_init__(self):
        if not isinstance(self.ranks, str) or not 5 <= len(self.ranks) <= 15 or len(set(self.ranks)) != len(self.ranks):
            raise ValidationError('ranks must be 5..15 unique symbols')
        if not isinstance(self.suits, str) or not 2 <= len(self.suits) <= 4 or len(set(self.suits)) != len(self.suits):
            raise ValidationError('suits must be 2..4 unique symbols; five-of-a-kind unsupported')
        integer(self.hole_count, 'hole_count', 1, 4)
        if not isinstance(self.board_by_street, tuple) or not 1 <= len(self.board_by_street) <= 6:
            raise ValidationError('board_by_street must be a tuple of 1..6 streets')
        for v in self.board_by_street: integer(v, 'street reveal count', 1, 5)
        if not 5 <= self.hole_count + self.board_count <= 9:
            raise ValidationError('supported total hand size is 5..9 cards')
        if 2*self.hole_count + self.board_count > self.deck_size:
            raise ValidationError('deck too small')
        if not isinstance(self.category_order, tuple) or set(self.category_order) != set(CATEGORIES) or len(self.category_order) != 9:
            raise ValidationError('category_order must permute all categories')
        if not isinstance(self.wheel, bool): raise ValidationError('wheel must be boolean')
        if self.exact_hole_used is not None:
            integer(self.exact_hole_used, 'exact_hole_used', 0, min(5, self.hole_count))
            if 5-self.exact_hole_used > self.board_count:
                raise ValidationError('not enough board cards for selection constraint')
        if self.straight_patterns is not None:
            if not isinstance(self.straight_patterns, tuple) or len(self.straight_patterns)>32:
                raise ValidationError('invalid straight patterns')
            for ranks, high in self.straight_patterns:
                if len(ranks)!=5 or len(set(ranks))!=5:
                    raise ValidationError('straight needs five unique ranks')
                for r in ranks: integer(r, 'straight rank', 0, len(self.ranks)-1)
                integer(high, 'straight high', 0, len(self.ranks)-1)

    @property
    def deck_size(self): return len(self.ranks)*len(self.suits)
    @property
    def board_count(self): return sum(self.board_by_street)
    @property
    def board_lengths(self):
        lengths=[0]; n=0
        for k in self.board_by_street: n+=k; lengths.append(n)
        return tuple(lengths)
    @property
    def patterns(self):
        if self.straight_patterns is not None: return self.straight_patterns
        p=[(tuple(range(high-4, high+1)), high) for high in range(4,len(self.ranks))]
        if self.wheel: p.append(((0,1,2,3,len(self.ranks)-1),3))
        return tuple(p)
    @property
    def fast_standard(self):
        return len(self.ranks)==13 and len(self.suits)==4 and self.hole_count==2 and self.board_count==5 and self.category_order==CATEGORIES and self.wheel and self.exact_hole_used is None and self.straight_patterns is None

    def card(self, value):
        if isinstance(value, int) and not isinstance(value,bool):
            return integer(value,'card',0,self.deck_size-1)
        if not isinstance(value,str): raise ValidationError('card must be string or int')
        v=value.strip().replace('10','T')
        symbols={'♠':'s','♥':'h','♦':'d','♣':'c'}
        if len(v)!=2: raise ValidationError('invalid card text')
        rank=v[0].upper(); suit=symbols.get(v[1],v[1].lower())
        if rank not in self.ranks or suit not in self.suits:
            raise ValidationError('card outside configured deck')
        return self.ranks.index(rank)*len(self.suits)+self.suits.index(suit)

    def cards(self, values):
        if not isinstance(values, (list,tuple)) or len(values)>self.deck_size:
            raise ValidationError('invalid card list')
        out=tuple(self.card(v) for v in values)
        if len(set(out))!=len(out): raise ValidationError('duplicate cards')
        return out


@dataclass(frozen=True)
class Settings:
    # Replay mode is an explicit hypothesis. 'off' is the conservative default.
    duplicate_mode: str = 'off'  # off / board / pair_id
    risk_strength: float = 0.0  # experimental, not assumed beneficial
    alpha: float = 0.02
    max_samples: int = 1024
    batch_size: int = 128
    max_exact: int = 2000
    decision_cap_s: float = 0.025
    reserve_fraction: float = 0.25
    prior_fold_a: float = 2.0
    prior_fold_b: float = 4.0
    proactive_bluff: bool = False
    cache_size: int = 512
    history_size: int = 1600

    def __post_init__(self):
        if self.duplicate_mode not in ('off','board','pair_id'): raise ValidationError('duplicate_mode')
        number(self.risk_strength,'risk_strength'); number(self.decision_cap_s,'decision_cap_s')
        if self.risk_strength>0.5 or not 0 < self.decision_cap_s <= 0.15: raise ValidationError('unsafe compute/risk settings')
        if not 0<self.alpha<1 or not 0.1<=self.reserve_fraction<=0.8: raise ValidationError('alpha/reserve')
        for name,lo,hi in [('max_samples',64,8192),('batch_size',8,256),('max_exact',1,4000),
                            ('cache_size',1,2048),('history_size',1,4096)]:
            integer(getattr(self,name),name,lo,hi)
        number(self.prior_fold_a,'prior_fold_a',0.01); number(self.prior_fold_b,'prior_fold_b',0.01)
        if not isinstance(self.proactive_bluff,bool): raise ValidationError('proactive_bluff')


@dataclass(frozen=True)
class Action:
    kind: str
    # bet pay = chips contributed NOW, INCLUDING any call. No implied fractions.
    pay: float = 0.0

    def __post_init__(self):
        if self.kind not in ('fold','check','call','bet'): raise ValidationError('invalid action kind')
        number(self.pay,'action pay')
        if self.kind!='bet' and self.pay!=0: raise ValidationError('only bet carries pay')


def safe_action(legal):
    for kind in ('check','fold','call'):
        for a in legal:
            if a.kind==kind: return a
    if legal: return min(legal,key=lambda a:a.pay)
    raise ValidationError('no known legal fallback')


@dataclass(frozen=True)
class Observation:
    request_id: str
    hand_id: str
    hole: tuple
    board: tuple
    pot: float
    to_call: float
    my_stack: float
    opp_stack: float
    legal: tuple
    pair_id: Optional[str] = None
    chip_lead: float = 0.0
    hands_left: Optional[int] = None

    def validate(self, rules):
        if not isinstance(self.request_id,str) or not isinstance(self.hand_id,str):
            raise ValidationError('canonical IDs must be strings')
        if not isinstance(self.hole,tuple) or not isinstance(self.board,tuple):
            raise ValidationError('canonical cards must be tuples')
        identifier(self.request_id,'request_id'); identifier(self.hand_id,'hand_id')
        if self.pair_id is not None: identifier(self.pair_id,'pair_id')
        if len(self.hole)!=rules.hole_count or len(self.board) not in rules.board_lengths:
            raise ValidationError('hole/board size inconsistent with rules')
        if rules.cards(self.hole+self.board) != self.hole+self.board:
            raise ValidationError('canonical card encoding required')
        for name in ('pot','to_call','my_stack','opp_stack'): number(getattr(self,name),name)
        if self.to_call>self.pot+1e-9: raise ValidationError('pot must include outstanding opponent bet')
        number(self.chip_lead,'chip_lead',-1e12)
        if self.hands_left is not None: integer(self.hands_left,'hands_left')
        if not isinstance(self.legal,tuple) or not 1<=len(self.legal)<=64 or len(set(self.legal))!=len(self.legal):
            raise ValidationError('invalid legal set')
        for a in self.legal:
            if not isinstance(a,Action): raise ValidationError('legal action type')
            if a.kind=='check' and self.to_call>0: raise ValidationError('cannot check facing bet')
            if a.kind=='call' and (self.to_call<=0 or self.my_stack<=0): raise ValidationError('cannot call free or empty stack')
            if a.kind=='bet' and (a.pay<=self.to_call or a.pay>self.my_stack+1e-9 or self.opp_stack<=0):
                raise ValidationError('invalid bet payment')
        return self

    def price(self):
        # Exclude an opponent overbet that we cannot match (uncalled refund).
        call=min(self.to_call,self.my_stack)
        pot=self.pot-max(0.0,self.to_call-self.my_stack)
        return call,pot,call/(pot+call) if pot+call else 0.0


class ComputeBank:
    """Tracks full request handling, not only equity. Host time_left may tighten it.
    Waiting on stdin is excluded locally; wall accounting by host is authoritative.
    """
    def __init__(self, total_s, hands_total, reserve_fraction, clock=time.perf_counter):
        number(total_s,'bank total',0.01); integer(hands_total,'hands_total',1,100_000)
        self.total=float(total_s); self.hands_total=hands_total
        self.reserve_fraction=reserve_fraction; self.clock=clock
        self.spent=0.0; self.host_left=None; self.requests=0
    def remaining(self):
        own=max(0.0,self.total*(1-self.reserve_fraction)-self.spent)
        if self.host_left is not None:
            own=min(own,max(0.0,self.host_left-self.total*self.reserve_fraction))
        return own
    def update_host(self,left):
        number(left,'time_left'); self.host_left=float(left)
    def charge(self,elapsed):
        self.spent+=max(0.0,elapsed)
        if self.host_left is not None: self.host_left=max(0.0,self.host_left-max(0.0,elapsed))
        self.requests+=1
    def budget(self,hands_left,cap):
        # Allocate a conservative fraction per HAND; multiple requests share it.
        left=max(1,hands_left if hands_left is not None else self.hands_total)
        return min(cap,self.remaining(),self.remaining()/left/4)


class Evaluator:
    """Exact evaluation for configured deck/order/selection; optimized standard path.
    Supports rank-order changes, short decks, board geometry and exact hole usage.
    Other mechanics (wild cards, lowball, mandatory suits, etc.) need new plugins.
    """
    def __init__(self,rules):
        self.rules=rules
        self.fast=rules.fast_standard
        self.cat={name:i for i,name in enumerate(rules.category_order)}
        total=rules.hole_count+rules.board_count
        self.indices=np.array([c for c in combinations(range(total),5)
                               if rules.exact_hole_used is None or sum(i<rules.hole_count for i in c)==rules.exact_hole_used],np.int64)
        if not len(self.indices): raise ValidationError('no valid five-card subsets')

    def _five(self,c):
        nr,ns=len(self.rules.ranks),len(self.rules.suits)
        n=len(c); rows=np.arange(n)
        rank=(c//ns).astype(np.int64); suit=c%ns
        cnt=np.zeros((n,nr),np.int8)
        for j in range(5): np.add.at(cnt,(rows,rank[:,j]),1)
        present=cnt>0
        flush=np.all(suit==suit[:,:1],axis=1)
        straight=np.full(n,-1,np.int64)
        for ranks,high in self.rules.patterns:
            straight=np.maximum(straight,np.where(np.all(present[:,ranks],axis=1),high,-1))
        values=np.arange(nr)[None,:]
        def top(mask,k):
            return np.sort(np.where(mask,values,-1),axis=1)[:,::-1][:,:k]
        def pack(ranks):
            out=np.zeros(n,np.int64)
            for j in range(ranks.shape[1]): out=(out<<4)|np.maximum(0,ranks[:,j])
            return out
        def score(name,tie,eligible):
            return np.where(eligible,(self.cat[name]<<24)+tie,-1)
        sorted_ranks=np.sort(rank,axis=1)[:,::-1]
        pairs=top(cnt==2,2); trips=top(cnt==3,1)[:,0]; quads=top(cnt==4,1)[:,0]
        kickers=top(cnt==1,3)
        full=(trips>=0)&(pairs[:,0]>=0)
        sf=flush&(straight>=0)
        result=score('high',pack(sorted_ranks),~flush&(straight<0)&(pairs[:,0]<0)&(trips<0)&(quads<0))
        result=np.maximum(result,score('pair',(pairs[:,0]<<12)|pack(kickers),(pairs[:,0]>=0)&(pairs[:,1]<0)&(trips<0)))
        result=np.maximum(result,score('two_pair',(pairs[:,0]<<8)|(pairs[:,1]<<4)|kickers[:,0],pairs[:,1]>=0))
        result=np.maximum(result,score('trips',(trips<<8)|pack(kickers[:,:2]),(trips>=0)&~full))
        result=np.maximum(result,score('straight',straight,(straight>=0)&~flush))
        result=np.maximum(result,score('flush',pack(sorted_ranks),flush&~sf))
        result=np.maximum(result,score('full_house',(trips<<4)|pairs[:,0],full))
        result=np.maximum(result,score('quads',(quads<<4)|kickers[:,0],quads>=0))
        result=np.maximum(result,score('straight_flush',straight,sf))
        return result

    def score(self,cards):
        c=np.asarray(cards)
        total=self.rules.hole_count+self.rules.board_count
        if c.ndim!=2 or c.shape[1]!=total or not np.issubdtype(c.dtype,np.integer):
            raise ValidationError('invalid evaluator shape/type')
        if np.any(c<0) or np.any(c>=self.rules.deck_size) or (len(c) and np.any(np.diff(np.sort(c,axis=1),axis=1)==0)):
            raise ValidationError('invalid evaluator cards')
        if not len(c): return np.empty(0,np.int64)
        if self.fast:
            # Score encoding differs from generic but relative ordering is identical.
            return fast_eval_batch(c)
        out=np.empty(len(c),np.int64)
        # Bounded intermediate arrays even with 9 choose 5 subsets.
        for start in range(0,len(c),32):
            chunk=c[start:start+32]
            vals=self._five(chunk[:,self.indices].reshape(-1,5)).reshape(len(chunk),-1)
            out[start:start+len(chunk)]=vals.max(axis=1)
        return out


@dataclass(frozen=True)
class EquityResult:
    value: float
    low: float
    high: float
    samples: int
    exact: bool
    source: str
    looks: int = 0


class EquityEngine:
    def __init__(self,rules,settings,rng,clock=time.perf_counter):
        self.rules=rules; self.settings=settings; self.rng=rng; self.clock=clock
        self.evaluator=Evaluator(rules); self.cache=OrderedDict(); self.partial=None
    def _put(self,key,result):
        self.cache[key]=result; self.cache.move_to_end(key)
        while len(self.cache)>self.settings.cache_size: self.cache.popitem(last=False)
    def estimate(self,hole,board,opponent,thresholds,deadline):
        self.partial=None
        hole=tuple(hole); board=tuple(board); opponent=tuple(opponent) if opponent is not None else None
        used=hole+board+(opponent or ())
        if len(set(used))!=len(used): raise ValidationError('equity card collision')
        key=(tuple(sorted(hole)),board,tuple(sorted(opponent)) if opponent else None)
        cached=self.cache.get(key)
        if cached is not None:
            self.cache.move_to_end(key)
            if cached.exact or cached.samples>=self.settings.max_samples or all(cached.high<t or cached.low>t for t in thresholds):
                return cached
        if self.clock()>=deadline: return None
        rem=np.array([c for c in range(self.rules.deck_size) if c not in set(used)],np.int64)
        need=self.rules.board_count-len(board); nh=self.rules.hole_count
        if need<0 or len(rem)<need+(0 if opponent else nh): raise ValidationError('not enough unseen cards')
        total=math.comb(len(rem),need) if opponent is not None else self.settings.max_exact+1
        if opponent is not None and total<=self.settings.max_exact:
            count=0; won=0.0; batch=[]
            for runout in combinations(rem,need):
                batch.append(runout)
                if len(batch)==self.settings.batch_size or count+len(batch)==total:
                    if self.clock()>=deadline: return None  # NEVER report biased enumeration prefix.
                    x=np.asarray(batch,np.int64).reshape(len(batch),need)
                    scores=self._compare(hole,board,np.tile(opponent,(len(batch),1)),x)
                    won+=float(scores.sum()); count+=len(batch); batch=[]
            v=won/count; result=EquityResult(v,v,v,count,True,'known-exact')
            self._put(key,result); return result
        count=cached.samples if cached is not None else 0
        won=round(cached.value*count*2)/2 if cached is not None else 0.0
        looks=cached.looks if cached is not None else 0
        result=cached
        batch_size=self.settings.batch_size if self.rules.fast_standard else min(16,self.settings.batch_size)
        while count<self.settings.max_samples and self.clock()<deadline:
            n=min(batch_size,self.settings.max_samples-count)
            take=need+(0 if opponent else nh)
            if take:
                keys=self.rng.random((n,len(rem)))
                pick=rem[np.argpartition(keys,take-1,axis=1)[:,:take]]
            else: pick=np.empty((n,0),np.int64)
            opp=np.tile(opponent,(n,1)) if opponent is not None else pick[:,:nh]
            runouts=pick if opponent is not None else pick[:,nh:]
            scores=self._compare(hole,board,opp,runouts)
            count+=n; won+=float(scores.sum()); looks+=1
            value=won/count
            # alpha/(k*(k+1)) spending + Hoeffding: valid over all inspected looks.
            width=math.sqrt(math.log(2*looks*(looks+1)/self.settings.alpha)/(2*count))
            result=EquityResult(value,max(0.0,value-width),min(1.0,value+width),count,False,
                                'known-mc' if opponent is not None else 'random-range-mc',looks)
            self.partial=result
            self._put(key,result)
            if count>=64 and all(result.high<t or result.low>t for t in thresholds): break
        # Resume cached MC samples without resetting alpha spending or pretending
        # a previously stopped estimate has precision it does not possess.
        return result
    def _compare(self,hole,board,opp,runouts):
        n=len(runouts); nh=self.rules.hole_count; nb=len(board)
        a=np.empty((n,nh+self.rules.board_count),np.int64); b=np.empty_like(a)
        a[:,:nh]=hole; b[:,:nh]=opp
        a[:,nh:nh+nb]=board; b[:,nh:nh+nb]=board
        a[:,nh+nb:]=runouts; b[:,nh+nb:]=runouts
        sa,sb=self.evaluator.score(a),self.evaluator.score(b)
        return (sa>sb).astype(float)+0.5*(sa==sb)


@dataclass
class HandRecord:
    hole: tuple
    board: tuple
    pair_id: Optional[str]
    terminal: bool = False


class DuplicateMemory:
    def __init__(self,rules,settings):
        self.rules=rules; self.settings=settings; self.history=OrderedDict()
        self.matches=0; self.contradictions=0; self.confirmed_swaps=0; self.inferred={}; self.current_id=None
    def _compatible(self,record,hole,board):
        k=min(len(record.board),len(board))
        return not set(record.hole)&set(hole+board) and record.board[:k]==board[:k]
    def observe(self,obs):
        existing=self.history.get(obs.hand_id)
        if existing is not None and existing.terminal: raise ValidationError('new request for finished hand')
        if existing and (existing.hole!=tuple(sorted(obs.hole)) or existing.board!=obs.board[:len(existing.board)] or existing.pair_id!=obs.pair_id):
            raise ValidationError('hand ID reused or board regressed/changed')
        new=existing is None
        if new:
            # Count only genuine new-hand replay evidence, not every request.
            if len(obs.board)>=3 and any(hid!=obs.hand_id and len(h.board)>=3 and self._compatible(h,obs.hole,obs.board)
                                          for hid,h in self.history.items()): self.matches+=1
        elif len(existing.board)<3<=len(obs.board):
            if any(hid!=obs.hand_id and len(h.board)>=3 and self._compatible(h,obs.hole,obs.board)
                   for hid,h in self.history.items()): self.matches+=1
        self.history[obs.hand_id]=HandRecord(tuple(sorted(obs.hole)),obs.board,obs.pair_id)
        self.history.move_to_end(obs.hand_id); self.current_id=obs.hand_id
        while len(self.history)>self.settings.history_size:
            hid,_=self.history.popitem(last=False); self.inferred.pop(hid,None)
    def infer(self,obs):
        if self.settings.duplicate_mode=='off' or self.contradictions: return None
        candidates=set()
        for hid,h in self.history.items():
            if hid==obs.hand_id or not self._compatible(h,obs.hole,obs.board): continue
            by_id=self.settings.duplicate_mode=='pair_id' and obs.pair_id is not None and h.pair_id==obs.pair_id
            k=min(len(h.board),len(obs.board))
            by_board=self.matches>=3 and k>=3 and h.board[:k]==obs.board[:k]
            if by_id or by_board: candidates.add(h.hole)
        if len(candidates)!=1: return None
        inferred=next(iter(candidates)); self.inferred[obs.hand_id]=inferred
        return inferred
    def finish_hand(self,hand_id,public_board=None,opponent=None):
        record=self.history.get(hand_id)
        if record is None: raise ValidationError('unknown finished hand')
        board=record.board if public_board is None else self.rules.cards(public_board)
        if len(board) not in self.rules.board_lengths or board[:len(record.board)]!=record.board or set(board)&set(record.hole):
            raise ValidationError('inconsistent public final board')
        if opponent is not None:
            opponent=self.rules.cards(opponent)
            if len(opponent)!=self.rules.hole_count or set(opponent)&set(record.hole+board):
                raise ValidationError('impossible public opponent cards')
        if len(record.board)<3<=len(board) and any(hid!=hand_id and len(h.board)>=3 and self._compatible(h,record.hole,board)
                                                   for hid,h in self.history.items()): self.matches+=1
        self.history[hand_id]=HandRecord(record.hole,board,record.pair_id,True)
        if opponent is not None: self.reveal(hand_id,opponent)

    def reveal(self,hand_id,opponent):
        opponent=self.rules.cards(opponent)
        if len(opponent)!=self.rules.hole_count: raise ValidationError('invalid opponent reveal')
        record=self.history.get(hand_id)
        if record is None: raise ValidationError('reveal for unknown hand')
        if set(opponent)&set(record.hole+record.board): raise ValidationError('impossible public opponent cards')
        inferred=self.inferred.get(hand_id)
        if inferred is not None:
            if set(inferred)!=set(opponent): self.contradictions+=1
            else: self.confirmed_swaps+=1
        self.inferred.pop(hand_id,None)



class OpponentStats:
    def __init__(self,settings):
        self.settings=settings; self.counts={}; self.last_seq=-1
    @staticmethod
    def size_bin(ratio): return 0 if ratio<=0.5 else 1 if ratio<=1.0 else 2
    def observe(self,seq,street,kind,faced_bet,ratio):
        integer(seq,'event seq'); integer(street,'event street',0,6)
        if kind not in ('fold','check','call','bet'): raise ValidationError('opponent action')
        if not isinstance(faced_bet,bool): raise ValidationError('faced_bet must be bool')
        number(ratio,'faced ratio')
        if faced_bet and kind=='check': raise ValidationError('opponent cannot check facing bet')
        if seq<=self.last_seq: return False  # replayed/out-of-order histories do not inflate counts.
        self.last_seq=seq
        if faced_bet:
            key=(street,self.size_bin(ratio)); a,b,n=self.counts.get(key,(self.settings.prior_fold_a,self.settings.prior_fold_b,0))
            self.counts[key]=(a+int(kind=='fold'),b+int(kind!='fold'),n+1)
        return True
    def fold_lower(self,street,ratio):
        a,b,n=self.counts.get((street,self.size_bin(ratio)),(self.settings.prior_fold_a,self.settings.prior_fold_b,0))
        if n<12: return 0.0
        mean=a/(a+b); variance=a*b/((a+b)**2*(a+b+1))
        # Cantelli 90% posterior bound; not a guarantee against nonstationarity.
        return max(0.0,mean-3*math.sqrt(variance))


class Policy:
    """Fast heuristic, NOT a solved betting game. Future ranges remain a limitation."""
    def __init__(self,rules,settings,stats,rng):
        self.rules=rules; self.settings=settings; self.stats=stats; self.rng=rng
    def thresholds(self,obs):
        return (obs.price()[2]+0.035,0.66,0.86)
    def choose(self,obs,eq,known,hands_total):
        if eq is None: return safe_action(obs.legal)
        value=eq.value; call,pot,po=obs.price()
        street=self.rules.board_lengths.index(len(obs.board))
        passive=safe_action(obs.legal)
        bets=[a for a in obs.legal if a.kind=='bet']
        urgency=1-(obs.hands_left if obs.hands_left is not None else hands_total)/hands_total
        risk=-max(-1,min(1,obs.chip_lead/200))*max(0,min(1,urgency))*self.settings.risk_strength
        value_bar=0.66-0.15*risk
        margin=0.0 if known and eq.exact else 0.035-0.10*risk
        if call:
            if value<=po+margin: return passive
            passive=next((a for a in obs.legal if a.kind=='call'),passive)
            if value<0.86 or not bets: return passive
        elif value<=value_bar:
            if not self.settings.proactive_bluff or street==0 or not bets: return passive
            eligible=[]
            for a in bets:
                extra=min(a.pay,self.my_effective(obs))-call
                ratio=extra/max(1e-12,pot)
                f=self.stats.fold_lower(street,ratio)
                # Pure bluff break-even; conservative observations, not a prior.
                if f>ratio/(1+ratio)+0.08 and risk>=-0.1:
                    eligible.append(a)
            return min(eligible,key=lambda a:a.pay) if eligible and self.rng.random()<0.45 else passive
        if not bets: return passive
        target=call+pot*(1.0 if value>0.86 else 0.5)
        return min(bets,key=lambda a:abs(a.pay-target))
    @staticmethod
    def my_effective(obs): return min(obs.my_stack,obs.opp_stack+obs.to_call)


class BotSession:
    """All mutable bot state belongs to ONE match/opponent. No global model or RNG."""
    def __init__(self,match_id,rules=Rules(),settings=Settings(),hands_total=400,timebank_s=60,seed=0,clock=time.perf_counter):
        integer(seed,'seed',0,2**64-1)
        if not isinstance(rules,Rules) or not isinstance(settings,Settings): raise ValidationError('rules/settings type')
        self.match_id=identifier(match_id,'match_id'); self.rules=rules; self.settings=settings
        self.bank=ComputeBank(timebank_s,hands_total,settings.reserve_fraction,clock)
        self.clock=clock; self.rng=random.Random(seed); self.np_rng=np.random.default_rng(seed)
        self.equity=EquityEngine(rules,settings,self.np_rng,clock)
        self.duplicate=DuplicateMemory(rules,settings); self.opponent=OpponentStats(settings)
        self.policy=Policy(rules,settings,self.opponent,self.rng)
        self.responses=OrderedDict(); self.decisions=0; self.info_decisions=0; self.errors=0
        self.last_equity=None
    def act(self,obs,charge=True):
        start=self.clock()
        try:
            obs.validate(self.rules)
            if obs.request_id in self.responses:
                prior,action=self.responses[obs.request_id]
                if prior!=obs: raise ValidationError('request ID reused with different payload')
                self.responses.move_to_end(obs.request_id); return action
            if obs.hands_left is not None and obs.hands_left>self.bank.hands_total:
                raise ValidationError('hands_left exceeds match length')
            self.duplicate.observe(obs)
            known=self.duplicate.infer(obs)
            budget=self.bank.budget(obs.hands_left,self.settings.decision_cap_s)
            if len(obs.legal)==1 or budget<0.0005:
                result=None; action=safe_action(obs.legal)
            else:
                self.equity.partial=None
                try:
                    # Budget starts at request handling, not after validation.
                    left=max(0.0,start+budget-self.clock())
                    if left==0: raise ComputationExpired('no decision time remains')
                    with decision_guard(left):
                        result=self.equity.estimate(obs.hole,obs.board,known,self.policy.thresholds(obs),start+budget)
                        action=self.policy.choose(obs,result,known is not None,self.bank.hands_total)
                except ComputationExpired:
                    result=self.equity.partial
                    if result is not None and result.samples>=64:
                        action=self.policy.choose(obs,result,known is not None,self.bank.hands_total)
                    else:
                        result=None; action=safe_action(obs.legal)
                    self.errors+=1
            if action not in obs.legal: raise AssertionError('policy returned illegal action')
            self.last_equity=result; self.decisions+=1
            self.info_decisions+=int(known is not None and result is not None)
            self.responses[obs.request_id]=(obs,action)
            while len(self.responses)>self.settings.cache_size: self.responses.popitem(last=False)
            return action
        finally:
            if charge: self.bank.charge(self.clock()-start)

# SOURCE: adapter.py
import sys
import time
import json
import argparse

MAX_LINE_BYTES = 131072



def strict_json(text):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out: raise ValidationError('duplicate JSON key')
            out[key]=value
        return out
    def constant(value): raise ValidationError('nonfinite JSON')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=constant)


def rules_from_dict(value):
    if not isinstance(value,dict): raise ValidationError('rules must be an object')
    known=set(Rules.__dataclass_fields__)
    if set(value)-known: raise ValidationError('unknown rule fields')
    data=dict(value)
    for k in ('board_by_street','category_order'):
        if k in data: data[k]=tuple(data[k])
    if data.get('straight_patterns') is not None:
        data['straight_patterns']=tuple((tuple(ranks),high) for ranks,high in data['straight_patterns'])
    return Rules(**data)


def settings_from_dict(value):
    if not isinstance(value,dict) or set(value)-set(Settings.__dataclass_fields__):
        raise ValidationError('unknown setting fields')
    return Settings(**value)


def legal_from_json(values):
    if not isinstance(values,list) or not 1<=len(values)<=64: raise ValidationError('legal must be a nonempty bounded list')
    actions=[]
    for item in values:
        if not isinstance(item,dict) or set(item)-{'kind','pay'}: raise ValidationError('invalid action object')
        actions.append(Action(item.get('kind'),number(item.get('pay',0),'pay')))
    if len(set(actions))!=len(actions): raise ValidationError('duplicate legal action')
    return tuple(actions)


def observation_from_json(obj,rules):
    legal=legal_from_json(obj.get('legal'))
    hands_left=obj.get('hands_left')
    if hands_left is not None: hands_left=integer(hands_left,'hands_left')
    pair=obj.get('pair_id')
    return Observation(
        request_id=identifier(obj.get('request_id'),'request_id'),
        hand_id=identifier(obj.get('hand_id'),'hand_id'),
        hole=tuple(sorted(rules.cards(obj.get('hole')))),
        board=rules.cards(obj.get('board')),
        pot=number(obj.get('pot'),'pot'),to_call=number(obj.get('to_call'),'to_call'),
        my_stack=number(obj.get('my_stack'),'my_stack'),opp_stack=number(obj.get('opp_stack'),'opp_stack'),
        legal=legal,pair_id=identifier(pair,'pair_id') if pair is not None else None,
        chip_lead=number(obj.get('chip_lead',0),'chip_lead',-1e12),hands_left=hands_left)


def action_response(request_id,action):
    value={'kind':action.kind}
    if action.kind=='bet': value['pay']=action.pay
    return {'type':'action','request_id':request_id,'action':value}


class ExampleAdapter:
    def __init__(self,rules=Rules(),settings=Settings(),seed=0,boot_cost=0):
        self.rules=rules; self.settings=settings; self.seed=seed
        self.boot_cost=boot_cost; self.session=None; self.completed=set(); self.failures=0
    def handle(self,obj):
        if not isinstance(obj,dict): raise ValidationError('message must be object')
        kind=obj.get('type')
        if kind=='start_match':
            mid=identifier(obj.get('match_id'),'match_id')
            if self.session is not None and self.session.match_id==mid:
                raise ValidationError('duplicate start_match must not reset state or bank')
            if self.session is not None: raise ValidationError('end current match before starting another')
            if mid in self.completed: raise ValidationError('match ID reused')
            self.session=BotSession(mid,self.rules,self.settings,
                                    integer(obj.get('hands_total'),'hands_total',1,100_000),
                                    number(obj.get('timebank_s'),'timebank_s',0.01),self.seed)
            self.session.bank.charge(self.boot_cost); self.boot_cost=0
            return None
        if kind not in ('decision','opponent_event','showdown','hand_end','status','end_match'):
            raise ValidationError('unknown message type')
        if self.session is None: raise ValidationError('start_match required')
        session=self.session
        if identifier(obj.get('match_id'),'match_id')!=session.match_id:
            raise ValidationError('wrong match_id')
        if 'time_left_s' in obj: session.bank.update_host(number(obj['time_left_s'],'time_left_s'))
        if kind=='end_match':
            self.completed.add(session.match_id)
            if len(self.completed)>256: raise ValidationError('too many matches in one process')
            self.session=None; return None
        if kind=='opponent_event':
            session.opponent.observe(integer(obj.get('seq'),'seq'),integer(obj.get('street'),'street',0,len(self.rules.board_by_street)),
                                     obj.get('kind'),obj.get('faced_bet'),number(obj.get('faced_ratio',0),'faced_ratio'))
            return None
        if kind in ('showdown','hand_end'):
            hand_id=identifier(obj.get('hand_id'),'hand_id')
            opponent=self.rules.cards(obj['opponent_hole']) if 'opponent_hole' in obj else None
            session.duplicate.finish_hand(hand_id,obj.get('board'),opponent)
            return None
        if kind=='status': return None
        obs=observation_from_json(obj,self.rules)
        action=session.act(obs,charge=False)
        return action_response(obs.request_id,action)

    def fallback(self,obj):
        # Never invent an action, sizing, request ID, or match when parsing fails.
        if not isinstance(obj,dict) or obj.get('type')!='decision' or self.session is None:
            return None
        try:
            if identifier(obj.get('match_id'),'match_id')!=self.session.match_id: return None
            legal=legal_from_json(obj.get('legal'))
            request_id=identifier(obj.get('request_id'),'request_id')
            if self.session.responses.get(request_id) is not None:
                # A conflicting payload under an old ID is an error, not a new action.
                return None
            return action_response(request_id,safe_action(legal))
        except (ValueError,TypeError): return None


def read_bounded_lines(stream):
    while True:
        line=stream.readline(MAX_LINE_BYTES+1)
        if not line: return
        if len(line)>MAX_LINE_BYTES:
            while line and not line.endswith('\n'): line=stream.readline(MAX_LINE_BYTES+1)
            yield None
        else: yield line


def main(argv=None):
    parser=argparse.ArgumentParser(description='Example JSONL poker adapter — not an official protocol implementation')
    parser.add_argument('--config',help='read-only JSON configuration file')
    parser.add_argument('--seed',type=int,default=0)
    args=parser.parse_args(argv)
    rules,settings=Rules(),Settings()
    if args.config:
        with open(args.config,'r',encoding='utf-8') as f:
            text=f.read(MAX_LINE_BYTES+1)
        if len(text)>MAX_LINE_BYTES: raise ValidationError('config too large')
        config=strict_json(text)
        if not isinstance(config,dict) or set(config)-{'rules','settings'}: raise ValidationError('invalid config')
        rules=rules_from_dict(config.get('rules',{})); settings=settings_from_dict(config.get('settings',{}))
    adapter=ExampleAdapter(rules,settings,args.seed,globals().get('BOOT_COST',0))
    for line in read_bounded_lines(sys.stdin):
        start=time.perf_counter(); obj=None; prior=adapter.session
        try:
            if line is None: raise ValidationError('line too large')
            if not line.strip(): continue
            obj=strict_json(line)
            response=adapter.handle(obj)
        except Exception as exc:
            adapter.failures+=1
            if adapter.session: adapter.session.errors+=1
            response=adapter.fallback(obj)
            # Bounded diagnostics only, never traceback/prose on stdout.
            sys.stderr.write('input_error:'+type(exc).__name__+'\n')
        try:
            if response is not None:
                sys.stdout.write(json.dumps(response,allow_nan=False,separators=(',',':'))+'\n')
                sys.stdout.flush()
        finally:
            target=adapter.session if adapter.session is not None else prior
            if target: target.bank.charge(time.perf_counter()-start)




BOOT_COST=time.perf_counter()-PROGRAM_START
if __name__=='__main__':
    main()
