"""Exact rational sufficient bounds, independent of opponent/card models.
Research only: no integration into the frozen CORA policy or official protocol.
"""
from dataclasses import dataclass
from fractions import Fraction
import math

def rational(value):
    if isinstance(value,bool):raise ValueError('boolean is not money')
    if isinstance(value,Fraction):return value
    if isinstance(value,int):return Fraction(value)
    if isinstance(value,float):
        if not math.isfinite(value):raise ValueError('nonfinite amount')
        return Fraction(str(value))
    if isinstance(value,str):return Fraction(value)
    raise ValueError('unsupported amount')

@dataclass(frozen=True)
class Contract:
    """Assertions supplied by a verified game adapter, NOT inferred facts."""
    free_abandonment: bool
    paid_loss_bound_valid: bool
    future_post_bounds_valid: bool
    banked_score_matches_scoring: bool
    finish_without_forfeit: bool
    def require(self):
        if not all(x is True for x in (self.free_abandonment,self.paid_loss_bound_valid,self.future_post_bounds_valid,
                                     self.banked_score_matches_scoring,self.finish_without_forfeit)):
            raise ValueError('unverified certificate premises')

@dataclass(frozen=True)
class Certificate:
    lower_score: Fraction
    threshold: Fraction
    strict_success: bool
    scoring: str

class BoundSchedule:
    """O(H) preparation; O(1) rational queries for known heterogeneous posts.
    Optional cap defines SUM OF PER-HAND symmetric clipped net profit, not an
    unspecified cap on total/average chips. That scoreboard must be supplied.
    """
    def __init__(self,post_bounds,contract,hand_cap=None):
        contract.require();self.contract=contract
        posts=tuple(rational(x) for x in post_bounds)
        if not posts or any(x<0 for x in posts):raise ValueError('nonnegative nonempty post schedule required')
        self.cap=None if hand_cap is None else rational(hand_cap)
        if self.cap is not None and self.cap<=0:raise ValueError('positive cap required')
        self.posts=posts;costs=tuple(self._cost(x) for x in posts)
        suffix=[Fraction(0)]*(len(posts)+1)
        for i in range(len(posts)-1,-1,-1):suffix[i]=suffix[i+1]+costs[i]
        self.suffix=tuple(suffix)
    def _cost(self,paid):return paid if self.cap is None else min(paid,self.cap)
    def certify(self,banked_score,current_paid,current_index,threshold=0):
        if isinstance(current_index,bool) or not isinstance(current_index,int) or not 0<=current_index<len(self.posts):
            raise ValueError('current index outside schedule')
        paid=rational(current_paid)
        if paid<0:raise ValueError('negative paid contribution')
        target=rational(threshold)
        lower=rational(banked_score)-self._cost(paid)-self.suffix[current_index+1]
        return Certificate(lower,target,lower>target,'raw net' if self.cap is None else 'sum of per-hand clipped net')
    def certify_river_settlement(self,banked_score,credit,current_index,threshold=0):
        # The credit's current check/call plan MUST finish before later folds.
        # Existing CORA's immediate hard-lock/fold branch cannot use this bound.
        from research.guarantee_lab.river_credit import RiverCredit
        if not isinstance(credit,RiverCredit):raise ValueError('safe river proof required')
        if isinstance(current_index,bool) or not isinstance(current_index,int) or not 0<=current_index<len(self.posts):
            raise ValueError('current index outside schedule')
        floor=rational(credit.minimum_current_net)
        if floor<0:raise ValueError('negative river credit')
        scored=floor if self.cap is None else min(floor,self.cap)
        target=rational(threshold)
        lower=rational(banked_score)+scored-self.suffix[current_index+1]
        return Certificate(lower,target,lower>target,'raw net' if self.cap is None else 'sum of per-hand clipped net')

    def certify_safe_settlement(self,banked_score,credit,current_index,threshold=0):
        """Stage-neutral financial bound for a trusted river OR turn proof."""
        return self.certify_river_settlement(banked_score,credit,current_index,threshold)
