#!/usr/bin/env python3
"""
CAPSTONE: full-stack match-point proof.

Drives the ACTUAL shipped engine (runtime/bot.py `decide()` + its DuplicateTracker,
OpponentModel, MatchState) through full duplicate matches against realistic bot
opponents, scored the way the tournament scores them: MATCH POINTS (Win/Draw/Loss
on total chips).

This is the end-to-end answer to "does the whole system win matches?" — not a
unit test of one component.
"""
import sys, os, random, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'legacy'))
import bot_v1 as bot
from engine.game import Game, GameConfig
from engine.equity import equity_vs_range, pot_odds

NB = GameConfig().n_board


class FullBot:
    """Wraps the shipped bot.decide() and its state (DUP/OPP/MATCH/BANK)."""

    def __init__(self, use_duplicate=True, risk_dial=True):
        self.use_duplicate = use_duplicate
        self.risk_dial = risk_dial
        self.rng = random.Random(734)
        self.np_rng = bot.np.random.default_rng(735)
        self.hand_id = 0
        self.decisions = 0
        self.info = 0

    def reset(self):
        bot.DUP = bot.DuplicateTracker()
        bot.OPP = bot.OpponentModel()
        bot.MATCH = bot.MatchState()
        bot.BANK = bot.TimeBank()

    def set_match_state(self, lead, remaining):
        if self.risk_dial:
            bot.MATCH.update(lead, remaining)

    def decide(self, obs):
        obs = dict(obs)
        obs['hand_id'] = self.hand_id
        obs['street'] += 1  # engine -1/0/1/2 -> shipped 0/1/2/3
        obs['max_raises'] = obs['cfg'].max_raises
        bot.DUP.observe_request(obs)
        before = bot.DUP.info_decisions
        saved = bot.DUP
        if not self.use_duplicate:
            bot.DUP = bot.DuplicateTracker()
        try:
            act = bot.decide(obs, self.rng, self.np_rng)
        finally:
            bot.DUP = saved
        assert act in obs['legal'], ('illegal shipped action', act, obs['legal'])
        self.info += saved.info_decisions - before
        self.decisions += 1
        return act

    def learn_public(self, history, seat):
        # End-of-hand action history is public. NO hidden cards/runout are fed.
        for i in range(1, len(history)):
            street, p, act = history[i]
            prev_street, prev_p, prev_act = history[i-1]
            if p != seat and prev_p == seat and street == prev_street:
                if prev_act[0] == 'bet':
                    bot.OPP.observe_facing_bet(street+1, act[0])
                elif prev_act[0] == 'check':
                    bot.OPP.observe_checked_to(street+1, act[0])


# ---------------- realistic opponents ----------------
class OverFolder:
    name = "OverFolder"
    def __init__(self, seed=0): self._r = random.Random(seed)
    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1: return legal[0]
        po = pot_odds(obs['to_call'], obs['pot'])
        eq = equity_vs_range(obs['hole'], obs['board'], n_draws=120, seed=self._r.randrange(1 << 30))
        can_bet = any(a[0] == 'bet' for a in legal)
        if obs['to_call'] <= 0:
            return ('bet', 1.0) if can_bet and eq > 0.78 else (('check',) if ('check',) in legal else legal[0])
        if eq > po + 0.22: return ('call',)
        return ('fold',) if ('fold',) in legal else ('call',)

class CallingStation:
    name = "CallingStation"
    def __init__(self, seed=0): self._r = random.Random(seed)
    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1: return legal[0]
        po = pot_odds(obs['to_call'], obs['pot'])
        eq = equity_vs_range(obs['hole'], obs['board'], n_draws=120, seed=self._r.randrange(1 << 30))
        can_bet = any(a[0] == 'bet' for a in legal)
        if obs['to_call'] <= 0:
            return ('bet', 1.0) if can_bet and eq > 0.72 else (('check',) if ('check',) in legal else legal[0])
        return ('call',) if eq > po - 0.10 else (('fold',) if ('fold',) in legal else ('call',))

class Balanced:
    name = "Balanced"
    def __init__(self, seed=0): self._r = random.Random(seed)
    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1: return legal[0]
        po = pot_odds(obs['to_call'], obs['pot'])
        eq = equity_vs_range(obs['hole'], obs['board'], n_draws=150, seed=self._r.randrange(1 << 30))
        can_bet = any(a[0] == 'bet' for a in legal)
        if obs['to_call'] <= 0:
            return ('bet', 1.0) if can_bet and eq > 0.70 else (('check',) if ('check',) in legal else legal[0])
        return ('call',) if eq > po + 0.05 else (('fold',) if ('fold',) in legal else ('call',))


class Aggressor:
    name = 'Aggressor'
    def __init__(self, seed=0): self._r = random.Random(seed)
    def decide(self, obs):
        legal = obs['legal']
        if len(legal) == 1: return legal[0]
        po = pot_odds(obs['to_call'], obs['pot'])
        eq = equity_vs_range(obs['hole'], obs['board'], n_draws=150, seed=self._r.randrange(1 << 30))
        bets = [a for a in legal if a[0]=='bet']
        if obs['to_call'] <= 0:
            if bets and (eq>0.58 or self._r.random()<0.28):
                return min(bets, key=lambda a:abs(a[1]-1.0))
            return ('check',) if ('check',) in legal else legal[0]
        if bets and eq>0.80:
            return min(bets, key=lambda a:abs(a[1]-1.0))
        return ('call',) if eq>po+0.02 else (('fold',) if ('fold',) in legal else legal[0])


def play_match(A, B, n_deals, seed):
    """Full duplicate match. Returns A's chip net.  Updates A's match state live."""
    rng = random.Random(seed); deck = list(range(52))
    a_net = 0.0
    for i in range(n_deals):
        if hasattr(A, 'set_match_state'):
            A.set_match_state(a_net, 1.0 - i / max(1, n_deals))
        rng.shuffle(deck); dealt = deck[:9]
        # copy 1: A seat0 (holds dealt[:2])
        A.hand_id = 2*i
        d1, hist1 = Game(GameConfig(), seed=seed + i).play_hand(dealt, A, B)
        A.learn_public(hist1, 0)
        A.set_match_state(a_net+d1, 1.0-(i+0.5)/max(1,n_deals))
        A.hand_id = 2*i+1
        # copy 2: A seat1 (holds dealt[2:4]); seats swapped
        d2, hist2 = Game(GameConfig(), seed=seed + i + 10_000).play_hand(dealt, B, A)
        A.learn_public(hist2, 1)
        a_net += d1 + (-d2)
    return a_net


def main():
    print("=" * 72)
    print("CAPSTONE: full-stack bot vs realistic opponents, MATCH-POINT scoring")
    print("=" * 72)
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--matches', type=int, default=8)
    parser.add_argument('--deals', type=int, default=60)
    parser.add_argument('--seed-base', type=int, default=3000)
    parser.add_argument('--output', default='fullmatch_results.json')
    parser.add_argument('--risk-ablation', action='store_true')
    parser.add_argument('--aggressor', action='store_true')
    args = parser.parse_args()
    n_matches, n_deals = args.matches, args.deals
    import json
    results = []
    opponents = [("OverFolder", OverFolder), ("CallingStation", CallingStation), ("Balanced", Balanced)]

    if args.aggressor:
        opponents.append(('Aggressor', Aggressor))
    # A/B: full stack (all layers) vs NO-duplicate (ablation), same opponents
    configurations = [("FULL STACK", True, True), ("ABLATION: no duplicate-exploit", False, True)]
    if args.risk_ablation:
        configurations.append(("ABLATION: neutral risk dial", True, False))
    for label, use_dup, risk in configurations:
        print(f"\n--- {label} ---")
        for oname, Ofac in opponents:
            mp = 0.0; w = d = l = 0; chips = 0.0; nets = []; infos = 0; decisions = 0; compute = 0.0
            t0 = time.time()
            for m in range(n_matches):
                A = FullBot(use_duplicate=use_dup, risk_dial=risk); A.reset()
                B = Ofac(seed=args.seed_base + 200 + m)
                net = play_match(A, B, n_deals, args.seed_base + m)
                chips += net; nets.append(net)
                infos += A.info; decisions += A.decisions; compute += bot.BANK.spent
                if net > 0: w += 1; mp += 1.0
                elif net == 0: d += 1; mp += 0.5
                else: l += 1
            print(f"  vs {oname:15s}: {w}W-{d}D-{l}L   avg MP={mp/n_matches:.3f}   avg chips={chips/n_matches:+.1f}   ({time.time()-t0:.0f}s)")
            results.append(dict(duplicate=use_dup, risk=risk, opponent=oname, nets=nets,
                                wins=w, draws=d, losses=l, info_decisions=infos,
                                decisions=decisions, compute_s=compute))
    if os.path.basename(args.output) != args.output or not args.output.endswith('.json'):
        raise ValueError('output must be a plain .json filename')
    folder = os.path.join(os.path.dirname(__file__), '..', 'evidence', 'legacy_bench', 'reruns')
    os.makedirs(folder,exist_ok=True)
    path = os.path.join(folder, args.output)
    with open(path, 'w') as f:
        json.dump(dict(matches=n_matches, deals=n_deals, results=results), f, indent=2)
    print('Saved', path, flush=True)



if __name__ == '__main__':
    main()
