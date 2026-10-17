import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "android/app/src/main/java/com/example/airemote"

class OperatorStopWiringTest(unittest.TestCase):
    def test_fail_closed_storage(self):
        src = (BASE / "OperatorStopStore.kt").read_text()
        self.assertIn("getBoolean(STOPPED, true)", src)
        self.assertIn(".putBoolean(STOPPED, true).commit()", src)
        self.assertIn(".putBoolean(STOPPED, false).commit()", src)

    def test_activity_persists_stop_before_service_command(self):
        src = (BASE / "MainActivity.kt").read_text()
        a = src.index("private fun emergencyStop()")
        b = src.index("private fun stopAgentCycle", a)
        body = src[a:b]
        self.assertLess(body.index("OperatorStopStore.stop(this)"), body.index("setAction(CaptureService.ACTION_STOP)"))
        self.assertIn("OperatorStopStore.armFromOperator", src)

    def test_capture_service_guards_starts(self):
        src = (BASE / "CaptureService.kt").read_text()
        for action in ("ACTION_START ->", "ACTION_STREAM_START, ACTION_FAST_START ->", "ACTION_POKER_START ->"):
            start = src.index(action)
            self.assertIn("OperatorStopStore.isStopped(this)", src[start:start+460])
        self.assertIn("OperatorStopStore.stop(this)", src)

    def test_gesture_service_guards_dispatch(self):
        src = (BASE / "DemoAccessibilityService.kt").read_text()
        self.assertIn("OperatorStopStore.isStopped(service)", src)
        self.assertIn("OperatorStopStore.isStopped(this)", src)
        self.assertIn("BuildConfig.EXTERNAL_GAME_ACTIONS_ENABLED", src)

if __name__ == "__main__": unittest.main()
