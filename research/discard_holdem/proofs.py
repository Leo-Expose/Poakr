"""Pointwise Discard Hold'em proofs from own/public cards; no opponent model.
The organizer PDFs prescribe standard ranking after the exposed discard.
"""
from itertools import combinations
import numpy as np
from engine.numpy_eval import eval_batch

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
