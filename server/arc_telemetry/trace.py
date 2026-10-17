"""Privacy-preserving, deterministic end-to-end timing traces for a test harness.

Times are supplied *monotonic milliseconds on one clock*. Phone/server timestamps
must NEVER be combined as if their clocks were synchronized. Use Android-only
capture-to-response timestamps for true E2E, or stage duration telemetry recorded
independently. Store no player names, cards, money amounts or image bytes.

All outputs are advisory-only. In particular a displayed 30/60s icon is not an
actual count-down and cannot be used as a betting deadline or execution permit.
"""
from __future__ import annotations
from collections import OrderedDict, deque
from math import ceil, isfinite
from threading import RLock

STAGES = ('capture', 'encode', 'uplink', 'vision', 'model', 'downlink', 'verify')
BLOCKED_SCENES = frozenset({'overlay','menu','replay','disconnected','lobby','showdown','unknown'})

class TraceError(ValueError): pass

def _integer(value, name, *, upper=10**12):
    if type(value) is not int or not 0 <= value <= upper:
        raise TraceError('invalid_'+name)

def _latency(v):
    if type(v) not in (float,int) or not isfinite(v) or not 0 <= v <= 120000:
        raise TraceError('invalid_duration')
    return float(v)

def _quantile(data, pct):
    if not data:return None
    sorted_data=sorted(data)
    return round(sorted_data[max(0,ceil(len(data)*pct)-1)],3)

class TraceLedger:
    """Bounded, thread-safe telemetry and strictly ordered frame acceptance.

    begin() / complete() use a *single monotonic clock* per trace. Only one
    pending frame per session; any newer frame invalidates the older pending
    trace. Completion records latency but never triggers actions.
    """
    def __init__(self, *, max_sessions=16, window=200, max_age_ms=1300, min_samples=10):
        if not 1<=max_sessions<=1024 or not 1<=window<=10000 or not 1<=min_samples<=window:
            raise TraceError('invalid_configuration')
        self.max_sessions=max_sessions
        self.max_age_ms=max_age_ms
        self.min_samples=min_samples
        self.window=window
        self.sessions=OrderedDict()
        self.pending={}
        self.stages={s:deque(maxlen=window) for s in STAGES}
        self.whole=deque(maxlen=window)
        self.decisions=deque(maxlen=window)
        self.lock=RLock()

    def begin(self, *, session_id, sequence, captured_ms, received_ms, scene='live_table'):
        if type(session_id) is not str or not 8<=len(session_id)<=64 or not all(x.isalnum() or x=='-' for x in session_id):
            raise TraceError('invalid_session')
        for n,v in [('sequence',sequence),('captured_ms',captured_ms),('received_ms',received_ms)]:_integer(v,n)
        if received_ms<captured_ms:raise TraceError('negative_frame_age')
        if type(scene) is not str or len(scene)>40:raise TraceError('invalid_scene')
        with self.lock:
            last=self.sessions.get(session_id,-1)
            if sequence<=last:
                return {'status':'REJECT_SEQUENCE','action':None,'money_actions_enabled':False}
            if session_id not in self.sessions and len(self.sessions)>=self.max_sessions:
                return {'status':'REJECT_CAPACITY','action':None,'money_actions_enabled':False}
            self.sessions[session_id]=sequence
            key=(session_id,sequence)
            # A new observation supersedes all older pending work for that session.
            for prev in tuple(self.pending):
                if prev[0]==session_id:del self.pending[prev]
            age=received_ms-captured_ms
            if scene != 'live_table':
                return {'status':'BLOCKED_SCENE','action':None,'money_actions_enabled':False}
            if age>self.max_age_ms:
                return {'status':'STALE_ON_ARRIVAL','action':None,'money_actions_enabled':False}
            self.pending[key]={'start_ms':captured_ms,'last_ms':received_ms,'durations':{},'scene':scene}
            return {'status':'TRACKING','action':None,'money_actions_enabled':False}

    def stage(self, *, session_id, sequence, stage, duration_ms, observed_at_ms):
        if stage not in STAGES:raise TraceError('invalid_stage')
        dur=_latency(duration_ms)
        _integer(observed_at_ms,'observed_at_ms')
        with self.lock:
            key=(session_id,sequence)
            row=self.pending.get(key)
            if row is None:return {'status':'SUPERSEDED_OR_UNKNOWN'}
            if stage in row['durations']:return {'status':'DUPLICATE_STAGE'}
            if observed_at_ms<row['last_ms']:return {'status':'CLOCK_REGRESSION'}
            # Non-decreasing receive/complete timestamps, not sum of durations,
            # establish end-to-end latency. Some stages can overlap in real systems.
            row['last_ms']=observed_at_ms
            row['durations'][stage]=dur
            self.stages[stage].append(dur)
            return {'status':'RECORDED'}

    def complete(self, *, session_id, sequence, completed_ms):
        _integer(completed_ms,'completed_ms')
        with self.lock:
            key=(session_id,sequence)
            row=self.pending.pop(key,None)
            if row is None:return {'status':'DISCARDED_SUPERSEDED','action':None,'money_actions_enabled':False}
            if completed_ms<row['last_ms']:
                return {'status':'DISCARDED_CLOCK_REGRESSION','action':None,'money_actions_enabled':False}
            total=completed_ms-row['start_ms']
            reason='TIMING_ONLY_INCOMPLETE' if any(s not in row['durations'] for s in STAGES) else 'TIMING_ONLY_COMPLETE'
            if total>self.max_age_ms:reason='DISCARDED_STALE_RESPONSE'
            self.whole.append(float(total))
            self.decisions.append(reason)
            return {'status':reason,'total_ms':total,'stage_count':len(row['durations']),
                    'timer_verified':False,'action':None,'money_actions_enabled':False}

    def summary(self):
        with self.lock:
            stages={s:{'n':len(v),'p50_ms':_quantile(v,.5),'p95_ms':_quantile(v,.95),'p99_ms':_quantile(v,.99)} for s,v in self.stages.items()}
            return {'latency_scope':'SIMULATION_OR_MEASURED_MONOTONIC_ONLY',
                    'e2e':{'n':len(self.whole),'p50_ms':_quantile(self.whole,.5),'p95_ms':_quantile(self.whole,.95),'p99_ms':_quantile(self.whole,.99)},
                    'stages':stages,'results':{k:list(self.decisions).count(k) for k in set(self.decisions)},
                    'calibrated':len(self.whole)>=self.min_samples and all(len(v)>=self.min_samples for v in self.stages.values()),
                    'timer_verified':False,'authorized_actions':[],'money_actions_enabled':False}
