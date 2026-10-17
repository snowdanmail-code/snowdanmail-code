import unittest
from arc_turn.deadlines import LatencyEnvelope
from arc_fastloop.gate import FrameGate
from arc_turn.timeline import TurnCueTimeline

class FakeClock:
    def __init__(self):self.t=100.
    def __call__(self):return self.t
    def add(self,x):self.t+=x

class DeadlineTests(unittest.TestCase):
    def test_unknown_timer_does_not_invent_clock(self):
        d=LatencyEnvelope(min_samples=1)
        a=d.advise(remaining_ms=None)
        self.assertEqual(a['status'],'TIMER_UNVERIFIED')
        self.assertIsNone(a['estimated_required_ms'])
        self.assertFalse(a['money_actions_enabled'])
    def test_incomplete_latency_never_claims_safe(self):
        d=LatencyEnvelope(min_samples=2)
        d.record('vision',20)
        self.assertEqual(d.advise(remaining_ms=30000)['status'],'LATENCY_UNCALIBRATED')
    def test_full_envelope(self):
        d=LatencyEnvelope(min_samples=2)
        for name in ('capture','uplink','vision','model','downlink','verify'):
            for ms in (100,200):d.record(name,ms)
        self.assertEqual(d.advise(remaining_ms=1300,frame_age_ms=100,reserve_ms=200)['status'],
                         'OBSERVATION_BUDGET_EXCEEDED')
        r=d.advise(remaining_ms=3000,frame_age_ms=100,reserve_ms=200)
        self.assertEqual(r['estimated_required_ms'],1500)
        self.assertEqual(r['status'],'ESTIMATED_BUDGET_ONLY')
        self.assertFalse(r['timer_verified'])
        self.assertEqual(r['authorized_actions'],[])
    def test_p95_window(self):
        d=LatencyEnvelope(window=10,min_samples=1)
        for k in range(12):d.record('vision',k+1)
        self.assertEqual(d.snapshot()['vision'],{'n':10,'p95_ms':12.0})
    def test_validation(self):
        d=LatencyEnvelope()
        for name,value in [('bad',10),('vision',-1),('vision',float('nan')),('vision',float('inf'))]:
            with self.assertRaises(ValueError):d.record(name,value)
        for kwargs in ({'remaining_ms':True},{'frame_age_ms':-1},{'reserve_ms':-1}):
            with self.assertRaises(ValueError):d.advise(**kwargs)
    def test_gate_unknown_timer_allowed_only_as_read_only_observation(self):
        clock=FakeClock();g=FrameGate(now=clock,min_interval_ms=0)
        r=g.reserve('test-session-v15',1,20,None,b'1')
        self.assertEqual(r['status'],'accepted')
        clock.add(.2)
        self.assertEqual(g.complete(r['ticket']),'fresh_observation')
        self.assertEqual(g.reserve('test-session-v15',2,20,2500,b'2')['status'],'timer_insufficient')
    def test_timeline_timer_unverified_not_stable_turn(self):
        clock=FakeClock();t=TurnCueTimeline(now=clock)
        a=t.observe(session_id='test-session-v15',sequence=1,cue='ACTIVE_COLOUR_TRIAD',frame_age_ms=1,remaining_ms=None)
        clock.add(.3)
        b=t.observe(session_id='test-session-v15',sequence=2,cue='ACTIVE_COLOUR_TRIAD',frame_age_ms=1,remaining_ms=None)
        self.assertEqual(a['status'],'TIMER_UNVERIFIED')
        self.assertEqual(b['status'],'TIMER_UNVERIFIED')
        self.assertFalse(b['verified_turn'])
        self.assertFalse(b['money_actions_enabled'])
if __name__=='__main__':unittest.main()
