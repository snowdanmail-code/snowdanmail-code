"""Poker strategy study on invented, non-monetary Texas Hold'em examples.

IMPORTANT: This is a simplified one-street thought experiment. Estimated fold
probabilities and equities are INPUT assumptions, not inferred facts. The
module neither connects to 1win nor executes bets; it is not a poker solver.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal
import json

POSITIONS = ('early', 'middle', 'late')
STREETS = ('preflop', 'flop', 'turn', 'river')

@dataclass(frozen=True)
class LabSpot:
    """Hypothetical spot; quantities are play-money chips, not currency."""
    pot: float
    to_call: float
    effective_stack: float
    equity: float
    estimated_fold_probability: float
    opponents: int
    position: str
    street: str
    board_threat: float
    blocker_relevance: float
    villain_observations: int
    reliable_observation: bool = True

    def validate(self):
        for name in ('pot','to_call','effective_stack','equity','estimated_fold_probability','board_threat','blocker_relevance'):
            value = getattr(self, name)
            if type(value) not in (float, int) or not isfinite(value):
                raise ValueError('invalid numeric input: ' + name)
        if self.pot <= 0 or self.to_call < 0 or self.effective_stack <= 0:
            raise ValueError('invalid chips')
        if self.to_call > self.effective_stack:
            raise ValueError('call above stack: side pots not modeled')
        for name in ('equity','estimated_fold_probability','board_threat','blocker_relevance'):
            if not 0 <= getattr(self,name) <= 1:
                raise ValueError('out of bounds: ' + name)
        if type(self.opponents) is not int or not 1 <= self.opponents <= 9:
            raise ValueError('opponents')
        if type(self.villain_observations) is not int or self.villain_observations < 0:
            raise ValueError('villain observations')
        if type(self.reliable_observation) is not bool:
            raise ValueError('observation flag')
        if self.position not in POSITIONS or self.street not in STREETS:
            raise ValueError('position or street')

@dataclass(frozen=True)
class LabLine:
    id: str
    action: Literal['fold','check','call','bet']
    intent: Literal['defense','passive','value','bluff']
    chips: float
    simplified_ev: float
    explanation: str

@dataclass(frozen=True)
class Study:
    spot: LabSpot
    lines: tuple[LabLine, ...]
    baseline_id: str | None
    warnings: tuple[str, ...]


def ev_call(equity: float, pot: float, call: float) -> float:
    """Incremental EV if showdown follows immediately, ignoring future bets/rake."""
    return equity * pot - (1.0 - equity) * call


def ev_bet(equity: float, pot: float, bet: float, fold_probability: float) -> float:
    """One opponent calls full size or folds, no raises/future streets/rake."""
    return fold_probability * pot + (1.0 - fold_probability) * (
        equity * (pot + bet) - (1.0 - equity) * bet
    )


def _risk_adjusted_fold_probability(spot: LabSpot) -> float:
    """Deliberately pessimistic, illustrative—not calibrated."""
    uncertainty_penalty = .15 if spot.villain_observations < 50 else .05
    return max(0.0, spot.estimated_fold_probability - uncertainty_penalty)


def build_study(spot: LabSpot) -> Study:
    spot.validate()
    warnings = [
        'SIMULATION ONLY: no 1win interaction, no real-money actions',
        'Approximate one-street chip EV; no rake, future betting, raises, range uncertainty or ICM',
        'Equity and opponent fold probability are assumptions, not known opponent cards',
    ]
    if not spot.reliable_observation:
        return Study(spot, (), None, tuple(warnings + ['Unreliable observation: no decision']))
    lines: list[LabLine] = []
    if spot.to_call:
        lines.append(LabLine('fold', 'fold','defense',0,0,'No additional chips invested'))
        lines.append(LabLine('call','call','defense',spot.to_call,
                             round(ev_call(spot.equity,spot.pot,spot.to_call),3),
                             'Showdown approximation; calls above stack excluded'))
        # Raises facing a bet require extra pot/call/raise response modelling.
        warnings.append('Raising over a bet is not modeled in this version')
    else:
        lines.append(LabLine('check','check','passive',0,0,
                             'Checking is assigned 0 immediate chip EV; future value is not modeled'))
        for frac in (.33, .5, .75):
            amount = round(min(spot.pot*frac,spot.effective_stack),2)
            if amount <= 0 or any(abs(l.chips-amount)<1e-8 for l in lines if l.action=='bet'):
                continue
            if spot.equity >= .65:
                label = 'value'
            elif (spot.equity <= .40 and spot.position == 'late' and
                  spot.blocker_relevance >= .5 and spot.villain_observations >= 20 and
                  spot.opponents == 1 and spot.board_threat >= .35):
                label = 'bluff'
            else:
                continue
            # Conservative adjustments for incomplete opponent evidence.
            fold_p = _risk_adjusted_fold_probability(spot)
            ev = ev_bet(spot.equity,spot.pot,amount,fold_p)
            if label == 'bluff' and (fold_p < .35 or ev <= 0):
                continue
            lines.append(LabLine(f'{label}_{int(frac*100)}', 'bet',label,amount,round(ev,3),
                    f'Estimated fold rate after uncertainty penalty: {fold_p:.2f}; opponent response simplified'))
    # This is a mathematical BASELINE for laboratory comparison, NOT a GPT model answer.
    top = max(lines,key=lambda x:x.simplified_ev) if lines else None
    baseline = top.id if top is not None else None
    if spot.villain_observations < 50:
        warnings.append('Small opponent sample: fold probability not calibrated')
    return Study(spot,tuple(lines),baseline,tuple(warnings))


def make_gpt_brief(study: Study) -> dict:
    """Structured study for possible future eligible ChatGPT testing; no network call."""
    if not study.lines:
        raise ValueError('Refuse: insufficient observation data')
    return {
        'mode': 'offline_synthetic_poker_study',
        'execution_allowed': False,
        'prompt': (
            'Analyze this hypothetical play-money Texas Holdem training spot. '
            'Consider opponent ranges, position, board, sample-size uncertainty, '
            'value betting and whether a bluff has a credible basis. '
            'Select a candidate ID from the provided lines; state assumptions and uncertainty. '
            'Do not claim solver-optimal play or attempt real-game interaction.'
        ),
        'spot': asdict(study.spot),
        'candidates': [asdict(line) for line in study.lines],
        'baseline_id': study.baseline_id,
        'limitations': list(study.warnings),
        'expected_response': {
            'candidate_id': 'one of the listed IDs',
            'reason': 'short explanatory sentence',
            'confidence': 'number from 0 to 1',
            'bluff_considerations': 'short explanation; never a mandatory bluff',
        },
    }


def validate_lab_choice(study: Study, response: dict) -> dict:
    """Verify a hypothetical model recommendation, NEVER yield a real action request."""
    expected = {'candidate_id','reason','confidence','bluff_considerations'}
    if type(response) is not dict or set(response) != expected:
        raise ValueError('invalid schema')
    if response['candidate_id'] not in {line.id for line in study.lines}:
        raise ValueError('unknown/illegal study choice')
    if type(response['confidence']) not in (int,float) or not isfinite(response['confidence']) or not 0<=response['confidence']<=1:
        raise ValueError('confidence')
    for k in ('reason','bluff_considerations'):
        if type(response[k]) is not str or not 1<=len(response[k])<=500:
            raise ValueError(k)
    matching = next(l for l in study.lines if l.id == response['candidate_id'])
    return {'mode':'analysis_only','simulated_line':asdict(matching),
            'explanation':response['reason'],'bluff_considerations':response['bluff_considerations'],
            'model_confidence_uncalibrated':response['confidence'],
            'execution_allowed':False, 'real_game_actions': []}


def study_as_json(spot: LabSpot) -> str:
    return json.dumps(make_gpt_brief(build_study(spot)),ensure_ascii=False,indent=2)
