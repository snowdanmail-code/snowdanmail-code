"""Fast-loop safety and performance primitives.

Client age / remaining time are advisory and CANNOT authorize any action.
Each session is single-flight and latest-sequence-wins. Frames aren't stored.
Responses are never an execution instruction, including when marked fresh.
"""
from __future__ import annotations
from collections import OrderedDict,deque
from dataclasses import dataclass
import hashlib
import math
import threading
import time

class GateError(ValueError):pass

@dataclass(frozen=True)
class Ticket:
    session_id:str
    sequence:int
    generation:int
    reserved_at:float
    deadline_at:float

class RollingLatency:
    def __init__(self,max_samples=256):
        self.lock=threading.Lock()
        self.values=deque(maxlen=max_samples)

    def record(self,elapsed_ms):
        if not isinstance(elapsed_ms,(int,float)) or not math.isfinite(elapsed_ms) or elapsed_ms<0:
            raise ValueError('invalid_duration')
        with self.lock:self.values.append(round(float(elapsed_ms),3))

    def summary(self):
        with self.lock:values=sorted(self.values)
        if not values:return {'n':0,'p50_ms':None,'p95_ms':None,'max_ms':None}
        def q(f):return values[min(len(values)-1,math.ceil(len(values)*f)-1)]
        return {'n':len(values),'p50_ms':q(.5),'p95_ms':q(.95),'max_ms':values[-1]}

class FrameGate:
    def __init__(self, *, now=time.monotonic, max_sessions=16, max_frame_age_ms=1300,
                 min_remaining_ms=3000, processing_budget_ms=1200, min_interval_ms=100):
        self.now=now
        self.lock=threading.Lock()
        self.max_sessions=max_sessions
        self.max_frame_age_ms=max_frame_age_ms
        self.min_remaining_ms=min_remaining_ms
        self.processing_budget_ms=processing_budget_ms
        self.min_interval_ms=min_interval_ms
        self.sessions=OrderedDict()
        self.latency=RollingLatency()

    def _check(self, session_id, sequence, frame_age_ms, remaining_ms, fingerprint):
        if not isinstance(session_id,str) or not 8<=len(session_id)<=64 or not all(
           x.isalnum() or x=='-' for x in session_id):raise GateError('invalid_session')
        if type(sequence) is not int or not 0<=sequence<10**12:raise GateError('invalid_sequence')
        if type(frame_age_ms) is not int or not 0<=frame_age_ms<=600_000:raise GateError('invalid_frame_age')
        if remaining_ms is not None and (type(remaining_ms) is not int or not 0<=remaining_ms<=180_000):raise GateError('invalid_timer')
        if not isinstance(fingerprint,str) or len(fingerprint)!=64 or any(c not in '0123456789abcdef' for c in fingerprint):
            raise GateError('invalid_fingerprint')

    def reserve(self,session_id,sequence,frame_age_ms,remaining_ms,jpeg):
        fingerprint=hashlib.sha256(jpeg).hexdigest()
        self._check(session_id,sequence,frame_age_ms,remaining_ms,fingerprint)
        t=self.now()
        with self.lock:
            for key,row in list(self.sessions.items()):
                if t-row['seen']>600 and not row['busy']:
                    del self.sessions[key]
            if session_id not in self.sessions:
                if len(self.sessions)>=self.max_sessions:
                    return {'status':'capacity','ticket':None}
                self.sessions[session_id]={'seq':-1,'busy':False,'generation':0,'seen':t,
                    'last_accept':-1e10,'fingerprint':None}
            row=self.sessions[session_id]
            if sequence<=row['seq']:
                return {'status':'out_of_order','ticket':None}
            # Every newer frame invalidates previous in-flight work, even on abstention.
            row['seq']=sequence;row['generation']+=1;row['seen']=t
            if frame_age_ms>self.max_frame_age_ms:
                return {'status':'stale_frame','ticket':None}
            if remaining_ms is not None and remaining_ms<self.min_remaining_ms:
                return {'status':'timer_insufficient','ticket':None}
            if row['busy']:
                return {'status':'busy_dropped_old','ticket':None}
            if row['fingerprint']==fingerprint:
                return {'status':'unchanged','ticket':None}
            if (t-row['last_accept'])*1000<self.min_interval_ms:
                return {'status':'paced','ticket':None}
            row['busy']=True
            row['fingerprint']=fingerprint
            row['last_accept']=t
            # Deadline conservatively limited by both local CPU budget and user-reported clock.
            available_ms=(self.processing_budget_ms if remaining_ms is None else
                          min(self.processing_budget_ms, max(0,remaining_ms-self.min_remaining_ms)))
            ticket=Ticket(session_id,sequence,row['generation'],t,t+available_ms/1000)
            return {'status':'accepted','ticket':ticket}

    def complete(self,ticket,*,error=False):
        t=self.now()
        self.latency.record(max(0,(t-ticket.reserved_at)*1000))
        with self.lock:
            row=self.sessions.get(ticket.session_id)
            if row is None:return 'discarded_session'
            row['busy']=False
            if error:return 'failed'
            if row['generation']!=ticket.generation or row['seq']!=ticket.sequence:
                return 'discarded_superseded'
            if t>ticket.deadline_at:return 'discarded_deadline'
            return 'fresh_observation'

    def reset(self):
        with self.lock:self.sessions.clear()
