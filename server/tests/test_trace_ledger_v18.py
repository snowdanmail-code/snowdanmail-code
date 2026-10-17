import unittest
from arc_telemetry import TraceLedger, TraceError, STAGES
from arc_telemetry.lab import replay_traces

SID='test-trace-session'

class TraceLedgerTests(unittest.TestCase):
    def setUp(self):self.l=TraceLedger(min_samples=2,max_age_ms=1000)
    def started(self,seq=1,start=1000,at=1000,scene='live_table'):
        return self.l.begin(session_id=SID,sequence=seq,captured_ms=start,received_ms=at,scene=scene)
    def log(self,seq=1,start=1000,step=10):
        for i,s in enumerate(STAGES):
            r=self.l.stage(session_id=SID,sequence=seq,stage=s,duration_ms=step,observed_at_ms=start+(i+1)*step)
            self.assertEqual(r['status'],'RECORDED')
    def test_complete_synthetic(self):
        self.assertEqual(self.started()['status'],'TRACKING')
        self.log()
        out=self.l.complete(session_id=SID,sequence=1,completed_ms=1080)
        self.assertEqual(out['status'],'TIMING_ONLY_COMPLETE')
        self.assertEqual(out['total_ms'],80)
        self.assertIsNone(out['action'])
        self.assertFalse(out['money_actions_enabled'])
        s=self.l.summary()
        self.assertEqual(s['e2e']['p95_ms'],80)
        self.assertFalse(s['calibrated'])
    def test_old_frame_blocked(self):
        self.assertEqual(self.started(start=1000,at=2001)['status'],'STALE_ON_ARRIVAL')
        self.assertEqual(self.l.complete(session_id=SID,sequence=1,completed_ms=2100)['status'],'DISCARDED_SUPERSEDED')
    def test_only_whitelisted_live_table(self):
        for i,state in enumerate(('overlay','menu','replay','disconnected','lobby','showdown','unknown','game_unknown')):
            self.assertEqual(self.started(seq=i+1,scene=state)['status'],'BLOCKED_SCENE')
        self.assertEqual(self.started(seq=10)['status'],'TRACKING')
    def test_newer_supersedes_pending(self):
        self.started()
        self.assertEqual(self.started(seq=2)['status'],'TRACKING')
        self.assertEqual(self.l.complete(session_id=SID,sequence=1,completed_ms=1010)['status'],'DISCARDED_SUPERSEDED')
        self.assertEqual(self.l.stage(session_id=SID,sequence=1,stage='model',duration_ms=8,observed_at_ms=1010)['status'],'SUPERSEDED_OR_UNKNOWN')
        self.assertEqual(self.l.complete(session_id=SID,sequence=2,completed_ms=1010)['status'],'TIMING_ONLY_INCOMPLETE')
    def test_sequence_must_increase_even_on_abstain(self):
        self.started(scene='menu')
        self.assertEqual(self.started(scene='live_table')['status'],'REJECT_SEQUENCE')
        self.assertEqual(self.started(seq=0)['status'],'REJECT_SEQUENCE')
    def test_reject_wrong_clock_domain(self):
        with self.assertRaises(TraceError):self.started(start=1002,at=1000)
        self.started()
        self.assertEqual(self.l.stage(session_id=SID,sequence=1,stage='model',duration_ms=20,observed_at_ms=999)['status'],'CLOCK_REGRESSION')
    def test_duplicate_stage_and_invalid_duration(self):
        self.started()
        kwargs={'session_id':SID,'sequence':1,'stage':'model','duration_ms':8,'observed_at_ms':1001}
        self.assertEqual(self.l.stage(**kwargs)['status'],'RECORDED')
        self.assertEqual(self.l.stage(**kwargs)['status'],'DUPLICATE_STAGE')
        for value in (-1,True,float('nan'),float('inf'),120001):
            with self.assertRaises(TraceError):self.l.stage(**(kwargs | {'duration_ms':value}))
    def test_late_response_no_actions(self):
        self.started(); self.log()
        r=self.l.complete(session_id=SID,sequence=1,completed_ms=2200)
        self.assertEqual(r['status'],'DISCARDED_STALE_RESPONSE')
        self.assertFalse(r['money_actions_enabled'])
    def test_calibration_p95(self):
        for seq,start in [(1,1000),(2,2000)]:
            self.started(seq=seq,start=start,at=start)
            self.log(seq=seq,start=start,step=10)
            self.l.complete(session_id=SID,sequence=seq,completed_ms=start+80)
        summary=self.l.summary()
        self.assertTrue(summary['calibrated'])
        self.assertEqual(summary['e2e']['p95_ms'],80)
        self.assertEqual(summary['stages']['model']['n'],2)
        self.assertEqual(summary['authorized_actions'],[])
    def test_session_capacity(self):
        ledger=TraceLedger(max_sessions=1)
        self.assertEqual(ledger.begin(session_id=SID,sequence=1,captured_ms=0,received_ms=0)['status'],'TRACKING')
        self.assertEqual(ledger.begin(session_id='other-session-123',sequence=1,captured_ms=0,received_ms=0)['status'],'REJECT_CAPACITY')
    def test_deterministic_replay_counts(self):
        r=replay_traces(rows=30)
        self.assertEqual(r['summary']['e2e']['n'],30)
        self.assertTrue(r['summary']['calibrated'])
        self.assertEqual(len(r['cases']),30)
        self.assertFalse(r['live_android_network_tested'])
        self.assertEqual(r['summary']['authorized_actions'],[])

if __name__=='__main__':unittest.main()
