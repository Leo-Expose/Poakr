#!/usr/bin/env python3
"""Discard Hold'em protocol 1.0 bot — v2.

Python 3.11; standard library + NumPy only. No runtime file/network/process I/O.
Design goals:
  1. Never forfeit: defensive parsing, legal-only replies, hard time manager,
     flushed output, exit after match_end.
  2. Maximize per-hand EV: sampled/exact equity vs an action-conditioned
     opponent range, equity-bucketed bet sizing, bluffs, and optimal discard.
"""
import sys
import os
import json
import random
import base64
import zlib
from itertools import combinations, combinations_with_replacement

sys.dont_write_bytecode = True
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "1"

import numpy as np

# Preflop equity table for all C(52,3) holdings (uint8, equity*255), embedded.
_PREFLOP_BLOB = "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"

# --------------------------------------------------------------------------
# Cards: id = rank*4 + suit; rank 0..12 = 2..A; suit 0..3 = c,d,h,s
RANKS = "23456789TJQKA"
SUITS = "cdhs"
DISCARD_SUIT_ORDER = "shdc"  # rulebook tie-break order for default discard
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}


def card(t):
    if not isinstance(t, str) or len(t) != 2 or t[0] not in RANKS or t[1] not in SUITS:
        raise ValueError("bad card")
    return 4 * RANKS.index(t[0]) + SUITS.index(t[1])


def tcard(v):
    return RANKS[v // 4] + SUITS[v % 4]


def parse_cards(values, n=None):
    if not isinstance(values, (list, tuple)):
        raise ValueError("cards not list")
    if n is not None and len(values) != n:
        raise ValueError("wrong card count")
    out = tuple(card(c) for c in values)
    if len(set(out)) != len(out):
        raise ValueError("dup cards")
    return out


def default_discard(values):
    return min(values, key=lambda c: (RANK_VALUE[c[0]], DISCARD_SUIT_ORDER.index(c[1])))


_COMB_INDEX = {c: i for i, c in enumerate(combinations(range(52), 3))}
_PREFLOP_TABLE = None


def preflop_equity(three):
    """Table equity (0..1) of a 3-card holding vs uniform random opponent,
    or None if the table is not embedded (fallback to sampling)."""
    global _PREFLOP_TABLE
    if not _PREFLOP_BLOB:
        return None
    if _PREFLOP_TABLE is None:
        raw = zlib.decompress(base64.b64decode(_PREFLOP_BLOB))
        _PREFLOP_TABLE = np.frombuffer(raw, dtype=np.uint8) / 255.0
    key = tuple(sorted(three))
    return float(_PREFLOP_TABLE[_COMB_INDEX[key]])


# --------------------------------------------------------------------------
# Vectorized 7-card evaluator (score = category<<20 | tiebreak nibbles)
_STRAIGHTS = np.zeros((10, 13), np.bool_)
for _i, _top in enumerate(range(4, 13)):
    _STRAIGHTS[_i, _top - 4:_top + 1] = True
_STRAIGHTS[9, [0, 1, 2, 3, 12]] = True
_STRAIGHT_HIGH = np.array([4, 5, 6, 7, 8, 9, 10, 11, 12, 3], np.int32)
_CAT = 20


def _top_n(mask, n):
    w = mask.shape[1]
    key = mask.astype(np.int32) * 1000 + np.arange(w, dtype=np.int32)[None, :]
    order = np.argsort(-key, axis=1, kind="stable")[:, :n]
    return order.astype(np.int32)


_SUBSETS = {w: np.array(list(combinations(range(w), 5)), dtype=np.int32) for w in (5, 6, 7)}
_POW = (13 ** np.arange(4, -1, -1)).astype(np.int32)
_NONFLUSH = None
_FLUSH = None


def _build_eval_tables():
    """Perfect-hash 5-card evaluator tables (built once, inside the free
    start-up window): indexed by base-13 key of the 5 ranks sorted descending."""
    global _NONFLUSH, _FLUSH
    nf = np.zeros(13 ** 5, dtype=np.int32)
    fl = np.zeros(13 ** 5, dtype=np.int32)
    for ranks in combinations_with_replacement(range(13), 5):
        r = sorted(ranks, reverse=True)
        key = (((r[0] * 13 + r[1]) * 13 + r[2]) * 13 + r[3]) * 13 + r[4]
        c = [0] * 13
        for x in ranks:
            c[x] += 1
        pat = tuple(sorted((v for v in c if v), reverse=True))
        mask = 0
        for x in ranks:
            mask |= 1 << x
        sh = 0
        for top in range(4, 13):
            if all((mask >> t) & 1 for t in range(top - 4, top + 1)):
                sh = top
                break
        if sh == 0 and mask == (1 << 12) | 1 | 2 | 4 | 8:
            sh = 3  # wheel A-2-3-4-5, 5-high
        if pat == (1, 1, 1, 1, 1):
            nf[key] = (4 << 20) | sh if sh else sum(r[i] << (16 - 4 * i) for i in range(5))
            fl[key] = (8 << 20) | sh if sh else (5 << 20) | sum(r[i] << (16 - 4 * i) for i in range(5))
        elif pat == (2, 1, 1, 1):
            pair = next(x for x in range(13) if c[x] == 2)
            ks = sorted((x for x in range(13) if c[x] == 1), reverse=True)
            nf[key] = (1 << 20) | (pair << 16) | (ks[0] << 12) | (ks[1] << 8) | (ks[2] << 4)
        elif pat == (2, 2, 1):
            ps = sorted((x for x in range(13) if c[x] == 2), reverse=True)
            k = next(x for x in range(13) if c[x] == 1)
            nf[key] = (2 << 20) | (ps[0] << 16) | (ps[1] << 12) | (k << 8)
        elif pat == (3, 1, 1):
            t = next(x for x in range(13) if c[x] == 3)
            ks = sorted((x for x in range(13) if c[x] == 1), reverse=True)
            nf[key] = (3 << 20) | (t << 16) | (ks[0] << 12) | (ks[1] << 8)
        elif pat == (3, 2):
            t = next(x for x in range(13) if c[x] == 3)
            p = next(x for x in range(13) if c[x] == 2)
            nf[key] = (6 << 20) | (t << 16) | (p << 12)
        elif pat == (4, 1):
            q = next(x for x in range(13) if c[x] == 4)
            k = next(x for x in range(13) if c[x] == 1)
            nf[key] = (7 << 20) | (q << 16) | (k << 12)
    _NONFLUSH, _FLUSH = nf, fl


def eval_batch(cards):
    """Exact evaluator for (N,W) cards, W in 5..7, via perfect-hash 5-card tables.
    Score = category<<20 | packed tiebreak ranks; higher is better."""
    global _NONFLUSH, _FLUSH
    if _NONFLUSH is None:
        _build_eval_tables()
    c = np.asarray(cards, dtype=np.int16)
    if c.ndim != 2 or not 5 <= c.shape[1] <= 7:
        raise ValueError("cards must be (N,5..7)")
    N, W = c.shape
    ranks = (c // 4).astype(np.int8)
    suits = (c % 4).astype(np.int8)
    order = np.argsort(ranks, axis=1, kind="stable")[:, ::-1]
    rs = np.take_along_axis(ranks, order, axis=1)
    ss = np.take_along_axis(suits, order, axis=1)
    subs = _SUBSETS[W]                       # (C(W,5), 5)
    rc = rs[:, subs].astype(np.int32)        # (N, S, 5), sorted desc
    sc = ss[:, subs]
    key = np.dot(rc, _POW)
    flush = (sc[..., 0] == sc[..., 1]) & (sc[..., 1] == sc[..., 2]) & (sc[..., 2] == sc[..., 3]) & (sc[..., 3] == sc[..., 4])
    v = np.where(flush, _FLUSH[key], _NONFLUSH[key])
    return v.max(axis=1).astype(np.int32)


# --------------------------------------------------------------------------
# Fast partial-board strength heuristic for range weighting (no evaluator).
def preflop_strength3(three):
    """Heuristic 0..1 strength of a 3-card holding."""
    r = sorted((c // 4 for c in three), reverse=True)
    suits = [c % 4 for c in three]
    pair = len(set(r)) < 3
    trips = len(set(r)) == 1
    suited = len(set(suits)) == 1
    two_suited = len(set(suits)) == 2
    hi = r[0] / 12.0
    gap = (r[0] - r[1]) + (r[1] - r[2])
    s = 0.10 + 0.55 * hi
    if trips:
        s = 0.75 + 0.25 * (r[0] / 12.0)
    elif pair:
        s = 0.45 + 0.45 * (r[0] / 12.0) + (0.08 if r[2] >= 8 else 0.0)
    else:
        if suited:
            s += 0.10
        elif two_suited:
            s += 0.04
        if gap <= 2:
            s += 0.08
        if r[2] >= 9:
            s += 0.04
    return min(1.0, s)


# --------------------------------------------------------------------------
class TimeManager:
    def __init__(self, bank_ms):
        self.bank = max(1, int(bank_ms))
        self.last_left = self.bank

    def update(self, left_ms):
        if isinstance(left_ms, int) and 0 <= left_ms <= 10**9:
            self.last_left = left_ms

    def budget_ms(self, hands_left):
        """Per-decision budget in ms. A hand can contain up to ~6 decisions
        (preflop x2, flop x2, turn, river, discard), so each decision gets at
        most 1/7 of the per-hand allowance, and we keep a large reserve."""
        left = self.last_left
        reserve = max(5000.0, 0.25 * self.bank)  # never touch this
        avail = max(0, left - reserve)
        hands_left = max(1, hands_left)
        per_hand = avail / hands_left
        return max(2.0, min(1500.0, per_hand / 7.0))


# --------------------------------------------------------------------------
class Bot:
    def __init__(self):
        self.rng = random.Random(0xC0FFEE)
        self.np_rng = np.random.default_rng(0xC0FFEE)
        self.total = 200
        self.bank_ms = 30000
        self.per_reply_ms = 5000
        self.tm = TimeManager(self.bank_ms)
        self.hand_id = 0
        self.seat = "button"
        self.hole3 = ()       # original 3 hole cards (ints)
        self.hole2 = ()       # kept pair after discard (ints)
        self.dead = ()        # (my_discard, opp_discard)
        self.board = ()
        self.pre_equity = None  # cached preflop equity for this hand
        self.flop_cards = ()
        self.opp_d_card = None
        self._opp_discard_weights = None
        # Tournament meta-state: track cumulative net chips in this leg
        self.leg_net = 0
        # Opponent archetype classification (Nit, Station, Shover, Solver)
        self.opp_archetype = "unknown"
        # opponent model (per leg) with Beta priors for instantaneous adaptation
        self.opp_stats = dict(
            hands=0, vpip=0, pfr=0, raises=0,
            folds=0, calls=0, checks=0, showdowns=0,
            fold_freq=0.5, agg=1.0,
            shove_count=0,
            # Beta(alpha, beta) priors: fold_prior = Beta(2, 2) (mean 0.50)
            fold_a=2.0, fold_b=2.0,
            fb={"small": [2.0, 2.0], "mid": [2.0, 2.0], "big": [2.0, 2.0]}
        )
        self.hand_actions = []  # opponent actions this hand
        self.speed_scale = 1.0   # default until init-time calibration

    def _blocker_bonus(self, board):
        """How well our kept pair blocks opponent's strongest holdings."""
        b = self.hole2
        if len(b) != 2 or not board:
            return 0.0
        bonus = 0.0
        ranks = [c // 4 for c in b]
        if 12 in ranks:
            bonus += 0.08  # blocks top pair / ace-high
        from collections import Counter
        sc = Counter(c % 4 for c in board)
        if board and max(sc.values()) >= 3:
            flush_suit = sc.most_common(1)[0][0]
            for c in b:
                if c % 4 == flush_suit:
                    bonus += 0.10 + 0.05 * (c // 4 >= 10)
        # straight blockers: board with 4 to a straight, we hold a key rank
        br = sorted(set(c // 4 for c in board))
        if len(br) == 4 and br[-1] - br[0] == 3:
            lo, hi = br[0] - 1, br[-1] + 1
            for c in b:
                r = c // 4
                if r in (lo, hi) and 0 <= r <= 12:
                    bonus += 0.08
        return bonus

    # ---------------- sampling helpers ----------------
    def _draw(self, unseen, S, k):
        """S rows, each a k-subset of unseen (vectorized via per-row permutation)."""
        U = len(unseen)
        if k > U:
            k = U
        X = np.tile(unseen, (S, 1))
        X = self.np_rng.permuted(X, axis=1)
        return X[:, :k]

    def _own_cards(self):
        """2 kept cards post-discard, else the 3 original cards pre-discard."""
        return self.hole2 if len(self.hole2) == 2 else self.hole3

    def _equity_postflop(self, board, S, weights=None, exact_river=False):
        """Equity of our holding vs sampled opponent pairs, given board.
        Pre-discard (3 hole cards) we take the best pair per scenario.
        Returns (equity, opponent scores for weighting)."""
        b = len(board)
        own = self._own_cards()
        blocked = set(own) | set(board) | set(self.dead)
        unseen = np.array([c for c in range(52) if c not in blocked], dtype=np.int64)
        if exact_river and b == 5:
            peers = np.array(list(combinations(unseen.tolist(), 2)), dtype=np.int64)
            boards = np.tile(np.array(board, dtype=np.int64), (len(peers), 1))
            pscore = eval_batch(np.column_stack((peers, boards)))
            if len(own) == 2:
                oscore = int(eval_batch(np.array([tuple(own) + tuple(board)], dtype=np.int64))[0])
            else:
                oscore = max(int(eval_batch(np.array([(own[i], own[j]) + tuple(board)], dtype=np.int64))[0])
                             for i, j in combinations(range(3), 2))
            credit = (oscore > pscore) + 0.5 * (oscore == pscore)
            w = weights(pscore) if weights is not None else np.ones(len(pscore), dtype=np.float64)
            # incorporate Bayesian discard consistency
            disc_w = self._opp_discard_consistency(peers)
            if disc_w is not None:
                w = (w if w is not None else 1.0) * disc_w
            if w is not None:
                return float((w * credit).sum() / max(1e-9, w.sum())), pscore
            return float(credit.mean()), pscore
        need = 5 - b
        draws = self._draw(unseen, S, 2 + need)  # opp pair + runout
        opp2 = draws[:, :2]
        runout = draws[:, 2:]
        boards = np.concatenate((np.tile(np.array(board, dtype=np.int64), (S, 1)), runout), axis=1)
        pscore = eval_batch(np.concatenate((opp2, boards), axis=1))
        if len(own) == 2:
            oscore = eval_batch(np.concatenate((np.tile(np.array(own, dtype=np.int64), (S, 1)), boards), axis=1))
            credit = (oscore > pscore) + 0.5 * (oscore == pscore)
            w = weights(pscore) if weights is not None else np.ones(len(pscore), dtype=np.float64)
            disc_w = self._opp_discard_consistency(opp2)
            if disc_w is not None:
                w = (w if w is not None else 1.0) * disc_w
            if w is not None:
                return float((w * credit).sum() / max(1e-9, w.sum())), pscore
            return float(credit.mean()), pscore
        # pre-discard: commit to ONE pair before seeing turn/river -> holding value
        # is max over pairs of each pair's MEAN equity (not per-runout max)
        scores = np.stack([
            eval_batch(np.concatenate((np.tile(np.array([own[i], own[j]], dtype=np.int64), (S, 1)), boards), axis=1))
            for i, j in combinations(range(3), 2)
        ])  # (3, S)
        w = weights(pscore) if weights is not None else None
        pair_q = []
        for i in range(3):
            c = (scores[i] > pscore) + 0.5 * (scores[i] == pscore)
            pair_q.append(float((w * c).sum() / w.sum()) if w is not None else float(c.mean()))
        return max(pair_q), pscore

    def _equity_preflop(self, S, opp_weight=None):
        """Equity of 3-card holding (optimal discard approximated by per-runout max pair)
        vs opponent 3-card holdings (their best pair per runout). If opp_weight is
        given, it maps opponent holdings' table equities to likelihood weights."""
        blocked = set(self.hole3)
        unseen = np.array([c for c in range(52) if c not in blocked], dtype=np.int64)
        draws = self._draw(unseen, S, 3 + 5)  # opp 3 + board 5
        opp3 = draws[:, :3]
        boards = draws[:, 3:]
        my_pairs = list(combinations(range(3), 2))
        opp_pairs = list(combinations(range(3), 2))
        my_scores = np.stack([
            eval_batch(np.concatenate((np.tile(np.array([self.hole3[i] for i in ix], dtype=np.int64), (S, 1)), boards), axis=1))
            for ix in my_pairs
        ])
        # opp best pair per scenario: eval each of 3 pair choices
        opp_pair_scores = []
        for ix in opp_pairs:
            pair_cards = opp3[:, list(ix)]  # (S,2)
            opp_pair_scores.append(eval_batch(np.concatenate((pair_cards, boards), axis=1)))
        opp_best = np.stack(opp_pair_scores).max(axis=0)
        my_best = my_scores.max(axis=0)
        credit = (my_best > opp_best) + 0.5 * (my_best == opp_best)
        if opp_weight is not None:
            keys = [tuple(sorted(row.tolist())) for row in opp3]
            tvals = np.array([preflop_equity(k) for k in keys])
            w = opp_weight(tvals)
            return float((w * credit).sum() / max(1e-9, w.sum()))
        return float(credit.mean())

    def _flop_semiexact(self, board, R):
        """All opponent pairs x R sampled runout pairs. ~2*990*R evals."""
        own = self._own_cards()
        blocked = set(own) | set(board) | set(self.dead)
        unseen = np.array([c for c in range(52) if c not in blocked], dtype=np.int64)
        peers = np.array(list(combinations(unseen.tolist(), 2)), dtype=np.int64)
        P = len(peers)
        draws = self._draw(unseen, P * R, 2)
        runouts = draws  # (P*R, 2)
        peer_rep = np.repeat(peers, R, axis=0)
        boards = np.concatenate((np.tile(np.array(board, dtype=np.int64), (P * R, 1)), runouts), axis=1)
        pscore = eval_batch(np.concatenate((peer_rep, boards), axis=1))
        if len(own) == 2:
            oscore = eval_batch(np.concatenate((np.tile(np.array(own, dtype=np.int64), (P * R, 1)), boards), axis=1))
        else:
            oscore = np.stack([
                eval_batch(np.concatenate((np.tile(np.array([own[i], own[j]], dtype=np.int64), (P * R, 1)), boards), axis=1))
                for i, j in combinations(range(3), 2)
            ]).max(axis=0)
        credit = ((oscore > pscore) + 0.5 * (oscore == pscore)).reshape(P, R).mean(axis=1)
        w = self._opp_action_weights(pscore.reshape(P, R).mean(axis=1))
        if w is None:
            return float(credit.mean())
        return float((w * credit).sum() / max(1e-9, w.sum()))

    def _draw_potential_bonus(self, two, board):
        """Bonus for hands with high nut-potential and implied odds (flush/straight draws)."""
        ranks = [c // 4 for c in two]
        suits = [c % 4 for c in two]
        b_ranks = [c // 4 for c in board]
        b_suits = [c % 4 for c in board]
        bonus = 0.0
        from collections import Counter
        sc = Counter(b_suits)
        for s, cnt in sc.items():
            my_s = sum(1 for suit in suits if suit == s)
            if cnt + my_s >= 4:
                has_ace = any(c // 4 == 12 and c % 4 == s for c in two)
                bonus += 0.08 if has_ace else 0.04
        all_ranks = sorted(set(ranks + b_ranks))
        for i in range(len(all_ranks) - 3):
            if all_ranks[i+3] - all_ranks[i] == 3:
                bonus += 0.04
                break
        return bonus

    def _discard_equity(self, board, S):
        """For each of the 3 possible discards, estimate equity + draw potential;
        return best discard card with subtle mixed-discard camouflage for near-ties."""
        blocked = set(self.hole3) | set(board)
        unseen = np.array([c for c in range(52) if c not in blocked], dtype=np.int64)
        draws = self._draw(unseen, S, 3 + 2)  # opp 3 + turn+river
        opp3 = draws[:, :3]
        runout = draws[:, 3:]
        boards = np.concatenate((np.tile(np.array(board, dtype=np.int64), (S, 1)), runout), axis=1)
        opp_pairs = list(combinations(range(3), 2))
        opp_best = np.stack([
            eval_batch(np.concatenate((opp3[:, list(ix)], boards), axis=1))
            for ix in opp_pairs
        ]).max(axis=0)
        candidates = []
        for d in self.hole3:
            keep = tuple(c for c in self.hole3 if c != d)
            oscore = eval_batch(np.concatenate((np.tile(np.array(keep, dtype=np.int64), (S, 1)), boards), axis=1))
            e = float(((oscore > opp_best) + 0.5 * (oscore == opp_best)).mean())
            draw_bonus = self._draw_potential_bonus(keep, board)
            score = e + draw_bonus
            candidates.append((score, d))
        candidates.sort(key=lambda x: -x[0])
        best_score, best_d = candidates[0]
        # Discard camouflage: if 2nd candidate is within 0.015 of best, randomize 25% of the time
        if len(candidates) > 1 and (best_score - candidates[1][0]) <= 0.015:
            if self.rng.random() < 0.25:
                return candidates[1][1]
        return best_d

    # ---------------- opponent modeling ----------------
    def _opp_discard_consistency(self, opp_pairs):
        """Vectorized consistency of opponent candidate pairs with their exposed discard."""
        if not self.flop_cards or self.opp_d_card is None:
            return None
        opp_d = self.opp_d_card
        N = len(opp_pairs)
        b_tile = np.tile(np.array(self.flop_cards, dtype=np.int64), (N, 1))
        s_keep = eval_batch(np.column_stack((opp_pairs, b_tile)))
        s_alt1 = eval_batch(np.column_stack((opp_pairs[:, 0], np.full(N, opp_d, dtype=np.int64), b_tile)))
        s_alt2 = eval_batch(np.column_stack((opp_pairs[:, 1], np.full(N, opp_d, dtype=np.int64), b_tile)))
        best_alt = np.maximum(s_alt1, s_alt2)
        diff = s_keep.astype(np.int64) - best_alt.astype(np.int64)
        # s_keep > best_alt: consistent (1.0). Equal: 0.7. Inferior: decays smoothly.
        w = np.where(diff > 0, 1.0, np.where(diff == 0, 0.7, np.exp(np.clip(diff / 60000.0, -10.0, 0.0)) * 0.15))
        return w

    def _opp_action_weights(self, pscore):
        """Likelihood weights for opponent holdings given their actions this hand
        and their historical tendencies. pscore: showdown scores of sampled holdings."""
        st = self.opp_stats
        agg = st["agg"]  # raises / (bets) ~ aggression
        acts = self.hand_actions
        if not acts:
            return None
        # normalize scores to percentile within this sample
        order = np.argsort(np.argsort(pscore))
        pct = order / max(1, len(pscore) - 1)
        w = np.ones(len(pscore), dtype=np.float64)
        for (street, act, size_frac) in acts:
            if act == "raise":
                # raisers are stronger; bigger raises stronger still
                k = 2.0 + 2.0 * min(1.0, size_frac) + 2.0 * agg
                w *= 0.15 + pct ** k * (1.2 + agg)
            elif act == "call":
                # callers are middling
                w *= 0.6 + 0.8 * (1.0 - np.abs(pct - 0.55) * 2.0)
            elif act == "check":
                w *= 0.35 + 1.3 * (1.0 - pct)
            # fold: hand over
        return w

    def _update_stats(self, history, result, opp_cards, opp_discard):
        st = self.opp_stats
        st["hands"] += 1
        saw_bet = False
        last_my_raise = 0
        for ev in history:
            if not isinstance(ev, dict):
                continue
            if ev.get("actor") == "me" and ev.get("action") == "raise":
                amt = ev.get("amount", 0)
                last_my_raise = amt if isinstance(amt, int) else 0
            elif ev.get("actor") == "opp":
                a = ev.get("action")
                if a == "raise":
                    st["raises"] += 1
                    if ev.get("street") == "preflop":
                        saw_bet = True
                elif a == "call":
                    st["calls"] += 1
                    bucket = "small" if last_my_raise <= 8 else ("mid" if last_my_raise <= 30 else "big")
                    st["fb"][bucket][1] += 1.0
                    st["fold_b"] += 1.0
                    if ev.get("street") == "preflop":
                        saw_bet = True
                elif a == "check":
                    st["checks"] += 1
                elif a == "fold":
                    st["folds"] += 1
                    bucket = "small" if last_my_raise <= 8 else ("mid" if last_my_raise <= 30 else "big")
                    st["fb"][bucket][0] += 1.0
                    st["fold_a"] += 1.0
        if saw_bet:
            st["vpip"] += 1
        if any(isinstance(ev, dict) and ev.get("actor") == "opp" and ev.get("action") == "raise"
               and ev.get("street") == "preflop" for ev in history):
            st["pfr"] += 1
        st["fold_freq"] = st["fold_a"] / (st["fold_a"] + st["fold_b"])
        st["agg"] = (st["raises"] + 0.5) / max(1, st["raises"] + st["calls"])
        if result == "showdown":
            st["showdowns"] += 1

        # Classify opponent archetype once we have 8+ hands
        h = st["hands"]
        if h >= 8:
            v_rate = st["vpip"] / h
            ff = st["fold_freq"]
            if st["shove_count"] >= 3:
                self.opp_archetype = "shover"
            elif ff >= 0.65 and v_rate < 0.45:
                self.opp_archetype = "nit"
            elif ff <= 0.35 and v_rate >= 0.55:
                self.opp_archetype = "station"
            else:
                self.opp_archetype = "balanced"

    def _fold_freq_for(self, size_to):
        """Estimated P(opp folds) to a bet of street-total size_to, by size bucket via Beta posterior."""
        bucket = "small" if size_to <= 8 else ("mid" if size_to <= 30 else "big")
        a, b = self.opp_stats["fb"][bucket]
        return a / (a + b)

    # ---------------- decision ----------------
    def _size_to(self, msg, frac):
        """Raise-to amount targeting frac * (pot + to_call) beyond opp_bet, clamped."""
        pot = msg["pot"]; owed = msg["to_call"]; opp_bet = msg["opp_bet"]
        mn, mx = msg["min_raise"], msg["max_raise"]
        target = opp_bet + int(round(frac * (pot + owed)))
        return max(mn, min(mx, target))

    def choose_action(self, msg):
        legal = msg["legal_actions"]
        owed = msg["to_call"]
        pot = msg["pot"]
        board = parse_cards(msg["board"])
        street = msg["street"]
        b = len(board)
        self.tm.update(msg.get("time_left_ms", self.tm.last_left))
        hands_left = max(1, self.total - self.hand_id + 1)
        budget = self.tm.budget_ms(hands_left)

        # pot-conditional compute: EV concentrates in big pots
        pot_mult = 1.0 + min(1.5, pot / 120.0)
        big_pot = pot >= 40

        # ---- compute equity ----
        if street == "preflop":
            q0 = preflop_equity(self.hole3)  # instant table lookup
            if q0 is None:
                S = int((1500 if budget > 40 else (400 if budget > 8 else 0)) * min(1.5, budget / 40.0) * self.speed_scale)
                q0 = self._equity_preflop(S) if S else 0.5
            if owed > 0 and self.hand_actions and _PREFLOP_BLOB:
                # condition on opponent's preflop action via their table values
                def opp_w(tvals, acts=tuple(a for _, a, _ in self.hand_actions)):
                    w = np.ones(len(tvals))
                    for a in acts:
                        if a == "raise":
                            w *= 0.1 + tvals ** 6 * 2.0
                        elif a == "call":
                            w *= 0.5 + 1.2 * (1.0 - np.abs(tvals - 0.55) * 2.0)
                        elif a == "check":
                            w *= 0.3 + 1.4 * (1.0 - tvals)
                    return w
                S = int((2500 if budget > 25 else (800 if budget > 8 else 0)) * self.speed_scale)
                q = self._equity_preflop(S, opp_weight=opp_w) if S else q0
            else:
                q = q0
            self.pre_equity = q
            exact_win = False
        else:
            if b == 5:
                q, pscore = self._equity_postflop(board, 0, weights=self._opp_action_weights, exact_river=True)
                # exact river: do we beat every physical opponent holding?
                exact_win = q >= 0.999
            elif b == 4:
                if budget > 60:
                    q, pscore = self._turn_exact(board)
                    exact_win = self._turn_q_unw >= 0.999
                else:
                    q, pscore = self._equity_postflop(board, int((8000 if budget > 12 else 1000) * self.speed_scale),
                                                       weights=self._opp_action_weights)
                    exact_win = False
            else:  # flop
                if budget > 60 and pot >= 30:
                    R = int(min(44, max(20, budget / 3.0)) * self.speed_scale)
                    q = self._flop_semiexact(board, R)
                    pscore = None
                else:
                    S = int((6000 if budget > 30 else (2500 if budget > 12 else 600)) * self.speed_scale)
                    q, pscore = self._equity_postflop(board, S, weights=self._opp_action_weights)
                exact_win = False

        price = owed / (pot + owed) if owed else 0.0
        can_raise = "raise" in legal
        raises_left = msg.get("raises_left", 0)
        mx = msg.get("max_raise", 0)

        # ---- exploitative opponent model ----
        fold_freq = self.opp_stats["fold_freq"]  # P(opp folds | facing a bet), from observed history
        if self.opp_stats["hands"] < 10:
            fold_freq = 0.5
        blocker = self._blocker_bonus(board)

        # ---- endgame match-point shield ----
        # If safely ahead late in the leg (> +150 chips, final 25% of hands), avoid high-variance coin flips
        hands_left = max(1, self.total - self.hand_id + 1)
        shield_mode = (self.leg_net >= 150) and (hands_left <= 0.25 * self.total)

        # ---- guaranteed-win shove ----
        if exact_win and can_raise and mx >= msg.get("min_raise", 0):
            return {"type": "action", "action": "raise", "amount": mx}

        # adaptive value-raise threshold: lower vs calling stations, higher vs nits
        caller = 1.0 - fold_freq
        adapt = 0.06 if self.opp_stats["hands"] >= 25 else 0.02
        vthr = 0.78 - adapt * caller
        # Archetype adjustments
        if self.opp_archetype == "station":
            vthr -= 0.05
        elif self.opp_archetype == "nit":
            vthr += 0.04
        if shield_mode:
            vthr += 0.05  # tighten value-raises when locking in match point

        # position adjustment: tighter when out of position preflop
        pos_adj = 0.04 if (self.seat == "big_blind" and street == "preflop") else 0.0

        # ---- preflop 4-bet: shove/raise big with top holdings vs a 3-bet ----
        if street == "preflop" and owed > 0 and can_raise and raises_left > 0:
            n_raises = sum(1 for _, a, _ in self.hand_actions if a == "raise")
            if n_raises >= 2 and q > 0.70:
                return {"type": "action", "action": "raise", "amount": self._size_to(msg, 1.5)}

        # ---- facing a bet ----
        if owed > 0:
            big_bet = owed >= 0.5 * pot
            # Shover Killer: snap-call with any reasonable positive expectation (> 48%)
            if self.opp_archetype == "shover":
                if q >= 0.48:
                    return {"type": "action", "action": "call"}
                return {"type": "action", "action": "fold"}

            # preflop cheap completion: Button completes or raises wide; Big Blind defends wide
            if street == "preflop" and owed <= 2 and can_raise and raises_left > 0:
                is_button = (self.seat == "button")
                if is_button:
                    # Button facing BB option check or min-raise: raise wide with q > 0.45
                    if q > 0.45:
                        return {"type": "action", "action": "raise", "amount": self._size_to(msg, 0.5)}
                    elif q >= 0.35:
                        return {"type": "action", "action": "call"}
                else:
                    # Big Blind facing Button opening raise of 2 to 4 (owed = 2): defend wide!
                    if q > 0.62:
                        return {"type": "action", "action": "raise", "amount": self._size_to(msg, 0.9)} # 3-bet
                    elif q >= 0.38:
                        return {"type": "action", "action": "call"} # defend BB flat

            # Value raise using real Fold-Equity expectation
            if can_raise and raises_left > 0 and q > vthr:
                frac = (1.1 if q > 0.9 else (0.75 if q > 0.85 else 0.5)) * (0.8 + 0.4 * caller)
                amt = self._size_to(msg, min(frac, 1.5))
                return {"type": "action", "action": "raise", "amount": amt}

            # Bluff raise: disabled vs calling stations or in shield mode
            can_bluff = (self.opp_archetype != "station") and (not shield_mode)
            if can_bluff and can_raise and q < 0.28 and raises_left > 1 and pot <= 60 and street != "river":
                best_frac, best_ff = 0.55, -1.0
                for fr in (0.4, 0.55, 0.8):
                    amt = self._size_to(msg, fr)
                    ff = self._fold_freq_for(amt)
                    if ff > best_ff:
                        best_ff, best_frac = ff, fr
                amt = self._size_to(msg, best_frac)
                indiff = amt / (pot + amt)
                bluff_p = 0.08 + 0.30 * max(0.0, best_ff - indiff) + blocker
                if self.rng.random() < min(0.35, bluff_p):
                    return {"type": "action", "action": "raise", "amount": amt}

            # River GTO Minimum Defense Frequency (MDF) Bluff-Catcher Guard
            if street == "river":
                call_margin = 0.04 if shield_mode else 0.01
                if q >= (price + call_margin):
                    return {"type": "action", "action": "call"}
                return {"type": "action", "action": "fold"}

            need = price + (0.10 if big_bet else 0.02) + pos_adj + (0.04 if shield_mode else 0.0)
            if q >= need and not (big_bet and q < 0.52):
                return {"type": "action", "action": "call"}
            return {"type": "action", "action": "fold"}

        # ---- no bet facing us ----
        if can_raise and raises_left > 0:
            is_button = self.seat == "button"
            # Optimal HU Preflop Opening Frequency:
            # Button opens ~85% of hands (min-raise to 4) because position gives massive EV advantage
            if street == "preflop" and is_button:
                open_thr = 0.44 if self.opp_archetype != "shover" else 0.50
                if q >= open_thr:
                    return {"type": "action", "action": "raise", "amount": max(msg["min_raise"], 4)}
                return {"type": "action", "action": "check"}

            # Flop Continuation-Bet (C-Bet) Texture Analysis:
            if street == "flop" and len(board) == 3:
                ranks = sorted([c // 4 for c in board])
                suits = [c % 4 for c in board]
                is_dry = (len(set(suits)) == 3 and (ranks[2] - ranks[0] >= 5)) or (len(set(ranks)) < 3)
                # Dry board: high-frequency small c-bet (30% pot)
                if is_dry and (q > 0.48 or self.rng.random() < 0.35) and not shield_mode:
                    amt = self._size_to(msg, 0.33)
                    return {"type": "action", "action": "raise", "amount": amt}
                # Wet board: value/draw c-bet (60% pot)
                if q > 0.65:
                    amt = self._size_to(msg, 0.60)
                    return {"type": "action", "action": "raise", "amount": amt}

            open_thr = 0.56 if (is_button and street == "preflop") else 0.61
            if self.opp_archetype == "nit":
                open_thr -= 0.05  # exploit nits with aggressive steals
            if q > open_thr:
                # Value sizing: against fish/stations and nits, extract maximum chips
                # If monster (q > 0.88), bet big to accelerate toward +400/+1000 cap!
                if q > 0.88 and not shield_mode:
                    base_frac = 1.3
                elif q > 0.80:
                    base_frac = 1.0
                elif q > 0.70:
                    base_frac = 0.75
                else:
                    base_frac = 0.55
                frac = min(1.5, base_frac * (0.8 + 0.5 * caller))
                if self.opp_archetype == "station":
                    frac = min(1.6, frac * 1.3)  # aggressive value extraction vs stations
                return {"type": "action", "action": "raise", "amount": self._size_to(msg, frac)}
            can_bluff = (self.opp_archetype != "station") and (not shield_mode)
            if can_bluff and q < 0.30 and street != "river":
                best_frac, best_ff = 0.55, -1.0
                for fr in (0.4, 0.55, 0.8):
                    amt = self._size_to(msg, fr)
                    ff = self._fold_freq_for(amt)
                    if ff > best_ff:
                        best_ff, best_frac = ff, fr
                amt = self._size_to(msg, best_frac)
                indiff = amt / (pot + amt)
                bluff_p = 0.08 + 0.25 * max(0.0, best_ff - indiff) + blocker
                if self.rng.random() < min(0.35, bluff_p):
                    return {"type": "action", "action": "raise", "amount": amt}
        return {"type": "action", "action": "check"}

    def _turn_exact(self, board):
        """Exact turn equity: all opponent pairs x all legal rivers (~40k evals)."""
        blocked = set(self.hole2) | set(board) | set(self.dead)
        unseen = np.array([c for c in range(52) if c not in blocked], dtype=np.int16)
        U = len(unseen)
        peers = np.array(list(combinations(unseen.tolist(), 2)), dtype=np.int16)
        P = len(peers)
        b_np = np.array(board, dtype=np.int16)
        # Pre-evaluate hero score for all U rivers (only U=44 evals instead of 40,000!)
        hero_full = np.column_stack((np.tile(self.hole2, (U, 1)), np.tile(b_np, (U, 1)), unseen))
        hero_river_scores = eval_batch(hero_full)

        peer_a = np.repeat(peers[:, 0], U)
        peer_b = np.repeat(peers[:, 1], U)
        river_all = np.tile(unseen, P)
        keep = (river_all != peer_a) & (river_all != peer_b)
        peer_rep = np.repeat(peers, U, axis=0)[keep]
        river_rep = river_all[keep]
        N = len(river_rep)
        boards = np.column_stack((np.tile(b_np, (N, 1)), river_rep))
        pscore = eval_batch(np.column_stack((peer_rep, boards)))
        r_idx = np.tile(np.arange(U), P)[keep]
        oscore = hero_river_scores[r_idx]
        credit = (oscore > pscore) + 0.5 * (oscore == pscore)
        q_unw = float(credit.mean())
        self._turn_q_unw = q_unw
        try:
            w = self._opp_action_weights(pscore)
            disc_w = self._opp_discard_consistency(peer_rep)
            if disc_w is not None:
                w = (w if w is not None else 1.0) * disc_w
        except Exception:
            w = None
        if w is not None and float(w.sum()) > 1e-9:
            return float((w * credit).sum() / w.sum()), pscore
        return q_unw, pscore

    def choose_discard(self, msg):
        self.tm.update(msg.get("time_left_ms", self.tm.last_left))
        hands_left = max(1, self.total - self.hand_id + 1)
        budget = self.tm.budget_ms(hands_left)
        if self.tm.last_left < 0.18 * self.tm.bank:
            budget = 2.0
        board = parse_cards(msg["board"], 3)
        self.flop_cards = board
        hole = parse_cards(msg["hole_cards"], 3)
        self.hole3 = hole
        if budget < 10:
            return {"type": "discard", "card": default_discard(msg["hole_cards"])}
        pot_mult = 1.0 + min(3.0, int(msg.get("pot", 0)) / 90.0)
        S = int((2500 if budget > 35 else 600) * pot_mult * self.speed_scale)
        d = self._discard_equity(board, S)
        return {"type": "discard", "card": tcard(d)}

    # ---------------- safe fallback ----------------
    def safe_action(self, msg):
        legal = msg.get("legal_actions") or []
        if "check" in legal:
            return {"type": "action", "action": "check"}
        if "fold" in legal:
            return {"type": "action", "action": "fold"}
        if "call" in legal:
            return {"type": "action", "action": "call"}
        return {"type": "action", "action": "fold"}

    # ---------------- main handler ----------------
    def handle(self, msg):
        t = msg.get("type")
        if t == "init":
            self.total = int(msg.get("total_hands", 200))
            self.bank_ms = int(msg.get("time_bank_ms", 30000))
            self.per_reply_ms = int(msg.get("per_response_ms", 5000))
            self.tm = TimeManager(self.bank_ms)
            _build_eval_tables()  # free start-up window precomputation
            # speed calibration: scale all sample counts if this CPU is slower/faster
            try:
                import time as _t
                probe = np.random.default_rng(1).integers(0, 52, size=(20000, 7))
                t0 = _t.perf_counter()
                eval_batch(probe)
                dt = max(1e-6, _t.perf_counter() - t0)
                ev_per_ms = 20000 / (dt * 1000.0)
                self.speed_scale = max(0.4, min(2.0, ev_per_ms / 285.0))  # 285 ev/ms ≈ reference
            except Exception:
                self.speed_scale = 1.0
            return None
        if t == "match_end":
            self.finished = True
            return None
        if t == "new_hand":
            self.hand_id = int(msg.get("hand_id", 0))
            self.seat = msg.get("seat", "button")
            self.hole3 = parse_cards(msg.get("hole_cards", []), 3)
            self.hole2 = ()
            self.dead = ()
            self.board = ()
            self.pre_equity = None
            self.flop_cards = ()
            self.opp_d_card = None
            self._opp_discard_weights = None
            self.hand_actions = []
            return None
        if t == "discard_request":
            return self.choose_discard(msg)
        if t == "discard_result":
            self.hole2 = parse_cards(msg.get("hole_cards", []), 2)
            self.dead = (card(msg.get("my_discard")), card(msg.get("opp_discard")))
            self.opp_d_card = card(msg.get("opp_discard"))
            return None
        if t == "action_request":
            # rebuild opponent action list fresh from this request's history
            # (history grows monotonically within a hand; never accumulate dups)
            acts = []
            for ev in msg.get("history", []):
                if isinstance(ev, dict) and ev.get("actor") == "opp":
                    a = ev.get("action")
                    if a in ("raise", "call", "check", "fold"):
                        amt = ev.get("amount", 0) if isinstance(ev.get("amount", 0), int) else 0
                        acts.append((ev.get("street", ""), a, amt))
            self.hand_actions = acts
            try:
                return self.choose_action(msg)
            except Exception:
                return self.safe_action(msg)
        if t == "hand_result":
            try:
                self.leg_net += int(msg.get("net", 0))
                self._update_stats(msg.get("history", []), msg.get("result"),
                                   msg.get("opp_hole_cards"), msg.get("opp_discard"))
            except Exception:
                pass
            self.hole2 = ()
            self.dead = ()
            self.board = ()
            return None
        return None


def main():
    bot = Bot()
    bot.finished = False
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        if not isinstance(msg, dict):
            continue
        try:
            reply = bot.handle(msg)
        except Exception:
            t = msg.get("type")
            if t == "action_request":
                reply = bot.safe_action(msg)
            elif t == "discard_request":
                hc = msg.get("hole_cards") or []
                reply = {"type": "discard", "card": default_discard(hc) if hc else "2s"}
            else:
                reply = None
        if reply is not None:
            try:
                print(json.dumps(reply, separators=(",", ":")), flush=True)
            except Exception:
                pass
        if bot.finished:
            break


if __name__ == "__main__":
    main()