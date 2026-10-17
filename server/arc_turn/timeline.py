"""Stateful read-only cue history with monotonic age and expiry guards.

An observation may be stable visually, but that does not confer permission
for any UI tap. Store no screenshots or user identities.
"""
from __future__ import annotations
from collections import OrderedDict
import threading
import time

class TurnCueTimeline:
    def __init__(self,*,now=time.monotonic,min_frames=2,min_dwell_ms=150,
                 max_gap_ms=1500,max_sessions=16,clear_after_seconds=600):
        self.now=now
        self.lock=threading.Lock()
        self.rows=OrderedDict()
        self.min_frames=min_frames
        self.min_dwell_ms=min_dwell_ms
        self.max_gap_ms=max_gap_ms
        self.max_sessions=max_sessions
        self.clear_after_seconds=clear_after_seconds

    def observe(self, *, session_id,sequence,cue,frame_age_ms,remaining_ms):
        # Parameters were previously checked by FrameGate. Timeline validates
        # again so it is safe to use independently.
        if not isinstance(session_id,str) or not 8<=len(session_id)<=64:
            raise ValueError('invalid_session')
        if type(sequence) is not int or sequence<0:
            raise ValueError('invalid_sequence')
        if type(frame_age_ms) is not int or frame_age_ms<0:
            raise ValueError('invalid_age')
        if remaining_ms is not None and (type(remaining_ms) is not int or remaining_ms<0):
            raise ValueError('invalid_remaining')
        if not isinstance(cue,str) or cue not in {
                'ACTIVE_COLOUR_TRIAD','RIGHT_GOLD_ONLY','NO_ACTIVE_COLOUR_CUES',
                'AMBIGUOUS_COLOURS','BLOCKED_SCENE','UNSUPPORTED_GEOMETRY','SCENE_CONFLICT'}:
            raise ValueError('invalid_cue')
        t=self.now()
        with self.lock:
            for key,row in list(self.rows.items()):
                if t-row['last_seen']>self.clear_after_seconds:del self.rows[key]
            row=self.rows.get(session_id)
            if row is None:
                if len(self.rows)>=self.max_sessions:
                    return self._result('CAPACITY',0)
                row={'sequence':-1,'last_seen':t,'start':t,'cue':None,'streak':0}
                self.rows[session_id]=row
            if sequence<=row['sequence']:
                return self._result('OUT_OF_ORDER',row['streak'])
            gap=(t-row['last_seen'])*1000
            same=cue==row['cue'] and gap<=self.max_gap_ms
            row['sequence']=sequence
            row['start']=row['start'] if same else t
            row['streak']=row['streak']+1 if same else 1
            row['last_seen']=t
            row['cue']=cue
            if frame_age_ms>1300:
                state='STALE'
            elif remaining_ms is None:
                state='TIMER_UNVERIFIED'
            elif remaining_ms<3000:
                state='LOW_TIME'
            elif cue in ('BLOCKED_SCENE','SCENE_CONFLICT','UNSUPPORTED_GEOMETRY'):
                state='NO_READABLE_TURN'
            elif cue not in ('ACTIVE_COLOUR_TRIAD','RIGHT_GOLD_ONLY'):
                state='NO_STABLE_ACTIVE_CUES'
            elif row['streak']>=self.min_frames and (t-row['start'])*1000>=self.min_dwell_ms:
                state='VISUAL_PATTERN_STABLE_NOT_VERIFIED'
            else:
                state='PENDING_SECOND_OBSERVATION'
            return self._result(state,row['streak'])

    @staticmethod
    def _result(status,streak):
        return {'status':status,'streak':streak,'verified_turn':False,
                'action':None,'money_actions_enabled':False}

    def reset(self):
        with self.lock:self.rows.clear()
