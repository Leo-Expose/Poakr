"""
Invariant-based decision policies.

All policies read only game-theoretic invariants computed from the observation:
  equity      : P(win)+0.5P(tie) vs a random hand (or vs a modelled range)
  pot_odds    : required equity to call
  spr         : stack-to-pot ratio
  leverage    : chips at risk / pot
  street      : 0..n
  position    : button / big blind

They never look at raw card ids except through equity.  That is what makes them
transfer across the unknown custom variant.
"""
from __future__ import annotations
import math
from engine.equity import equity_vs_range, made_hand_strength, spr, pot_odds


class Policy:
    name = "base"
    def decide(self, obs):
        raise NotImplementedError


def _eq(obs, draws=250, seed=0):
    return equity_vs_range(obs['hole'], obs['board'], n_draws=draws, seed=seed)


def _po(obs):
    return pot_odds(obs['to_call'], obs['pot'])


def _sprv(obs):
    return spr(obs['pot'], obs['my_stack'], obs['to_call'])


# ------------------------------------------------------------------ baseline ---
class PotOddsPolicy(Policy):
    """Call if equity > pot odds (with small margin).  Bet for value when strong."""
    name = "PotOdds"
    def __init__(self, margin=0.02, value_thresh=0.62, bluff_freq=0.0):
        self.margin = margin
        self.vt = value_thresh
        self.bluff = bluff_freq

    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1:
            return legal[0]
        eq = _eq(obs, 220, obs.get('_h', 0))
        po = _po(obs)
        can_bet = any(a[0] == 'bet' for a in legal)
        can_check = ('check',) in legal
        # facing no bet
        if obs['to_call'] <= 0:
            if can_bet and eq > self.vt:
                # value bet: size scales with equity
                return ('bet', 1.0 if eq > 0.8 else 0.5)
            return ('check',) if can_check else legal[0]
        # facing a bet
        if eq > po + self.margin:
            # strong enough to call; raise if very strong and allowed
            if can_bet and eq > 0.85 and obs['n_raises'] < obs['cfg'].max_raises:
                return ('bet', 0.5)
            return ('call',)
        return ('fold',) if ('fold',) in legal else ('call',)


class TightAggressive(Policy):
    """Tighter value threshold, more aggression, occasional bluff."""
    name = "TAG"
    def __init__(self, lo=0.30, hi=0.70):
        self.lo, self.hi = lo, hi

    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1:
            return legal[0]
        eq = _eq(obs, 220, obs.get('_h', 0))
        po = _po(obs)
        can_bet = any(a[0] == 'bet' for a in legal)
        if obs['to_call'] <= 0:
            if can_bet:
                if eq > self.hi:
                    return ('bet', 1.0)
                if eq > self.lo and obs['street'] >= 1:
                    return ('bet', 0.5)
            return ('check',) if ('check',) in legal else legal[0]
        # facing bet
        rr = po + 0.03
        if eq > rr + 0.25 and obs['n_raises'] < obs['cfg'].max_raises and can_bet:
            return ('bet', 0.5)
        if eq > rr:
            return ('call',)
        return ('fold',) if ('fold',) in legal else ('call',)


# --------------------------------------------------------- the novel policy ---
class MatchPointPolicy(Policy):
    """
    THE KEY BREAKTHROUGH: optimise P(win the MATCH), not E[chips].

    The tournament scores a match as Win/Draw/Loss on total chips across all the
    duplicate deals.  That is a STEP utility in final chip difference, not a
    linear one.  The correct objective therefore depends on:
      - our current chip LEAD (signed),
      - how much of the match remains (leverage of the remaining deals),
      - the variance we should carry.

    When AHEAD late -> suppress variance (fold marginal spots, value bet only).
    When BEHIND    -> increase variance (bluff more, call wider, gamble).

    `aggression` is a signed risk dial derived from the match state:
        +1 = maximise variance (behind, need to catch up)
        -1 = minimise variance (ahead, protect the lead)
    and it modulates every threshold continuously.

    `time_budget` also implements the SECOND breakthrough: compute is invested by
    value-of-computation.  Trivial decisions (fold 72o preflop) get a hair of
    compute; high-leverage decisions (big pot, close equity) get full sampling.
    The `compute_scale` dial lets us bank time and spend it where it matters.
    """
    name = "MatchPoint"

    def __init__(self, lead=0.0, remaining=1.0, base_draws=180, adapt=True):
        self.lead = lead            # our chip lead (signed)
        self.remaining = remaining  # fraction of match remaining in [0,1]
        self.base_draws = base_draws
        self.adapt = adapt
        self.compute_used = 0       # accounting for the time-bank breakthrough

    # ---- risk dial: how much variance to carry (in [-1, +1]) ----
    def risk_dial(self):
        # normalise lead by a reference pot scale (~100 bb = 200 chips)
        scale = 200.0
        rel = max(-1.0, min(1.0, self.lead / scale))
        # when little match remains, the lead matters more (protect/attack)
        urgency = 1.0 - self.remaining
        # SIGN CONVENTION: dial > 0 means we are BEHIND and should INCREASE variance
        # (gamble, bluff, call wide); dial < 0 means AHEAD and should DECREASE it.
        # lead > 0 is ahead -> therefore NEGATIVE dial.  Flip the sign of rel.
        d = -rel * (0.35 + 0.65 * urgency)
        return max(-1.0, min(1.0, d))

    # ---- value of computation: how many Monte-Carlo draws this decision deserves ----
    def draws_for(self, obs, po):
        pot = obs['pot']
        to_call = obs['to_call']
        # leverage = fraction of stack this decision can swing
        leverage = min(1.0, (pot + to_call) / max(1.0, obs['my_stack'] + obs['opp_stack']))
        # closeness to the decision boundary -> high value of computation
        # cheap preflop folds get almost none
        street_w = 0.4 + 0.6 * (obs['street'] + 1) / 3.0
        # base + leverage premium
        d = self.base_draws * (0.25 + 1.75 * leverage) * street_w
        d = int(max(20, min(self.base_draws * 6, d)))
        self.compute_used += d
        return d

    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1:
            return legal[0]

        po = _po(obs)
        dial = self.risk_dial()
        draws = self.draws_for(obs, po)
        eq = _eq(obs, draws, abs(hash((obs['street'], tuple(obs['hole']), tuple(obs['board'])))) & 0xFFFF)

        can_bet = any(a[0] == 'bet' for a in legal)
        can_check = ('check',) in legal

        # thresholds slide with the risk dial:
        #   dial<0 (ahead)  -> play tighter: higher value bar, fold more marginal
        #   dial>0 (behind) -> play looser: lower value bar, call wider, bluff more
        value_bar = 0.66 - 0.14 * dial        # ahead: 0.80 ; behind: 0.52
        call_slack = -0.02 - 0.12 * dial       # ahead: require eq > po+0.10 ; behind: po-0.14
        bluff_p = max(0.0, 0.35 * dial)        # only bluff when behind

        # ---- acting, no bet to call ----
        if obs['to_call'] <= 0:
            if can_bet:
                # thin value / bluff mixture
                if eq > value_bar:
                    size = 1.0 if eq > value_bar + 0.18 else 0.5
                    return ('bet', size)
                # bluff when behind and the board is 'scary enough' (equity is low but
                # we can represent) — approximated by street+position
                if dial > 0.2 and obs['street'] >= 1:
                    import random as _r
                    if _r.random() < bluff_p:
                        return ('bet', 0.5)
            return ('check',) if can_check else legal[0]

        # ---- facing a bet ----
        if eq > po + call_slack:
            # continue; raise only if strongly ahead of the bar and not protecting
            if can_bet and eq > value_bar + 0.20 and obs['n_raises'] < obs['cfg'].max_raises:
                return ('bet', 0.5)
            return ('call',)
        # marginal fold/continue decided by the dial already folded into call_slack
        return ('fold',) if ('fold',) in legal else ('call',)


# --------------------------------------------------------------------------
class FixedComputeMatchPointPolicy(MatchPointPolicy):
    """Ablation: identical decisions but a FIXED compute per call (no VOC banking)."""
    name = "MatchPoint-FixedCompute"

    def draws_for(self, obs, po):
        d = self.base_draws
        self.compute_used += d
        return d
