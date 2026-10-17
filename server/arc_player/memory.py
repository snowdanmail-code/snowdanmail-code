"""Observed opponent tendencies only, with conservative small-sample estimates.

Scores are evidence summaries, not mind-reading or guaranteed predictions.
No real names or external identifiers need be stored here.
"""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import threading

ACTIONS = frozenset({'fold', 'check', 'call', 'bet', 'raise'})


@dataclass(frozen=True)
class ObservedAction:
    hand_id: str
    street: str
    pseudonym: str
    action: str
    faced_bet: bool
    showdown: bool = False

    def validate(self):
        if not self.hand_id or self.street not in {'preflop', 'flop', 'turn', 'river'}:
            raise ValueError('invalid_event')
        if not self.pseudonym or len(self.pseudonym) > 64:
            raise ValueError('invalid_pseudonym')
        if self.action not in ACTIONS:
            raise ValueError('invalid_action')
        if type(self.faced_bet) is not bool or type(self.showdown) is not bool:
            raise ValueError('invalid_flags')


class OpponentMemory:
    """Tracks action evidence; small samples remain explicitly uncertain."""
    def __init__(self):
        self._events: dict[str, list[ObservedAction]] = defaultdict(list)
        self._keys: set[tuple] = set()

    def observe(self, event: ObservedAction, *, sequence: int) -> bool:
        event.validate()
        if type(sequence) is not int or sequence < 0:
            raise ValueError('invalid_sequence')
        key = (event.hand_id, sequence, event.pseudonym)
        if key in self._keys:
            return False
        self._keys.add(key)
        self._events[event.pseudonym].append(event)
        return True

    def report(self, pseudonym: str) -> dict:
        events = self._events.get(pseudonym, [])
        faced = sum(e.faced_bet for e in events)
        folded = sum(e.faced_bet and e.action == 'fold' for e in events)
        raises = sum(e.action == 'raise' for e in events)
        # Beta(1,1) smoothing; ALWAYS show n to prevent overinterpretation.
        return {'id': pseudonym, 'sample_actions': len(events),
                'faced_bet_samples': faced, 'folds_when_facing_bet': folded,
                'fold_to_bet_smoothed': round((folded + 1) / (faced + 2), 4),
                'raise_rate_smoothed': round((raises + 1) / (len(events) + 2), 4),
                'reliability': 'insufficient' if faced < 30 else 'limited_evidence'}

    def list_reports(self):
        return [self.report(k) for k in sorted(self._events)]


class AppendOnlyEvidence:
    """SHA-256 linked JSONL; appends only, refuses to load altered log."""
    def __init__(self, filename: str):
        self.path = Path(filename)
        self._lock = threading.Lock()
        self._last_hash = '0'*64
        if self.path.exists():
            self._last_hash = self.verify()

    def verify(self) -> str:
        last = '0'*64
        with self.path.open('r', encoding='utf-8') as f:
            for index, line in enumerate(f, 1):
                row = json.loads(line)
                event = row.get('event')
                if not isinstance(event, dict) or row.get('previous') != last:
                    raise ValueError(f'ledger_invalid_chain_line_{index}')
                canonical = json.dumps({'previous': last, 'event': event}, sort_keys=True, ensure_ascii=False)
                expected = hashlib.sha256(canonical.encode()).hexdigest()
                if row.get('hash') != expected:
                    raise ValueError(f'ledger_modified_line_{index}')
                last = expected
        return last

    def append(self, event: dict) -> str:
        # sanitized caller data; don't include account credentials or raw screenshots.
        if not isinstance(event, dict) or len(json.dumps(event)) > 4096:
            raise ValueError('invalid_event_length')
        with self._lock:
            if self.path.exists() and self.verify() != self._last_hash:
                raise ValueError('ledger_changed_externally')
            canonical = json.dumps({'previous': self._last_hash, 'event': event}, sort_keys=True, ensure_ascii=False)
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            record = dict(previous=self._last_hash, event=event, hash=digest)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + '\n')
                f.flush()
                os.fsync(f.fileno())
            self._last_hash = digest
            return digest
