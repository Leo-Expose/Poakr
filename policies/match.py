"""
Duplicate-deal match runner.

Matches the tournament format:
  - every deal is played TWICE with seats swapped (duplicate deals)
  - a match is scored on TOTAL chips -> Win / Draw / Loss  (match points 1 / 0.5 / 0)
  - tie-break uses capped chips per hand

This is the harness that proves the decision framework.  It lets us measure
P(win the match) for different policies under the REAL objective, which is the
only thing that matters for the leaderboard.
"""
from __future__ import annotations
import random
import math
from dataclasses import dataclass, field

from engine.game import Game, GameConfig


@dataclass
class MatchResult:
    p0_chips: float
    p1_chips: float
    hands: int
    deals: int
    p0_decisions_compute: int = 0
    winner: int = -1                  # 0, 1, or -1 draw
    match_points_p0: float = 0.0

    def capped_chips_per_hand(self, cap=50.0):
        # tie-break formula: capped chips per hand
        per = (self.p0_chips) / max(1, self.hands)
        return max(-cap, min(cap, per))


def play_deal(game: Game, dealt, policyA, policyB):
    """
    One deal played twice with swapped seats.
    Returns the NET chip advantage for the 'A side' summed across both copies.
      copy 1: A in seat 0 (SB), B in seat 1 (BB)
      copy 2: A in seat 1 (BB), B in seat 0 (SB)
    """
    d1, _ = game.play_hand(dealt, policyA, policyB)     # delta for seat0 = A
    d2, _ = game.play_hand(dealt, policyB, policyA)     # delta for seat0 = B -> A is seat1
    # in copy2, A is seat1, so A's chips = -delta_for_seat0
    a_net = d1 + (-d2)
    return a_net, d1, d2


def run_match(policyA, policyB, n_deals=200, seed=0, cfg=None, track_compute=None, adaptive=False):
    """
    A full match of `n_deal` duplicate deals (= 2*n_deals hands).
    Returns MatchResult with match points for policyA.

    If `adaptive` is True, any policy that exposes `.lead` and `.remaining` is fed
    the live match state between deals, so the risk dial can protect a lead or
    chase a deficit as the match unfolds (this is the whole point of match-point
    optimisation).  This does not peek at the opponent's cards — it only uses the
    running chip score, which any real bot can track.
    """
    cfg = cfg or GameConfig()
    game = Game(cfg, seed=seed)
    rng = random.Random(seed)
    deck = list(range(cfg.n_ranks * cfg.n_suits))

    a_chips = 0.0
    b_chips = 0.0
    hands = 0
    for i in range(n_deals):
        if adaptive:
            frac_done = i / max(1, n_deals)
            for pol in (policyA, policyB):
                if hasattr(pol, 'lead') and hasattr(pol, 'remaining'):
                    # each policy sees its OWN lead
                    if pol is policyA:
                        pol.lead = a_chips - b_chips
                    else:
                        pol.lead = b_chips - a_chips
                    pol.remaining = 1.0 - frac_done
        rng.shuffle(deck)
        need = 2 * cfg.n_hole + cfg.n_board
        dealt = deck[:need]
        net, d1, d2 = play_deal(game, dealt, policyA, policyB)
        a_chips += net
        b_chips -= net
        hands += 2

    if a_chips > b_chips:
        winner, mp = 0, 1.0
    elif a_chips < b_chips:
        winner, mp = 1, 0.0
    else:
        winner, mp = -1, 0.5

    res = MatchResult(
        p0_chips=a_chips, p1_chips=b_chips, hands=hands, deals=n_deals,
        winner=winner, match_points_p0=mp,
    )
    if track_compute is not None:
        res.p0_decisions_compute = getattr(policyA, 'compute_used', 0)
    return res


def round_robin(policies, n_deals=100, seed=0, cfg=None):
    """
    Play every policy against every other, return a scoreboard of match points.
    Mirrors the Swiss / round-robin scoring.
    """
    n = len(policies)
    pts = [0.0] * n
    games = 0
    for i in range(n):
        for j in range(i + 1, n):
            r = run_match(policies[i], policies[j], n_deals=n_deals, seed=seed + games, cfg=cfg)
            pts[i] += r.match_points_p0
            pts[j] += 1.0 - r.match_points_p0
            games += 1
    return pts, games


def duplicate_variance_report(policyA, policyB, n_deals=200, seed=0, cfg=None):
    """
    Quantify the core structural insight: duplicate deals collapse variance.
    Compare the std-dev of the per-DEAL net under (a) duplicate play and (b) plain
    independent hands.  A smaller std means skill edges compound more reliably.
    """
    import statistics
    cfg = cfg or GameConfig()
    game = Game(cfg, seed=seed)
    rng = random.Random(seed)
    deck = list(range(cfg.n_ranks * cfg.n_suits))
    dup_nets = []
    single_nets = []
    for i in range(n_deals):
        rng.shuffle(deck)
        need = 2 * cfg.n_hole + cfg.n_board
        dealt = deck[:need]
        net, d1, d2 = play_deal(game, dealt, policyA, policyB)
        dup_nets.append(net)
        single_nets.append(d1)     # single (non-duplicate) copy only
    return {
        'dup_mean': statistics.fmean(dup_nets),
        'dup_stdev': statistics.pstdev(dup_nets),
        'single_mean': statistics.fmean(single_nets),
        'single_stdev': statistics.pstdev(single_nets),
    }
