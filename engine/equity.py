"""
Shared fast equity + invariant features for the policy layer.

Every policy uses the SAME equity engine so that measured differences isolate the
DECISION FRAMEWORK, not the evaluator.  Equity is estimated by Monte-Carlo with
the pure-NumPy exact evaluator (validated against an exhaustive ground truth).
"""
import numpy as np
from engine.numpy_eval import eval_batch
from engine.cards import make_best_of, make_evaluator

_E5 = make_evaluator(13, 4)
_BEST = make_best_of(_E5, 7)


def _suits(ranks_suits):
    return ranks_suits


def equity_vs_range(hole, board, n_draws=400, seed=0, cfg=None):
    """
    P(win) + 0.5*P(tie) of `hole` vs a uniformly random unseen 2-card hand,
    given `board` (list of 0..5 cards).  Returns float in [0,1].
    Vectorised Monte-Carlo.
    """
    hole = list(hole)
    board = list(board)
    known = set(hole) | set(board)
    rem = np.array([c for c in range(52) if c not in known], np.int64)
    n_board = len(board)
    need = 5 - n_board
    if len(rem) < 2 + need:
        return 0.5

    rng = np.random.default_rng(seed & 0xFFFFFFFF)
    n = n_draws
    # sample opponent hole + remaining board cards for all draws at once
    # we need 2 + need distinct cards per draw from rem
    take = 2 + need
    # random matrix of indices
    keys = rng.random((n, len(rem)))
    idx = np.argpartition(keys, take - 1, axis=1)[:, :take]   # (n, take)
    picked = rem[idx]                                        # (n, take) card ids

    opp = picked[:, :2]
    newcards = picked[:, 2:]

    my = np.empty((n, 7), np.int64)
    op = np.empty((n, 7), np.int64)
    my[:, :2] = hole
    op[:, :2] = opp
    if n_board:
        my[:, 2:2 + n_board] = board
        op[:, 2:2 + n_board] = board
    my[:, 2 + n_board:] = newcards
    op[:, 2 + n_board:] = newcards

    sm = eval_batch(my)
    so = eval_batch(op)
    wins = (sm > so).sum() + 0.5 * (sm == so).sum()
    return float(wins) / n


def made_hand_strength(hole, board, cfg=None):
    """
    Crude made-hand strength in [0,1] using only the current best 5-card category
    and kicker depth.  Cheap, no sampling.  Used as a fast pre-filter / feature.
    """
    if not board:
        return None
    s = _BEST(list(hole), list(board))
    cat = (s >> 20) & 0xF
    tie = s & 0xFFFFF
    # normalise: category dominates, kicker breaks ties
    return (cat + tie / 0x100000) / 9.0


def spr(pot, my_stack, to_call=0.0):
    """Stack-to-pot ratio (invariant)."""
    p = pot + to_call
    return my_stack / p if p > 0 else float('inf')


def pot_odds(to_call, pot):
    """Pot odds as a required equity fraction (invariant)."""
    total = pot + to_call
    return to_call / total if total > 0 else 0.0


def implied_draw_equity(hole, board, n_draws=300, seed=1):
    """
    Equity of reaching showdown with NO further betting, i.e. raw realized equity.
    Same as equity_vs_range but with more samples for the 'big pot' path.
    """
    return equity_vs_range(hole, board, n_draws=n_draws, seed=seed)
