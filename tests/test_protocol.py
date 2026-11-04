import copy
import importlib.util
import itertools
import json
import random
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluator import eval_batch
from src.proofs import (
    card,
    default_discard,
    future_blinds,
    match_cap_score,
    parse_cards,
    quads_turn,
    river_floor,
    river_geometry,
    text_card,
)
from src.protocol import DiscardBot, replay


def init(bot, hands=4):
    return bot.handle(
        dict(
            type="init",
            protocol_version="1.0",
            total_hands=hands,
            starting_stack=200,
            small_blind=1,
            big_blind=2,
            time_bank_ms=60000,
            per_response_ms=5000,
        )
    )


def new(bot, hand_id, seat, holes):
    return bot.handle(
        dict(type="new_hand", hand_id=hand_id, seat=seat, hole_cards=holes, stack=200, opp_stack=200)
    )


def request(bot, history, street="preflop", board=None):
    state = replay(history, bot.seat, street)
    to_call = max(0, state.bets[1] - state.bets[0])
    message = dict(
        type="action_request",
        hand_id=bot.hand_id,
        street=street,
        board=board or [],
        pot=state.pot,
        my_bet=state.bets[0],
        opp_bet=state.bets[1],
        to_call=to_call,
        my_stack=200 - state.paid[0],
        opp_stack=200 - state.paid[1],
        history=copy.deepcopy(history),
        legal_actions=["fold", "call"] if to_call else ["check"],
        raises_left=4 - state.raises,
        time_left_ms=60000,
    )
    if state.raises < 4 and max(state.paid) < 200:
        maximum = min(state.bets[0] + 200 - state.paid[0], state.bets[1] + 200 - state.paid[1])
        message["legal_actions"].append("raise")
        message.update(min_raise=min(maximum, state.bets[1] + max(2, state.delta)), max_raise=maximum)
    return message


def comeback(spend=False, hands=4):
    bot = DiscardBot(spend_to_cap=spend)
    init(bot, hands)
    new(bot, 1, "button", ["Ah", "Ac", "Kd"])
    past = [
        dict(street="preflop", actor="me", action="raise", amount=60),
        dict(street="preflop", actor="opp", action="raise", amount=200),
        dict(street="preflop", actor="me", action="fold"),
    ]
    bot.handle(
        dict(
            type="hand_result",
            hand_id=1,
            result="fold",
            net=-60,
            board=[],
            my_hole_cards=["Ah", "Ac", "Kd"],
            opp_hole_cards=None,
            opp_discard=None,
            history=past,
        )
    )
    new(bot, 2, "big_blind", ["9c", "9d", "4c"])
    history = [
        dict(street="preflop", actor="opp", action="raise", amount=50),
        dict(street="preflop", actor="me", action="call", amount=50),
        dict(street="flop", actor="me", action="check"),
        dict(street="flop", actor="opp", action="check"),
    ]
    discard = bot.handle(
        dict(
            type="discard_request",
            hand_id=2,
            hole_cards=["9c", "9d", "4c"],
            board=["9h", "9s", "2c"],
            pot=100,
            my_stack=150,
            opp_stack=150,
            time_left_ms=60000,
        )
    )
    assert discard == dict(type="discard", card="4c")
    bot.handle(dict(type="discard_result", hand_id=2, my_discard="4c", opp_discard="Ah", hole_cards=["9c", "9d"]))
    history.extend(
        [
            dict(street="turn", actor="me", action="check"),
            dict(street="turn", actor="opp", action="raise", amount=20),
        ]
    )
    return bot, history


def decode_score(score):
    lengths = (5, 4, 3, 3, 1, 5, 2, 2, 1)
    category = score >> 20
    count = lengths[category]
    return (category,) + tuple(((score >> (4 * (count - 1 - i))) & 15) + 2 for i in range(count))


def load_reference_engine():
    spec = importlib.util.spec_from_file_location("official_engine", ROOT / "tools/engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProofTests(unittest.TestCase):
    def test_card_mapping_and_default_tie_order(self):
        self.assertEqual([text_card(card(x)) for x in ["As", "Td", "2c"]], ["As", "Td", "2c"])
        self.assertEqual(default_discard(["2c", "2s", "2h"]), "2s")
        self.assertEqual(default_discard(["Ah", "2c", "2d"]), "2d")
        for value in ("10c", "as", "A♠", "ZZ", True):
            with self.assertRaises(ValueError):
                card(value)
        with self.assertRaises(ValueError):
            parse_cards(["As", "As"], (2,))

    def test_exact_alternating_blind_suffix(self):
        for seat in ("button", "big_blind"):
            for hands in range(1001):
                expected = sum(
                    (2, 1)[i % 2] if seat == "button" else (1, 2)[i % 2] for i in range(hands)
                )
                self.assertEqual(future_blinds(seat, hands), expected)
        with self.assertRaises(ValueError):
            future_blinds("button", True)

    def test_cap_is_per_match_not_per_hand(self):
        self.assertEqual(match_cap_score([(600, 400, 400)]), 1)
        self.assertEqual(match_cap_score([(600, 400, 400), (-550, 400, 400)]), 0)
        self.assertEqual(match_cap_score([(50, 2, 400)]), 25)

    def _all_worlds(self, hero, board, dead):
        deck = [c for c in range(52) if c not in hero + board + dead]
        worlds = np.array(
            [(a, b, river) for a, b in itertools.combinations(deck, 2) for river in deck if river not in (a, b)],
            dtype=np.int64,
        )
        self.assertEqual(len(worlds), 39732)
        boards = np.column_stack((np.tile(board, (len(worlds), 1)), worlds[:, 2]))
        own = np.column_stack((np.tile(hero, (len(worlds), 1)), boards))
        peer = np.column_stack((worlds[:, :2], boards))
        self.assertTrue(np.all(eval_batch(own) > eval_batch(peer)))

    def test_dead_card_blocks_nonrainbow_straight_flush_all_39732_worlds(self):
        hero = tuple(map(card, ["9c", "9d"]))
        board = tuple(map(card, ["9h", "9s", "2c", "3c"]))
        dead = tuple(map(card, ["4c", "Ah"]))
        self.assertTrue(quads_turn(hero, board, dead))
        self._all_worlds(hero, board, dead)
        self.assertFalse(quads_turn(hero, board, tuple(map(card, ["Ad", "Ah"]))))

    def test_dead_ace_blocks_higher_quads_all_39732_worlds(self):
        hero = tuple(map(card, ["9c", "9d"]))
        board = tuple(map(card, ["9h", "9s", "Ac", "3d"]))
        dead = tuple(map(card, ["4c", "Ah"]))
        self.assertTrue(quads_turn(hero, board, dead))
        self._all_worlds(hero, board, dead)
        self.assertFalse(quads_turn(hero, board, tuple(map(card, ["2c", "4c"]))))

    def test_river_uses_both_discards_all_physical_peers(self):
        hero = tuple(map(card, ["As", "Ks"]))
        board = tuple(map(card, ["Ts", "Js", "Qs", "2c", "3d"]))
        dead = tuple(map(card, ["4c", "Ah"]))
        self.assertEqual(river_floor(hero, board, dead, 70), (70, 903))
        relation, count, equity = river_geometry(hero, board, dead)
        self.assertEqual((relation, count, equity), (1, 903, 1.0))

    def test_three_hole_quads_cannot_survive_mandatory_discard(self):
        with self.assertRaises(ValueError):
            quads_turn((28, 29, 30), (31, 0, 5, 10), (12, 16))

    def test_margin_budget_induction_all_small_losses(self):
        for bank, future in itertools.product(range(1, 30), range(12)):
            budget = bank - future - 1
            for paid in range(max(0, budget) + 1):
                if budget < 0:
                    continue
                self.assertGreaterEqual(bank - paid - future, 1)


class EvaluatorTests(unittest.TestCase):
    def test_evaluator_matches_official_rank5(self):
        reference = load_reference_engine()
        rng = random.Random(92)
        for _ in range(1000):
            row = rng.sample(range(52), 7)
            score = int(eval_batch(np.array([row], dtype=np.int64))[0])
            expected = reference.best_hand(
                [text_card(c) for c in row[:2]], [text_card(c) for c in row[2:]]
            )
            self.assertEqual(decode_score(score), expected)


class ProtocolTests(unittest.TestCase):
    def test_unknown_types_and_fields_are_ignored(self):
        a = DiscardBot()
        b = DiscardBot()
        init(a)
        init(b)
        self.assertIsNone(a.handle(dict(type="future_message", arbitrary=["unknown"])))
        for bot in (a, b):
            new(bot, 1, "button", ["As", "Kd", "7c"])
        req = request(a, [])
        changed = copy.deepcopy(req)
        changed.update(future_flag=True, opponent_hole_cards=["2s", "2h", "2d"], unrevealed_board=["Ac"] * 5)
        self.assertEqual(a.handle(req), b.handle(changed))

    def test_call_and_raise_amounts_are_street_totals(self):
        history = [
            dict(street="preflop", actor="me", action="raise", amount=6),
            dict(street="preflop", actor="opp", action="call", amount=6),
            dict(street="flop", actor="opp", action="raise", amount=6),
            dict(street="flop", actor="me", action="call", amount=6),
        ]
        state = replay(history, "button", "turn")
        self.assertEqual(state.paid, [12, 12])
        self.assertEqual(state.bets, [0, 0])
        bad = copy.deepcopy(history)
        bad[1]["amount"] = 4
        with self.assertRaises(ValueError):
            replay(bad, "button", "turn")

    def test_big_blind_has_option_after_limp_and_raise_limit(self):
        state = replay([dict(street="preflop", actor="me", action="call", amount=2)], "button", "preflop")
        self.assertFalse(state.closed)
        self.assertEqual(state.actor, "opp")
        self.assertEqual(state.raises, 1)
        history = [
            dict(street="preflop", actor="me", action="raise", amount=4),
            dict(street="preflop", actor="opp", action="raise", amount=6),
            dict(street="preflop", actor="me", action="raise", amount=8),
        ]
        self.assertEqual(replay(history, "button", "preflop").raises, 4)
        history.append(dict(street="preflop", actor="opp", action="raise", amount=10))
        with self.assertRaises(ValueError):
            replay(history, "button", "preflop")

    def test_coupled_discard_commits_one_pair_not_max_per_runout(self):
        bot = DiscardBot(samples=4)
        bot.original = bot.own = (0, 4, 8)
        bot.dead = ()
        calls = []

        def fake(rows):
            calls.append(len(rows))
            if len(calls) == 1:
                return np.zeros(12, dtype=int)
            return np.array([1, -1, 1, -1, -1, 1, -1, 1, 0, 0, 0, 0])

        with patch("src.protocol.eval_batch", side_effect=fake):
            equity, keep = bot._equity((12, 16, 20))
        self.assertEqual(equity, 0.5)
        self.assertIn(keep, list(itertools.combinations(bot.own, 2)))

    def test_new_turn_certificate_settles_before_abandoning(self):
        bot, history = comeback()
        reply = bot.handle(request(bot, history, "turn", ["9h", "9s", "2c", "3c"]))
        self.assertEqual(reply, dict(type="action", action="call"))
        self.assertTrue(bot.pending)
        self.assertFalse(bot.locked)
        self.assertEqual(bot.certificate["lower"], 7)
        history.append(dict(street="turn", actor="me", action="call", amount=20))
        self.assertEqual(bot.handle(request(bot, history, "river", ["9h", "9s", "2c", "3c", "2h"]))["action"], "check")
        history.extend(
            [
                dict(street="river", actor="me", action="check"),
                dict(street="river", actor="opp", action="check"),
            ]
        )
        bot.handle(
            dict(
                type="hand_result",
                hand_id=2,
                result="showdown",
                net=70,
                board=["9h", "9s", "2c", "3c", "2h"],
                my_hole_cards=["9c", "9d"],
                opp_hole_cards=["Ac", "Kd"],
                opp_discard="Ah",
                history=history,
            )
        )
        self.assertEqual(bot.score, 10)
        self.assertTrue(bot.locked)
        self.assertFalse(bot.pending)

    def test_cap_target_preserves_initial_certified_floor(self):
        bot, history = comeback(True)
        bot.handle(request(bot, history, "turn", ["9h", "9s", "2c", "3c"]))
        self.assertEqual(bot.certificate["abandonment_lower"], 7)
        self.assertEqual(bot.certificate["lower"], 7)

    def test_cap_seeking_never_spends_through_reserved_match_win(self):
        bot, history = comeback(True, hands=6)
        bot.handle(request(bot, history, "turn", ["9h", "9s", "2c", "3c"]))
        history.append(dict(street="turn", actor="me", action="call", amount=20))
        bot.handle(request(bot, history, "river", ["9h", "9s", "2c", "3c", "2h"]))
        history.extend(
            [
                dict(street="river", actor="me", action="check"),
                dict(street="river", actor="opp", action="check"),
            ]
        )
        bot.handle(
            dict(
                type="hand_result",
                hand_id=2,
                result="showdown",
                net=70,
                board=["9h", "9s", "2c", "3c", "2h"],
                my_hole_cards=["9c", "9d"],
                opp_hole_cards=["Ac", "Kd"],
                opp_discard="Ah",
                history=history,
            )
        )
        self.assertEqual(bot.score, 10)
        self.assertEqual(bot.reserve, 4)
        new(bot, 3, "button", ["2c", "3d", "4h"])
        self.assertEqual(bot.handle(request(bot, []))["action"], "fold")
        bot.handle(
            dict(
                type="hand_result",
                hand_id=3,
                result="fold",
                net=-1,
                board=[],
                my_hole_cards=["2c", "3d", "4h"],
                opp_hole_cards=None,
                opp_discard=None,
                history=[dict(street="preflop", actor="me", action="fold")],
            )
        )
        new(bot, 4, "big_blind", ["2c", "3d", "4h"])
        bot.handle(
            dict(
                type="hand_result",
                hand_id=4,
                result="fold",
                net=1,
                board=[],
                my_hole_cards=["2c", "3d", "4h"],
                opp_hole_cards=None,
                opp_discard=None,
                history=[dict(street="preflop", actor="opp", action="fold")],
            )
        )
        new(bot, 5, "button", ["As", "Ad", "Ac"])
        with patch.object(bot, "_equity", return_value=(1.0, (card("As"), card("Ad")))):
            reply = bot.handle(request(bot, []))
        self.assertEqual(reply["action"], "raise")
        self.assertLessEqual(reply["amount"], 4)
        history = [
            dict(street="preflop", actor="me", action="raise", amount=reply["amount"]),
            dict(street="preflop", actor="opp", action="raise", amount=200),
        ]
        self.assertEqual(bot.handle(request(bot, history))["action"], "fold")
        history.append(dict(street="preflop", actor="me", action="fold"))
        bot.handle(
            dict(
                type="hand_result",
                hand_id=5,
                result="fold",
                net=-reply["amount"],
                board=[],
                my_hole_cards=["As", "Ad", "Ac"],
                opp_hole_cards=None,
                opp_discard=None,
                history=history,
            )
        )
        new(bot, 6, "big_blind", ["2c", "3d", "4h"])
        history = [dict(street="preflop", actor="opp", action="raise", amount=200)]
        self.assertEqual(bot.handle(request(bot, history))["action"], "fold")
        history.append(dict(street="preflop", actor="me", action="fold"))
        bot.handle(
            dict(
                type="hand_result",
                hand_id=6,
                result="fold",
                net=-2,
                board=[],
                my_hole_cards=["2c", "3d", "4h"],
                opp_hole_cards=None,
                opp_discard=None,
                history=history,
            )
        )
        self.assertGreaterEqual(bot.score, 4)
        self.assertTrue(bot.score_trusted)

    def test_low_bank_still_answers_discard_and_pending_call(self):
        bot, history = comeback()
        req = request(bot, history, "turn", ["9h", "9s", "2c", "3c"])
        req["time_left_ms"] = 1
        self.assertEqual(bot.handle(req)["action"], "call")
        other = DiscardBot()
        init(other)
        new(other, 1, "button", ["2c", "2s", "Ah"])
        reply = other.handle(
            dict(
                type="discard_request",
                hand_id=1,
                hole_cards=["2c", "2s", "Ah"],
                board=["3d", "4d", "5h"],
                pot=4,
                my_stack=198,
                opp_stack=198,
                time_left_ms=1,
            )
        )
        self.assertEqual(reply, dict(type="discard", card="2s"))

    def test_reconciliation_and_notice_withdraw_certificate(self):
        bot = DiscardBot()
        init(bot)
        new(bot, 1, "button", ["As", "Kd", "7c"])
        req = request(bot, [])
        bot.handle(req)
        with self.assertRaises(ValueError):
            bot.handle(req)
        bot.handle(dict(type="notice", code="illegal_action", applied="fold"))
        self.assertFalse(bot.score_trusted)
        self.assertIsNone(bot.expected_reply)

    def test_wrong_price_or_dead_card_collision_rejected(self):
        bot, history = comeback()
        req = request(bot, history, "turn", ["9h", "9s", "2c", "3c"])
        req["to_call"] = 1
        with self.assertRaises(ValueError):
            bot.handle(req)
        with self.assertRaises(ValueError):
            bot.handle(
                dict(
                    type="discard_result",
                    hand_id=2,
                    my_discard="4c",
                    opp_discard="9c",
                    hole_cards=["9c", "9d"],
                )
            )

    def test_single_file_actual_stdio(self):
        transcript = [
            dict(
                type="init",
                protocol_version="1.0",
                total_hands=400,
                starting_stack=200,
                small_blind=1,
                big_blind=2,
                time_bank_ms=60000,
                per_response_ms=5000,
            ),
            dict(type="new_hand", hand_id=1, seat="button", hole_cards=["As", "Kd", "7c"], stack=200, opp_stack=200),
            dict(type="future_kind"),
            dict(
                type="action_request",
                hand_id=1,
                street="preflop",
                board=[],
                pot=3,
                my_bet=1,
                opp_bet=2,
                to_call=1,
                my_stack=199,
                opp_stack=198,
                legal_actions=["fold", "call", "raise"],
                min_raise=4,
                max_raise=200,
                raises_left=3,
                history=[],
                time_left_ms=60000,
            ),
            dict(type="match_end", reason="complete"),
        ]
        process = subprocess.run(
            [sys.executable, "-B", str(ROOT / "bot.py")],
            input="\n".join(map(json.dumps, transcript)) + "\n",
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(process.stderr, "")
        self.assertEqual(len(process.stdout.splitlines()), 1)
        self.assertIn(json.loads(process.stdout)["action"], ("fold", "call", "raise"))


class MatchTests(unittest.TestCase):
    def test_official_engine_short_match(self):
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/engine.py"),
                str(ROOT / "bot.py"),
                str(ROOT / "tools/random_bot.py"),
                "--hands",
                "20",
                "--seed",
                "123",
                "--log-dir",
                "",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertNotIn("forfeit", process.stdout.lower())
        self.assertIn("notices 0", process.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
