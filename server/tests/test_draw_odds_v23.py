"""v2.3 exact offline draw odds: math, contract and authentication."""
import http.client
import json
import os
import threading
import unittest
from http.server import ThreadingHTTPServer
from math import comb
from unittest.mock import patch

from arc_poker_math.draw_odds import draw_hit_odds
from arc_poker_math.holdem import InvalidCards
from server import ApiHandler


class DrawOddsMathTests(unittest.TestCase):
    def test_flop_nine_outs_exact(self):
        # 9 unseen hearts with four hearts exposed on hero+flop.
        out = draw_hit_odds(['Ah', 'Kh'], ['Qh', 'Jh', '2c'],
                            ['2h', '3h', '4h', '5h', '6h', '7h', '8h', '9h', 'Th'])
        self.assertEqual(out['unknown_cards'], 47)
        self.assertEqual(out['cards_to_come'], 2)
        self.assertAlmostEqual(out['hit_next_card_probability'], 9/47)
        self.assertAlmostEqual(out['hit_by_river_probability'], 1-comb(38,2)/comb(47,2))
        self.assertFalse(out['money_actions_enabled'])
        self.assertFalse(out['uses_openai_api'])
        self.assertIsNone(out['action'])

    def test_turn_nine_outs(self):
        out = draw_hit_odds(['Ah', 'Kh'], ['Qh', 'Jh', '2c', '3d'],
                            ['2h', '3h', '4h', '5h', '6h', '7h', '8h', '9h', 'Th'])
        self.assertEqual(out['unknown_cards'], 46)
        self.assertEqual(out['cards_to_come'], 1)
        self.assertAlmostEqual(out['hit_by_river_probability'], 9/46)
        self.assertAlmostEqual(out['hit_next_card_probability'], 9/46)

    def test_zero_outs(self):
        out=draw_hit_odds(['As','Ks'],['2d','3c','4h'],[])
        self.assertEqual(out['hit_by_river_probability'],0)

    def test_every_unseen_card(self):
        from arc_poker_math.holdem import DECK
        known=['As','Ks','2d','3c','4h']
        out=draw_hit_odds(known[:2],known[2:],[c for c in DECK if c not in known])
        self.assertEqual(out['hit_next_card_probability'],1)
        self.assertEqual(out['hit_by_river_probability'],1)

    def test_invalid_exposed_duplicate_and_bad_cards(self):
        cases=[(['As'],['2c','3d','4h'],[]),
               (['As','Ks'],['2c','3d'],[]),
               (['As','Ks'],['2c','3d','4h'],['As']),
               (['As','Ks'],['2c','3d','4h'],['5c','5c']),
               (['As','Ks'],['2c','3d','4h'],['ZZ']),
               (['As','Ks'],['2c','3d','4h'],'5c')]
        for hero,board,outs in cases:
            with self.subTest(hero=hero,board=board,outs=outs):
                with self.assertRaises((InvalidCards,ValueError)):
                    draw_hit_odds(hero,board,outs)

    def test_normalized_ten(self):
        out=draw_hit_odds(['10h','Kh'],['Qh','Jh','2c'],['Ah'])
        self.assertEqual(out['hero_cards'][0],'Th')
        self.assertEqual(out['outs_cards'][0],'Ah')

    def test_deterministic(self):
        args=(['As','Ks'],['2d','3c','4h'],['5s','6s'])
        self.assertEqual(draw_hit_odds(*args),draw_hit_odds(*args))


class DrawOddsHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        p=patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'draw-odds-token-123'})
        p.start()
        self.addCleanup(p.stop)
        self.good={'request':'math_draw_odds','hero_cards':['Ah','Kh'],
                   'board_cards':['Qh','Jh','2c'], 'outs_cards':['3h','4h']}

    def post(self,payload,token='draw-odds-token-123',path='/math/draw-odds'):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=10)
        c.request('POST',path,json.dumps(payload).encode(),{
            'X-Device-Token':token,'Content-Type':'application/json'})
        r=c.getresponse()
        status,body=r.status,json.loads(r.read())
        c.close()
        return status,body

    def test_success_without_openai(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            status,res=self.post(self.good)
        self.assertEqual(status,200)
        self.assertEqual(res['method'],'exact_hypergeometric')
        self.assertEqual(res['outs_count'],2)
        self.assertIsNone(res['action'])

    def test_reject_wrong_token(self):
        self.assertEqual(self.post(self.good,token='invalid')[0],401)

    def test_reject_extra_field(self):
        self.assertEqual(self.post({**self.good,'bet_amount':100})[0],400)

    def test_reject_wrong_task(self):
        self.assertEqual(self.post({**self.good,'request':'math_equity'})[0],400)

    def test_reject_visible_out(self):
        self.assertEqual(self.post({**self.good,'outs_cards':['Ah']})[0],422)

    def test_reject_malformed_payload(self):
        self.assertEqual(self.post({**self.good,'outs_cards':123})[0],422)


if __name__=='__main__':
    unittest.main()
