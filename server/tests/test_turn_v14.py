"""Pure offline tests for conservative 1win-like button colour cues.

Synthetic UI is intentionally not a real-money execution target.
"""
import unittest
import cv2
import numpy as np
from arc_turn import TurnCueReader,TurnCueTimeline
from arc_fastloop.gate import FrameGate
from arc_fastloop.observe import FastObserver


def frame(which='active', width=709,height=1536):
    img=np.full((height,width,3),(32,32,37),dtype=np.uint8)
    left,mid,right=(0.17,0.5,0.83)
    for x in (left,mid,right):
        cv2.rectangle(img,(int(width*(x-.09)),int(height*.915)),
                      (int(width*(x+.09)),int(height*.988)),(53,53,58),-1)
    colors={'left':(5,10,190),'middle':(20,145,15),'right':(5,160,190)}
    if which=='active':locs=('left','middle','right')
    elif which=='sizing':locs=('right',)
    elif which in ('preaction','empty'):locs=()
    elif which=='partial':locs=('left',)
    else:raise ValueError('which')
    for n,x in [('left',left),('middle',mid),('right',right)]:
        if n in locs:
            cv2.rectangle(img,(int(width*(x-.09)),int(height*.915)),
                          (int(width*(x+.09)),int(height*.988)),colors[n],-1)
    return img

class Clock:
    def __init__(self):self.value=100.
    def __call__(self):return self.value
    def add(self,x):self.value+=x

class TestTurnCueReader(unittest.TestCase):
    def setUp(self):self.reader=TurnCueReader()
    def test_three_button_colours_only_cue(self):
        r=self.reader.read_image(frame('active'),screen_state='live_table')
        self.assertEqual(r['cue'],'ACTIVE_COLOUR_TRIAD')
        self.assertFalse(r['turn_verified'])
        self.assertFalse(r['wager_enabled'])
        self.assertEqual(r['authorized_actions'],[])
    def test_preaction_not_turn(self):
        self.assertEqual(self.reader.read_image(frame('preaction'),screen_state='live_table')['cue'],
                         'NO_ACTIVE_COLOUR_CUES')
    def test_one_colour_insufficient(self):
        self.assertEqual(self.reader.read_image(frame('partial'),screen_state='live_table')['cue'],
                         'AMBIGUOUS_COLOURS')
    def test_right_button_is_not_turn_proof(self):
        r=self.reader.read_image(frame('sizing'),screen_state='raise_panel')
        self.assertEqual(r['cue'],'RIGHT_GOLD_ONLY')
        self.assertFalse(r['turn_verified'])
    def test_scene_conflict(self):
        self.assertEqual(self.reader.read_image(frame('sizing'),screen_state='live_table')['cue'],
                         'SCENE_CONFLICT')
    def test_replay_overlay_disconnected_block(self):
        for scene in ('replay','disconnected','menu','overlay','session_history','showdown'):
            with self.subTest(scene=scene):
                self.assertEqual(self.reader.read_image(frame('active'),screen_state=scene)['cue'],
                                 'BLOCKED_SCENE')
    def test_phone_resolution(self):
        self.assertEqual(self.reader.read_image(frame('active',1080,2340),screen_state='live_table')['cue'],
                         'ACTIVE_COLOUR_TRIAD')
    def test_unsupported_geometry(self):
        self.assertEqual(self.reader.read_image(np.zeros((100,120,3),dtype=np.uint8))['cue'],
                         'UNSUPPORTED_GEOMETRY')
    def test_bad_input(self):
        with self.assertRaises(ValueError):self.reader.read_image(None)
        with self.assertRaises(ValueError):self.reader.read_image(frame(),screen_state=None)

class TestTurnTimeline(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.track=TurnCueTimeline(now=self.clock)
        self.session='test-session-v14'
        self.active='ACTIVE_COLOUR_TRIAD'
    def update(self,n,cue=None,age=10,remaining=30000):
        return self.track.observe(session_id=self.session,sequence=n,
            cue=cue or self.active,frame_age_ms=age,remaining_ms=remaining)
    def test_first_is_pending_second_stable_after_dwell(self):
        self.assertEqual(self.update(1)['status'],'PENDING_SECOND_OBSERVATION')
        self.clock.add(.2)
        second=self.update(2)
        self.assertEqual(second['status'],'VISUAL_PATTERN_STABLE_NOT_VERIFIED')
        self.assertFalse(second['verified_turn'])
        self.assertIsNone(second['action'])
        self.assertFalse(second['money_actions_enabled'])
    def test_two_immediate_frames_not_stable(self):
        self.update(1);self.clock.add(.02)
        self.assertEqual(self.update(2)['status'],'PENDING_SECOND_OBSERVATION')
    def test_gap_forces_fresh_state(self):
        self.update(1);self.clock.add(1.6)
        self.assertEqual(self.update(2)['status'],'PENDING_SECOND_OBSERVATION')
    def test_colour_loss_resets(self):
        self.update(1);self.clock.add(.3);self.update(2)
        self.assertEqual(self.update(3,'NO_ACTIVE_COLOUR_CUES')['status'],'NO_STABLE_ACTIVE_CUES')
        self.assertEqual(self.update(4)['status'],'PENDING_SECOND_OBSERVATION')
    def test_unsafe_scene_and_time(self):
        self.assertEqual(self.update(1,'BLOCKED_SCENE')['status'],'NO_READABLE_TURN')
        self.assertEqual(self.update(2,age=1600)['status'],'STALE')
        self.assertEqual(self.update(3,remaining=2500)['status'],'LOW_TIME')
    def test_order_and_reset(self):
        self.update(1)
        self.assertEqual(self.update(1)['status'],'OUT_OF_ORDER')
        self.track.reset()
        self.assertEqual(self.update(1)['status'],'PENDING_SECOND_OBSERVATION')
    def test_capacity_and_expiration(self):
        t=TurnCueTimeline(now=self.clock,max_sessions=1,clear_after_seconds=1)
        t.observe(session_id='session-0001',sequence=1,cue=self.active,frame_age_ms=0,remaining_ms=30000)
        self.assertEqual(t.observe(session_id='session-0002',sequence=1,cue=self.active,frame_age_ms=0,remaining_ms=30000)['status'],'CAPACITY')
        self.clock.add(2)
        self.assertEqual(t.observe(session_id='session-0002',sequence=1,cue=self.active,frame_age_ms=0,remaining_ms=30000)['status'],'PENDING_SECOND_OBSERVATION')
    def test_invalid_data(self):
        with self.assertRaises(ValueError):self.update(True)
        with self.assertRaises(ValueError):self.update(1,remaining=-1)

class ObserverStub:
    def read(self,*args,**kwargs):return {'quality':'measured','action':None}

class IntegrationTest(unittest.TestCase):
    def test_integration_keeps_money_disabled(self):
        _,jpg=cv2.imencode('.jpg',frame())
        clock=Clock()
        obs=FastObserver(observer=ObserverStub(),
            gate=FrameGate(now=clock,min_interval_ms=0),
            turn_timeline=TurnCueTimeline(now=clock))
        a=obs.observe(session_id='integration-v14',sequence=1,frame_age_ms=10,
            remaining_ms=30000,jpeg=jpg.tobytes(),screen_state='live_table')
        self.assertEqual(a['status'],'fresh_observation')
        self.assertEqual(a['turn_cues']['cue'],'ACTIVE_COLOUR_TRIAD')
        self.assertEqual(a['turn_timeline']['status'],'PENDING_SECOND_OBSERVATION')
        self.assertFalse(a['money_actions_enabled'])
        self.assertIsNone(a['action'])
        clock.add(.22)
        _,jpg2=cv2.imencode('.jpg',frame('active')+np.uint8(1))
        b=obs.observe(session_id='integration-v14',sequence=2,frame_age_ms=10,
            remaining_ms=30000,jpeg=jpg2.tobytes(),screen_state='live_table')
        self.assertEqual(b['status'],'fresh_observation')
        self.assertEqual(b['turn_timeline']['status'],'VISUAL_PATTERN_STABLE_NOT_VERIFIED')
        self.assertFalse(b['turn_timeline']['verified_turn'])

if __name__=='__main__':unittest.main()
