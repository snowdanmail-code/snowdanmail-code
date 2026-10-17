"""V1.5: conservative *advisory* processing envelope. NEVER an execution token.

Unknown stage telemetry or unverified timer yields an unverified status.
Uses supplied measurements exclusively; no fictitious latency estimates.
"""
from __future__ import annotations
from collections import deque
from math import ceil, isfinite
from threading import Lock


class LatencyEnvelope:
    def __init__(self, window=100, *, min_samples=10):
        if not (1 <= window <= 1000 and 1 <= min_samples <= window):
            raise ValueError('invalid_window')
        self.window=window
        self.min_samples=min_samples
        self.samples={name:deque(maxlen=window) for name in ('capture','uplink','vision','model','downlink','verify')}
        self.lock=Lock()

    def record(self, stage, duration_ms):
        if stage not in self.samples or type(duration_ms) not in (int,float) or not isfinite(duration_ms) or not 0 <= duration_ms <= 120000:
            raise ValueError('invalid_latency')
        with self.lock:self.samples[stage].append(float(duration_ms))

    def snapshot(self):
        with self.lock:
            out={}
            for stage,series in self.samples.items():
                values=sorted(series)
                n=len(values)
                out[stage]={'n':n,'p95_ms':values[max(0,ceil(n*.95)-1)] if n else None}
            return out

    def advise(self, *, remaining_ms=None, frame_age_ms=0, reserve_ms=1500):
        if (remaining_ms is not None and (type(remaining_ms) is not int or remaining_ms<0)) or            type(frame_age_ms) is not int or frame_age_ms<0 or type(reserve_ms) is not int or reserve_ms<0:
            raise ValueError('invalid_advisory')
        data=self.snapshot()
        # Even with complete measurements a client-supplied timer does not confirm the live timer.
        known=all(value['n']>=self.min_samples for value in data.values())
        required_ms=(ceil(sum(value['p95_ms'] for value in data.values())) +
                     frame_age_ms + reserve_ms) if known else None
        if remaining_ms is None:
            status='TIMER_UNVERIFIED'
        elif not known:
            status='LATENCY_UNCALIBRATED'
        elif remaining_ms < required_ms:
            status='OBSERVATION_BUDGET_EXCEEDED'
        else:
            status='ESTIMATED_BUDGET_ONLY'
        return {'status':status,'estimated_required_ms':required_ms,
                'reported_remaining_ms':remaining_ms,'timer_verified':False,
                'authorized_actions':[],'money_actions_enabled':False,
                'stage_latencies':data,
                'warning':'Advisory only. No automatic taps, no proof of remaining turn time.'}
