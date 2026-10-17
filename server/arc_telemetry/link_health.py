"""Pure, read-only quality-of-service monitor for screenshot observations.

No network I/O, timers, gameplay decisions, or execution permissions. Each
observation is timestamped by the *same local monotonic clock*. An unreliable
connection reduces the rate of optional analysis; it never authorizes a tap.
"""
from __future__ import annotations

from collections import deque
from math import ceil, isfinite
from threading import RLock

OUTCOMES = frozenset(('ok', 'timeout', 'transport_error', 'stale_response', 'superseded'))
TRANSPORTS = frozenset(('wifi', 'cellular', 'unknown'))


class LinkHealthError(ValueError):
    pass


def quantile(values, fraction):
    if not values:
        return None
    s = sorted(values)
    return round(s[max(0, ceil(len(s) * fraction) - 1)], 2)


class ObservationLinkHealth:
    """Bounded stats; fail-closed trust and increasing retry intervals.

    States reflect *observation transport*, not player status. During network
    failures client may still attempt sparse read-only health observations.
    """

    def __init__(self, *, window=64, min_samples=15, degrade_p95_ms=1800,
                 severe_p95_ms=3500, fail_threshold=3):
        if (type(window) is not int or not 5 <= window <= 1024 or
                type(min_samples) is not int or not 2 <= min_samples <= window or
                type(fail_threshold) is not int or not 2 <= fail_threshold <= 20):
            raise LinkHealthError('invalid_configuration')
        if not (0 < degrade_p95_ms < severe_p95_ms <= 60000):
            raise LinkHealthError('invalid_thresholds')
        self.window = window
        self.min_samples = min_samples
        self.degrade_p95_ms = degrade_p95_ms
        self.severe_p95_ms = severe_p95_ms
        self.fail_threshold = fail_threshold
        self._samples = deque(maxlen=window)
        self._outcomes = deque(maxlen=window)
        self._consecutive_failures = 0
        self._recovery_streak = 0
        self._recovery_needed = False
        self._last_sequence = -1
        self._last_time = -1
        self._transport = 'unknown'
        self._lock = RLock()

    def record(self, *, sequence, seen_at_ms, outcome, rtt_ms=None, transport='unknown'):
        if type(sequence) is not int or sequence < 0 or type(seen_at_ms) is not int or seen_at_ms < 0:
            raise LinkHealthError('invalid_monotonic_frame')
        if type(outcome) is not str or type(transport) is not str or outcome not in OUTCOMES or transport not in TRANSPORTS:
            raise LinkHealthError('invalid_outcome_or_transport')
        if outcome == 'ok' and (type(rtt_ms) not in (int, float) or
                                not isfinite(rtt_ms) or not 0 <= rtt_ms <= 60000):
            raise LinkHealthError('invalid_rtt')
        if rtt_ms is not None and (type(rtt_ms) not in (int, float) or
                                    not isfinite(rtt_ms) or not 0 <= rtt_ms <= 60000):
            raise LinkHealthError('invalid_rtt')
        with self._lock:
            if sequence <= self._last_sequence:
                return {'status': 'REJECT_DUPLICATE_OR_OLD', 'action': None,
                        'money_actions_enabled': False}
            if seen_at_ms < self._last_time:
                return {'status': 'REJECT_CLOCK_REGRESSION', 'action': None,
                        'money_actions_enabled': False}
            if transport != self._transport:
                # RTT histories from Wi-Fi and cellular networks must not mix.
                self._samples.clear()
                self._outcomes.clear()
                self._consecutive_failures = 0
                self._recovery_streak = 0
                self._recovery_needed = False
                self._transport = transport
            self._last_sequence = sequence
            self._last_time = seen_at_ms
            self._outcomes.append(outcome)
            if outcome == 'ok':
                self._samples.append(float(rtt_ms))
                self._consecutive_failures = 0
                if self._recovery_needed:
                    self._recovery_streak += 1
                    if self._recovery_streak >= 3:
                        self._recovery_needed = False
                        self._recovery_streak = 0
            else:
                self._consecutive_failures += 1
                self._recovery_streak = 0
                if self._consecutive_failures >= self.fail_threshold:
                    self._recovery_needed = True
            result = self._snapshot()
            result['status'] = 'RECORDED'
            return result

    def _snapshot(self):
        p95 = quantile(self._samples, .95)
        enough = len(self._samples) >= self.min_samples
        if self._recovery_needed or self._consecutive_failures >= self.fail_threshold:
            state = 'UNRELIABLE'
            suggested_interval_ms = 5000
        elif self._consecutive_failures:
            state = 'DEGRADED'
            suggested_interval_ms = 1500
        elif not enough:
            state = 'UNCALIBRATED'
            suggested_interval_ms = 1000
        elif p95 > self.severe_p95_ms:
            state = 'UNRELIABLE'
            suggested_interval_ms = 5000
        elif p95 > self.degrade_p95_ms:
            state = 'DEGRADED'
            suggested_interval_ms = 1500
        else:
            state = 'HEALTHY'
            suggested_interval_ms = 500
        return {'state': state, 'transport': self._transport,
                'samples': len(self._samples), 'sample_target': self.min_samples,
                'failures_in_row': self._consecutive_failures,
                'recovery_confirmations_pending': 3 - self._recovery_streak if self._recovery_needed else 0,
                'p50_rtt_ms': quantile(self._samples, .5),
                'p95_rtt_ms': p95, 'p99_rtt_ms': quantile(self._samples, .99),
                'suggested_observation_interval_ms': suggested_interval_ms,
                'actual_game_deadline_known': False, 'action': None,
                'money_actions_enabled': False}

    def summary(self):
        with self._lock:
            return dict(self._snapshot())
