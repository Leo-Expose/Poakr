#!/usr/bin/env python3
"""CORA research: standard Holdem EXAMPLE JSONL adapter, NOT official protocol.
Target: Python 3.11 (execution qualification pending), stdlib + NumPy, no installs/network/runtime file writes.
"""
from __future__ import annotations
import os, time
import sys
PROGRAM_START=time.perf_counter()
sys.dont_write_bytecode=True
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
        if settings.duplicate_mode!='off':raise ValidationError('CORA excludes duplicate-hole inference')
        if not isinstance(rules,Rules) or not isinstance(settings,Settings): raise ValidationError('rules/settings type')
        self.match_id=identifier(match_id,'match_id'); self.rules=rules; self.settings=settings
        self.bank=ComputeBank(timebank_s,hands_total,settings.reserve_fraction,clock)
        self.clock=clock; self.rng=random.Random(seed); self.np_rng=np.random.default_rng(seed)
        self.equity=EquityEngine(rules,settings,self.np_rng,clock)
        self.duplicate=SimpleNamespace(history={}); self.opponent=OpponentStats(settings)
        self.policy=Policy(rules,settings,self.opponent,self.rng)
        self.responses=OrderedDict(); self.decisions=0; self.info_decisions=0; self.errors=0
        self.last_equity=None

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




def read_bounded_lines(stream):
    while True:
        line=stream.readline(MAX_LINE_BYTES+1)
        if not line: return
        if len(line)>MAX_LINE_BYTES:
            while line and not line.endswith('\n'): line=stream.readline(MAX_LINE_BYTES+1)
            yield None
        else: yield line






BOOT_COST=time.perf_counter()-PROGRAM_START

# Research modules share embedded helpers; no package imports.
from types import SimpleNamespace
core=sys.modules[__name__]

# RESEARCH SOURCE: kernels.py
import math
from itertools import combinations, product
import numpy as np


class RiverKernel:
    """All two-hole hands on a shared final board, with exact disjoint-hand CDFs.

    L(h)=G_< - I_a,< - I_b,<
    T(h)=G_= - I_a,= - I_b,= + 1
    denominator=C(D-board-2,2).
    Scores are evaluated once. Histograms replace the pairwise overlap matrix.
    """
    def __init__(self,board,rules=Rules()):
        if rules.hole_count!=2 or len(board)!=rules.board_count:
            raise ValidationError('river kernel requires two hole cards + final board')
        self.rules=rules; self.board=rules.cards(board)
        available=[c for c in range(rules.deck_size) if c not in self.board]
        if len(available)<4: raise ValidationError('not enough cards')
        self.holes=np.array(list(combinations(available,2)),dtype=np.int64)
        self.index={tuple(h):i for i,h in enumerate(self.holes.tolist())}
        cards=np.empty((len(self.holes),2+len(board)),np.int64)
        cards[:,:2]=self.holes; cards[:,2:]=self.board
        self.scores=Evaluator(rules).score(cards)
        _,group,count=np.unique(self.scores,return_inverse=True,return_counts=True)
        global_lower=np.cumsum(count)-count
        incidence=np.zeros((rules.deck_size,len(count)),np.int32)
        np.add.at(incidence,(self.holes[:,0],group),1)
        np.add.at(incidence,(self.holes[:,1],group),1)
        prefix=np.cumsum(incidence,axis=1)-incidence
        a,b=self.holes.T
        low=global_lower[group]-prefix[a,group]-prefix[b,group]
        tie=count[group]-incidence[a,group]-incidence[b,group]+1
        denominator=math.comb(len(available)-2,2)
        self.percentile=(low+.5*tie)/denominator
        self.work_bytes=self.holes.nbytes+self.scores.nbytes+incidence.nbytes+prefix.nbytes+group.nbytes
        assert np.all((self.percentile>=0)&(self.percentile<=1))
    def view(self,hero):
        hero=tuple(sorted(self.rules.cards(hero)))
        if len(hero)!=2 or hero not in self.index: raise ValidationError('invalid hero hole')
        mask=~np.any(np.isin(self.holes,hero),axis=1)
        ids=np.flatnonzero(mask); own=self.scores[self.index[hero]]
        outcome=np.sign(own-self.scores[ids]) # +1 win, 0 tie, -1 loss
        payoff=(outcome>0).astype(float)+.5*(outcome==0)
        return ids,self.percentile[ids],payoff,outcome


def sigmoid(x): return 1/(1+np.exp(-np.clip(x,-40,40)))


class PolicyMixture:
    """Finite latent policy family; public action/outcome likelihood, not clairvoyance.
    Each hand preserves the parameter/card joint belief until its public end.
    """
    def __init__(self):
        params=np.array(list(product((.50,.65,.80,.90),(0.,.10,.30),(-.10,.05,.22),(0.,.5),(1.,0.))),float)
        self.threshold,self.bluff,self.slack,self.raise_rate,self.value_rate=params.T
        self.weights=np.where(self.value_rate==1,4.,1.); self.weights/=self.weights.sum(); self.hands=0
    def likelihood(self,z,kind,faced,price,can_raise=True):
        z=np.asarray(z)[None,:];epsilon=.002
        # Uniform contamination over LEGAL actions gives a proper categorical
        # distribution, unlike independently clipping three probabilities.
        if not faced:
            if not can_raise:
                if kind!='check':raise ValidationError('impossible free action')
                return np.ones((len(self.weights),z.shape[1]))
            if kind not in ('bet','check'):raise ValidationError('invalid free action')
            bet=self.bluff[:,None]+(1-self.bluff[:,None])*sigmoid((z-self.threshold[:,None])/.035)
            weak_only=self.bluff[:,None]*sigmoid((.45-z)/.05)
            bet=np.where(self.value_rate[:,None]==1,bet,weak_only)
            value=bet if kind=='bet' else 1-bet
            return (1-2*epsilon)*value+epsilon
        if kind not in ('fold','call','bet') or (kind=='bet' and not can_raise):
            raise ValidationError('invalid faced action')
        cont=sigmoid((z-(price+self.slack[:,None]))/.035)
        raised=self.raise_rate[:,None]*sigmoid((z-.82)/.04) if can_raise else 0.
        value=1-cont if kind=='fold' else cont*(raised if kind=='bet' else 1-raised)
        nlegal=3 if can_raise else 2
        return (1-nlegal*epsilon)*value+epsilon
    def begin(self,kernel,hero,compress=True): return HandBelief(self,kernel,hero,compress)


class HandBelief:
    def __init__(self,model,kernel,hero,compress=True):
        self.model=model; self.kernel=kernel
        self.ids,z,payoff,outcome=kernel.view(hero)
        if compress:
            # Exact quotient for this likelihood/payoff family, not approximate
            # card clustering. Counts retain prior mass of merged card pairs.
            keys,count=np.unique(np.column_stack((z,outcome)),axis=0,return_counts=True)
            self.z=keys[:,0]; self.outcome=keys[:,1]
            self.payoff=(self.outcome>0).astype(float)+.5*(self.outcome==0)
            mass=count/len(self.ids)
        else:
            self.z=z;self.payoff=payoff;self.outcome=outcome;mass=np.full(len(self.ids),1/len(self.ids))
        self._state=(model.weights[:,None]*mass[None,:],-1,0)
    @property
    def joint(self): return self._state[0]
    @property
    def evidence(self): return self._state[2]
    def observe(self,kind,faced,price,can_raise=True,event_id=None):
        previous=self._state
        event_id=previous[1]+1 if event_id is None else event_id
        if event_id<=previous[1]: return False
        new=previous[0]*self.model.likelihood(self.z,kind,faced,price,can_raise)
        new/=new.sum()
        # One commit: an interrupt cannot leave unnormalized mass or cause
        # evidence to be applied twice when a public history is replayed.
        self._state=(new,event_id,previous[2]+1)
        return True
    def equity(self): return float(np.sum(self.joint*self.payoff[None,:]))
    def response(self,price,can_raise=True):
        cont=sigmoid((self.z[None,:]-(price+self.model.slack[:,None]))/.035)
        nlegal=3 if can_raise else 2
        cont=(1-nlegal*.002)*cont+(nlegal-1)*.002
        continue_mass=float(np.sum(self.joint*cont))
        win_mass=float(np.sum(self.joint*cont*self.payoff[None,:]))
        return continue_mass,win_mass
    def finish(self,outcome=None):
        if outcome is not None:
            mask=self.outcome==outcome
            if not np.any(mask):raise ValidationError('impossible public showdown outcome')
            new=self.joint*mask[None,:]
            new/=new.sum(); self._state=(new,self._state[1],self._state[2])
        if self.evidence:
            marginal=self.joint.sum(axis=1)
            # Explicit contamination floor for nonstationarity/model misspecification.
            weights=.995*marginal+.005/len(marginal)
            weights/=weights.sum(); self.model.weights=weights; self.model.hands+=1


class WinLock:
    """Conditional hard certificate for raw cumulative net-chip win scoring.
    Net is COMPLETED-hand own chip profit, not twice that chip difference.
    Remaining includes current hand. Abandonment incurs current committed chips
    plus future forced posting bounds. No optional calls/bets may follow the lock.
    """
    @staticmethod
    def lower_bound(banked_net,current_paid,remaining_hands,max_future_post):
        vals=(banked_net,current_paid,max_future_post)
        if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in vals):
            raise ValidationError('invalid lock inputs')
        if current_paid<0 or max_future_post<0 or isinstance(remaining_hands,bool) or not isinstance(remaining_hands,int) or remaining_hands<1:
            raise ValidationError('invalid lock bounds')
        return banked_net-current_paid-(remaining_hands-1)*max_future_post
    @classmethod
    def certified(cls,*args): return cls.lower_bound(*args)>1e-9

# RESEARCH SOURCE: agent.py
import json,time,math,random
from collections import OrderedDict
import numpy as np


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



# RESEARCH SOURCE: stream_adapter.py
import sys,json,time,hashlib,argparse
from types import SimpleNamespace
from collections import OrderedDict


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

EMBEDDED_PREFLOP={(0, 0, 0):0.4971923828125,(1, 0, 0):0.321197509765625,(1, 0, 1):0.3634033203125,(1, 1, 0):0.534332275390625,(2, 0, 0):0.330169677734375,(2, 0, 1):0.372833251953125,(2, 1, 0):0.352569580078125,(2, 1, 1):0.39306640625,(2, 2, 0):0.57562255859375,(3, 0, 0):0.345245361328125,(3, 0, 1):0.37628173828125,(3, 1, 0):0.364837646484375,(3, 1, 1):0.393646240234375,(3, 2, 0):0.377716064453125,(3, 2, 1):0.408294677734375,(3, 3, 0):0.600738525390625,(4, 0, 0):0.34417724609375,(4, 0, 1):0.380401611328125,(4, 1, 0):0.362030029296875,(4, 1, 1):0.39239501953125,(4, 2, 0):0.380645751953125,(4, 2, 1):0.413665771484375,(4, 3, 0):0.40283203125,(4, 3, 1):0.424407958984375,(4, 4, 0):0.626678466796875,(5, 0, 0):0.348175048828125,(5, 0, 1):0.382080078125,(5, 1, 0):0.360076904296875,(5, 1, 1):0.400665283203125,(5, 2, 0):0.385498046875,(5, 2, 1):0.4178466796875,(5, 3, 0):0.400604248046875,(5, 3, 1):0.438873291015625,(5, 4, 0):0.418609619140625,(5, 4, 1):0.452239990234375,(5, 5, 0):0.660980224609375,(6, 0, 0):0.36590576171875,(6, 0, 1):0.40618896484375,(6, 1, 0):0.377471923828125,(6, 1, 1):0.411834716796875,(6, 2, 0):0.398651123046875,(6, 2, 1):0.42303466796875,(6, 3, 0):0.4151611328125,(6, 3, 1):0.44854736328125,(6, 4, 0):0.435546875,(6, 4, 1):0.467437744140625,(6, 5, 0):0.4442138671875,(6, 5, 1):0.48138427734375,(6, 6, 0):0.69287109375,(7, 0, 0):0.390899658203125,(7, 0, 1):0.42230224609375,(7, 1, 0):0.395660400390625,(7, 1, 1):0.429931640625,(7, 2, 0):0.403717041015625,(7, 2, 1):0.43804931640625,(7, 3, 0):0.419952392578125,(7, 3, 1):0.449737548828125,(7, 4, 0):0.43927001953125,(7, 4, 1):0.474578857421875,(7, 5, 0):0.469482421875,(7, 5, 1):0.49365234375,(7, 6, 0):0.4847412109375,(7, 6, 1):0.5006103515625,(7, 7, 0):0.716522216796875,(8, 0, 0):0.41607666015625,(8, 0, 1):0.449676513671875,(8, 1, 0):0.43145751953125,(8, 1, 1):0.453155517578125,(8, 2, 0):0.43115234375,(8, 2, 1):0.464935302734375,(8, 3, 0):0.44219970703125,(8, 3, 1):0.4755859375,(8, 4, 0):0.46612548828125,(8, 4, 1):0.4947509765625,(8, 5, 0):0.480316162109375,(8, 5, 1):0.5135498046875,(8, 6, 0):0.492279052734375,(8, 6, 1):0.5286865234375,(8, 7, 0):0.51751708984375,(8, 7, 1):0.541412353515625,(8, 8, 0):0.7540283203125,(9, 0, 0):0.4466552734375,(9, 0, 1):0.472625732421875,(9, 1, 0):0.459991455078125,(9, 1, 1):0.481414794921875,(9, 2, 0):0.464508056640625,(9, 2, 1):0.489501953125,(9, 3, 0):0.46673583984375,(9, 3, 1):0.502960205078125,(9, 4, 0):0.47625732421875,(9, 4, 1):0.50341796875,(9, 5, 0):0.494171142578125,(9, 5, 1):0.521636962890625,(9, 6, 0):0.514404296875,(9, 6, 1):0.54217529296875,(9, 7, 0):0.529022216796875,(9, 7, 1):0.554046630859375,(9, 8, 0):0.558197021484375,(9, 8, 1):0.576568603515625,(9, 9, 0):0.771759033203125,(10, 0, 0):0.47698974609375,(10, 0, 1):0.507415771484375,(10, 1, 0):0.48480224609375,(10, 1, 1):0.50946044921875,(10, 2, 0):0.4959716796875,(10, 2, 1):0.518524169921875,(10, 3, 0):0.50079345703125,(10, 3, 1):0.527252197265625,(10, 4, 0):0.51531982421875,(10, 4, 1):0.53399658203125,(10, 5, 0):0.515167236328125,(10, 5, 1):0.5426025390625,(10, 6, 0):0.533172607421875,(10, 6, 1):0.559783935546875,(10, 7, 0):0.552001953125,(10, 7, 1):0.57379150390625,(10, 8, 0):0.576263427734375,(10, 8, 1):0.59552001953125,(10, 9, 0):0.582275390625,(10, 9, 1):0.603759765625,(10, 10, 0):0.800384521484375,(11, 0, 0):0.503997802734375,(11, 0, 1):0.53009033203125,(11, 1, 0):0.515472412109375,(11, 1, 1):0.540863037109375,(11, 2, 0):0.52032470703125,(11, 2, 1):0.55487060546875,(11, 3, 0):0.533538818359375,(11, 3, 1):0.553314208984375,(11, 4, 0):0.542083740234375,(11, 4, 1):0.567413330078125,(11, 5, 0):0.548828125,(11, 5, 1):0.5748291015625,(11, 6, 0):0.55975341796875,(11, 6, 1):0.583770751953125,(11, 7, 0):0.575714111328125,(11, 7, 1):0.59893798828125,(11, 8, 0):0.597198486328125,(11, 8, 1):0.621551513671875,(11, 9, 0):0.60198974609375,(11, 9, 1):0.628875732421875,(11, 10, 0):0.61578369140625,(11, 10, 1):0.636077880859375,(11, 11, 0):0.824249267578125,(12, 0, 0):0.55255126953125,(12, 0, 1):0.579132080078125,(12, 1, 0):0.560760498046875,(12, 1, 1):0.5880126953125,(12, 2, 0):0.5631103515625,(12, 2, 1):0.591033935546875,(12, 3, 0):0.572479248046875,(12, 3, 1):0.59442138671875,(12, 4, 0):0.57000732421875,(12, 4, 1):0.596832275390625,(12, 5, 0):0.582977294921875,(12, 5, 1):0.60870361328125,(12, 6, 0):0.603271484375,(12, 6, 1):0.61871337890625,(12, 7, 0):0.60626220703125,(12, 7, 1):0.624176025390625,(12, 8, 0):0.622100830078125,(12, 8, 1):0.646942138671875,(12, 9, 0):0.63458251953125,(12, 9, 1):0.656951904296875,(12, 10, 0):0.64263916015625,(12, 10, 1):0.6630859375,(12, 11, 0):0.651580810546875,(12, 11, 1):0.67034912109375,(12, 12, 0):0.853485107421875}
BOOT_COST=time.perf_counter()-PROGRAM_START
if __name__=='__main__':
    cora_main(EMBEDDED_PREFLOP,BOOT_COST)
