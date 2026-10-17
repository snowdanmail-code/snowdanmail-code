import json
import os
from pathlib import Path
import tempfile
import unittest
from arc_vision.dataset import validate_manifest
from arc_vision.ui_policy import FrameCategory, interpret_frame, can_review_history

FIXTURES = Path(__file__).resolve().parents[2] / "datasets" / "capture_20261017"

class VideoFixtureTests(unittest.TestCase):
    def test_fixtures_integrity(self):
        self.assertEqual(validate_manifest(FIXTURES), 18)

    def test_overlays_never_interpreted_as_active_game(self):
        for kind in [FrameCategory.OVERLAY_SESSION_STATS, FrameCategory.OVERLAY_HAND_HISTORY,
                     FrameCategory.OVERLAY_WAITLIST]:
            self.assertEqual(interpret_frame(kind)["status"], "OVERLAY")
            self.assertFalse(interpret_frame(kind)["allow_active_commands"])

    def test_connection_replay_unknown_never_authorize(self):
        self.assertEqual(interpret_frame(FrameCategory.ACTIVE_ACTION, playback_mode=True)["status"], "REPLAY")
        self.assertEqual(interpret_frame(FrameCategory.ACTIVE_ACTION, connection_ok=False)["status"], "CONNECTION_LOST")
        self.assertEqual(interpret_frame(FrameCategory.UNKNOWN)["status"], "UNKNOWN")

    def test_history_review_requires_complete_exit(self):
        self.assertFalse(can_review_history(confirmed_zero_open_tables=False, any_active_session=False, state_is_known=True))
        self.assertFalse(can_review_history(confirmed_zero_open_tables=True, any_active_session=True, state_is_known=True))
        self.assertFalse(can_review_history(confirmed_zero_open_tables=True, any_active_session=False, state_is_known=False))
        self.assertTrue(can_review_history(confirmed_zero_open_tables=True, any_active_session=False, state_is_known=True))

    def test_dataset_are_reviewed_samples_not_training_claims(self):
        data=json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(all(e["annotation_method"] == "manual_visual_review" for e in data["entries"]))
        self.assertFalse(any(s["included_in_archive"] for s in data["sources"].values()))

if __name__ == "__main__": unittest.main()
