"""Deterministic latency gates and read-only API regression."""
import base64
import http.client
import json
import os
from pathlib import Path
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from arc_fastloop.gate import FrameGate, GateError, RollingLatency
from arc_fastloop.observe import FastObserver
from server import ApiHandler

class FakeClock:
    def __init__(self):self.time=1000.
    def __call__(self):return self.time
    def advance(self,sec):self.time+=sec

class FakeObserver:
    def read(self,*args,**kwargs):return {'quality':'measured','action':None}

class FastGateTests(unittest.TestCase):
    def setUp(self):
        self.clock=FakeClock()
        self.gate=FrameGate(now=self.clock,min_interval_ms=0)
    def r(self,seq=1,jpeg=b'abc',age=10,remaining=30000,session='test-session'):
        return self.gate.reserve(session,seq,age,remaining,jpeg)
    def test_successful_observation(self):
        t=self.r()['ticket']
        self.clock.advance(.012)
        self.assertEqual(self.gate.complete(t),'fresh_observation')
        self.assertEqual(self.gate.latency.summary()['n'],1)
    def test_expired_frame_rejected(self):
        self.assertEqual(self.r(age=1301)['status'],'stale_frame')
        self.assertEqual(self.r(seq=2,remaining=2999)['status'],'timer_insufficient')
        self.assertIsNone(self.r(seq=3,age=1301)['ticket'])
    def test_superseded_response(self):
        t=self.r()['ticket']
        self.assertEqual(self.r(seq=2,jpeg=b'def')['status'],'busy_dropped_old')
        self.assertEqual(self.gate.complete(t),'discarded_superseded')
        self.assertEqual(self.r(seq=3,jpeg=b'ghi')['status'],'accepted')
    def test_deadline_rejected(self):
        t=self.r()['ticket']; self.clock.advance(1.21)
        self.assertEqual(self.gate.complete(t),'discarded_deadline')
    def test_unchanged_image_skipped(self):
        t=self.r()['ticket']; self.gate.complete(t)
        self.assertEqual(self.r(seq=2)['status'],'unchanged')
    def test_seq_and_metadata_guards(self):
        self.assertEqual(self.r(seq=1)['status'],'accepted')
        self.assertEqual(self.r(seq=1)['status'],'out_of_order')
        for data in ((True,10,30000),(3,-1,30000),(4,1,False),(5,1,190000)):
            with self.subTest(data=data),self.assertRaises(GateError):
                self.r(seq=data[0],age=data[1],remaining=data[2])
    def test_bounded_sessions(self):
        gate=FrameGate(now=self.clock,max_sessions=1)
        self.assertEqual(gate.reserve('session-0001',1,2,30000,b'x')['status'],'accepted')
        self.assertEqual(gate.reserve('session-0002',1,2,30000,b'x')['status'],'capacity')
    def test_observer_not_called_if_stale(self):
        obs=FastObserver(observer=FakeObserver(),gate=self.gate)
        out=obs.observe(session_id='test-session',sequence=1,frame_age_ms=1700,
                        remaining_ms=30000,jpeg=b'x',screen_state='live_table')
        self.assertNotIn('observation',out)
        self.assertFalse(out['can_place_wager'])
    def test_rolling_summary(self):
        r=RollingLatency()
        for v in range(1,101):r.record(v)
        self.assertEqual(r.summary()['p50_ms'],50)
        self.assertEqual(r.summary()['p95_ms'],95)

class FastHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def request(self,data,token='token-fastloop-v13'):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        c.request('POST','/fast/observe',json.dumps(data).encode(),
                  {'Content-Type':'application/json','X-Device-Token':token})
        r=c.getresponse();body=json.loads(r.read());code=r.status;c.close()
        return code,body
    def test_observe_and_auth(self):
        frame=(Path(__file__).resolve().parents[2]/'datasets/cards_gold/cards_1307.jpg').read_bytes()
        payload={'request':'fast_observe','session_id':'test-session-v13',
                'sequence':801,'frame_age_ms':20,'remaining_ms':30000,
                'screen_state':'unknown','image_base64':base64.b64encode(frame).decode()}
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'token-fastloop-v13'}):
            self.assertEqual(self.request(payload,'bad')[0],401)
            code,out=self.request(payload)
            self.assertEqual(code,200)
            self.assertNotIn('tap',out)
            self.assertIsNone(out['action'])
            self.assertFalse(out['money_actions_enabled'])
            self.assertIn(out['status'],('fresh_observation','discarded_deadline'))
            self.assertEqual(self.request({**payload,'extra':True})[0],400)
            self.assertEqual(self.request({**payload,'frame_age_ms':100000})[1]['status'],'out_of_order')
    def test_stale_and_unsupported(self):
        frame=(Path(__file__).resolve().parents[2]/'datasets/cards_gold/cards_1307.jpg').read_bytes()
        payload={'request':'fast_observe','session_id':'second-session-v13','sequence':1,
                'frame_age_ms':3000,'remaining_ms':30000,'screen_state':'unknown',
                'image_base64':base64.b64encode(frame).decode()}
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'token-fastloop-v13'}):
            code,out=self.request(payload)
            self.assertEqual(code,200)
            self.assertEqual(out['status'],'stale_frame')
            self.assertEqual(self.request({**payload,'sequence':2,'screen_state':'impossible'})[0],400)

if __name__=='__main__':unittest.main()
