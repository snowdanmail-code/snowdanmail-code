"""Offline capture diagnostics, deliberately never requests an AI completion."""
import base64
from io import BytesIO
import http.client
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arc_offline_inspect import inspect_jpeg, InvalidOfflineFrame
from server import ApiHandler

TOKEN = 'v22-only-offline-diagnostics-token'


def jpeg(width=640, height=960, color=(100, 120, 140)):
    out = BytesIO()
    Image.new('RGB', (width, height), color).save(out, 'JPEG', quality=75)
    return out.getvalue()


class OfflineInspectorUnitTests(unittest.TestCase):
    def test_valid_jpeg_and_no_action(self):
        report = inspect_jpeg(jpeg())
        self.assertEqual((report['width'], report['height']), (640, 960))
        self.assertEqual(report['mode'], 'offline_capture_diagnostics')
        self.assertIsNone(report['action'])
        self.assertFalse(report['uses_openai_api'])
        self.assertFalse(report['uses_chatgpt_subscription'])
        self.assertFalse(report['money_actions_enabled'])
        self.assertIn('low_contrast', report['quality_flags'])

    def test_reject_fake_jpeg_markers(self):
        with self.assertRaises(InvalidOfflineFrame):
            inspect_jpeg(b'\xff\xd8fake\xff\xd9')

    def test_reject_small_image(self):
        with self.assertRaisesRegex(InvalidOfflineFrame, 'unsupported_dimensions'):
            inspect_jpeg(jpeg(32, 32))

    def test_reject_oversized_image(self):
        with self.assertRaisesRegex(InvalidOfflineFrame, 'unsupported_dimensions'):
            inspect_jpeg(jpeg(4100, 64))

    def test_reject_truncated_image(self):
        data = jpeg()
        with self.assertRaises(InvalidOfflineFrame):
            inspect_jpeg(data[:100] + b'\xff\xd9')

    def test_does_not_write_to_disk(self):
        with patch('builtins.open', side_effect=AssertionError('disk access forbidden')):
            self.assertEqual(inspect_jpeg(jpeg())['provider'], 'local_pillow')


class OfflineInspectorHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), ApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def request(self, payload, token=TOKEN):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['X-Device-Token'] = token
        conn.request('POST', '/offline/inspect', body=json.dumps(payload), headers=headers)
        r = conn.getresponse()
        code, body = r.status, json.loads(r.read())
        conn.close()
        return code, body

    def test_http_local_mode_even_when_api_key_exists(self):
        payload = {'request': 'offline_inspect', 'image_base64': base64.b64encode(jpeg()).decode()}
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN, 'OPENAI_API_KEY': 'must-not-use'}):
            with patch('server.analyze_with_openai', side_effect=AssertionError('network API forbidden')):
                code, body = self.request(payload)
        self.assertEqual(code, 200)
        self.assertEqual(body['mode'], 'offline_capture_diagnostics')
        self.assertIsNone(body['action'])

    def test_http_requires_token(self):
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN}):
            code, body = self.request({'request': 'offline_inspect'}, token=None)
        self.assertEqual(code, 401)

    def test_http_rejects_extra_fields(self):
        payload = {'request': 'offline_inspect', 'image_base64': base64.b64encode(jpeg()).decode(), 'action': 'bet'}
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN}):
            code, body = self.request(payload)
        self.assertEqual((code, body['error']), (400, 'offline_invalid_fields'))

    def test_http_rejects_corrupted_frame(self):
        payload = {'request': 'offline_inspect', 'image_base64': base64.b64encode(b'\xff\xd8bad\xff\xd9').decode()}
        with patch.dict(os.environ, {'ARC_DEVICE_TOKEN': TOKEN}):
            code, body = self.request(payload)
        self.assertEqual((code, body['error']), (422, 'invalid_or_truncated_jpeg'))


if __name__ == '__main__':
    unittest.main()
