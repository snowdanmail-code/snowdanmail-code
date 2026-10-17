"""Deterministic card arithmetic and read-only API regression fixtures."""
import json
import http.client
import threading
from http.server import ThreadingHTTPServer
import unittest
from unittest.mock import patch
import os
from arc_poker_math.holdem import (parse_cards,rank_five,evaluate_seven,best_hand,
                                   equity_vs_random,pot_odds,estimate_pot_ev,InvalidCards)
from arc_vision.consistency import assess_screen
from server import ApiHandler


class PokerMathTests(unittest.TestCase):
    def test_all_hand_categories(self):
        cases=[
            ('As Kd Qc Jc 9s',0), ('As Ad Kc Jd 9h',1),
            ('As Ad Kc Kd 9h',2), ('As Ad Ah Kd 9h',3),
            ('As 2d 3c 4h 5s',4), ('Ah Kh 9h 5h 2h',5),
            ('As Ad Ah Kd Kh',6), ('As Ad Ah Ac Kh',7),
            ('9h Th Jh Qh Kh',8),
        ]
        for card_str,expected in cases:
            with self.subTest(category=expected):
                self.assertEqual(rank_five(card_str.split())[0],expected)

    def test_wheel_is_five_high_not_ace_high(self):
        wheel=rank_five('As 2d 3c 4h 5s'.split())
        six_high=rank_five('2s 3d 4c 5h 6s'.split())
        self.assertEqual(wheel,(4,5))
        self.assertGreater(six_high,wheel)

    def test_tie_breakers(self):
        self.assertGreater(rank_five('As Ad Kd Qc Jh'.split()),
                           rank_five('Ks Kd Qh Jc Th'.split()))
        self.assertGreater(rank_five('Ah Kh 9h 5h 2h'.split()),
                           rank_five('Ad Kd 8d 5d 2d'.split()))
        self.assertEqual(rank_five('As Kd Qh Jc Ts'.split()),
                         rank_five('Ac Kh Qd Js Tc'.split()))

    def test_showdown_from_user_shared_completed_hand_fixtures(self):
        examples=[
          (['Kc','8h'],['2d','Ks','6c','6s','6h'],'full_house'),
          (['5h','7h'],['3s','5d','Js','3d','As'],'two_pair'),
          (['Qd','4d'],['2h','Ts','Qc','Jc','Qs'],'three_of_a_kind'),
          (['Qc','Qs'],['Qd','2s','Ks','4c','Kc'],'full_house'),
          (['5c','8s'],['3s','2s','3h','Ts','Qd'],'one_pair'),
        ]
        for hero,board,want in examples:
            with self.subTest(hero=hero):
                self.assertEqual(best_hand(hero,board)['category'],want)

    def test_7_card_best_five(self):
        self.assertEqual(evaluate_seven('Ah Kh Qh Jh Th 2c 2s'.split()),(8,14))
        self.assertEqual(evaluate_seven('As Ks Qs Js Ts'.split()),(8,14))

    def test_duplicates_invalid_and_omaha_not_accepted(self):
        for cards in [['As','As'],['Ac','Ah','Ad'],['Ac','AA'],['As','10z']]:
            with self.assertRaises(InvalidCards):parse_cards(cards,allowed_counts={2})
        with self.assertRaises(InvalidCards):best_hand(['As','Kd'],['As','2c','3d'])
        with self.assertRaises(InvalidCards):equity_vs_random(['As','Kd','Qd','Jc'])

    def test_equity_is_exact_on_river(self):
        # Royal flush for hero only, cannot be beaten or tied by another hand.
        res=equity_vs_random(['As','Ks'],['Qs','Js','Ts','2d','3c'])
        self.assertEqual(res['method'],'exact_river')
        self.assertEqual(res['samples'],990)
        self.assertEqual(res['equity'],1.0)
        self.assertIsNone(res['action'])

    def test_board_plays_all_tie(self):
        res=equity_vs_random(['2c','3d'],['As','Ks','Qs','Js','Ts'])
        self.assertEqual(res['equity'],0.5)
        self.assertEqual(res['tie_probability'],1.0)

    def test_monte_carlo_repeatable_and_not_strategy(self):
        x=equity_vs_random(['Qd','4d'],['2h','Ts','Qc'],samples=70,seed=42)
        y=equity_vs_random(['Qd','4d'],['2h','Ts','Qc'],samples=70,seed=42)
        self.assertEqual(x,y)
        self.assertTrue(0<=x['equity']<=1)
        self.assertIn('uniform_random_opponent',x['assumption'])

    def test_pot_odds_and_ev_are_descriptive_only(self):
        self.assertAlmostEqual(pot_odds(.14,.06),.3)
        self.assertAlmostEqual(estimate_pot_ev(.14,.06,.3)['ev_chips'],0)
        self.assertIsNone(estimate_pot_ev(.14,.06,.3)['action'])
        for bad in [-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):pot_odds(bad,1)

    def test_screen_consistency(self):
        good={'screen':'action_controls','variant':'holdem_nl',
              'hero_cards':['Qd','4d'],'board_cards':['2h','Ts','Qc'],'pot':.11,
              'is_hero_turn':True, 'visible_buttons':['check']}
        result=assess_screen(good)
        self.assertEqual(result['quality'],'consistent')
        self.assertTrue(result['safe_to_infer_cards'])
        self.assertFalse(assess_screen(good,is_overlay=True)['safe_to_infer_cards'])
        duplicate={**good,'hero_cards':['Qc','4d']}
        self.assertEqual(assess_screen(duplicate)['quality'],'rejected')
        invalid={**good,'board_cards':['2h','Ts']}
        self.assertEqual(assess_screen(invalid)['quality'],'rejected')
        no_replay={**good,'screen':'replay'}
        self.assertFalse(assess_screen(no_replay)['safe_to_infer_cards'] if 'safe_to_infer_cards' in assess_screen(no_replay) else False)

class PokerMathHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.port=cls.http.server_port
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close()

    def fetch(self,payload,token='math-research-token-123'):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=30)
        headers={'Content-Type':'application/json','X-Device-Token':token}
        conn.request('POST','/math/equity',json.dumps(payload).encode(),headers)
        result=conn.getresponse()
        status,body=result.status,json.loads(result.read())
        conn.close()
        return status,body

    def setUp(self):
        patcher=patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'math-research-token-123'})
        patcher.start();self.addCleanup(patcher.stop)

    def test_authenticated_read_only_math(self):
        data={'request':'math_equity','hero_cards':['As','Ks'],
              'board_cards':['Qs','Js','Ts','2d','3c'],'samples':50,'seed':5}
        status,r=self.fetch(data)
        self.assertEqual(status,200)
        self.assertEqual(r['equity'],1.0)
        self.assertFalse(r['money_actions_enabled'])
        self.assertIsNone(r['action'])

    def test_missing_token_and_nonmatching_game_cards_fail(self):
        data={'request':'math_equity','hero_cards':['As','As'],
              'board_cards':[],'samples':50,'seed':1}
        self.assertEqual(self.fetch(data,'wrong-token')[0],401)
        self.assertEqual(self.fetch(data)[0],422)
        self.assertEqual(self.fetch({**data,'samples':3000})[0],400)

if __name__=='__main__':unittest.main()
