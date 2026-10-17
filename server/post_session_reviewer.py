"""Independent, offline post-session Hold'em review.

Never accesses the Android device or 1win, never triggers replay, never places bets.
Running a review requires positive *verified full exit* and an independently
observed empty 'My tables' screen. Screenshots alone are not authoritative.
"""
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from threading import RLock
from typing import Any
import re

VALID_STREETS = ('preflop', 'flop', 'turn', 'river')
VALID_ACTIONS = ('fold', 'check', 'call', 'bet', 'raise', 'small_blind', 'big_blind', 'ante')
ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{1,80}$')

class ReviewBlocked(RuntimeError):
    pass

class InvalidHistory(ValueError):
    pass


def money(value: Any) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise InvalidHistory('money must be an exact string in decimal notation')
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise InvalidHistory('bad money amount') from None
    if not n.is_finite() or n < 0 or n.as_tuple().exponent < -2:
        raise InvalidHistory('invalid money precision/amount')
    return n


@dataclass
class ReviewGate:
    """Fail-closed gate; UI controls must not directly set verified state.

    Caller must verify three independent facts: a session was tracked,
    the table close completed, and a fresh, confident 'My tables: 0' state.
    In a real Android client, independent evidence must come from a trusted
    controller, NOT from an unverified GPT instruction.
    """
    session_id: str | None = None
    state: str = 'idle'
    _exit_completed: bool = False
    _empty_tables: bool = False
    _lock: RLock = field(default_factory=RLock, repr=False)

    def entered_table(self, session_id: str):
        if not ID_PATTERN.fullmatch(session_id):
            raise ValueError('bad session ID')
        with self._lock:
            self.session_id = session_id
            self.state = 'playing'
            self._exit_completed = False
            self._empty_tables = False

    def exit_requested(self):
        with self._lock:
            if self.state not in ('playing', 'exiting'):
                raise ReviewBlocked('no active table to exit')
            self.state = 'exiting'
            self._exit_completed = False
            self._empty_tables = False

    def table_close_confirmed(self, session_id: str, *, confirmation_source: str):
        """Call only after a table-close outcome is confirmed, not after a tap.

        A menu tap 'Back to lobby' or 'Stand up' is NOT a close confirmation.
        """
        with self._lock:
            if self.session_id != session_id or self.state != 'exiting':
                raise ReviewBlocked('unexpected close confirmation')
            if confirmation_source != 'verified_table_closed':
                raise ReviewBlocked('untrusted table close confirmation')
            self._exit_completed = True
            self.state = 'closed_unverified'

    def observe_my_tables(self, *, screen: str, open_tables: int | None,
                          confidence: float, is_fresh: bool):
        with self._lock:
            self._empty_tables = False
            if not (self._exit_completed and self.state in ('closed_unverified', 'review_ready')):
                return False
            if (screen != 'my_tables' or not is_fresh or type(open_tables) is not int
                    or type(confidence) not in (int, float) or confidence < 0.99):
                self.state = 'closed_unverified'
                return False
            if open_tables != 0:
                self.state = 'closed_unverified'
                return False
            self._empty_tables = True
            self.state = 'review_ready'
            return True

    def require_ready(self, session_id: str):
        with self._lock:
            if (self.session_id != session_id or self.state != 'review_ready'
                    or not self._exit_completed or not self._empty_tables):
                raise ReviewBlocked('Review only after fully exiting and verifying no open tables')

    def invalidate(self):
        """Any UI uncertainty, reconnect, return to table or other open seat."""
        with self._lock:
            self.state = 'unknown'
            self._exit_completed = False
            self._empty_tables = False


@dataclass(frozen=True)
class Action:
    street: str
    player: str
    action: str
    amount: Decimal


def parse_actions(raw: list[dict]) -> list[Action]:
    if not isinstance(raw, list) or len(raw) > 200:
        raise InvalidHistory('actions should be a list of at most 200 entries')
    out = []
    last_street_index = -1
    for item in raw:
        if not isinstance(item, dict) or set(item) != {'street', 'player', 'action', 'amount'}:
            raise InvalidHistory('invalid action structure')
        street, actor, verb = item['street'], item['player'], item['action']
        if street not in VALID_STREETS or verb not in VALID_ACTIONS or not isinstance(actor, str) or not ID_PATTERN.fullmatch(actor):
            raise InvalidHistory('invalid actor/street/action')
        idx = VALID_STREETS.index(street)
        if idx < last_street_index:
            raise InvalidHistory('street order reversed')
        last_street_index = idx
        cost = money(item['amount'])
        if verb in ('fold', 'check') and cost != 0:
            raise InvalidHistory('fold/check cannot add a bet')
        out.append(Action(street, actor, verb, cost))
    return out


def pot_odds(pot_before_call: Any, amount_to_call: Any) -> str | None:
    """Required showdown equity for a call, ignoring implied odds and rake.
    Assumes pot_before_call includes all previously committed bets.
    """
    pot, call = money(pot_before_call), money(amount_to_call)
    if call == 0:
        return None
    return str((call / (pot + call) * 100).quantize(Decimal('0.01'))) + '%'


class PostSessionReviewer:
    """Read-only replay/history analyzer; deliberately NOT coupled to live controls."""
    def __init__(self, gate: ReviewGate):
        self.gate = gate

    def analyze(self, session_id: str, hands: list[dict]) -> dict:
        self.gate.require_ready(session_id)
        if not isinstance(hands, list) or len(hands) > 2000:
            raise InvalidHistory('invalid hands')
        reports = []
        for hand in hands:
            if not isinstance(hand, dict) or set(hand) != {'hand_id', 'game', 'hero', 'actions', 'net_result'}:
                raise InvalidHistory('invalid hand structure')
            if hand['game'] != 'holdem_nl':
                # Omaha is excluded entirely from Hold'em reports.
                continue
            hid, hero = hand['hand_id'], hand['hero']
            if not isinstance(hid, str) or not ID_PATTERN.fullmatch(hid) or not isinstance(hero, str) or not ID_PATTERN.fullmatch(hero):
                raise InvalidHistory('bad hand or player ID')
            actions = parse_actions(hand['actions'])
            if hand['net_result'] is None:
                net_result = None
            else:
                try:
                    result_value = Decimal(str(hand['net_result']))
                except (InvalidOperation, TypeError, ValueError):
                    raise InvalidHistory('invalid net result') from None
                if not result_value.is_finite():
                    raise InvalidHistory('non-finite net result')
                money(abs(result_value))
                net_result = str(result_value)
            pre = [a for a in actions if a.street == 'preflop' and a.player == hero]
            # Posting forced blinds does not count towards VPIP.
            voluntary = any(a.action in ('call', 'bet', 'raise') for a in pre)
            raised = any(a.action == 'raise' for a in pre)
            observed_streets = sorted({a.street for a in actions}, key=VALID_STREETS.index)
            reports.append({
                'hand_id':hid, 'net_result':net_result,
                'events':len(actions), 'streets_with_logged_actions':observed_streets,
                'hero_vpip_observed':voluntary if pre else None,
                'hero_pfr_observed':raised if pre else None,
                'has_action_history':bool(actions),
                'evaluation':('historical log available; decisions require ranges, position and pot context'
                              if actions else 'result only; cannot evaluate betting decisions or bluffs'),
            })
        # A new table visit invalidates eligibility; check once more before returning.
        self.gate.require_ready(session_id)
        return {
            'session_id':session_id,
            'mode':'AFTER_FULL_EXIT_ONLY',
            'read_only':True,
            'hands_reviewed':len(reports),
            'hands':reports,
            'caution':'Outcomes alone do not determine whether the strategy or a bluff was correct. No live-game actions.',
        }
