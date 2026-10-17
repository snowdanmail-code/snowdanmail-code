"""Isolated checks for model contract and HTTP sandbox route."""
import base64
import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent import SCHEMA, ModelResultError, verify_plan, fake_demo_plan, decide_with_gpt
from server import ApiHandler

TOKEN = "this-is-a-test-token-12345"
JPEG = b"\xff\xd8" + b"demojpeg" + b"\xff\xd9"


class SandboxAgentTests(unittest.TestCase):
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

    def fetch(self, path="/demo/next", body=None, token=TOKEN):
        if body is None:
            body = self.payload(0)
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("POST", path, body=json.dumps(body), headers={
            "X-Device-Token": token, "Content-Type": "application/json",
        })
        resp = conn.getresponse()
        status, result = resp.status, json.loads(resp.read())
        conn.close()
        return status, result

    def payload(self, count):
        return {"request": "demo_next", "image_base64": base64.b64encode(JPEG).decode(),
                "sandbox_state": {"tap_count": count}}

    def ask(self, count=0, token=TOKEN):
        return self.fetch(body=self.payload(count), token=token)

    def test_without_key_returns_explicit_demo_mode(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            status, result = self.ask(0)
        self.assertEqual(status, 200)
        self.assertEqual(result["mode"], "demo")
        self.assertEqual(result["scope"], "own_app_only")
        self.assertEqual(result["action"], "tap_own_test_button")

    def test_demo_second_step_finishes(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            status, result = self.ask(1)
        self.assertEqual(status, 200)
        self.assertEqual(result["action"], "finish")

    def test_wrong_token_rejected(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN}):
            status, _ = self.ask(token="incorrect-secret")
        self.assertEqual(status, 401)

    def test_injected_foreign_action_rejected(self):
        with self.assertRaises(ModelResultError):
            verify_plan({"action": "tap_anywhere", "reason": "fake"}, 0)

    def test_place_bet_rejected(self):
        with self.assertRaises(ModelResultError):
            verify_plan({"action": "place_bet", "reason": "fake"}, 0)

    def test_open_browser_rejected(self):
        with self.assertRaises(ModelResultError):
            verify_plan({"action": "open_browser", "reason": "fake"}, 0)

    def test_coordinate_click_rejected(self):
        with self.assertRaises(ModelResultError):
            verify_plan({"action": "click_xy", "reason": "fake"}, 0)

    def test_repeat_touch_is_forced_to_finish(self):
        self.assertEqual(verify_plan({"action": "tap_own_test_button", "reason": "again"}, 1)["action"], "finish")

    def test_invalid_count_rejected(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            status, result = self.ask(99)
        self.assertEqual(status, 400)
        self.assertEqual(result["error"], "invalid_demo_state")

    def test_bool_count_rejected(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            status, _ = self.ask(True)
        self.assertEqual(status, 400)

    def test_missing_demo_state_rejected(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            body = self.payload(0)
            del body["sandbox_state"]
            status, _ = self.fetch(body=body)
        self.assertEqual(status, 400)

    def test_wrong_request_rejected(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            body = self.payload(0)
            body["request"] = "tap"
            status, _ = self.fetch(body=body)
        self.assertEqual(status, 400)

    def test_missing_image_rejected(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            body = self.payload(0)
            del body["image_base64"]
            status, _ = self.fetch(body=body)
        self.assertEqual(status, 400)

    def test_unsupported_path_rejected(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN}):
            status, _ = self.fetch(path="/action")
        self.assertEqual(status, 404)

    def test_openai_mock_path(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": "fake"}):
            with patch("server.decide_with_gpt", return_value={"action": "wait", "reason": "unclear"}) as decision:
                status, result = self.ask(0)
                decision.assert_called_once()
        self.assertEqual(status, 200)
        self.assertEqual(result["mode"], "openai")
        self.assertEqual(result["action"], "wait")

    def test_strict_schema_disallows_extra_actions(self):
        self.assertIs(SCHEMA["additionalProperties"], False)
        self.assertEqual(set(SCHEMA["properties"]["action"]["enum"]),
                         {"tap_own_test_button", "finish", "wait"})

    def test_not_dict_plan_rejected(self):
        with self.assertRaises(ModelResultError):
            verify_plan(["tap_own_test_button"], 0)

    def test_missing_action_rejected(self):
        with self.assertRaises(ModelResultError):
            verify_plan({"reason": "none"}, 0)

    def test_invalid_reason_rejected(self):
        with self.assertRaises(ModelResultError):
            verify_plan({"action": "finish", "reason": 123}, 0)

    def test_reason_truncated_to_200_chars(self):
        result = verify_plan({"action": "wait", "reason": "x" * 1000}, 0)
        self.assertEqual(len(result["reason"]), 200)

    def test_fake_demo_has_no_internet_dependency(self):
        self.assertEqual(fake_demo_plan(0)["action"], "tap_own_test_button")
        self.assertEqual(fake_demo_plan(1)["action"], "finish")

    def test_invalid_model_result_returns_422(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": "fake"}):
            with patch("server.decide_with_gpt", side_effect=ModelResultError("bad")):
                status, result = self.ask(0)
        self.assertEqual(status, 422)
        self.assertEqual(result["error"], "invalid_model_result")

    def test_post_to_analyze_not_agent_action(self):
        with patch.dict(os.environ, {"ARC_DEVICE_TOKEN": TOKEN, "OPENAI_API_KEY": ""}):
            status, _ = self.fetch(path="/analyze", body=self.payload(0))
        self.assertEqual(status, 400)

    def test_valid_finish_passthrough(self):
        self.assertEqual(verify_plan({"action": "finish", "reason": "done"}, 1)["action"], "finish")

    def test_valid_wait_passthrough(self):
        self.assertEqual(verify_plan({"action": "wait", "reason": "unclear"}, 0)["action"], "wait")

    def test_gpt_request_uses_schema_and_store_false(self):
        captured = {}
        class FakeHTTPResponse:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit):
                return json.dumps({"status": "completed", "output": [{
                    "type": "message", "content": [{"type": "output_text", "text":
                    '{"action":"wait","reason":"unclear"}'}]}]}).encode()
        def inspect(request, timeout):
            captured.update(json.loads(request.data))
            return FakeHTTPResponse()
        with patch("agent.urlopen", side_effect=inspect):
            plan = decide_with_gpt(JPEG, 0, "FAKE", "gpt-5-mini")
        self.assertEqual(plan["action"], "wait")
        self.assertIs(captured["store"], False)
        self.assertEqual(captured["text"]["format"]["type"], "json_schema")
        self.assertEqual(captured["text"]["format"]["strict"], True)
        self.assertEqual(captured["input"][0]["content"][1]["type"], "input_image")


if __name__ == "__main__":
    unittest.main()
