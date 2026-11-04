"""Proof-aware reference controller, NOT an official adapter or a full poker bot.

Only trusted local adapter code may mutate the ledger. Monetary amounts are
integer ticks. No wire-supplied certificate or scoreboard is accepted. Contracts
remain assertions about actual rules/lifecycle; this module cannot verify a host.
"""
from dataclasses import dataclass, replace
from enum import Enum
from research.guarantee_lab.certificates import BoundSchedule, Contract, Certificate
from research.guarantee_lab.river_credit import RiverContract, prove_river_credit
from research.guarantee_lab.turn_credit import TurnContract, prove_turn_credit


class UnsafeState(ValueError):
    pass


class StaleRequest(ValueError):
    pass


def tick(x):
    if type(x) is not int or x < 0:
        raise ValueError('nonnegative integer ticks required')
    return x


def cards(values, lengths):
    if not isinstance(values, (tuple, list)) or len(values) not in lengths:
        raise ValueError('bounded card list/tuple with correct count required')
    values = tuple(values)
    if any(type(c) is not int or not 0 <= c < 52 for c in values):
        raise ValueError('normalized standard cards required')
    if len(set(values)) != len(values):
        raise ValueError('duplicate cards')
    return values


@dataclass(frozen=True)
class Hand:
    hand_id: str
    index: int
    hero: tuple
    board: tuple = ()
    paid: tuple = (0, 0)


@dataclass(frozen=True)
class Receipt:
    hand_id: str
    index: int
    paid: tuple
    payouts: tuple
    result: str
    net: int
    hero: tuple
    board: tuple


class TickLedger:
    """Bounded match ledger: O(H) hand IDs, O(1) event storage.

    Sequence numbers are exact, match-wide, monotonically increasing. Duplicate,
    skipped and conflicting events are rejected without partially applying them.
    Refunds are included in terminal payouts, not separate intermediate events.
    The payout convention is matched heads-up stakes plus uncalled refunds.
    """
    def __init__(self, stack, hand_count, cap=None):
        self.stack = tick(stack)
        if self.stack == 0 or type(hand_count) is not int or hand_count <= 0:
            raise ValueError('positive stack and hand count required')
        self.hand_count = hand_count
        self.cap = None if cap is None else tick(cap)
        if self.cap == 0:
            raise ValueError('positive cap required')
        self._active = None
        self._seen = set()
        self._completed = 0
        self._revision = 0
        self._raw = self._clipped = 0
        self._last = None

    @property
    def active(self): return self._active
    @property
    def revision(self): return self._revision
    @property
    def raw(self): return self._raw
    @property
    def clipped(self): return self._clipped
    @property
    def score(self): return self.raw if self.cap is None else self.clipped
    @property
    def completed(self): return self._completed
    @property
    def last(self): return self._last

    def _event(self, sequence, hand_id=None):
        if type(sequence) is not int or sequence != self.revision + 1:
            raise StaleRequest('replayed, skipped or conflicting event sequence')
        if hand_id is not None and (self.active is None or hand_id != self.active.hand_id):
            raise StaleRequest('event is not for the active hand')

    def begin(self, sequence, hand_id, hero):
        self._event(sequence)
        if self.active is not None or self.completed >= self.hand_count:
            raise ValueError('previous hand unfinished or match complete')
        if not isinstance(hand_id, str) or not 0 < len(hand_id) <= 128 or hand_id in self._seen:
            raise ValueError('fresh bounded hand ID required')
        hero = cards(hero, (2,))
        self._active = Hand(hand_id, self.completed, hero)
        self._seen.add(hand_id)
        self._revision = sequence

    def pay(self, sequence, hand_id, player, amount):
        self._event(sequence, hand_id)
        if type(player) is not int or player not in (0, 1):
            raise ValueError('player must be 0 or 1')
        amount = tick(amount)
        paid = list(self.active.paid)
        paid[player] += amount
        if paid[player] > self.stack:
            raise ValueError('payment exceeds equal hand-start stack')
        self._active = replace(self.active, paid=tuple(paid))
        self._revision = sequence

    def reveal(self, sequence, hand_id, board):
        self._event(sequence, hand_id)
        board = cards(board, (3, 4, 5))
        old = self.active.board
        if len(board) <= len(old) or board[:len(old)] != old or set(board) & set(self.active.hero):
            raise ValueError('board must strictly extend visible cards without collision')
        self._active = replace(self.active, board=board)
        self._revision = sequence

    def touch(self, sequence, hand_id):
        """Trusted confirmation of a zero-payment action; consumes replay token."""
        self._event(sequence, hand_id)
        self._revision = sequence

    def expected_payouts(self, result):
        if self.active is None:
            raise ValueError('no active hand')
        a, b = self.active.paid
        matched = min(a, b)
        if result in ('hero_win', 'peer_fold'): return (a + matched, b - matched)
        if result in ('peer_win', 'hero_fold'): return (a - matched, b + matched)
        if result == 'tie': return (a, b)
        raise ValueError('unknown terminal result')

    def settle(self, sequence, hand_id, result, payouts, reported_raw=None, reported_clipped=None):
        self._event(sequence, hand_id)
        if not isinstance(payouts, (tuple, list)) or len(payouts) != 2:
            raise ValueError('exactly two bounded payouts required')
        payouts = tuple(tick(x) for x in payouts)
        expected = self.expected_payouts(result)
        if payouts != expected:
            raise ValueError('payout disagrees with matched/refunded result or pot conservation')
        h = self.active
        net = payouts[0] - h.paid[0]
        raw = self.raw + net
        clipped = self.clipped + (net if self.cap is None else max(-self.cap, min(self.cap, net)))
        for reported, actual in ((reported_raw, raw), (reported_clipped, clipped)):
            if reported is not None and (type(reported) is not int or reported != actual):
                raise ValueError('host scoreboard does not match independently computed ledger')
        self._last = Receipt(h.hand_id, h.index, h.paid, payouts, result, net, h.hero, h.board)
        self._raw, self._clipped = raw, clipped
        self._completed += 1
        self._active = None
        self._revision = sequence
        return self.last


class Mode(str, Enum):
    WATCH = 'WATCH'
    SETTLE_SAFE_HAND = 'SETTLE_SAFE_HAND'
    ABANDON = 'ABANDON'
    DONE = 'DONE'
    INVALID = 'INVALID'


@dataclass(frozen=True)
class Rules:
    """Trusted configuration, never created from unvalidated wire booleans."""
    version: str
    financial: Contract
    river: RiverContract
    turn: TurnContract


@dataclass(frozen=True)
class Request:
    hand_id: str
    revision: int
    rule_version: str
    hero: tuple
    board: tuple
    to_call: int
    legal: frozenset


@dataclass(frozen=True)
class Decision:
    request: Request
    action: str
    amount: int
    mode: Mode


class SettlementController:
    """Separate overlay: WATCH returns None for the ordinary policy.

    A safe-settlement certificate NEVER authorizes an immediate fold. Decision
    tokens bind the hand, rules, cards, ledger revision and actual legal actions.
    choose() performs no rank enumeration; expensive river proof is cold-path
    try_arm() only. Python object internals are not a security boundary.
    """
    def __init__(self, ledger, post_bounds, rules, threshold=0):
        if type(threshold) is not int or not isinstance(rules.version, str) or not rules.version:
            raise ValueError('integer threshold and named rule version required')
        posts = tuple(tick(x) for x in post_bounds)
        if len(posts) != ledger.hand_count:
            raise ValueError('schedule and match length disagree')
        self.ledger, self.rules = ledger, rules
        self.schedule = BoundSchedule(posts, rules.financial, ledger.cap)
        self.threshold = threshold
        self._initial_rules = rules
        self._confirmed_revision = None
        self._protected_index = None
        self.mode = Mode.WATCH
        self.certificate = None
        self.reason = None
        self._credit = None
        self._anchor = None
        self._abandon_started = None

    def invalidate(self, reason):
        self.mode = Mode.INVALID
        self.certificate = None
        self.reason = reason
        raise UnsafeState(reason)

    def _sync(self):
        if self.mode == Mode.INVALID:
            raise UnsafeState(self.reason)
        if self.rules != self._initial_rules:
            self.invalidate('rule configuration changed; create a newly verified controller')
        h = self.ledger.active
        if self.mode == Mode.SETTLE_SAFE_HAND:
            if h is None or h.hand_id != self._anchor.hand_id:
                receipt = self.ledger.last
                if receipt is None or receipt.hand_id != self._anchor.hand_id:
                    self.invalidate('pending hand disappeared without a validated settlement')
                if (receipt.index != self._anchor.index or receipt.hero != self._anchor.hero
                        or receipt.board[:len(self._anchor.board)] != self._anchor.board):
                    self.invalidate('settlement does not bind to the pending cards and hand')
                if receipt.result in ('hero_win','peer_win','tie') and (len(receipt.board) != 5 or receipt.paid[0] != receipt.paid[1]):
                    self.invalidate('unmatched or incomplete safe showdown')
                if self._credit.strictly_beats_every_peer and receipt.result not in ('hero_win','peer_fold'):
                    self.invalidate('settled rank result conflicts with strict proof')
                if receipt.net < self._credit.minimum_current_net or receipt.result == 'hero_fold':
                    self.invalidate('settlement violated the pending proof')
                self.mode = Mode.ABANDON
                self._credit = self._anchor = None
            elif (h.hero != self._anchor.hero or h.board[:len(self._anchor.board)] != self._anchor.board
                  or h.paid[1] < self._anchor.paid[1]):
                self.invalidate('pending proof facts changed')
        if self.mode == Mode.ABANDON:
            last = self.ledger.last
            if last is not None and last.index > self._protected_index and last.paid[0] > self.schedule.posts[last.index]:
                self.invalidate('completed future hand exceeded its verified cost bound')
        if self.mode == Mode.ABANDON and h is None:
            lower = self.ledger.score - self.schedule.suffix[self.ledger.completed]
            self.certificate = Certificate(lower, self.threshold, lower > self.threshold,
                                           'raw net' if self.ledger.cap is None else 'sum of per-hand clipped net')
            if not self.certificate.strict_success:
                self.invalidate('validated settlement no longer preserves a positive margin')
        if h is None:
            if self.ledger.completed == self.ledger.hand_count:
                self.mode = Mode.DONE
            return
        if self.mode == Mode.ABANDON:
            if h.hand_id != self._abandon_started and h.paid[0] > self.schedule.posts[h.index]:
                self.invalidate('future abandonment cost exceeded its verified upper bound')
            certificate = self.schedule.certify(self.ledger.score, h.paid[0], h.index, self.threshold)
            if not certificate.strict_success:
                self.invalidate('abandonment margin no longer positive')
            self.certificate = certificate

    def try_arm(self):
        self._sync()
        if self.mode != Mode.WATCH or self.ledger.active is None:
            return self.certificate
        h = self.ledger.active
        immediate = self.schedule.certify(self.ledger.score, h.paid[0], h.index, self.threshold)
        if immediate.strict_success:
            self.mode, self.certificate = Mode.ABANDON, immediate
            # Current paid amount need not fit its original future-post bound.
            # Only subsequently entered hands must fit that bound.
            self._abandon_started = h.hand_id
            self._protected_index = h.index
            return immediate
        if h.paid[0] > h.paid[1]:
            return None  # not a validated check/call decision point
        if len(h.board) == 4:
            credit = prove_turn_credit(h.hero, h.board, h.paid[1], self.rules.turn)
        elif len(h.board) == 5:
            from research.kernels import RiverKernel
            credit = prove_river_credit(RiverKernel(h.board), h.hero, h.paid[1], self.rules.river)
        else:
            return None
        if credit is None:
            return None
        certificate = self.schedule.certify_safe_settlement(self.ledger.score, credit, h.index, self.threshold)
        if not certificate.strict_success:
            return None
        self._credit, self._anchor = credit, h
        self._abandon_started, self._protected_index = h.hand_id, h.index
        self.mode, self.certificate = Mode.SETTLE_SAFE_HAND, certificate
        return certificate

    def choose(self, request, deadline_recovery=False):
        """Same safe O(1)-sized selection on recovery; never fall back to folding
        a pending safe hand. This is not an OS scheduling/clock guarantee.
        """
        self._sync()
        h = self.ledger.active
        if h is None or self.ledger.revision == self._confirmed_revision:
            raise StaleRequest('no fresh active decision point; own action already confirmed')
        if (request.hand_id != h.hand_id or type(request.revision) is not int
                or request.revision != self.ledger.revision or request.rule_version != self.rules.version
                or request.hero != h.hero or request.board != h.board):
            raise StaleRequest('request does not bind to current trusted state')
        tick(request.to_call)
        if request.to_call != max(0, h.paid[1] - h.paid[0]):
            self.invalidate('call price does not match the contribution ledger')
        if not isinstance(request.legal, frozenset) or not request.legal or not request.legal <= {'check', 'call', 'fold', 'raise'}:
            raise ValueError('bounded normalized legal-action set required')
        if self.mode == Mode.WATCH:
            return None
        if self.mode == Mode.SETTLE_SAFE_HAND:
            action = 'check' if request.to_call == 0 else 'call'
            if action not in request.legal:
                self.invalidate('required safe continuation is not legal; do not substitute fold')
        elif self.mode == Mode.ABANDON:
            action = 'check' if request.to_call == 0 and 'check' in request.legal else 'fold'
            if action not in request.legal:
                self.invalidate('verified free abandonment is unavailable')
        else:
            raise UnsafeState('no certified action in this mode')
        return Decision(request, action, request.to_call if action == 'call' else 0, self.mode)

    def confirm(self, decision):
        """Call only AFTER the host accepts the exact selected own action.
        Transport uncertainty requires adapter reconciliation, not guessed cash.
        """
        expected = self.choose(decision.request)
        if expected is None or decision != expected:
            raise StaleRequest('forged, changed or obsolete decision')
        h = self.ledger.active
        seq = self.ledger.revision + 1
        if decision.action == 'call':
            self.ledger.pay(seq, h.hand_id, 0, decision.amount)
        else:
            self.ledger.touch(seq, h.hand_id)
        self._confirmed_revision = self.ledger.revision
        return decision

    def settle(self, sequence, hand_id, result, payouts, **reported):
        self._sync()
        if self.mode == Mode.SETTLE_SAFE_HAND:
            expected = self.ledger.expected_payouts(result)
            if expected[0] - self.ledger.active.paid[0] < self._credit.minimum_current_net or result == 'hero_fold':
                self.invalidate('terminal result conflicts with the pending proof')
            if self._credit.strictly_beats_every_peer and result not in ('hero_win', 'peer_fold'):
                self.invalidate('terminal rank outcome contradicts a strict win proof')
            if result in ('hero_win', 'peer_win', 'tie'):
                if len(self.ledger.active.board) != 5 or self.ledger.active.paid[0] != self.ledger.active.paid[1]:
                    self.invalidate('safe showdown requires a complete board and matched contributions')
        receipt = self.ledger.settle(sequence, hand_id, result, payouts, **reported)
        self._sync()
        return receipt
