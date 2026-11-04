"""
CONTROLLED policy with an explicit variance dial — for proving the core insight.

`risk` in [0,1] is the only knob:
   risk -> 0 : tight, small bets, few bluffs, fold marginal   (LOW variance)
   risk -> 1 : loose, big bets, many bluffs, call wide         (HIGH variance)

Everything else (equity engine, features) is identical across the sweep, so any
difference in match outcomes is caused purely by the variance/EV tradeoff.  This
lets us test the Sharpe-ratio objective against ground truth with a clean
single-parameter family.
"""
from __future__ import annotations
import random
from engine.equity import equity_vs_range, pot_odds


class RiskPolicy:
    name = "Risk"

    def __init__(self, risk=0.5, lead=0.0, remaining=1.0, adaptive=False, seed=0):
        self.risk = risk          # static variance dial in [0,1]
        self.lead = lead
        self.remaining = remaining
        self.adaptive = adaptive
        self.compute_used = 0
        self._rng = random.Random(seed)

    def eff_risk(self):
        """If adaptive, modulate the static risk by the match state (the dial)."""
        if not self.adaptive:
            return self.risk
        scale = 200.0
        rel = max(-1.0, min(1.0, self.lead / scale))
        urgency = 1.0 - self.remaining
        # ahead (rel>0) -> lower risk (protect); behind -> higher risk (chase)
        dial = -rel * (0.4 + 0.6 * urgency)
        r = self.risk + 0.45 * dial
        return max(0.02, min(0.98, r))

    def _draws(self, obs):
        pot = obs['pot']
        leverage = min(1.0, (pot + obs['to_call']) / max(1.0, obs['my_stack'] + obs['opp_stack']))
        street_w = 0.5 + 0.5 * (obs['street'] + 1) / 3.0
        d = int(max(30, min(1200, 150 * (0.4 + 1.6 * leverage) * street_w)))
        self.compute_used += d
        return d

    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1:
            return legal[0]
        r = self.eff_risk()
        eq = equity_vs_range(obs['hole'], obs['board'], n_draws=self._draws(obs),
                             seed=self._rng.randrange(1 << 30))
        po = pot_odds(obs['to_call'], obs['pot'])
        can_bet = any(a[0] == 'bet' for a in legal)
        can_check = ('check',) in legal
        max_raises = obs['cfg'].max_raises

        # thresholds slide linearly with the variance dial
        value_bar = 0.80 - 0.34 * r          # r=0 -> 0.80 (only nuts), r=1 -> 0.46 (thin)
        call_slack = 0.10 - 0.28 * r         # r=0 -> +0.10 (tight), r=1 -> -0.18 (sticky)
        bluff_p = 0.55 * r                   # r=0 -> none, r=1 -> often
        bet_size = 0.5 if r < 0.5 else 1.0   # small vs big bets
        raise_bar = 0.86 - 0.30 * r

        if obs['to_call'] <= 0:
            if can_bet:
                if eq > value_bar:
                    return ('bet', 1.0 if eq > value_bar + 0.2 else bet_size)
                # bluff only if aggressive and behind-ish (risk high)
                if self._rng.random() < bluff_p and obs['street'] >= 1:
                    return ('bet', bet_size)
            return ('check',) if can_check else legal[0]

        # facing a bet
        if eq > po + call_slack:
            if can_bet and eq > raise_bar and obs['n_raises'] < max_raises:
                return ('bet', 0.5)
            return ('call',)
        return ('fold',) if ('fold',) in legal else ('call',)
