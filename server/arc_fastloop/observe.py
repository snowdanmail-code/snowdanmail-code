"""Read-only fast perception. No OpenAI required for the local first pass.

Stage measurements use monotonic clocks and describe local computation only,
not the Android uplink, model latency, or end-to-end real-time reliability.
"""
from __future__ import annotations
import time
from arc_vision.combined_observer import CompositeObserver
from .gate import FrameGate
from arc_turn import TurnCueReader, TurnCueTimeline
from arc_turn.deadlines import LatencyEnvelope
from arc_turn.stopwatch import StopwatchCue
from arc_turn.timer_digits import TimerDigitReader
import cv2
import numpy as np

class FastObserver:
    def __init__(self,observer=None,gate=None,now=time.perf_counter,turn_reader=None,turn_timeline=None):
        self.observer=observer or CompositeObserver()
        self.gate=gate or FrameGate()
        self.now=now
        self.turn_reader=turn_reader or TurnCueReader()
        self.turn_timeline=turn_timeline or TurnCueTimeline()
        self.latency_envelope=LatencyEnvelope()
        self.stopwatch_reader=StopwatchCue()
        self.timer_digits_reader=TimerDigitReader()

    def observe(self,*,session_id,sequence,frame_age_ms,remaining_ms,jpeg,screen_state):
        info=self.gate.reserve(session_id,sequence,frame_age_ms,remaining_ms,jpeg)
        if info['status']!='accepted':
            return {'mode':'local_fast_observe','status':info['status'],
                    'action':None,'can_place_wager':False,'money_actions_enabled':False,
                    'timer_status':'UNVERIFIED' if remaining_ms is None else 'CLIENT_HINT_ONLY'}
        ticket=info['ticket']
        started=self.now()
        try:
            observation=self.observer.read(jpeg,screen_state=screen_state)
            # This read-only colour cue path is intentionally independent of
            # strategic/model decisions and never emits button coordinates.
            frame=cv2.imdecode(np.frombuffer(jpeg,dtype=np.uint8),cv2.IMREAD_COLOR)
            if frame is None:raise ValueError('invalid_jpeg')
            cues=self.turn_reader.read_image(frame,screen_state=screen_state)
            stopwatch=self.stopwatch_reader.read(frame,screen_state=screen_state)
            printed_label=self.timer_digits_reader.read(frame,screen_state=screen_state)
        except Exception:
            self.gate.complete(ticket,error=True)
            raise
        elapsed_ms=round(max(0,(self.now()-started)*1000),3)
        self.latency_envelope.record('vision', elapsed_ms)
        completed=self.gate.complete(ticket)
        result={'mode':'local_fast_observe','status':completed,'processing_ms':elapsed_ms,
                'action':None,'can_place_wager':False,'money_actions_enabled':False,
                'version':'v1.7.0',
                'timer_status':'UNVERIFIED' if remaining_ms is None else 'CLIENT_HINT_ONLY',
                'latency_scope':'SERVER_LOCAL_ONLY',
                'real_money_action_permitted':False,
                'deadline_advice':self.latency_envelope.advise(
                    remaining_ms=remaining_ms,frame_age_ms=frame_age_ms)}
        # Late or superseded observations must not enter user-visible game state.
        if completed=='fresh_observation':
            result['observation']=observation
            result['turn_cues']=cues
            result['stopwatch_cue']=stopwatch
            result['timer_label']=printed_label
            result['turn_timeline']=self.turn_timeline.observe(
                session_id=session_id,sequence=sequence,cue=cues['cue'],
                frame_age_ms=frame_age_ms,remaining_ms=remaining_ms)
            result['version']='v1.6.0'
        return result
