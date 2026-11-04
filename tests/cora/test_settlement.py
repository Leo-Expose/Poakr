"""Reference-controller tests; synthetic rules, never organizer protocol evidence."""
import itertools
import unittest
from dataclasses import replace
from research.guarantee_lab.certificates import Contract
from research.guarantee_lab.river_credit import RiverContract
from research.guarantee_lab.turn_credit import TurnContract
from research.guarantee_lab.settlement import (
    TickLedger, SettlementController, Rules, Request, Mode, UnsafeState, StaleRequest,
)

RULES = Rules('standard-high-matched-ticks-v1', Contract(*([True]*5)),
              RiverContract(*([True]*7)), TurnContract(*([True]*7)))


def pay(ledger, player, amount):
    ledger.pay(ledger.revision+1, ledger.active.hand_id, player, amount)


def reveal(ledger, board):
    ledger.reveal(ledger.revision+1, ledger.active.hand_id, board)


def request(controller, legal=None):
    l = controller.ledger
    h = l.active
    owed = max(0, h.paid[1]-h.paid[0])
    return Request(h.hand_id, l.revision, controller.rules.version, h.hero, h.board, owed,
                   frozenset(legal or (('call','fold','raise') if owed else ('check','raise'))))


def seeded(raw=-60, cap=None, stack=200):
    ledger = TickLedger(stack, 4, cap)
    ledger.begin(1, 'past', (4,8))
    pay(ledger, 0, abs(raw))
    pay(ledger, 1, abs(raw) if raw > 0 else abs(raw)+1)
    if raw > 0:
        reveal(ledger, (12,16,20,24,32))
        ledger.settle(ledger.revision+1, 'past', 'hero_win', (2*raw,0))
    else:
        ledger.settle(ledger.revision+1, 'past', 'hero_fold', (0,2*abs(raw)+1))
    ledger.begin(ledger.revision+1, 'safe', (28,29))
    pay(ledger, 0, 50)
    pay(ledger, 1, 70)
    reveal(ledger, (30,31,0,5))
    return SettlementController(ledger, [60,2,3,5], RULES)


def finish_current(c, river_bet=0):
    l = c.ledger
    decision = c.choose(request(c))
    assert decision.action == 'call' and decision.amount == 20
    c.confirm(decision)
    reveal(l, (30,31,0,5,2))
    if river_bet:
        pay(l, 1, river_bet)
    decision = c.choose(request(c), deadline_recovery=True)
    c.confirm(decision)
    pot = sum(l.active.paid)
    c.settle(l.revision+1, 'safe', 'hero_win', (pot,0))


def lose_future(c, index, free_check_first=False, paid_override=None):
    l = c.ledger
    h_id = 'future-'+str(index)
    l.begin(l.revision+1, h_id, (4,8))
    cost = int(c.schedule.posts[index]) if paid_override is None else paid_override
    pay(l, 0, cost)
    pay(l, 1, cost)
    if free_check_first:
        d = c.choose(request(c))
        assert d.action == 'check'
        c.confirm(d)
    pay(l, 1, 1)
    d = c.choose(request(c))
    assert d.action == 'fold'
    c.confirm(d)
    c.settle(l.revision+1, h_id, 'hero_fold', (0,2*cost+1))


class LedgerTests(unittest.TestCase):
    def test_integer_money_and_limits(self):
        for value in (True, 1.0, '1', -1):
            with self.assertRaises(ValueError): TickLedger(value, 1)
        for count in (True, 0, -1):
            with self.assertRaises(ValueError): TickLedger(200, count)
        l = TickLedger(200, 1)
        l.begin(1, 'h', (0,1))
        for player, amount in ((True,1),(2,1),(0,201),(0,True),(0,-1)):
            with self.assertRaises(ValueError): l.pay(2,'h',player,amount)
            self.assertEqual(l.revision,1)
            self.assertEqual(l.active.paid,(0,0))

    def test_replays_collisions_and_board_extension(self):
        l = TickLedger(200,2)
        l.begin(1,'h',(0,1))
        with self.assertRaises(StaleRequest): l.pay(1,'h',0,1)
        with self.assertRaises(StaleRequest): l.pay(3,'h',0,1)
        with self.assertRaises(StaleRequest): l.pay(2,'other',0,1)
        for board in ((0,2,3),(2,2,3),(2,3), (True,3,4),([2],3,4)):
            with self.assertRaises(ValueError): l.reveal(2,'h',board)
        l.reveal(2,'h',(2,3,4))
        for board in ((2,3,4),(2,3,5,6),(2,3,4,0)):
            with self.assertRaises(ValueError): l.reveal(3,'h',board)
        l.settle(3,'h','tie',(0,0))
        with self.assertRaises(ValueError): l.begin(4,'h',(0,1))
        l.begin(4,'new',(0,1))
        self.assertEqual(l.active.index,1)

    def test_independent_payout_refund_and_clip_oracle(self):
        # All contributions 0..4, three showdown outcomes and both folds.
        # Independent oracle accounts for the matched contest and excess refunds.
        for a,b,outcome,cap in itertools.product(range(5),range(5),('hero_win','peer_win','tie','hero_fold','peer_fold'),(None,1,2)):
            l = TickLedger(4,1,cap)
            l.begin(1,'h',(0,1)); pay(l,0,a); pay(l,1,b)
            matched = min(a,b)
            if outcome == 'tie': gain = 0
            elif outcome in ('hero_win','peer_fold'): gain = matched
            else: gain = -matched
            payouts = (a+gain,b-gain)
            l.settle(l.revision+1,'h',outcome,payouts)
            self.assertEqual(l.raw,gain)
            self.assertEqual(l.clipped,gain if cap is None else max(-cap,min(cap,gain)))

    def test_bad_payout_and_scoreboard_are_atomic(self):
        l = TickLedger(200,1,2); l.begin(1,'h',(0,1)); pay(l,0,5); pay(l,1,5)
        seq = l.revision+1
        for payouts in ([],[10],[10,0,0],iter((10,0))):
            with self.assertRaises(ValueError): l.settle(seq,'h','hero_win',payouts)
        for kwargs,payouts in (({},(9,0)), ({'reported_raw':9},(10,0)),
                              ({'reported_clipped':5},(10,0)), ({'reported_raw':True},(10,0))):
            with self.assertRaises(ValueError): l.settle(seq,'h','hero_win',payouts,**kwargs)
            self.assertEqual(l.raw,0); self.assertIsNotNone(l.active)
            self.assertEqual(l.revision,seq-1)
        l.settle(seq,'h','hero_win',(10,0),reported_raw=5,reported_clipped=2)
        with self.assertRaises(StaleRequest): l.settle(seq,'h','hero_win',(10,0))


class SettlementTests(unittest.TestCase):
    def test_turn_comeback_no_fold_until_payout(self):
        c = seeded(); self.assertEqual(c.ledger.raw,-60)
        certificate = c.try_arm()
        self.assertEqual(certificate.lower_score,2)
        self.assertEqual(c.mode,Mode.SETTLE_SAFE_HAND)
        d = c.choose(request(c),deadline_recovery=True)
        self.assertEqual((d.action,d.amount),('call',20))
        self.assertEqual(c.mode,Mode.SETTLE_SAFE_HAND)
        finish_current(c,130)
        self.assertEqual(c.ledger.raw,140)
        self.assertEqual(c.mode,Mode.ABANDON)
        lose_future(c,2,True); lose_future(c,3)
        self.assertEqual(c.mode,Mode.DONE)
        self.assertEqual(c.ledger.raw,132)
        self.assertEqual(c.certificate.lower_score,132)

    def test_all_discrete_river_bets_against_independent_match_oracle(self):
        # Stack 74 / paid 70 leaves all legal integer river bets 0..4.
        # Hero never raises: check or one bet/call closes this remaining round.
        for bet in range(5):
            c = seeded(stack=74); c.try_arm(); finish_current(c,bet)
            lose_future(c,2); lose_future(c,3,True)
            self.assertEqual(c.ledger.raw, -60+(70+bet)-3-5)
            self.assertGreater(c.ledger.raw,0)
            self.assertEqual(c.mode,Mode.DONE)

    def test_stale_and_forged_tokens_never_authorize_actions(self):
        c = seeded(); c.try_arm(); r = request(c); d = c.choose(r)
        for changed in (replace(r,hand_id='other'),replace(r,revision=r.revision-1),
                        replace(r,rule_version='unknown'),replace(r,hero=(0,1)),replace(r,board=(30,31,0,4))):
            with self.assertRaises(StaleRequest): c.choose(changed)
        for changed in (replace(d,action='fold'),replace(d,amount=1),replace(d,mode=Mode.ABANDON)):
            with self.assertRaises(StaleRequest): c.confirm(changed)
        c.confirm(d)
        with self.assertRaises(StaleRequest): c.confirm(d)
        self.assertEqual(c.ledger.active.paid,(70,70))
        self.assertEqual(c.mode,Mode.SETTLE_SAFE_HAND)

    def test_card_reveal_expires_previous_decision(self):
        c = seeded(); c.try_arm(); old = c.choose(request(c)); c.confirm(old)
        reveal(c.ledger,(30,31,0,5,2))
        with self.assertRaises(StaleRequest): c.confirm(old)
        self.assertEqual(c.choose(request(c)).action,'check')

    def test_missing_call_and_wrong_price_disable_not_fold(self):
        for missing in (True,False):
            c = seeded(); c.try_arm()
            r = request(c,('fold','raise')) if missing else replace(request(c),to_call=1)
            with self.assertRaises(UnsafeState): c.choose(r,deadline_recovery=True)
            self.assertEqual(c.mode,Mode.INVALID)
            self.assertIsNone(c.certificate)

    def test_invalid_terminal_events_do_not_activate_abandonment(self):
        for result,payouts in (('hero_fold',(0,120)),('peer_win',(0,120)),('tie',(50,70))):
            c = seeded(); c.try_arm()
            with self.assertRaises(UnsafeState): c.settle(c.ledger.revision+1,'safe',result,payouts)
            self.assertEqual(c.mode,Mode.INVALID)
            self.assertIsNotNone(c.ledger.active)
        c = seeded(); c.try_arm(); c.confirm(c.choose(request(c)))
        with self.assertRaises(UnsafeState): c.settle(c.ledger.revision+1,'safe','hero_win',(140,0))
        self.assertEqual(c.mode,Mode.INVALID)  # no river revealed

    def test_peer_fold_only_switches_after_validated_payout(self):
        c = seeded(); c.try_arm(); c.confirm(c.choose(request(c)))
        # A fold terminal need not reveal the unplayed river.
        c.settle(c.ledger.revision+1,'safe','peer_fold',(140,0))
        self.assertEqual(c.ledger.raw,10)
        self.assertEqual(c.mode,Mode.ABANDON)
        self.assertEqual(c.certificate.lower_score,2)

    def test_unreported_settlement_and_cost_violation_disable(self):
        c = seeded(); c.try_arm()
        c.ledger.settle(c.ledger.revision+1,'safe','hero_fold',(0,120))
        with self.assertRaises(UnsafeState): c.try_arm()
        c = seeded(); c.try_arm(); finish_current(c)
        c.ledger.begin(c.ledger.revision+1,'future',(4,8)); pay(c.ledger,0,4)
        with self.assertRaises(UnsafeState): c.choose(request(c))
        self.assertIsNone(c.certificate)

    def test_clipped_score_is_not_raw_score(self):
        c = seeded(cap=2)
        self.assertEqual(c.ledger.raw,-60); self.assertEqual(c.ledger.clipped,-2)
        self.assertIsNone(c.try_arm())  # -2 + 2 - 2 - 2 is not positive
        self.assertEqual(c.mode,Mode.WATCH)
        self.assertIsNone(c.choose(request(c)))

    def test_river_tie_credit_and_action_plan(self):
        l = TickLedger(200,2)
        l.begin(1,'past',(4,8)); pay(l,0,10); pay(l,1,10)
        l.settle(l.revision+1,'past','peer_fold',(20,0))
        l.begin(l.revision+1,'royal',(0,1)); pay(l,0,50); pay(l,1,70)
        reveal(l,(35,39,43,47,51))
        c = SettlementController(l,[2,3],RULES)
        self.assertEqual(c.try_arm().lower_score,10)
        self.assertEqual(c.mode,Mode.SETTLE_SAFE_HAND)
        c.confirm(c.choose(request(c)))
        c.settle(l.revision+1,'royal','tie',(70,70))
        self.assertEqual(l.raw,10); self.assertEqual(c.mode,Mode.DONE)

    def test_immediate_lock_is_distinct_and_current_paid_can_exceed_post_bound(self):
        c = seeded(raw=100)
        self.assertEqual(c.try_arm().lower_score,42)
        self.assertEqual(c.mode,Mode.ABANDON)
        self.assertEqual(c.choose(request(c)).action,'fold')
        c.confirm(c.choose(request(c)))
        c.settle(c.ledger.revision+1,'safe','hero_fold',(0,120))
        lose_future(c,2); lose_future(c,3)
        self.assertEqual(c.ledger.raw,42)
        self.assertEqual(c.mode,Mode.DONE)

    def test_all_bounded_future_posts_and_check_fold_paths(self):
        # 5 river sizes x 4 post sizes x 6 post sizes x 4 check/fold paths.
        count = 0
        for bet,a,b,check_a,check_b in itertools.product(range(5),range(4),range(6),(False,True),(False,True)):
            c = seeded(stack=74); c.try_arm(); finish_current(c,bet)
            lose_future(c,2,check_a,a); lose_future(c,3,check_b,b)
            self.assertEqual(c.ledger.raw, -60+70+bet-a-b)
            self.assertGreaterEqual(c.ledger.raw,2)
            self.assertEqual(c.mode,Mode.DONE)
            count += 1
        self.assertEqual(count,480)

    def test_changed_rules_duplicate_turn_and_bypassed_cost_are_detected(self):
        c = seeded(); c.try_arm(); c.confirm(c.choose(request(c)))
        with self.assertRaises(StaleRequest): c.choose(request(c))
        c.rules = replace(RULES,version='changed')
        with self.assertRaises(UnsafeState): c.try_arm()
        c = seeded(); c.try_arm(); finish_current(c)
        l = c.ledger
        l.begin(l.revision+1,'bad-future',(4,8)); pay(l,0,4); pay(l,1,5)
        l.settle(l.revision+1,'bad-future','hero_fold',(0,9))
        with self.assertRaises(UnsafeState): c.try_arm()
        self.assertIsNone(c.certificate)

    def test_false_contract_and_unknown_schedule_rejected(self):
        l = TickLedger(200,1)
        bad = replace(RULES,financial=Contract(False,True,True,True,True))
        with self.assertRaises(ValueError): SettlementController(l,[1],bad)
        with self.assertRaises(ValueError): SettlementController(l,[],RULES)
        with self.assertRaises(ValueError): SettlementController(l,[True],RULES)
        c = seeded()
        c.rules = replace(RULES,turn=TurnContract(*([True]*6)))
        with self.assertRaises(ValueError): c.try_arm()


if __name__ == '__main__': unittest.main(verbosity=2)
