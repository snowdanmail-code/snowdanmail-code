from http.server import ThreadingHTTPServer
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import ApiHandler
from test_runtime import make_registry,obs
from arc_runtime.adapter import from_gpt_screen
from lobby_agent import FIELDS

TOKEN='runtime-integration-token-123'

class RuntimeHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=ThreadingHTTPServer(('127.0.0.1',0),ApiHandler)
        cls.port=cls.http.server_port
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close()

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.mgr=make_registry(self.tmp.name)
        self.env=patch.dict(os.environ,{'ARC_DEVICE_TOKEN':TOKEN,
                                        'ARC_VERSION_REGISTRY_DIR':self.tmp.name,
                                        'ARC_RUNTIME_LAB':'1'})
        self.env.start();self.addCleanup(self.env.stop)

    def fetch(self,method,path,payload=None,token=TOKEN):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        headers={'Content-Type':'application/json'}
        if token:headers['X-Device-Token']=token
        c.request(method,path,body=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        rsp=c.getresponse();code=rsp.status;body=json.loads(rsp.read());c.close()
        return code,body

    def test_status_requires_auth(self):
        code,_=self.fetch('GET','/runtime/status',token='wrong')
        self.assertEqual(code,401)

    def test_status_uses_active_checkpoint(self):
        code,res=self.fetch('GET','/runtime/status')
        self.assertEqual(code,200)
        self.assertEqual(res['policy_name'],'baseline')
        self.assertFalse(res['money_actions_enabled'])

    def test_observation_returns_no_executable_action(self):
        data={'request':'runtime_observe','session_id':'session-alpha','scene':obs()}
        code,res=self.fetch('POST','/runtime/observe',data)
        self.assertEqual(code,200)
        self.assertIsNone(res['observation']['tap_command'])
        self.assertFalse(res['runtime']['autonomous_betting_enabled'])

    def test_observation_replay_blocked(self):
        data={'request':'runtime_observe','session_id':'session-alpha',
              'scene':obs(screen='replay',is_replay=True)}
        code,res=self.fetch('POST','/runtime/observe',data)
        self.assertEqual(code,200)
        self.assertEqual(res['observation']['recommendation'],'hold')

    def test_bad_observation_rejected(self):
        data={'request':'runtime_observe','session_id':'session-alpha','scene':obs(seated_players=2,active_players=5)}
        code,res=self.fetch('POST','/runtime/observe',data)
        self.assertEqual(code,422)

    def test_unauthorized_mutation_route(self):
        for path in ('/runtime/activate','/runtime/rollback','/runtime/tap'):
            code,_=self.fetch('POST',path,{'request':'activate','checkpoint':'check1'})
            self.assertEqual(code,404)

    def test_no_lab_exposure_by_default(self):
        with patch.dict(os.environ,{'ARC_RUNTIME_LAB':'0'}):
            code,res=self.fetch('GET','/runtime/status')
            self.assertEqual(code,503)

    def test_live_profile_switch_without_restart(self):
        self.fetch('GET','/runtime/status')
        self.mgr.activate('check1')
        code,res=self.fetch('GET','/runtime/status')
        self.assertEqual(code,200)
        self.assertEqual(res['policy_version'],'0.8.1')

    def test_gpt_screen_adapter_unknown_player_count(self):
        raw={name:([] if name in ('hero_cards','board_cards','visible_buttons','rows') else None)
             for name in FIELDS}
        raw.update({'screen':'table_playing','variant':'holdem_nl','confidence':.98,
                    'notes':'','hero_name':'Test','is_hero_turn':True})
        ob=from_gpt_screen(raw,frame_sequence=40,frame_age_ms=120)
        self.assertIsNone(ob['seated_players'])
        self.assertIsNone(ob['hero_seated'])
        self.assertIsNone(ob['hand_active'])

if __name__=='__main__':unittest.main()

# Extra integration coverage kept separate from the game screenshot data fixtures.
class FrameHintHttp(RuntimeHttp):
    def test_local_jpeg_hint_response(self):
        import base64
        import io
        from PIL import Image
        stream=io.BytesIO()
        Image.new('RGB',(709,1536),(28,28,38)).save(stream,format='JPEG')
        data={'request':'runtime_frame_hint','image_base64':base64.b64encode(stream.getvalue()).decode('ascii')}
        code,res=self.fetch('POST','/runtime/frame-hint',data)
        self.assertEqual(code,200)
        self.assertEqual(res['mode'],'offline_visual_hint')
        self.assertIsNone(res['action'])
        self.assertFalse(res['authoritative'])
        self.assertFalse(res['money_actions_enabled'])
