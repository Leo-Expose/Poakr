"""
Configurable, variant-agnostic poker engine (heads-up).

Everything is a parameter: deck geometry, hole count, board streets, hand-rank
rules, bet sizes, blinds, stacks.  The SAME engine is the reference semantics for
the shipped runtime and for the offline proof harness.

The point is to prove a DECISION FRAMEWORK, not to hardcode one variant.  The
policy layer above reads only game-theoretic invariants (equity, pot odds, SPR,
street, position), so it transfers across variants.
"""
from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional

from engine.cards import make_evaluator, make_best_of


@dataclass
class GameConfig:
    n_suits: int = 4
    n_ranks: int = 13
    n_hole: int = 2
    board_by_street: tuple = (3, 1, 1)      # flop, turn, river
    full_beats_flush: bool = True
    wheel_low: bool = True
    sb: float = 1.0
    bb: float = 2.0
    stack: float = 200.0
    bet_fracs: tuple = (0.5, 1.0, 2.0)      # bet/raise sizes as fraction of pot
    max_raises: int = 4

    @property
    def n_board(self):
        return sum(self.board_by_street)

    @property
    def n_streets(self):
        return len(self.board_by_street)

    def build_eval(self):
        self.eval5 = make_evaluator(self.n_ranks, self.n_suits, self.full_beats_flush, self.wheel_low)
        self.best = make_best_of(self.eval5, self.n_hole + self.n_board)
        return self.eval5, self.best


# action tuples
FOLD = ('fold',)
CHECK = ('check',)
CALL = ('call',)


def bet_action(frac):
    return ('bet', frac)


def is_aggressive(act):
    return act[0] == 'bet'


class HandState:
    __slots__ = ('cfg', 'hole', 'board', 'board_cards', 'stacks', 'committed',
                 'pot', 'to_act', 'raises', 'street', 'history', 'folded',
                 'allin', 'total_in')

    def __init__(self, cfg, hole, board_cards):
        self.cfg = cfg
        self.hole = hole
        self.board = []
        self.board_cards = board_cards
        self.stacks = [cfg.stack, cfg.stack]
        self.committed = [0.0, 0.0]     # this street
        self.total_in = [0.0, 0.0]      # this hand (all streets)
        self.pot = 0.0                  # settled chips from previous streets
        self.to_act = 0
        self.raises = 0
        self.street = -1
        self.history = []
        self.folded = -1
        self.allin = False

    def to_call(self, p):
        return self.committed[1 - p] - self.committed[p]

    def middle(self):
        return self.pot + self.committed[0] + self.committed[1]


class Game:
    def __init__(self, cfg: Optional[GameConfig] = None, seed: int = 0):
        self.cfg = cfg or GameConfig()
        self.cfg.build_eval()
        self.rng = random.Random(seed)
        self.deck = list(range(self.cfg.n_ranks * self.cfg.n_suits))

    # ------------------------------------------------------------- legality ---
    def legal_actions(self, st: HandState, p: int):
        cfg = self.cfg
        acts = []
        tc = st.to_call(p)
        can_raise = (not st.allin) and st.raises < cfg.max_raises and st.stacks[p] > max(0.0, tc) and st.stacks[1-p] > 0
        if tc <= 0:
            acts.append(CHECK)
            if can_raise:
                pot = st.middle()
                for f in cfg.bet_fracs:
                    acts.append(bet_action(f))
        else:
            acts.append(FOLD)
            acts.append(CALL)
            if can_raise:
                pot = st.middle()
                for f in cfg.bet_fracs:
                    acts.append(bet_action(f))
        return acts

    def apply(self, st: HandState, p: int, act):
        st.history.append((st.street, p, act))
        tc = st.to_call(p)
        if act[0] == 'fold':
            st.folded = p
            return
        if act[0] == 'check':
            return
        if act[0] == 'call':
            pay = min(tc, st.stacks[p])
            st.stacks[p] -= pay
            st.committed[p] += pay
            st.total_in[p] += pay
            if st.stacks[p] == 0:
                st.allin = True
            return
        if act[0] == 'bet':
            frac = act[1]
            pot = st.middle()
            # put in: call amount + frac*pot, capped by stack
            pay = min(tc + pot * frac, st.stacks[p])
            st.stacks[p] -= pay
            st.committed[p] += pay
            st.total_in[p] += pay
            st.raises += 1
            if st.stacks[p] == 0:
                st.allin = True

    # ------------------------------------------------------------ street flow ---
    def _reveal(self, st: HandState):
        cfg = self.cfg
        st.street += 1
        start = sum(cfg.board_by_street[:st.street])
        n = cfg.board_by_street[st.street]
        st.board.extend(st.board_cards[start:start + n])

    def _run_out_board(self, st: HandState):
        while st.street < self.cfg.n_streets - 1:
            self._reveal(st)

    def _betting_round(self, st: HandState, players, dealt) -> bool:
        """Returns True if we continue (to showdown/next street), False if folded out.

        NOTE: `committed` is NOT reset here.  On the preflop the blinds are already
        in `committed` and must be respected; on later streets `play_hand` settles
        and clears `committed` before calling this.  Resetting here would erase the
        blinds and collapse every hand to a blind-sized pot.
        """
        st.raises = 0
        # who acts first: preflop -> SB (player 0); postflop -> BB (player 1)
        p = 0 if st.street < 0 else 1
        acted = [False, False]
        while True:
            if st.folded >= 0:
                return False
            tc = st.to_call(p)
            if acted[p] and tc <= 0:
                # nothing to answer and this player has acted -> street complete
                return True
            if st.allin:
                # no further betting possible; if matched, done
                if st.committed[0] == st.committed[1]:
                    return True
            acts = self.legal_actions(st, p)
            obs = self.observe(st, p, acts, dealt)
            act = players[p].decide(obs)
            if act not in acts:
                act = self._coerce(act, acts)
            self.apply(st, p, act)
            acted[p] = True
            # if everyone is all-in and matched, stop
            if st.allin and st.committed[0] == st.committed[1]:
                return True
            p = 1 - p

    def _coerce(self, act, acts):
        if act in acts:
            return act
        if act and act[0] == 'bet':
            bets = [a for a in acts if a[0] == 'bet']
            if bets:
                return min(bets, key=lambda a: abs(a[1] - act[1]))
        if act == CHECK and CHECK not in acts and CALL in acts:
            return CALL
        if act == CALL and CALL not in acts and CHECK in acts:
            return CHECK
        return acts[0]

    # ------------------------------------------------------------- payouts ---
    def _payout(self, st: HandState, winner: int) -> float:
        """Return chips delta for player 0 (end_stack_0 - start_stack_0)."""
        t0, t1 = st.total_in
        contested = 2.0 * min(t0, t1)
        excess0 = max(0.0, t0 - t1)
        if winner == 0:
            share = contested
        elif winner == 1:
            share = 0.0
        else:
            share = contested * 0.5
        end0 = st.stacks[0] + share + excess0
        return end0 - self.cfg.stack

    # ------------------------------------------------------------- the hand ---
    def play_hand(self, dealt, policy0, policy1):
        cfg = self.cfg
        st = HandState(cfg, [dealt[:cfg.n_hole], dealt[cfg.n_hole:2 * cfg.n_hole]],
                       dealt[2 * cfg.n_hole:2 * cfg.n_hole + cfg.n_board])
        players = [policy0, policy1]

        # post blinds
        for p, blind in ((0, cfg.sb), (1, cfg.bb)):
            pay = min(blind, st.stacks[p])
            st.stacks[p] -= pay
            st.committed[p] += pay
            st.total_in[p] += pay

        # preflop
        st.street = -1
        if not self._betting_round(st, players, dealt):
            return self._payout(st, 1 - st.folded), st.history

        # postflop streets
        while st.street < cfg.n_streets - 1:
            st.pot += st.committed[0] + st.committed[1]
            st.committed = [0.0, 0.0]      # settle street, start fresh
            self._reveal(st)
            st.allin = st.stacks[0] == 0 or st.stacks[1] == 0
            if st.allin:
                self._run_out_board(st)
                break
            if not self._betting_round(st, players, dealt):
                return self._payout(st, 1 - st.folded), st.history

        # showdown
        best = cfg.best
        s0 = best(st.hole[0], st.board)
        s1 = best(st.hole[1], st.board)
        winner = 0 if s0 > s1 else (1 if s1 > s0 else -1)
        return self._payout(st, winner), st.history

    def observe(self, st, p, acts, dealt):
        cfg = self.cfg
        return {
            'hole': list(st.hole[p]),
            'board': list(st.board),
            'pot': st.middle(),
            'to_call': max(0.0, st.to_call(p)),
            'my_stack': st.stacks[p],
            'opp_stack': st.stacks[1 - p],
            'street': st.street,
            'legal': list(acts),
            'position': p,
            'history': list(st.history),
            'n_raises': st.raises,
            'cfg': cfg,
            'eval5': cfg.eval5,
            'best': cfg.best,
        }
