"""Stable structures/protocols for replaceable modules. No external imports."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, Literal

Street = Literal['preflop', 'flop', 'turn', 'river', 'showdown', 'unknown']
Action = Literal['fold', 'check', 'call', 'bet', 'raise', 'wait']

@dataclass(frozen=True)
class TableObservation:
    game: str
    street: Street
    hero_cards: tuple[str, ...]
    board_cards: tuple[str, ...]
    pot: Decimal
    to_call: Decimal
    seated_players: int
    active_players: int
    confidence: float
    is_replay: bool
    frame_sequence: int

@dataclass(frozen=True)
class Decision:
    action: Action
    explanation: str
    estimated_equity: float | None = None
    confidence: float = 0.0

class ScreenInterpreter(Protocol):
    def recognize(self, image_bytes: bytes) -> TableObservation: ...

class PokerMath(Protocol):
    def pot_odds(self, pot: Decimal, to_call: Decimal) -> Decimal: ...

class Strategy(Protocol):
    def suggest(self, obs: TableObservation, odds: Decimal) -> Decision: ...

class PostSessionAnalyzer(Protocol):
    def analyze_closed_session(self, session_id: str, events: list[dict]) -> dict: ...
