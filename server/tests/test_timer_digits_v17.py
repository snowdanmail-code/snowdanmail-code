import unittest
from pathlib import Path
import cv2
import numpy as np
from arc_turn.timer_digits import TimerDigitReader, LabelStabilizer

FIX=Path(__file__).parent/'fixtures_timer'

class DigitReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader=TimerDigitReader()
        cls.thirty=cv2.imread(str(FIX/'label30_170.jpg'))
        cls.sixty=cv2.imread(str(FIX/'label60_170.jpg'))

    def test_30_from_crop(self):
        result=self.reader.read_crop(self.thirty)
        self.assertEqual(result['displayed_label_seconds'],30)
        self.assertEqual(result['status'],'DISPLAY_LABEL_READ')
        self.assertIsNone(result['seconds_remaining'])
        self.assertFalse(result['turn_verified'])
        self.assertFalse(result['money_actions_enabled'])

    def test_60_from_crop(self):
        result=self.reader.read_crop(self.sixty)
        self.assertEqual(result['displayed_label_seconds'],60)
        self.assertIsNone(result['seconds_remaining'])

    def test_neither_icon_nor_overlay(self):
        self.assertEqual(self.reader.read_crop(np.zeros((170,170,3),np.uint8))['status'],'NO_RELIABLE_TIMER')
        occluded=self.thirty.copy()
        occluded[80:120,48:105]=0
        self.assertNotEqual(self.reader.read_crop(occluded)['status'],'DISPLAY_LABEL_READ')

    def test_blocked_views_do_not_report_seconds(self):
        for scene in ('replay','menu','showdown','overlay','disconnected','lobby'):
            with self.subTest(scene=scene):
                result=self.reader.read_crop(self.thirty,screen_state=scene)
                self.assertEqual(result['status'],'BLOCKED_SCENE')
                self.assertIsNone(result['displayed_label_seconds'])

    def test_unsupported_input(self):
        self.assertEqual(self.reader.read_crop(np.zeros((20,40,3),np.uint8))['status'],'UNSUPPORTED_GEOMETRY')
        self.assertRaises(ValueError,TimerDigitReader,max_error=0.0)

    def test_full_frame_30_synthetic(self):
        im=np.full((1536,709,3),35,np.uint8)
        glyph=cv2.imread(str(Path(__file__).resolve().parents[1]/'arc_turn/assets/stopwatch_glyph_v1.png'))
        im[1315:1404,531:625]=glyph
        result=self.reader.read(im,screen_state='live_table')
        self.assertEqual(result['status'],'DISPLAY_LABEL_READ')
        self.assertEqual(result['displayed_label_seconds'],30)
        self.assertFalse(result['countdown_verified'])

    def test_full_no_timer_and_bad_input(self):
        im=np.full((1536,709,3),35,np.uint8)
        self.assertEqual(self.reader.read(im,screen_state='live_table')['status'],'NO_RELIABLE_TIMER')
        self.assertRaises(ValueError,self.reader.read,None)

class FastObserverIntegrationTests(unittest.TestCase):
    def test_read_only_fast_observation_exports_label(self):
        from arc_fastloop.observe import FastObserver
        from arc_fastloop.gate import FrameGate
        frame=np.full((1536,709,3),35,np.uint8)
        glyph=cv2.imread(str(Path(__file__).resolve().parents[1]/'arc_turn/assets/stopwatch_glyph_v1.png'))
        frame[1315:1404,531:625]=glyph
        ok,jpeg=cv2.imencode('.jpg',frame)
        self.assertTrue(ok)
        class Observer:
            def read(self,*a,**kw): return {'mode':'fixture'}
        result=FastObserver(observer=Observer(),gate=FrameGate(min_interval_ms=0)).observe(
            session_id='timer-fixture-v17',sequence=1,frame_age_ms=1,
            remaining_ms=None,jpeg=jpeg.tobytes(),screen_state='live_table')
        self.assertEqual(result['status'],'fresh_observation')
        self.assertEqual(result['timer_label']['displayed_label_seconds'],30)
        self.assertIsNone(result['timer_label']['seconds_remaining'])
        self.assertIsNone(result['action'])
        self.assertFalse(result['money_actions_enabled'])

class StabilizerTests(unittest.TestCase):
    def test_only_confirms_display_not_remaining(self):
        stab=LabelStabilizer()
        r={'status':'DISPLAY_LABEL_READ','displayed_label_seconds':30}
        self.assertIsNone(stab.update(session_id='s',sequence=1,captured_ms=1000,reading=r)['displayed_label_seconds'])
        result=stab.update(session_id='s',sequence=2,captured_ms=1100,reading=r)
        self.assertEqual(result['displayed_label_seconds'],30)
        self.assertFalse(result['timer_verified'])
        self.assertIsNone(result['seconds_remaining'])

    def test_conflict_and_disconnect_reset(self):
        stab=LabelStabilizer()
        t30={'status':'DISPLAY_LABEL_READ','displayed_label_seconds':30}
        t60={'status':'DISPLAY_LABEL_READ','displayed_label_seconds':60}
        stab.update(session_id='s',sequence=1,captured_ms=10,reading=t30)
        self.assertIsNone(stab.update(session_id='s',sequence=2,captured_ms=15,reading=t60)['displayed_label_seconds'])
        self.assertEqual(stab.update(session_id='s',sequence=3,captured_ms=20,reading=t60)['displayed_label_seconds'],60)
        self.assertIsNone(stab.update(session_id='s',sequence=4,captured_ms=30,reading={'status':'BLOCKED_SCENE'})['displayed_label_seconds'])
        self.assertIsNone(stab.update(session_id='s',sequence=5,captured_ms=100,reading=t60)['displayed_label_seconds'])
        self.assertIsNone(stab.update(session_id='s2',sequence=6,captured_ms=105,reading=t60)['displayed_label_seconds'])

    def test_out_of_order_does_not_replace_current_vote(self):
        stab=LabelStabilizer()
        r={'status':'DISPLAY_LABEL_READ','displayed_label_seconds':30}
        stab.update(session_id='s',sequence=10,captured_ms=100,reading=r)
        self.assertEqual(stab.update(session_id='s',sequence=9,captured_ms=110,reading=r)['status'],'OUT_OF_ORDER_IGNORED')
        self.assertEqual(stab.update(session_id='s',sequence=11,captured_ms=120,reading=r)['displayed_label_seconds'],30)

    def test_large_time_gap_resets(self):
        stab=LabelStabilizer()
        r={'status':'DISPLAY_LABEL_READ','displayed_label_seconds':30}
        stab.update(session_id='s',sequence=1,captured_ms=0,reading=r)
        self.assertIsNone(stab.update(session_id='s',sequence=2,captured_ms=4000,reading=r)['displayed_label_seconds'])

if __name__=='__main__':unittest.main()
