"""Regression tests for read-only, fail-closed pixel recognition.

These benchmarks use cropped original card rectangles without personal identifiers.
Several holdout snapshots show different moments from a hand also represented
in the atlas. They are *not* independent new hands; don't market as generalization.
"""
import base64
import http.client
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from arc_vision.card_reader import TemplateCardReader, InvalidScreenshot
from server import ApiHandler

DATA=Path(__file__).resolve().parents[2]/'datasets'/'cards_gold'

class CardReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader=TemplateCardReader()
        cls.entries=json.loads((DATA/'gold.json').read_text())['entries']

    def test_every_gold_snapshot_matches_expected_status(self):
        for case in self.entries:
            with self.subTest(case=case['id']):
                result=self.reader.read((DATA/case['image']).read_bytes(),screen_state='live_table')
                self.assertEqual(result['quality'],case['expected'])
                self.assertIsNone(result['action'])
                self.assertFalse(result['money_actions_enabled'])
                if case['expected']=='complete':
                    self.assertEqual(result['hero_cards'],case['hero'])
                    self.assertEqual(result['board_cards'],case['board'])
                else:
                    self.assertEqual(result['hero_cards'],[])
                    self.assertEqual(result['board_cards'],[])

    def test_blocked_states_never_infer_cards(self):
        frame=(DATA/'cards_1301.jpg').read_bytes()
        for mode in ['replay','disconnected','overlay','lobby','session_history','raise_panel']:
            with self.subTest(mode=mode):
                result=self.reader.read(frame,screen_state=mode)
                self.assertEqual(result['quality'],'abstain')
                self.assertEqual(result['reason'],'screen_state_blocked')
                self.assertIsNone(result['action'])

    def test_broken_input_fails(self):
        with self.assertRaises(InvalidScreenshot):self.reader.read(b'x')
        with self.assertRaises(InvalidScreenshot):self.reader.read(b'\xff\xd8'+b'x'*250)
        with self.assertRaises(InvalidScreenshot):self.reader.read((DATA/'cards_1301.jpg').read_bytes(),screen_state='cannot_trust')

    def test_reader_never_generates_bets_even_for_complete_frame(self):
        result=self.reader.read((DATA/'cards_1307.jpg').read_bytes(),screen_state='live_table')
        self.assertNotIn('bet',str(result).lower())
        self.assertNotIn('tap',str(result).lower())
        self.assertEqual(result['reader_version'],'arc_fixed_glyph_v1.1.0')

class CardReaderHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close()

    def test_http_route_auth_and_read_only(self):
        f=(DATA/'cards_1301.jpg').read_bytes()
        payload={'request':'vision_cards','image_base64':base64.b64encode(f).decode(),
                 'screen_state':'live_table'}
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'test-vision-token-321'}):
            c=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=15)
            c.request('POST','/vision/cards',json.dumps(payload).encode(),
                      {'Content-Type':'application/json','X-Device-Token':'test-vision-token-321'})
            r=c.getresponse();res=json.loads(r.read());self.assertEqual(r.status,200);c.close()
            self.assertEqual(res['hero_cards'],['4d','Qd'])
            self.assertEqual(res['board_cards'],['2h','Ts','Qc'])
            self.assertFalse(res['money_actions_enabled'])
            self.assertIsNone(res['action'])
            c=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=15)
            c.request('POST','/vision/cards',json.dumps(payload).encode(),
                      {'Content-Type':'application/json','X-Device-Token':'wrong'})
            r=c.getresponse();r.read();self.assertEqual(r.status,401);c.close()
