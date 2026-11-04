"""Information contract for a FUTURE custom OpenSpiel discard-stage adapter.
Not a pyspiel.Game, not a full poker engine and not imported by submitted bot.
Omniscient environment state must NEVER be handed to a player policy directly.
"""
from dataclasses import dataclass,replace
from research.discard_holdem.proofs import card


@dataclass(frozen=True)
class DiscardCommitState:
    # Environment-only private/predealt fields.
    holes:tuple
    board:tuple
    committed:tuple=(None,None)
    history:tuple=()
    paid:tuple=(2,2)
    button:int=0
    hand_id:int=1
    total_hands:int=400
    match_net:tuple=(0,0)
    match_cap:int=400

    def __post_init__(self):
        for name in ('board','committed','paid','match_net'):object.__setattr__(self,name,tuple(getattr(self,name)))
        object.__setattr__(self,'holes',tuple(tuple(h) for h in self.holes))
        object.__setattr__(self,'history',tuple(tuple(e) for e in self.history))
        if len(self.holes)!=2 or any(len(h)!=3 for h in self.holes) or len(self.board)!=5:
            raise ValueError('three original holes per player and predealt five-card board required')
        values=[card(c) for h in self.holes for c in h]+[card(c) for c in self.board]
        if len(set(values))!=11:raise ValueError('colliding environment cards')
        if len(self.committed)!=2 or any(c is not None and c not in self.holes[p] for p,c in enumerate(self.committed)):
            raise ValueError('invalid private commitments')
        if type(self.button) is not int or self.button not in (0,1) or len(self.paid)!=2 or any(type(n) is not int or not 0<=n<=200 for n in self.paid):
            raise ValueError('bad public money/seat')
        if self.paid[0]!=self.paid[1]:raise ValueError('discard requires closed matching flop wagers')
        if type(self.hand_id) is not int or type(self.total_hands) is not int or not 1<=self.hand_id<=self.total_hands<=10000:raise ValueError('bad hand index')
        if type(self.match_cap) is not int or self.match_cap<=0:raise ValueError('bad configured match cap')
        if len(self.match_net)!=2 or any(type(n) is not int for n in self.match_net) or sum(self.match_net)!=0:raise ValueError('non-zero-sum scoreboard')
        for street,actor,action,amount in self.history:
            if street not in ('preflop','flop') or type(actor) is not int or actor not in (0,1) or action not in ('check','call','raise'):
                raise ValueError('invalid pre-discard public history')
            if action=='check' and amount is not None:raise ValueError('check has no amount')
            if action in ('call','raise') and (type(amount) is not int or not 0<=amount<=200):raise ValueError('TO amount required')
        # Full betting legality/replay is a separate future adapter obligation.

    def legal_discards(self,player):
        if type(player) is not int or player not in (0,1):raise ValueError('bad player')
        if self.committed[player] is not None:return ()
        return tuple(sorted(map(card,self.holes[player])))

    def information_key(self,player):
        legal=self.legal_discards(player)
        if not legal:raise ValueError('player already acted; no second discard decision')
        public_history=tuple((s,'me' if p==player else 'opp',a,n) for s,p,a,n in self.history)
        # No opponent holes, future board, or other's sealed commitment.
        return ('discard-commit-v1',tuple(map(card,self.holes[player])),tuple(map(card,self.board[:3])),public_history,
            (self.paid[player],self.paid[1-player]),'button' if player==self.button else 'big_blind',
            self.hand_id,self.total_hands,self.match_cap,(self.match_net[player],self.match_net[1-player]))

    def commit(self,player,action):
        if type(action) is not int or action not in self.legal_discards(player):raise ValueError('illegal discard action')
        selected=next(c for c in self.holes[player] if card(c)==action)
        pending=list(self.committed);pending[player]=selected
        return replace(self,committed=tuple(pending))

    def exposed_discards(self):
        return None if None in self.committed else self.committed
