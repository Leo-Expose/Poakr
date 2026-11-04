"""Fully enumerated three-card, one-bet Kuhn poker proof laboratory.
This is NOT a Hold'em controller or the organizer's modified game.
A strategy has six bits: three first-context actions + three response actions,
one per OWN card. No strategy can inspect the other player's actual card.
"""
from fractions import Fraction
from itertools import permutations

def bit(strategy,index):return (strategy>>index)&1

def payoff(first,second,card_first,card_second):
    if card_first==card_second or card_first not in range(3) or card_second not in range(3):raise ValueError('invalid deal')
    if not 0<=first<64 or not 0<=second<64:raise ValueError('invalid strategy')
    winner=1 if card_first>card_second else -1
    if bit(first,card_first): # first player bets
        return 2*winner if bit(second,3+card_second) else 1
    if not bit(second,card_second):return winner # check/check
    return 2*winner if bit(first,3+card_first) else -1

def solve():
    import numpy as np
    from scipy.optimize import linprog
    deals=tuple(permutations(range(3),2))
    numerators=np.array([[sum(payoff(a,b,*d) for d in deals) for b in range(64)] for a in range(64)],dtype=int)
    matrix=numerators/6
    objective=np.zeros(65);objective[-1]=-1
    lower=linprog(objective,A_ub=np.column_stack((-matrix.T,np.ones(64))),b_ub=np.zeros(64),
                  A_eq=np.array([[1]*64+[0]]),b_eq=[1],bounds=[(0,None)]*64+[(None,None)],method='highs')
    objective[-1]=1
    upper=linprog(objective,A_ub=np.column_stack((matrix,-np.ones(64))),b_ub=np.zeros(64),
                  A_eq=np.array([[1]*64+[0]]),b_eq=[1],bounds=[(0,None)]*64+[(None,None)],method='highs')
    if not lower.success or not upper.success:raise RuntimeError('LP failed')
    def reconstruct(values):
        if min(values)<-1e-10:raise AssertionError('negative LP mass')
        q=[Fraction(float(max(0,x))).limit_denominator(1000000) for x in values]
        total=sum(q);return [x/total for x in q]
    x,y=reconstruct(lower.x[:64]),reconstruct(upper.x[:64])
    # Proof uses exact rational arithmetic, NOT the floating LP tolerance.
    lo=min(sum(x[a]*int(numerators[a,b]) for a in range(64))/6 for b in range(64))
    hi=max(sum(y[b]*int(numerators[a,b]) for b in range(64))/6 for a in range(64))
    assert lo==hi==Fraction(-1,18),(lo,hi)
    # A fixed legal opponent checks after checks and calls every bet. On deal
    # (lowest, highest), every first-player policy loses: no clairvoyance needed.
    worst_deal=[payoff(a,56,0,2) for a in range(64)]
    assert max(worst_deal)==-1 and min(worst_deal)==-2
    # Duplicate witness: same (0,2) deal, roles AND hole cards swapped.
    # Opponent first-copy P2 bets/calls with highest card; second-copy P1 with
    # lowest card checks/folds. These decisions depend only on its own card.
    b_first=(1<<2)|(1<<5);b_second=b_first # same own-card-only policy in both roles
    duplicates=[payoff(a,b_first,0,2)-payoff(b_second,c,0,2) for a in range(64) for c in range(64)]
    assert max(duplicates)==0 and min(duplicates)==-1
    return dict(game='three-card Kuhn, ante 1, at most one bet of 1',pure_strategies_per_player=64,
                deals=6,terminal_policy_deal_evaluations=64*64*6,exact_lower=str(lo),exact_upper=str(hi),
                exact_primal_dual_gap=str(hi-lo),first_strategy={str(i):str(p) for i,p in enumerate(x) if p},
                second_strategy={str(i):str(p) for i,p in enumerate(y) if p},
                forced_loss_witness=dict(deal=[0,2],opponent_strategy=56,best_possible_profit=max(worst_deal)),
                duplicate_witness=dict(deal=[0,2],role_and_cards_swapped=True,opponent_first_strategy=b_first,
                                       opponent_second_strategy=b_second,own_policy_pairs_enumerated=len(duplicates),
                                       best_possible_total=max(duplicates),worst_total=min(duplicates)),
                scope='exact toy-poker result; not an official Holdem value or win-rate claim')
