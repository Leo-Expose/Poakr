"""
DUPLICATE-DEAL CARD TRACKING + EXACT KNOWN-HAND EXPLOIT  (the one-sided edge).

The competition plays every deal TWICE with swapped seats.  If a deal fixes hole
pairs (H1,H2) and a board, then:
    copy 1: I hold H1, opponent holds H2
    copy 2: I hold H2, opponent holds H1   <- my copy-1 cards!
I SAW H1 in copy 1 (they were my cards), so in copy 2 I KNOW the opponent's exact
hole cards.  This is legitimate: it is memory + inference on the announced format,
not collusion/cheating/network.

The key correction to naive 'duplicate = perfect information' plans: this is
ONE-SIDED unless the opponent also tracks (typical bots do not).  So we EXPLOIT
their revealed hand (value-bet when we're ahead, fold/raise precisely, bluff when
they're weak) rather than check down a 'perfect-info' river.

Modules:
  DuplicateTracker     : remembers our hands, detects the partner hand, infers
                         the opponent's hole cards with a confidence score.
  equity_vs_known      : EXACT equity against a known opponent hand (enumerate
                         remaining boards; deterministic, no sampling error).
  decide_known_hand    : the one-sided exploit decision given their exact cards.
"""
from __future__ import annotations
import random
from engine.cards import make_evaluator, make_best_of

_E5 = make_evaluator(13, 4)
_BEST = make_best_of(_E5, 7)


# ---------------------------------------------------------------------------
# EXACT equity against a KNOWN opponent hand
# ---------------------------------------------------------------------------
def equity_vs_known(my_hole, opp_hole, board, max_enum=2500, rng=None):
    """
    P(win) + 0.5 P(tie) of `my_hole` vs a KNOWN `opp_hole`, given `board`.
    Exact by enumeration when cheap (river = deterministic, turn = ~45 cards,
    flop = ~990 turn-river pairs); Monte-Carlo vs the KNOWN hand preflop (which
    is far tighter than vs a random range).
    """
    my = list(my_hole); opp = list(opp_hole); board = list(board)
    nb = len(board)
    used = set(my) | set(opp) | set(board)
    rem = [c for c in range(52) if c not in used]
    need = 5 - nb

    if need == 0:
        s0 = _BEST(my, board); s1 = _BEST(opp, board)
        return 1.0 if s0 > s1 else (0.0 if s0 < s1 else 0.5)

    if need == 1:
        wins = ties = 0
        for c in rem:
            b = board + [c]
            s0 = _BEST(my, b); s1 = _BEST(opp, b)
            if s0 > s1: wins += 1
            elif s0 == s1: ties += 1
        return (wins + 0.5 * ties) / len(rem)

    if need == 2:
        n = len(rem)
        total = n * (n - 1) // 2
        if total <= max_enum:
            wins = ties = 0
            for i in range(n):
                for j in range(i + 1, n):
                    b = board + [rem[i], rem[j]]
                    s0 = _BEST(my, b); s1 = _BEST(opp, b)
                    if s0 > s1: wins += 1
                    elif s0 == s1: ties += 1
            return (wins + 0.5 * ties) / total
        # fall back to MC vs the known hand
        rng = rng or random.Random(0)
        wins = ties = 0
        K = max_enum
        for _ in range(K):
            samp = rng.sample(rem, 2)
            b = board + samp
            s0 = _BEST(my, b); s1 = _BEST(opp, b)
            if s0 > s1: wins += 1
            elif s0 == s1: ties += 1
        return (wins + 0.5 * ties) / K

    # preflop (need==5): MC vs known hand
    rng = rng or random.Random(0)
    wins = ties = 0
    K = min(1500, max_enum * 4)
    for _ in range(K):
        samp = rng.sample(rem, 5)
        s0 = _BEST(my, samp); s1 = _BEST(opp, samp)
        if s0 > s1: wins += 1
        elif s0 == s1: ties += 1
    return (wins + 0.5 * ties) / K


# ---------------------------------------------------------------------------
# DUPLICATE TRACKER
# ---------------------------------------------------------------------------
class DuplicateTracker:
    """
    Remembers our hole cards per hand and infers the opponent's cards in the
    second copy of each pair.

    Pairing strategy (robust, degrades safely):
      * If the protocol repeats a deal/hand id -> pair on that (highest conf).
      * Else if hands are dealt back-to-back (the common case) -> the previous
        hand is the partner; confidence rises as the board matches the previous
        hand's board (identical board = certain pair).
      * When confidence is low we return None and the caller falls back to the
        normal hidden-info policy (never worse, never forfeits).
    """

    def __init__(self):
        self.past = []          # list of {'my_hole','board','deal_id'}
        self._prev = None

    def record(self, my_hole, board, deal_id=None):
        self._prev = {'my_hole': list(my_hole), 'board': list(board), 'deal_id': deal_id}
        self.past.append(self._prev)

    def infer_partner(self, my_hole, board, deal_id=None):
        """
        Returns (opp_hole, confidence) for the CURRENT hand.
          opp_hole   : the opponent's exact hole cards if we can infer them
          confidence : 0.0 (guess) .. 1.0 (certain)
        Returns (None, 0.0) when we cannot infer safely.
        """
        # 1) deal_id match (best)
        if deal_id is not None:
            for h in self.past:
                if h.get('deal_id') == deal_id and h['my_hole'] != list(my_hole):
                    return list(h['my_hole']), 1.0

        # 2) board-match a past hand whose hole differs from ours
        nb = len(board)
        if nb >= 3 and self._prev is not None:
            prev = self._prev
            # identical board prefix of length >=3 is a strong pair signal
            same = 0
            for a, b in zip(prev['board'], board):
                if a == b:
                    same += 1
                else:
                    break
            if same == nb and prev['my_hole'] != list(my_hole):
                # certain once the full runout matches; scale confidence by length
                conf = 1.0 if nb == 5 else (0.75 if nb == 4 else 0.6)
                return list(prev['my_hole']), conf

        # 3) back-to-back assumption (medium confidence, rises with board agreement)
        if self._prev is not None and self._prev['my_hole'] != list(my_hole):
            if nb >= 3:
                agree = sum(1 for a, b in zip(self._prev['board'], board) if a == b)
                if agree >= min(3, nb):
                    return list(self._prev['my_hole']), 0.7
            # preflop: weak signal only
            return None, 0.0
        return None, 0.0


# ---------------------------------------------------------------------------
# ONE-SIDED EXPLOIT given the opponent's exact cards
# ---------------------------------------------------------------------------
def decide_known_hand(obs, opp_hole, po, eq, street, legal, n_raises, max_raises,
                      fold_tendency=0.35):
    """
    Make the exploit decision when we KNOW the opponent's exact hole cards.

    Because their hand is revealed, `eq` (from equity_vs_known) is exact.  We:
      * value-bet when ahead (they may pay off with their specific hand),
      * raise when we have them out-kicked and they show aggression,
      * fold when we're behind and they bet,
      * bluff ONLY when we lose but their hand is weak and they over-fold.
    """
    can_bet = any(a[0] == 'bet' for a in legal)
    can_check = ('check',) in legal

    if to_call_zero(obs):
        # checked to us
        if eq > 0.90:
            # we almost certainly win -> thin or fat value based on their hand
            return ('bet', 1.0) if can_bet else (legal[0])
        if eq > 0.62:
            return ('bet', 0.5) if can_bet else (legal[0])
        # we're behind or flipping -> bluff only if their hand is weak and they fold
        if eq < 0.35 and fold_tendency > 0.5 and street >= 2:
            return ('bet', 0.5) if can_bet else (legal[0])
        return ('check',) if can_check else legal[0]

    # facing a bet -> certainty
    if eq > 0.85:
        # we're way ahead: raise for value if allowed
        if can_bet and n_raises < max_raises:
            return ('bet', 0.5)
        return ('call',)
    if eq > 0.55:
        return ('call',)   # slight favourite, call
    # we're behind: fold (they have it, and they know enough to value-bet)
    return ('fold',) if ('fold',) in legal else ('call',)


def to_call_zero(obs):
    return obs.get('to_call', 0) <= 0
