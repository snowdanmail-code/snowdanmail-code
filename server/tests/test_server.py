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
from server import ApiHandler

TOKEN = "this-is-a-test-token-12345"
JPEG = b"\xff\xd8" + b"test-image" + b"\xff\xd9"


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), ApiHandler)
        cls.port = cls.httpd.server_port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def fetch(self, method="GET", path="/health", payload=None, token=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Device-Token"] = token
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        status, body = resp.status, json.loads(resp.read())
        conn.close()
        return status, body

    def test_versions_readonly_requires_token_and_configuration(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "ARC_VERSION_REGISTRY_DIR": ""}):
            status, _ = self.fetch("GET", "/versions")
            self.assertEqual(status, 401)
            status, out = self.fetch("GET", "/versions", token=TOKEN)
            self.assertEqual(status, 503)
            self.assertEqual(out['error'], 'registry_not_configured')
        import tempfile
        from arc_versions.registry import VersionRegistry
        with tempfile.TemporaryDirectory() as d:
            VersionRegistry(d)
            with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "ARC_VERSION_REGISTRY_DIR": d}):
                status, out = self.fetch("GET", "/versions", token=TOKEN)
            self.assertEqual(status, 200)
            self.assertEqual(out['checkpoints'], [])

    def test_versions_endpoint_cannot_mutate(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "ARC_VERSION_REGISTRY_DIR": d}):
                status, _ = self.fetch("POST", "/versions", {}, token=TOKEN)
                self.assertEqual(status, 404)

    def test_health(self):
        status, data = self.fetch()
        self.assertEqual(status, 200)
        self.assertFalse(data["actions_enabled"])

    def test_deny_without_token(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            status, _ = self.fetch("POST", "/analyze", {"request": "describe"})
        self.assertEqual(status, 401)

    def test_demo_image_roundtrip(self):
        req = {"request": "describe", "image_base64": base64.b64encode(JPEG).decode()}
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            status, data = self.fetch("POST", "/analyze", req, TOKEN)
        self.assertEqual(status, 200)
        self.assertEqual(data["mode"], "demo")
        self.assertIsNone(data["action"])

    def test_block_arbitrary_actions(self):
        req = {"request": "tap", "image_base64": base64.b64encode(JPEG).decode()}
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN}):
            status, _ = self.fetch("POST", "/analyze", req, TOKEN)
        self.assertEqual(status, 400)
        status, _ = self.fetch("POST", "/tap", req, TOKEN)
        self.assertEqual(status, 404)

    def test_invalid_image(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN}):
            status, _ = self.fetch("POST", "/analyze", {"request": "describe", "image_base64": "bad"}, TOKEN)
        self.assertEqual(status, 400)

    def test_poker_denied_without_model_key(self):
        req={"request":"poker_decide","session_id":"test-session-123","sequence":1,
             "image_base64":base64.b64encode(JPEG).decode()}
        with patch.dict(os.environ,{"ARC_DEVICE_TOKEN":TOKEN,"OPENAI_API_KEY":""}):
            code, out=self.fetch("POST","/poker/decide",req,TOKEN)
        self.assertEqual(code,503)
        self.assertEqual(out["error"],"model_key_missing")

    def test_poker_no_real_action_without_arm_flag(self):
        req={"request":"poker_decide","session_id":"test-session-456","sequence":1,
             "image_base64":base64.b64encode(JPEG).decode()}
        sample={"action":"call","observed_cost":8.0,"observed_stack":100.0,
                "is_hero_turn":True,"is_table_visible":True,"readability":"clear",
                "confidence":0.99,"street":"flop","reason":"test"}
        with patch.dict(os.environ,{"ARC_DEVICE_TOKEN":TOKEN,"OPENAI_API_KEY":"mock-key",
                                    "ARC_ENABLE_POKER_ACTIONS":"0","ARC_MAX_SINGLE_WAGER_CHIPS":"20",
                                    "ARC_MAX_SESSION_WAGER_CHIPS":"40"}):
            with patch("server.gpt_poker_plan",return_value=sample):
                code,out=self.fetch("POST","/poker/decide",req,TOKEN)
        self.assertEqual(code,200)
        self.assertEqual(out["action"],"wait")
        self.assertFalse(out["enabled"])

    def test_poker_armed_call_is_checked_and_counted(self):
        req={"request":"poker_decide","session_id":"test-session-789","sequence":1,
             "image_base64":base64.b64encode(JPEG).decode()}
        sample={"action":"call","observed_cost":8.0,"observed_stack":100.0,
                "is_hero_turn":True,"is_table_visible":True,"readability":"clear",
                "confidence":0.99,"street":"flop","reason":"test"}
        with patch.dict(os.environ,{"ARC_DEVICE_TOKEN":TOKEN,"OPENAI_API_KEY":"mock-key",
                                    "ARC_ENABLE_POKER_ACTIONS":"1","ARC_MAX_SINGLE_WAGER_CHIPS":"10",
                                    "ARC_MAX_SESSION_WAGER_CHIPS":"20"}):
            with patch("server.gpt_poker_plan",return_value=sample):
                code,out=self.fetch("POST","/poker/decide",req,TOKEN)
        self.assertEqual(code,200)
        self.assertEqual(out["action"],"call")
        self.assertEqual(out["charged_chips"],8)

    def test_openai_client_wired(self):
        req = {"request": "describe", "image_base64": base64.b64encode(JPEG).decode()}
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": "placeholder"}):
            with patch("server.analyze_with_openai", return_value="На экране кнопка.") as fn:
                status, data = self.fetch("POST", "/analyze", req, TOKEN)
                fn.assert_called_once()
        self.assertEqual(status, 200)
        self.assertEqual(data["mode"], "openai")
        self.assertEqual(data["summary"], "На экране кнопка.")


if __name__ == "__main__":
    unittest.main()
