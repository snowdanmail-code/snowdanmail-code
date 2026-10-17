"""HTTP contract: a missing timer is represented as unknown, never invented."""
import base64
import http.client
import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from server import ApiHandler

class HttpTimerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def request(self,remaining_ms):
        frame=(Path(__file__).resolve().parents[2]/'datasets/cards_gold/cards_1307.jpg').read_bytes()
        doc={'request':'fast_observe','session_id':'v15-unknown-timer-001',
             'sequence':1 if remaining_ms is None else 2,'frame_age_ms':12,
             'remaining_ms':remaining_ms,'screen_state':'live_table',
             'image_base64':base64.b64encode(frame).decode()}
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        conn.request('POST','/fast/observe',json.dumps(doc).encode(),
                     {'X-Device-Token':'fake-v15-device-token','Content-Type':'application/json'})
        res=conn.getresponse();out=json.loads(res.read());status=res.status;conn.close()
        return status,out
    def test_unknown_client_timer_is_read_only(self):
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'fake-v15-device-token'}):
            status,out=self.request(None)
        self.assertEqual(status,200)
        self.assertIn(out['status'],('fresh_observation','discarded_deadline'))
        self.assertEqual(out['timer_status'],'UNVERIFIED')
        self.assertEqual(out['deadline_advice']['status'],'TIMER_UNVERIFIED')
        self.assertEqual(out['deadline_advice']['authorized_actions'],[])
        self.assertIsNone(out['action'])
        self.assertFalse(out['money_actions_enabled'])
        self.assertFalse(out['can_place_wager'])
        if out['status']=='fresh_observation':
            self.assertEqual(out['turn_timeline']['status'],'TIMER_UNVERIFIED')
            self.assertFalse(out['turn_timeline']['verified_turn'])
if __name__=='__main__':unittest.main()
