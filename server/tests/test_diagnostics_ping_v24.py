"""Authenticated read-only latency probe, no image and no money actions."""
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import ApiHandler

TOKEN = "offline-latency-probe-token"

class PingHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def fetch(self, path="/diagnostics/ping", token=None, method="GET", body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {}
        if token is not None:
            headers["X-Device-Token"] = token
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        code, headers, payload = response.status, dict(response.getheaders()), json.loads(response.read())
        conn.close()
        return code, headers, payload

    def test_auth_required(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN}):
            self.assertEqual(self.fetch()[0], 401)
            self.assertEqual(self.fetch(token="wrong-token")[0], 401)
            self.assertEqual(self.fetch(token=TOKEN)[0], 200)

    def test_reject_weak_server_token(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": "short"}):
            self.assertEqual(self.fetch(token="short")[0], 401)

    def test_readonly_offline_response(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            code, headers, payload = self.fetch(token=TOKEN)
        self.assertEqual(code, 200)
        self.assertEqual(payload["mode"], "offline_connection_diagnostic")
        self.assertFalse(payload["uses_openai_api"])
        self.assertFalse(payload["money_actions_enabled"])
        self.assertFalse(payload["image_processed"])
        self.assertIsNone(payload["action"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_reject_mutations_and_unknown_paths(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN}):
            self.assertEqual(self.fetch(method="POST", body='{"request":"ping"}', token=TOKEN)[0], 404)
            self.assertEqual(self.fetch(path="/diagnostics/ping?command=bet", token=TOKEN)[0], 404)

if __name__ == "__main__": unittest.main()
