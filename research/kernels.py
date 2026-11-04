"""Action-kernel research. Exact blocker correction, public-result model inference.
No actual opponent cards, duplicate-copy knowledge, network or runtime writes.
The parameter family is an approximation; exact enumeration is not exact strategy.
"""
from __future__ import annotations
import math
from itertools import combinations, product
import numpy as np
from runtime.bot import Rules, Evaluator, ValidationError


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
