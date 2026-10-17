"""Strict boundary between vision, GPT proposal, and an authorized play-chip executor.

This module is venue-agnostic. There is deliberately NO live 1win executor here.
The GPT provider is the central strategist. Safety checks are not strategic fallbacks.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol
import hashlib
import json
import math
import threading
import time


class DecisionRejected(ValueError):
    pass


class OperatorStop(RuntimeError):
    pass


class Action(str, Enum):
    FOLD = 'fold'
    CHECK = 'check'
    CALL = 'call'
    BET = 'bet'
    RAISE = 'raise'
    WAIT = 'wait'


@dataclass(frozen=True)
class GameSnapshot:
    # Values must originate from the observation/validation subsystem, not GPT's output.
    hand_id: str
    revision: int
    captured_at: float
    player_turn: bool
    game_mode: str
    screen: str
    street: str
    player_cards: tuple[str, ...]
    community_cards: tuple[str, ...]
    pot: int
    stack: int
    to_call: int
    min_raise_total: int
    max_raise_total: int
    allowed: frozenset[Action]
    confidence: float
    verification_frames: int
    table_id: str
    other_players: int

    def validate(self, now: float) -> None:
        if not self.hand_id or not self.table_id or self.revision < 0:
            raise DecisionRejected('invalid_identity')
        if self.game_mode != 'PLAY_CHIPS_NO_VALUE':
            raise DecisionRejected('not_confirmed_play_chips')
        if self.screen != 'TABLE' or not self.player_turn:
            raise DecisionRejected('not_players_turn')
        if self.street not in {'preflop', 'flop', 'turn', 'river'}:
            raise DecisionRejected('street_unknown')
        if not math.isfinite(self.captured_at) or now - self.captured_at > 2.0 or self.captured_at > now + 0.2:
            raise DecisionRejected('stale_frame')
        if self.confidence < .98 or self.verification_frames < 2:
            raise DecisionRejected('insufficient_observation')
        if len(self.player_cards) != 2 or len(set(self.player_cards + self.community_cards)) != len(self.player_cards + self.community_cards):
            raise DecisionRejected('cards_missing_or_duplicate')
        if len(self.community_cards) not in {0, 3, 4, 5}:
            raise DecisionRejected('invalid_board')
        if not (0 <= self.to_call <= self.stack and 0 <= self.pot and 0 <= self.stack):
            raise DecisionRejected('inconsistent_chips')
        if self.other_players < 1 or self.other_players > 9:
            raise DecisionRejected('player_count')
        if not self.allowed or not self.allowed.issubset(set(Action)):
            raise DecisionRejected('allowed_actions_unknown')
        if self.to_call == 0 and Action.CALL in self.allowed:
            raise DecisionRejected('illegal_call_when_free')
        if self.to_call > 0 and Action.CHECK in self.allowed:
            raise DecisionRejected('illegal_check_when_owed')
        if any(a in self.allowed for a in (Action.BET, Action.RAISE)):
            if not (0 < self.min_raise_total <= self.max_raise_total <= self.stack):
                raise DecisionRejected('raise_limits_missing')

    def fingerprint(self) -> str:
        # State revision MUST change after any observed action or new turn.
        material = (self.table_id, self.hand_id, self.revision, self.street,
                    self.player_cards, self.community_cards, self.pot, self.stack,
                    self.to_call, sorted(a.value for a in self.allowed))
        return hashlib.sha256(repr(material).encode()).hexdigest()


@dataclass(frozen=True)
class Proposal:
    hand_id: str
    revision: int
    action: Action
    total_chips: int
    confidence: float
    reason: str
    intent: str = 'value'  # value, bluff, defense, check, wait


@dataclass(frozen=True)
class VerifiedCommand:
    hand_id: str
    revision: int
    fingerprint: str
    action: Action
    total_chips: int
    intent: str


class Strategist(Protocol):
    def decide(self, snapshot: GameSnapshot) -> Proposal: ...


class ActionExecutor(Protocol):
    """An executor must require its own explicit, venue-specific authorization."""
    def execute(self, command: VerifiedCommand) -> bool: ...


class DecisionGate:
    def __init__(self, *, max_single_commit: int = 200, min_model_confidence: float = .85):
        self.max_single_commit = max_single_commit
        self.min_model_confidence = min_model_confidence

    def verify(self, snapshot: GameSnapshot, proposal: Proposal, now: float) -> VerifiedCommand:
        snapshot.validate(now)
        if proposal.hand_id != snapshot.hand_id or proposal.revision != snapshot.revision:
            raise DecisionRejected('decision_state_mismatch')
        if type(proposal.total_chips) is not int or proposal.total_chips < 0:
            raise DecisionRejected('amount_type_or_negative')
        if type(proposal.confidence) is not float or not math.isfinite(proposal.confidence) or proposal.confidence < self.min_model_confidence:
            raise DecisionRejected('insufficient_model_confidence')
        if not isinstance(proposal.action, Action) or proposal.action not in snapshot.allowed:
            raise DecisionRejected('illegal_action')
        if proposal.intent not in {'value', 'bluff', 'defense', 'check', 'wait'}:
            raise DecisionRejected('invalid_intent')
        if not isinstance(proposal.reason, str) or len(proposal.reason) > 500:
            raise DecisionRejected('invalid_reason')
        if proposal.action in (Action.FOLD, Action.CHECK, Action.WAIT):
            if proposal.total_chips != 0:
                raise DecisionRejected('nonzero_free_action')
        elif proposal.action is Action.CALL:
            if proposal.total_chips != snapshot.to_call:
                raise DecisionRejected('call_amount_mismatch')
        elif proposal.action in (Action.BET, Action.RAISE):
            if not snapshot.min_raise_total <= proposal.total_chips <= snapshot.max_raise_total:
                raise DecisionRejected('raise_outside_observed_limits')
        if proposal.total_chips > self.max_single_commit or proposal.total_chips > snapshot.stack:
            raise DecisionRejected('operator_chips_limit')
        return VerifiedCommand(snapshot.hand_id, snapshot.revision, snapshot.fingerprint(),
                               proposal.action, proposal.total_chips, proposal.intent)


class AutonomySession:
    """One decision per verified snapshot; STOP dominates all actions.

    The caller must obtain a new, verified screenshot AFTER each issued action.
    An executor's `True` denotes accepted gesture, not proof of completed game action.
    """
    def __init__(self, strategist: Strategist, executor: ActionExecutor,
                 gate: DecisionGate | None = None, clock=time.monotonic):
        self.strategist, self.executor = strategist, executor
        self.gate = gate or DecisionGate()
        self.clock = clock
        self._stopped = threading.Event()
        self._seen = set()
        self._lock = threading.Lock()
        self.events: list[dict] = []

    def stop(self):
        self._stopped.set()

    def step(self, snapshot: GameSnapshot) -> VerifiedCommand:
        with self._lock:
            if self._stopped.is_set():
                raise OperatorStop('operator_stop')
            key = (snapshot.table_id, snapshot.hand_id, snapshot.revision)
            if key in self._seen:
                raise DecisionRejected('duplicate_turn')
            snapshot.validate(self.clock())
            # Mark prior to awaiting the model to prevent duplicate execution after a timeout.
            self._seen.add(key)
            try:
                proposal = self.strategist.decide(snapshot)
                if self._stopped.is_set():
                    raise OperatorStop('operator_stop')
                command = self.gate.verify(snapshot, proposal, self.clock())
                if self._stopped.is_set():
                    raise OperatorStop('operator_stop')
                accepted = self.executor.execute(command)
                if not accepted:
                    raise DecisionRejected('executor_rejected')
                self.events.append({'hand': snapshot.hand_id, 'rev': snapshot.revision,
                                    'action': command.action.value, 'chips': command.total_chips,
                                    'intent': command.intent, 'status': 'issued_not_confirmed'})
                return command
            except Exception as exc:
                self.events.append({'hand': snapshot.hand_id, 'rev': snapshot.revision,
                                    'status': 'blocked', 'reason': type(exc).__name__ + ':' + str(exc)[:120]})
                raise

    def jsonl(self) -> str:
        return ''.join(json.dumps(ev, ensure_ascii=False, sort_keys=True) + '\n' for ev in self.events)
