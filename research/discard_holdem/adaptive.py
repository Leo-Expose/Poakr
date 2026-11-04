"""Experimental public-action range guard + bounded cheap-steal probe.
Heuristic adaptation, not a solved game or calibrated Bayesian posterior.
Original accounting/certificate/pending/budget implementation is inherited.
No duplicate recognition, past private-card learning, or hidden input access.
"""
import math
from itertools import combinations
import numpy as np
from engine.numpy_eval import eval_batch
from research.discard_holdem.partial_eval import eval_made
from research.discard_holdem.protocol import DiscardBot


def empirical_percentile(values):
    """Midranks: tied scores receive identical weights, independent of row order."""
    _,inverse,counts=np.unique(values,return_inverse=True,return_counts=True)
    middle=(np.cumsum(counts)-.5*counts)/len(values)
    return middle[inverse]


def current_strength(peers,board):
    """Only the CURRENT public board, never the sampled future runout."""
    n=len(peers)
    if not board:
        ranks=np.sort(peers//4,axis=1)
        paired=np.full(n,-1,dtype=np.int64)
        for i,j in combinations(range(peers.shape[1]),2):
            paired=np.maximum(paired,np.where(ranks[:,i]==ranks[:,j],ranks[:,i],-1))
        return np.where(paired>=0,13**3+paired*13+ranks[:,-1],ranks[:,-1]*13+ranks[:,-2])
    options=list(combinations(range(peers.shape[1]),2))
    full=np.stack([np.column_stack((peers[:,ix],np.tile(board,(n,1)))) for ix in options])
    return eval_made(full.reshape(-1,2+len(board))).reshape(len(options),n).max(axis=0)


class AdaptiveDiscardBot(DiscardBot):
    def __init__(self,samples=128,spend_to_cap=True):
        super().__init__(samples,spend_to_cap)
        self.opp_n=[0,0];self.opp_raises=[0,0]
        self.cheap_n=0;self.cheap_folds=0;self.steal_used=False
        self.context=None;self.range_calls=0;self.cheap_steals=0

    def _learn_terminal(self,msg,seat):
        # Called ONLY after original independent ledger/payout validation succeeds.
        # Retain aggregate PUBLIC actions only, never revealed hole cards/boards.
        bets=[1,2] if seat=='button' else [2,1];street='preflop'
        for event in msg['history']:
            if event['street']!=street:street=event['street'];bets=[0,0]
            who=0 if event['actor']=='me' else 1;owed=max(0,bets[1-who]-bets[who])
            if who==1:
                bucket=0 if street=='preflop' else 1
                self.opp_n[bucket]+=1;self.opp_raises[bucket]+=event['action']=='raise'
                if 0<owed<=4:
                    self.cheap_n+=1;self.cheap_folds+=event['action']=='fold'
            if event['action'] in ('raise','call'):bets[who]=event['amount']

    def _range_weights(self,strength,msg):
        bucket=0 if msg['street']=='preflop' else 1
        observed=self.opp_n[bucket]
        rate=(self.opp_raises[bucket]+2)/(observed+6)
        pressure=min(1.,msg['to_call']/max(1,msg['pot']))
        mass=min(1.,max(.15,2.2*rate*(1.-.3*pressure)))
        percentile=empirical_percentile(strength)
        likelihood=.15+.85/(1.+np.exp(-(percentile-(1.-mass))/.08))
        # Shrink toward the baseline. No support is removed; weights are heuristic.
        alpha=observed/(observed+12.)
        weights=(1.-alpha)+alpha*likelihood/likelihood.mean()
        return weights

    def _equity(self,board):
        msg=self.context
        if not msg or msg.get('type')!='action_request' or not msg['to_call']:
            return super()._equity(board)
        # A call to the blind alone is not evidence of an aggressive range.
        aggressive=any(e['actor']=='opp' and e['action']=='raise' and e['street']==msg['street'] for e in msg['history'])
        if not aggressive:return super()._equity(board)
        key=('adaptive',self.own,board,self.dead,msg['street'],msg['to_call'],msg['pot'])
        if key in self.cache:return self.cache[key]
        blocked=set(self.original)|set(board)|set(self.dead)
        deck=[c for c in range(52) if c not in blocked]
        peer_count=3 if len(self.own)==3 else 2
        need=5-len(board)
        if len(board)==5:
            worlds=np.array(list(combinations(deck,2)),dtype=np.int64)
        else:
            worlds=np.array([self.rng.sample(deck,peer_count+need) for _ in range(self.samples)],dtype=np.int64)
        n=len(worlds);peers=worlds[:,:peer_count]
        boards=np.column_stack((np.tile(board,(n,1)),worlds[:,peer_count:]))
        peer_options=list(combinations(range(peer_count),2))
        full=np.stack([np.column_stack((peers[:,ix],boards)) for ix in peer_options])
        strongest=eval_batch(full.reshape(-1,7)).reshape(len(peer_options),n).max(axis=0)
        own_pairs=list(combinations(self.own,2))
        own_full=np.stack([np.column_stack((np.tile(pair,(n,1)),boards)) for pair in own_pairs])
        scores=eval_batch(own_full.reshape(-1,7)).reshape(len(own_pairs),n)
        weights=self._range_weights(current_strength(peers,board),msg)
        means=(((scores>strongest)+.5*(scores==strongest))*weights).sum(axis=1)/weights.sum()
        best=int(np.argmax(means));result=(float(means[best]),own_pairs[best])
        if len(self.cache)<12:self.cache[key]=result
        self.range_calls+=1
        return result

    def _cheap_steal(self,msg,reply):
        # Never override certified pending settlement, the locked budget, or low-bank recovery.
        if self.pending or self.locked or self.steal_used or not self.score_trusted:return reply
        if msg['time_left_ms']<100 or self.per_reply<100:return reply
        if self.cheap_n<8 or self.completed<8 or 'raise' not in msg['legal_actions']:return reply
        if reply['action']=='raise' or msg['to_call']>2:return reply
        risk=msg['min_raise']-msg['my_bet']
        if risk>4:return reply
        # Conservative plug-in lower estimate, NOT an anytime/adaptive confidence bound.
        p=(self.cheap_folds+2)/(self.cheap_n+5)
        lower=p-1.64*math.sqrt(p*(1-p)/(self.cheap_n+5))
        threshold=risk/(msg['pot']+risk)
        if lower<=threshold+.08:return reply
        self.steal_used=True;self.cheap_steals+=1
        return dict(type='action',action='raise',amount=msg['min_raise'])

    def _handle(self,msg):
        self.context=msg if isinstance(msg,dict) and msg.get('type') in ('action_request','discard_request') else None
        kind=msg.get('type') if isinstance(msg,dict) else None
        old_seat=getattr(self,'seat',None)
        reply=super()._handle(msg)
        if kind=='new_hand':self.steal_used=False
        elif kind=='hand_result' and self.score_trusted:self._learn_terminal(msg,old_seat)
        elif kind=='action_request' and reply is not None:reply=self._cheap_steal(msg,reply)
        return reply
