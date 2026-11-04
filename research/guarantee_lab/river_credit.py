"""Research-only card-independent-of-opponent-model safe settlement credit.
Use ALL physically legal opposing hands, never posterior-truncated support.
"""
from dataclasses import dataclass
from fractions import Fraction
from research.guarantee_lab.certificates import rational

@dataclass(frozen=True)
class RiverContract:
    final_public_board: bool
    ranking_matches_game: bool
    no_rake_or_fees: bool
    equal_initial_stacks: bool
    legal_check_call_finishes: bool
    opponent_paid_is_actual_total: bool
    standard_matched_payouts_and_refunds: bool=False
    def require(self):
        if not all(x is True for x in (self.final_public_board,self.ranking_matches_game,self.no_rake_or_fees,
                                     self.equal_initial_stacks,self.legal_check_call_finishes,self.opponent_paid_is_actual_total,self.standard_matched_payouts_and_refunds)):
            raise ValueError('unverified safe-river premises')

@dataclass(frozen=True)
class RiverCredit:
    minimum_current_net: Fraction
    board: tuple
    hero: tuple
    legal_peer_hands: int
    strictly_beats_every_peer: bool
    required_current_policy: str='check/call through settlement; never fold or raise'
    required_later_policy: str='free check/fold abandonment'

def prove_river_credit(kernel,hero,opponent_paid,contract):
    contract.require();paid=rational(opponent_paid)
    if paid<0:raise ValueError('negative opposing contribution')
    ids,z,payoff,outcome=kernel.view(hero)
    if len(ids)==0:raise ValueError('empty physical peer set')
    if min(outcome)<0:return None
    strict=bool(min(outcome)>0)
    # A tie returns own matched contribution: net >=0. A strict win returns
    # at least the opponent's already-paid contribution under these premises.
    floor=paid if strict else Fraction(0)
    return RiverCredit(floor,tuple(kernel.board),tuple(sorted(kernel.rules.cards(hero))),len(ids),strict)
