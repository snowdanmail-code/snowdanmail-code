import unittest
from pathlib import Path
import cv2
import numpy as np
from arc_turn.stopwatch import StopwatchCue

class StopwatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.reader=StopwatchCue()
    @staticmethod
    def example(icon=True):
        im=np.full((1536,709,3), (35,35,38),np.uint8)
        if icon:
            glyph=cv2.imread(str(Path(__file__).resolve().parents[1]/'arc_turn/assets/stopwatch_glyph_v1.png'))
            im[1315:1404,531:625]=glyph
        return im
    def test_icon_detected_but_seconds_never_trusted(self):
        result=self.reader.read(self.example(),screen_state='live_table')
        self.assertEqual(result['cue'],'STOPWATCH_ICON_CANDIDATE')
        self.assertIsNone(result['seconds_remaining'])
        self.assertFalse(result['timer_verified'])
        self.assertFalse(result['money_actions_enabled'])
    def test_two_android_screen_sizes(self):
        frame=cv2.resize(self.example(),(1080,2340))
        result=self.reader.read(frame,screen_state='live_table')
        self.assertEqual(result['cue'],'STOPWATCH_ICON_CANDIDATE')
        self.assertIsNone(result['seconds_remaining'])
    def test_no_icon_abstain(self):
        result=self.reader.read(self.example(False),screen_state='live_table')
        self.assertEqual(result['cue'],'NO_RELIABLE_STOPWATCH_ICON')
    def test_blocked_scene(self):
        for s in ['replay','showdown','menu','overlay','disconnected','lobby','session_history']:
            with self.subTest(s=s):
                self.assertEqual(self.reader.read(self.example(),screen_state=s)['cue'],'BLOCKED_SCENE')
    def test_geometry_and_validation(self):
        self.assertEqual(self.reader.read(np.zeros((100,100,3),np.uint8))['cue'],'UNSUPPORTED_GEOMETRY')
        with self.assertRaises(ValueError):self.reader.read(None)
        with self.assertRaises(ValueError):StopwatchCue(threshold=.2)
if __name__=='__main__':unittest.main()
