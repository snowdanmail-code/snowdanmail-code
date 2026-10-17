import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from arc_versions.registry import VersionRegistry, encode
from arc_runtime.release import ReleaseReader, RuntimeUntrusted, validate_policy, standard_policy
from arc_runtime.observe import Observer, InvalidObservation
from arc_runtime.service import ObserverService


def obs(**overrides):
    data={'screen':'table_playing','confidence':.99,'game':'holdem_nl',
          'frame_sequence':1,'frame_age_ms':200,'is_replay':False,
          'seated_players':6,'active_players':2,'hero_seated':True,'hand_active':True}
    data.update(overrides)
    return data


def make_registry(path):
    reg=VersionRegistry(path,lab_mode=True,safe_to_switch=lambda:True)
    reg.register_artifact('contracts','1.0.0',b'contract')
    for idx,p in enumerate((standard_policy('baseline',.82,2),standard_policy('strict',.94,3))):
        version=f'0.8.{idx}'
        reg.register_artifact('runtime_policy',version,encode(p),requires={'contracts':'1.0.0'})
        name=f'release{idx}';cp=f'check{idx}'
        reg.create_release(name,{'contracts':'1.0.0','runtime_policy':version})
        reg.create_checkpoint(cp,name,test_report={'release_id':name,'passed':True,'total_tests':2,'failures':0},approved_by='unit-lab')
    reg.activate('check0')
    return reg


class RuntimePolicyTests(unittest.TestCase):
    def test_policy_valid(self): self.assertEqual(standard_policy()['allowed_game'],'holdem_nl')
    def test_unknown_policy_key(self):
        bad=standard_policy(); bad['command']='tap'
        with self.assertRaises(RuntimeUntrusted): validate_policy(bad)
    def test_money_actions_rejected(self):
        bad=standard_policy();bad['allow_money_actions']=True
        with self.assertRaises(RuntimeUntrusted): validate_policy(bad)
    def test_other_variants_rejected(self):
        bad=standard_policy();bad['allowed_game']='omaha_pl'
        with self.assertRaises(RuntimeUntrusted): validate_policy(bad)
    def test_replay_analysis_rejected(self):
        bad=standard_policy();bad['allow_replay_analysis']=True
        with self.assertRaises(RuntimeUntrusted): validate_policy(bad)
    def test_invalid_confidence_rejected(self):
        for x in ('0.9', 0,1.1,True):
            bad=standard_policy();bad['min_confidence']=x
            with self.assertRaises(RuntimeUntrusted):validate_policy(bad)

class StateMachineTests(unittest.TestCase):
    def setUp(self):self.o=Observer(standard_policy())
    def test_stable_2_frames(self):
        a=self.o.evaluate('session-alpha',obs())
        b=self.o.evaluate('session-alpha',obs(frame_sequence=2))
        self.assertEqual(a['reason'],'await_stable_frame')
        self.assertEqual(b['stable_scene'],'table_playing')
        self.assertEqual(b['recommendation'],'observe')
    def test_only_2_active_does_not_trigger_exit(self):
        self.o.evaluate('session-alpha',obs())
        out=self.o.evaluate('session-alpha',obs(frame_sequence=2))
        self.assertFalse(out['exit_candidate_after_hand'])
    def test_2_seated_flags_for_exit(self):
        self.o.evaluate('session-alpha',obs(seated_players=2))
        out=self.o.evaluate('session-alpha',obs(frame_sequence=2,seated_players=2))
        self.assertTrue(out['exit_candidate_after_hand'])
        self.assertEqual(out['recommendation'],'observe')
    def test_2_seated_exit_only_after_hand(self):
        self.o.evaluate('session-alpha',obs(seated_players=2))
        self.o.evaluate('session-alpha',obs(frame_sequence=2,seated_players=2))
        self.o.evaluate('session-alpha',obs(frame_sequence=3,seated_players=2,
                                            screen='table_waiting',hand_active=False))
        out=self.o.evaluate('session-alpha',obs(frame_sequence=4,seated_players=2,
                                                screen='table_waiting',hand_active=False))
        self.assertEqual(out['recommendation'],'review_table_exit')
        self.assertFalse(out['money_actions_enabled'])
        self.assertIsNone(out['tap_command'])
    def test_player_rejoins_cancels_flag(self):
        self.o.evaluate('session-alpha',obs(seated_players=2))
        self.o.evaluate('session-alpha',obs(frame_sequence=2,seated_players=2))
        out=self.o.evaluate('session-alpha',obs(frame_sequence=3,seated_players=3))
        self.assertFalse(out['exit_candidate_after_hand'])
    def test_replay_blocks(self):
        out=self.o.evaluate('session-alpha',obs(screen='replay',is_replay=True))
        self.assertEqual(out['recommendation'],'hold')
        self.assertEqual(out['stable_scene'],'unknown')
    def test_disconnected_blocks(self):
        out=self.o.evaluate('session-alpha',obs(screen='disconnected',hand_active=None))
        self.assertEqual(out['reason'],'replay_or_disconnect')
    def test_low_confidence_blocks(self):
        out=self.o.evaluate('session-alpha',obs(confidence=.5))
        self.assertEqual(out['recommendation'],'hold')
    def test_unknown_blocks(self):
        out=self.o.evaluate('session-alpha',obs(screen='unknown'))
        self.assertEqual(out['recommendation'],'hold')
    def test_omaha_blocks(self):
        out=self.o.evaluate('session-alpha',obs(game='omaha_pl'))
        self.assertEqual(out['recommendation'],'hold')
    def test_stale_frame_rejected(self):
        with self.assertRaises(InvalidObservation):
            self.o.evaluate('session-alpha',obs(frame_age_ms=7000))
    def test_duplicate_rejected(self):
        self.o.evaluate('session-alpha',obs())
        with self.assertRaises(InvalidObservation):self.o.evaluate('session-alpha',obs())
    def test_older_sequence_rejected(self):
        self.o.evaluate('session-alpha',obs(frame_sequence=30))
        with self.assertRaises(InvalidObservation):self.o.evaluate('session-alpha',obs(frame_sequence=29))
    def test_active_beyond_seated_rejected(self):
        with self.assertRaises(InvalidObservation): self.o.evaluate('session-alpha',obs(seated_players=2,active_players=3))
    def test_wrong_replay_marker_rejected(self):
        with self.assertRaises(InvalidObservation): self.o.evaluate('session-alpha',obs(screen='replay',is_replay=False))
    def test_hand_in_lobby_rejected(self):
        with self.assertRaises(InvalidObservation):self.o.evaluate('session-alpha',obs(screen='cash_lobby',hand_active=True))
    def test_concurrent_sessions_independent(self):
        self.o.evaluate('session-alpha',obs())
        out=self.o.evaluate('session-bravo',obs())
        self.assertEqual(out['reason'],'await_stable_frame')
    def test_every_observation_is_non_executable(self):
        scenes=['cash_lobby','buyin_dialog','table_unseated','seat_selection','table_waiting',
                'table_playing','action_controls','raise_panel','showdown','session_history']
        for i,scene in enumerate(scenes):
            x=self.o.evaluate('session-alpha',obs(screen=scene,frame_sequence=i+1,hand_active=None))
            self.assertFalse(x['money_actions_enabled'])
            self.assertIsNone(x['tap_command'])
    def test_broken_numeric_fields(self):
        for kw in ({'confidence':'0.9'}, {'frame_sequence':True},{'seated_players':-1},
                   {'is_replay':'no'}, {'hero_seated':0}, {'active_players':11}):
            with self.assertRaises(InvalidObservation):
                self.o.evaluate('session-alpha',obs(**kw))

class ActiveReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.reg=make_registry(self.tmp.name)
    def test_pinned_baseline(self):
        snap=ReleaseReader(self.tmp.name,allow_lab=True).resolve()
        self.assertEqual(snap.policy_version,'0.8.0')
        self.assertEqual(snap.policy['stable_frames'],2)
    def test_production_rejects_unverified_lab(self):
        with self.assertRaises(RuntimeUntrusted):ReleaseReader(self.tmp.name).resolve()
    def test_switch_to_stricter_profile_at_runtime(self):
        svc=ObserverService(self.tmp.name,allow_lab=True)
        self.assertEqual(svc.status()['policy_version'],'0.8.0')
        svc.observe('session-alpha',obs())
        self.reg.activate('check1')
        self.assertEqual(svc.status()['policy_version'],'0.8.1')
        new=svc.observe('session-alpha',obs())
        self.assertEqual(new['observation']['reason'],'await_stable_frame')
        self.assertEqual(new['observation']['stable_scene'],'unknown')
        self.assertEqual(new['runtime']['policy_name'],'strict')
    def test_switch_back_restores_old_profile(self):
        svc=ObserverService(self.tmp.name,allow_lab=True)
        self.reg.activate('check1');self.assertEqual(svc.status()['policy_version'],'0.8.1')
        self.reg.activate('check0');self.assertEqual(svc.status()['policy_version'],'0.8.0')
    def test_modifying_blob_blocks_runtime(self):
        p=Path(self.tmp.name)/'blobs'
        release=self.reg.get_release('release0')
        h=self.reg._read(Path(self.tmp.name)/'artifacts.json')['runtime_policy@0.8.0']['sha256']
        (p/h).write_bytes(b'injected')
        with self.assertRaises(Exception):ReleaseReader(self.tmp.name,allow_lab=True).resolve()
    def test_corrupted_audit_blocks_runtime(self):
        p=Path(self.tmp.name)/'audit.jsonl'
        p.write_bytes(p.read_bytes().replace(b'checkpoint_activated',b'checkpoint_forged'))
        with self.assertRaises(Exception):ReleaseReader(self.tmp.name,allow_lab=True).resolve()
    def test_missing_activation_blocks(self):
        (Path(self.tmp.name)/'active.json').unlink()
        with self.assertRaises(RuntimeUntrusted):ReleaseReader(self.tmp.name,allow_lab=True).resolve()

if __name__ == '__main__':unittest.main()
