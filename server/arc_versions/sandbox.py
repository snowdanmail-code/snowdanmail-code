"""Offline demonstration that swaps policies without touching UI or making wagers."""
from decimal import Decimal
from .contracts import TableObservation, Decision

class ExactOdds:
    def pot_odds(self, pot: Decimal, to_call: Decimal) -> Decimal:
        if pot < 0 or to_call < 0: raise ValueError('negative bet')
        if to_call == 0: return Decimal('0')
        return to_call / (pot + to_call)

class ConservativeWaitPolicy:
    def suggest(self, obs: TableObservation, odds: Decimal) -> Decision:
        if obs.game != 'holdem_nl' or obs.is_replay or obs.confidence < 0.99:
            return Decision('wait', 'No reliable/live Holdem state')
        return Decision('wait', 'Sandbox analysis only; human controls money actions')

class SandboxRunner:
    def __init__(self, math_engine: ExactOdds, strategy: ConservativeWaitPolicy):
        self.math_engine = math_engine
        self.strategy = strategy
    def analyze(self, obs: TableObservation) -> dict:
        odds = self.math_engine.pot_odds(obs.pot, obs.to_call)
        result = self.strategy.suggest(obs, odds)
        return {'pot_odds': str(odds), 'action': result.action,
                'explanation': result.explanation, 'frame_sequence': obs.frame_sequence}
