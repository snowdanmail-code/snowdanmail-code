import unittest
from decimal import Decimal
from post_session_reviewer import (
  PostSessionReviewer, ReviewGate, ReviewBlocked, InvalidHistory, pot_odds, parse_actions)


def sample_hand(actions=None, game='holdem_nl'):
    return {'hand_id':'145849652','game':game,'hero':'hero','actions':actions or [],'net_result':'-0.01'}


class TestReviewGate(unittest.TestCase):
    def setUp(self):
        self.g = ReviewGate(); self.r = PostSessionReviewer(self.g)
        self.g.entered_table('s1')

    def ready(self):
        self.g.exit_requested()
        self.g.table_close_confirmed('s1',confirmation_source='verified_table_closed')
        self.assertTrue(self.g.observe_my_tables(screen='my_tables',open_tables=0,confidence=0.99,is_fresh=True))

    def test_live_is_blocked(self):
        with self.assertRaises(ReviewBlocked): self.r.analyze('s1',[sample_hand()])

    def test_exit_requested_not_enough(self):
        self.g.exit_requested()
        with self.assertRaises(ReviewBlocked): self.r.analyze('s1',[])

    def test_bad_close_confirmation(self):
        self.g.exit_requested()
        with self.assertRaises(ReviewBlocked):
            self.g.table_close_confirmed('s1',confirmation_source='back_to_lobby')

    def test_table_closed_but_not_verified_empty(self):
        self.g.exit_requested()
        self.g.table_close_confirmed('s1',confirmation_source='verified_table_closed')
        with self.assertRaises(ReviewBlocked): self.r.analyze('s1',[])

    def test_low_confidence_or_stale(self):
        self.g.exit_requested()
        self.g.table_close_confirmed('s1',confirmation_source='verified_table_closed')
        self.assertFalse(self.g.observe_my_tables(screen='my_tables',open_tables=0,confidence=.85,is_fresh=True))
        self.assertFalse(self.g.observe_my_tables(screen='my_tables',open_tables=0,confidence=1,is_fresh=False))
        with self.assertRaises(ReviewBlocked): self.r.analyze('s1',[])

    def test_other_tables_present(self):
        self.g.exit_requested()
        self.g.table_close_confirmed('s1',confirmation_source='verified_table_closed')
        self.assertFalse(self.g.observe_my_tables(screen='my_tables',open_tables=1,confidence=1,is_fresh=True))
        with self.assertRaises(ReviewBlocked): self.r.analyze('s1',[])

    def test_correct_full_exit(self):
        self.ready()
        report = self.r.analyze('s1',[sample_hand()])
        self.assertEqual(report['hands_reviewed'],1)
        self.assertFalse(report['hands'][0]['has_action_history'])

    def test_rejoin_invalidates(self):
        self.ready()
        self.g.entered_table('s2')
        with self.assertRaises(ReviewBlocked): self.r.analyze('s1',[])

    def test_disconnect_invalidates(self):
        self.ready()
        self.g.invalidate()
        with self.assertRaises(ReviewBlocked): self.r.analyze('s1',[])

    def test_omaha_excluded(self):
        self.ready()
        result=self.r.analyze('s1',[sample_hand(game='omaha_pl'),sample_hand()])
        self.assertEqual(result['hands_reviewed'],1)

    def test_non_finite_result_rejected(self):
        self.ready()
        bad = sample_hand()
        bad['net_result'] = 'NaN'
        with self.assertRaises(InvalidHistory): self.r.analyze('s1', [bad])

    def test_actions_preflop_vpip_and_pfr(self):
        self.ready()
        actions=[
          {'street':'preflop','player':'hero','action':'big_blind','amount':'0.02'},
          {'street':'preflop','player':'hero','action':'raise','amount':'0.04'},
          {'street':'flop','player':'hero','action':'check','amount':'0.00'}]
        result=self.r.analyze('s1',[sample_hand(actions)])
        self.assertTrue(result['hands'][0]['hero_vpip_observed'])
        self.assertTrue(result['hands'][0]['hero_pfr_observed'])

    def test_blind_only_not_vpip(self):
        self.ready()
        actions=[{'street':'preflop','player':'hero','action':'big_blind','amount':'0.02'}]
        self.assertFalse(self.r.analyze('s1',[sample_hand(actions)])['hands'][0]['hero_vpip_observed'])

    def test_invalid_actions(self):
        with self.assertRaises(InvalidHistory):
            parse_actions([{'street':'river','player':'hero','action':'raise','amount':'0.1'},
                           {'street':'flop','player':'hero','action':'call','amount':'0.2'}])
        with self.assertRaises(InvalidHistory):
            parse_actions([{'street':'flop','player':'hero','action':'fold','amount':'0.1'}])

    def test_pot_odds(self):
        self.assertEqual(pot_odds('0.13','0.06'),'31.58%')
        self.assertIsNone(pot_odds('0.13','0'))

    def test_bad_money(self):
        with self.assertRaises(InvalidHistory): pot_odds('NaN','0.01')
        with self.assertRaises(InvalidHistory): pot_odds('0.12','0.001')
        with self.assertRaises(InvalidHistory): pot_odds('0.12',0.01)


if __name__=='__main__': unittest.main()
