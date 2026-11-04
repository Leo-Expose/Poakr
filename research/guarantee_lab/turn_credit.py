"""Constant-size symbolic safe-turn rank proof; research only.
Standard 52-card high poker, two private cards, four public cards, one future
board card. No opponent model and no look at the actual future/opposing cards.
"""
from dataclasses import dataclass
from math import comb
from research.guarantee_lab.certificates import rational
from research.guarantee_lab.river_credit import RiverCredit

@dataclass(frozen=True)
class TurnContract:
    standard_52card_two_hole_high: bool
    exactly_one_future_board_card: bool
    no_rake_or_fees: bool
    equal_initial_stacks: bool
    legal_check_call_finishes: bool
    opponent_paid_is_actual_total: bool
    standard_matched_payouts_and_refunds: bool=False
    def require(self):
        if not all(x is True for x in (self.standard_52card_two_hole_high,self.exactly_one_future_board_card,self.no_rake_or_fees,
                                     self.equal_initial_stacks,self.legal_check_call_finishes,self.opponent_paid_is_actual_total,self.standard_matched_payouts_and_refunds)):
            raise ValueError('unverified safe-turn premises')

def prove_turn_credit(hero,board,opponent_paid,contract):
    contract.require();hero=tuple(hero);board=tuple(board)
    cards=hero+board
    if len(hero)!=2 or len(board)!=4 or len(set(cards))!=6 or any(isinstance(c,bool) or not isinstance(c,int) or not 0<=c<52 for c in cards):
        raise ValueError('standard distinct normalized integer cards required')
    paid=rational(opponent_paid)
    if paid<0:raise ValueError('negative opposing contribution')
    rank=hero[0]//4
    if hero[1]//4!=rank or sum(c//4==rank for c in board)!=2:return None
    others=[c//4 for c in board if c//4!=rank]
    if max(others)>=rank or len({c%4 for c in board})!=4:return None
    # Our pair + board pair exhaust all four cards of rank R. Public turn is
    # rainbow, so final board has at most 2 of any suit; +2 opposing hole cards
    # gives at most 4 suited cards: no opposing flush/straight flush. No higher
    # rank occurs on the turn; one river +2 opposing cards cannot make higher
    # quads. Every other category is below our quads under standard high rules.
    return RiverCredit(paid,board,tuple(sorted(hero)),comb(46,2),True,
                       'check/call through turn and river settlement; never fold or raise',
                       'free check/fold abandonment')
