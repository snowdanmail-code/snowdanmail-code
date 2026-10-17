import base64
from http.server import ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lobby_agent import validate_screen, rank_tables, buyin_preview, InvalidScreen, gpt_read_screen
from server import ApiHandler


def sample(screen='cash_lobby'):
    return {
        'screen':screen,'confidence':.99,'variant':'holdem_nl',
        'bankroll':None,'buyin_min':None,'buyin_max':None,'buyin_selected':None,
        'small_blind':None,'big_blind':None,'auto_rebuy_enabled':None,
        'is_hero_turn':None, 'hero_name':None, 'hero_stack':None,
        'hero_cards':[], 'board_cards':[], 'pot':None, 'action_timer_seconds':None,
        'visible_buttons':[], 'rows':[], 'notes':'',
    }


def row(name, *, variant='holdem_nl',taken=3,total=6,big=.02,minimum=.4,maximum=2,small=.01):
    return {'name':name,'variant':variant,'seats_total':total,'seats_taken':taken,
            'small_blind':small,'big_blind':big,'buyin_min':minimum,
            'buyin_max':maximum,'average_pot':.5}


class PokerScreenTests(unittest.TestCase):
    def test_accept_nulls(self):
        self.assertEqual(validate_screen(sample())['screen'],'cash_lobby')
    def test_missing_field_rejected(self):
        value=sample();value.pop('notes')
        with self.assertRaises(InvalidScreen):validate_screen(value)
    def test_reject_extra_model_command(self):
        value=sample();value['tap_at']=[.5,.5]
        with self.assertRaises(InvalidScreen):validate_screen(value)
    def test_negative_bankroll_rejected(self):
        value=sample();value['bankroll']=-1
        with self.assertRaises(InvalidScreen):validate_screen(value)
    def test_confidence_bounds(self):
        value=sample();value['confidence']=1.01
        with self.assertRaises(InvalidScreen):validate_screen(value)
    def test_invalid_seats(self):
        value=sample();value['rows']=[row('x',taken=7,total=6)]
        with self.assertRaises(InvalidScreen):validate_screen(value)
    def test_omaha_excluded(self):
        v=sample();v['rows']=[row('PLO',variant='omaha_pl')]
        self.assertEqual(rank_tables(v,bankroll=50)['recommended'],[])
    def test_unknown_bankroll_denies_selection(self):
        v=sample();v['rows']=[row('NL2')]
        self.assertEqual(rank_tables(v)['reason'],'bankroll_unknown')
    def test_occupied_excluded(self):
        v=sample();v['rows']=[row('Full',taken=6,total=6)]
        self.assertEqual(rank_tables(v,bankroll=50)['recommended'],[])
    def test_missing_big_blind_excluded(self):
        v=sample();v['rows']=[row('NoBlind',big=None)]
        self.assertEqual(rank_tables(v,bankroll=50)['recommended'],[])
    def test_cheapest_first(self):
        v=sample();v['rows']=[row('NL4',big=.04,minimum=1.60),row('NL2',big=.02,minimum=.4)]
        chosen=rank_tables(v,bankroll=100)['recommended']
        self.assertEqual([v['table'] for v in chosen],['NL2','NL4'])
    def test_no_available_table_with_user_427(self):
        v=sample();v['rows']=[row('California #2',big=.04,minimum=1.60)]
        result=rank_tables(v,bankroll=4.27)
        self.assertFalse(result['automatic_entry'])
        self.assertEqual(result['recommended'],[])
    def test_buyin_427_ratio(self):
        v=sample('buyin_dialog');v.update(bankroll=4.27,buyin_min=1.60,buyin_max=4.0,buyin_selected=1.60)
        result=buyin_preview(v)
        self.assertEqual(result['minimum_share_of_balance'],.3747)
        self.assertIsNone(result['recommended_amount'])
        self.assertTrue(result['risk_limit_exceeded'])
        self.assertFalse(result['automatic_confirmation'])
    def test_rebuy_label_does_not_imply_on(self):
        v=sample('buyin_dialog');v['auto_rebuy_enabled']=None
        self.assertIsNone(validate_screen(v)['auto_rebuy_enabled'])
    def test_buyin_selected_above_max_denied(self):
        v=sample('buyin_dialog');v.update(buyin_min=1.60,buyin_max=4.0,buyin_selected=4.50)
        with self.assertRaises(InvalidScreen):validate_screen(v)
    def test_observe_without_lobby_does_not_select(self):
        self.assertEqual(rank_tables(sample('raise_panel'),bankroll=50)['reason'],'not_lobby')
    def test_rank_does_not_mutate_input(self):
        v=sample();v['rows']=[row('NL2')];prev=json.dumps(v,sort_keys=True)
        rank_tables(v,bankroll=50)
        self.assertEqual(json.dumps(v,sort_keys=True),prev)
    def test_manifest_regions_in_bounds(self):
        root=Path(__file__).resolve().parents[1]
        raw=json.loads((root/'screenshots_manifest.json').read_text())
        w=raw['canvas']['width'];h=raw['canvas']['height']
        self.assertEqual(len(raw['screens']),7)
        for image in raw['screens']:
            self.assertIn(image['state'],['cash_lobby','buyin_dialog','table_playing','table_waiting',
                                          'action_controls','raise_panel','showdown'])
            for r in image['regions'].values():
                x1,y1,x2,y2=r
                self.assertTrue(0<=x1<x2<=w and 0<=y1<y2<=h)
    def test_gpt_schema_has_no_actions(self):
        from lobby_agent import SCREEN_SCHEMA
        self.assertNotIn('tap_at',SCREEN_SCHEMA['properties'])
        self.assertNotIn('wager_amount',SCREEN_SCHEMA['properties'])


class PokerScreenApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
    def post(self,token='sample-secret-token-128'):
        body=json.dumps({'request':'poker_screen','image_base64':base64.b64encode(b'\xff\xd8test\xff\xd9').decode()})
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        conn.request('POST','/poker/screen',body,headers={'X-Device-Token':token,
                                                         'Content-Type':'application/json'})
        response=conn.getresponse();data=json.loads(response.read());code=response.status;conn.close()
        return code,data
    def test_requires_api_key(self):
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'sample-secret-token-128','OPENAI_API_KEY':''}):
            code,data=self.post()
        self.assertEqual(code,503)
    def test_returns_lobby_only_no_gesture(self):
        v=sample();v['rows']=[row('NL2')]
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'sample-secret-token-128','OPENAI_API_KEY':'fake'}):
            with patch('server.gpt_read_screen',return_value=v):
                code,data=self.post()
        self.assertEqual(code,200)
        self.assertIsNone(data['action'])
        self.assertFalse(data['money_actions_enabled'])
        self.assertFalse(data['recommendation']['automatic_entry'])
    def test_invalid_screen_returns_422(self):
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'sample-secret-token-128','OPENAI_API_KEY':'fake'}):
            with patch('server.gpt_read_screen',side_effect=InvalidScreen('not_readable')):
                code,data=self.post()
        self.assertEqual(code,422)
        self.assertEqual(data['error'],'invalid_screen_observation')
    def test_deny_wrong_token(self):
        with patch.dict(os.environ,{'ARC_DEVICE_TOKEN':'sample-secret-token-128','OPENAI_API_KEY':'fake'}):
            code,_=self.post('wrong-token')
        self.assertEqual(code,401)


if __name__=='__main__': unittest.main()

class NavigationTests(unittest.TestCase):
    def test_lobby_to_table_path(self):
        from navigation_fsm import NavigationTracker
        n=NavigationTracker()
        for state in ('cash_lobby','buyin_dialog','table_waiting','action_controls','raise_panel','action_controls'):
            self.assertTrue(n.observe(state,0.99)['accepted'])
    def test_low_confidence_stops_transition(self):
        from navigation_fsm import NavigationTracker
        n=NavigationTracker()
        n.observe('cash_lobby',.99)
        self.assertFalse(n.observe('buyin_dialog',.7)['accepted'])
        self.assertEqual(n.state,'unknown')
    def test_impossible_transition_rejects(self):
        from navigation_fsm import NavigationTracker
        n=NavigationTracker();n.observe('buyin_dialog',.99)
        self.assertFalse(n.observe('raise_panel',.99)['accepted'])
    def test_hero_card_limit(self):
        v=sample();v['hero_cards']=['A♠','K♠','Q♠']
        with self.assertRaises(InvalidScreen):validate_screen(v)
