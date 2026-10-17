"""Offline security, pacing and server behavior tests. No billed API calls."""
import base64
from http.server import ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import ApiHandler, STREAM_MEMORY
from stream_agent import StreamMemory, parse_analysis

TOKEN = 'local-test-secret-987123'
JPEG = b'\xff\xd8' + b'jpeg-test-data' + b'\xff\xd9'
SESSION = 'session-testing-0001'

class Clock:
    def __init__(self): self.current = 100.0
    def __call__(self): return self.current

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.memory = StreamMemory(now=self.clock)
    def test_suppressed_without_key(self):
        self.assertEqual(self.memory.reserve(SESSION, 1, False)['kind'], 'demo')
    def test_first_frame_invoke_and_busy(self):
        self.assertEqual(self.memory.reserve(SESSION, 1, True)['kind'], 'invoke')
        self.assertEqual(self.memory.reserve(SESSION, 2, True)['kind'], 'busy')
    def test_rate_limit_then_continue(self):
        self.memory.reserve(SESSION, 1, True)
        self.memory.complete(SESSION, {'summary': 'test'})
        self.assertEqual(self.memory.reserve(SESSION, 2, True)['kind'], 'throttled')
        self.clock.current += 7
        self.assertEqual(self.memory.reserve(SESSION, 3, True)['kind'], 'invoke')
    def test_drops_old_frames(self):
        self.memory.reserve(SESSION, 5, False)
        with self.assertRaisesRegex(ValueError, 'out_of_order_frame'):
            self.memory.reserve(SESSION, 4, False)
    def test_bounded_history(self):
        for i in range(15):
            self.clock.current += 7
            self.memory.reserve(SESSION, i, True)
            self.memory.complete(SESSION, {'summary': str(i)})
        self.assertEqual(len(self.memory.sessions[SESSION]['history']), 6)
    def test_model_budget(self):
        for i in range(30):
            self.clock.current += 7
            self.memory.reserve(SESSION, i, True)
            self.memory.complete(SESSION)
        self.clock.current += 7
        self.assertEqual(self.memory.reserve(SESSION, 31, True)['kind'], 'budget_exhausted')
    def test_invalid_response_refused(self):
        with self.assertRaises(ValueError): parse_analysis({'readability': 'clear', 'summary': 'x'})
    def test_analysis_clear(self):
        self.assertEqual(parse_analysis({'readability':'clear','summary':'ok','visible_change':'none'})['readability'], 'clear')

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), ApiHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
    def setUp(self): STREAM_MEMORY.reset()
    def post(self, payload, token=TOKEN):
        conn = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        headers = {'Content-Type': 'application/json', 'X-Device-Token': token}
        conn.request('POST', '/stream/observe', json.dumps(payload), headers)
        resp = conn.getresponse()
        result = resp.status, json.loads(resp.read())
        conn.close()
        return result
    def body(self, seq=1, jpeg=JPEG, sess=SESSION):
        return {'request': 'stream_observe', 'session_id': sess,
                'sequence': seq, 'image_base64': base64.b64encode(jpeg).decode(),
                'frame': {'width': 450, 'height': 960, 'jpeg_quality': 75, 'profile': 1}}
    def test_demo_stream_receipt(self):
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN, 'OPENAI_API_KEY': ''}):
            code, result = self.post(self.body())
        self.assertEqual(code, 200)
        self.assertEqual(result['mode'], 'demo')
    def test_wrong_token(self):
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN}):
            code, _ = self.post(self.body(), 'wrong')
        self.assertEqual(code, 401)
    def test_replay_blocked(self):
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN, 'OPENAI_API_KEY': ''}):
            self.post(self.body())
            code, result = self.post(self.body())
        self.assertEqual(code, 409)
        self.assertEqual(result['error'], 'out_of_order_frame')
    def test_bad_profile(self):
        payload = self.body()
        payload['frame']['profile'] = -1
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN}):
            code, _ = self.post(payload)
        self.assertEqual(code, 400)
    def test_mock_openai_and_readability_escalation(self):
        response = {'summary': 'Мелкий текст не читается', 'readability':'unclear',
                    'visible_change': 'Изменился экран'}
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN, 'OPENAI_API_KEY': 'dummy'}):
            with patch('server.gpt_observe', return_value=response) as mocked:
                code, result = self.post(self.body())
        self.assertEqual(code, 200)
        self.assertEqual(result['mode'], 'openai')
        self.assertTrue(result['request_detail'])
        mocked.assert_called_once()
    def test_stream_no_remote_commands(self):
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN, 'OPENAI_API_KEY': ''}):
            code, result = self.post(self.body())
        self.assertEqual(code, 200)
        self.assertIsNone(result['action'])
    def test_large_image_rejected(self):
        payload = self.body(jpeg=b'\xff\xd8' + b'a'*650_001 + b'\xff\xd9')
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN}):
            code, result = self.post(payload)
        self.assertEqual(code, 400)
        self.assertEqual(result['error'], 'expected_jpeg')

if __name__ == '__main__': unittest.main()
