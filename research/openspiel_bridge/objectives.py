"""Exact objective audit using our own fully enumerated Kuhn lab.
NOT OpenSpiel execution, NOT a Discard Hold'em value/strategy.
SciPy locates candidate LP solutions; Fraction checks certify all inequalities.
"""
from fractions import Fraction
from itertools import permutations
import numpy as np
from scipy.optimize import linprog
from research.guarantee_lab.kuhn import payoff


def certify_matrix(numerators,denominator):
    """Zero-sum normal form, maximize row utility, minimize column utility.
    Exact rational primal/dual evaluation; a nonzero exact gap is a failure.
    """
    numerators=np.asarray(numerators)
    if numerators.dtype.kind not in 'iu':raise ValueError('matrix entries must be integers')
    if numerators.size and (int(numerators.min())<-(1<<63) or int(numerators.max())>=(1<<63)):
        raise ValueError('matrix entries exceed supported integer range')
    numerators=numerators.astype(np.int64)
    if numerators.ndim!=2 or min(numerators.shape)<1 or type(denominator) is not int or denominator<1:
        raise ValueError('nonempty integer matrix and positive integer denominator required')
    rows,cols=numerators.shape;matrix=numerators/denominator
    row=linprog(np.r_[np.zeros(rows),-1.],A_ub=np.c_[-matrix.T,np.ones(cols)],b_ub=np.zeros(cols),
        A_eq=np.array([[1]*rows+[0]]),b_eq=[1],bounds=[(0,None)]*rows+[(None,None)],method='highs')
    col=linprog(np.r_[np.zeros(cols),1.],A_ub=np.c_[matrix,-np.ones(rows)],b_ub=np.zeros(rows),
        A_eq=np.array([[1]*cols+[0]]),b_eq=[1],bounds=[(0,None)]*cols+[(None,None)],method='highs')
    if not row.success or not col.success:raise RuntimeError('LP failure')
    def rational(values):
        if min(values)<-1e-10:raise AssertionError('negative candidate mass')
        p=[Fraction(float(max(0,x))).limit_denominator(1000000) for x in values]
        total=sum(p)
        if not total:raise AssertionError('zero candidate mass')
        return [v/total for v in p]
    x,y=rational(row.x[:rows]),rational(col.x[:cols])
    lower=min(sum(x[i]*int(numerators[i,j]) for i in range(rows))/denominator for j in range(cols))
    upper=max(sum(y[j]*int(numerators[i,j]) for j in range(cols))/denominator for i in range(rows))
    if lower!=upper:raise AssertionError(('exact certification gap',lower,upper))
    return dict(value=str(lower),exact_lower=str(lower),exact_upper=str(upper),exact_gap=str(upper-lower),
        rows=rows,columns=cols,row_policy={str(i):str(p) for i,p in enumerate(x) if p},
        column_policy={str(i):str(p) for i,p in enumerate(y) if p})


def audit_objectives():
    deals=tuple(permutations(range(3),2))
    outcomes=np.array([[[payoff(a,b,*d) for d in deals] for b in range(64)] for a in range(64)],dtype=np.int64)
    report={}
    for label,array in [('chips',outcomes),('strict_win',(outcomes>0).astype(np.int64)),('nonloss',(outcomes>=0).astype(np.int64))]:
        report['uniform_chance_'+label]=certify_matrix(array.sum(axis=2),len(deals))
        # Opponent and legal deal both range over all columns. Hero's policy is
        # still own-card-only; only its pre-play mixed-strategy randomness averages.
        report['adversarial_deal_'+label]=certify_matrix(array.reshape(64,-1),1)
    assert report['uniform_chance_chips']['value']=='-1/18'
    assert report['uniform_chance_strict_win']['value']=='1/2'
    assert report['uniform_chance_nonloss']['value']=='1/2'
    assert report['adversarial_deal_chips']['value']=='-1'
    assert report['adversarial_deal_strict_win']['value']=='0'
    assert report['adversarial_deal_nonloss']['value']=='0'
    return dict(game='three-card Kuhn; ante1, at most one bet of1',deals=6,pure_strategies_per_player=64,
        complete_policy_deal_outcomes=int(outcomes.size),objectives=report,
        note='Distinct-card Kuhn has no terminal ties, so strict_win and nonloss coincide here. That is NOT true for Discard Holdem.',
        scope='Independent own SciPy/Fraction benchmark, not OpenSpiel execution, not an official-game solution')
