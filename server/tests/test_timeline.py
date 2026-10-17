import unittest
from arc_vision.timeline import HandTimeline

class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.tracker=HandTimeline()
        self.base={'hand_id':'145849582','variant':'holdem_nl',
                   'hero_cards':['5h','7h'],'board_cards':[]}

    def call(self,seq,phase,**overrides):
        data={**self.base,**overrides}
        return self.tracker.observe(frame_seq=seq,phase=phase,**data)

    def test_full_streets(self):
        self.assertEqual(self.call(1,'preflop')['status'],'accepted')
        self.assertEqual(self.call(2,'flop',board_cards=['3s','5d','Js'])['status'],'accepted')
        self.assertEqual(self.call(3,'turn',board_cards=['3s','5d','Js','3d'])['status'],'accepted')
        self.assertEqual(self.call(4,'river',board_cards=['3s','5d','Js','3d','As'])['status'],'accepted')
        self.assertEqual(self.call(5,'showdown',board_cards=['3s','5d','Js','3d','As'])['status'],'accepted')
        self.assertEqual(self.call(6,'preflop',hand_id='145849583',board_cards=[],hero_cards=['As','Kd'])['status'],'accepted')

    def test_reject_wrong_board_and_preserve_last_good_state(self):
        self.call(1,'flop',board_cards=['3s','5d','Js'])
        rejected=self.call(2,'turn',board_cards=['3s','4d','Js','3d'])
        self.assertEqual(rejected['reason'],'board_changed')
        self.assertEqual(rejected['frame_sequence'],1)
        self.assertEqual(self.call(3,'turn',board_cards=['3s','5d','Js','3d'])['status'],'accepted')

    def test_reject_hole_card_change(self):
        self.call(1,'preflop')
        self.assertEqual(self.call(2,'preflop',hero_cards=['5h','8h'])['reason'],'hero_cards_changed')

    def test_street_regression_and_wrong_board_length(self):
        self.call(1,'flop',board_cards=['3s','5d','Js'])
        self.assertEqual(self.call(2,'preflop')['reason'],'street_regressed')
        self.assertEqual(self.call(3,'turn',board_cards=['3s','5d','Js'])['reason'],'phase_board_mismatch')

    def test_lost_connection_and_overlay_force_resync(self):
        self.call(1,'preflop')
        self.assertEqual(self.call(2,'preflop',connected=False)['status'],'paused')
        self.assertEqual(self.call(3,'preflop')['status'],'needs_confirmation')
        self.assertEqual(self.call(4,'preflop')['status'],'accepted')
        self.assertEqual(self.call(5,'preflop',overlay=True)['reason'],'overlay')
        self.assertEqual(self.call(6,'preflop')['status'],'needs_confirmation')

    def test_replay_and_omaha_ignored(self):
        self.assertEqual(self.call(1,'preflop',playback=True)['status'],'paused')
        self.assertEqual(self.call(2,'preflop',variant='omaha_pl')['status'],'ignored')
        self.assertEqual(self.call(3,'preflop')['status'],'accepted')

    def test_duplicates_invalid(self):
        self.call(1,'preflop')
        self.assertEqual(self.call(1,'preflop')['status'],'rejected')
        self.assertEqual(self.call(2,'preflop',hero_cards=['Ah','Ah'])['status'],'rejected')

    def test_skipped_streets_allowed_for_sparse_video(self):
        self.assertEqual(self.call(1,'preflop')['status'],'accepted')
        self.assertEqual(self.call(2,'river',board_cards=['3s','5d','Js','3d','As'])['status'],'accepted')

if __name__=='__main__':unittest.main()
