import json
import tempfile
import threading
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from arc_versions.registry import VersionRegistry, RegistryError, CompatibilityError, UnsafeSwitch, AuditError
from arc_versions.sandbox import SandboxRunner, ExactOdds, ConservativeWaitPolicy
from arc_versions.contracts import TableObservation

class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.safe = False
        self.mgr = VersionRegistry(self.temp.name, safe_to_switch=lambda: self.safe, lab_mode=True)
        self.mgr.register_artifact('contracts', '1.0.0', b'wire-v1')
        self.mgr.register_artifact('poker_math', '1.0.0', b'exact-odds', requires={'contracts': '1.0.0'})
        self.mgr.register_artifact('strategy', '1.0.0', b'policy-a', requires={'poker_math': '1.0.0'})
        self.mgr.register_artifact('strategy', '1.1.0', b'policy-b', requires={'poker_math': '1.0.0'})
        self.components = {'contracts': '1.0.0','poker_math':'1.0.0','strategy':'1.0.0'}

    def tearDown(self): self.temp.cleanup()

    def _make(self, r='base', cp='point', components=None, model=''):
        self.mgr.create_release(r, components or self.components, external_model=model)
        return self.mgr.create_checkpoint(cp,r,
          test_report={'release_id':r,'passed':True,'total_tests':4,'failures':0},
          approved_by='local-unit-tests')

    def test_registry_status(self):
        self.assertEqual(self.mgr.status()['artifact_count'], 4)
        self.assertEqual(self.mgr.status()['active'], None)
        self.assertTrue(self.mgr.verify_audit()['ok'])

    def test_immutable_artifact_same_bytes_accepted(self):
        a = self.mgr.register_artifact('strategy','1.0.0',b'policy-a',requires={'poker_math':'1.0.0'})
        self.assertEqual(a['version'],'1.0.0')
        with self.assertRaises(RegistryError):
            self.mgr.register_artifact('strategy','1.0.0',b'modified')

    def test_blob_tampering_blocks(self):
        self.mgr.create_release('base', self.components)
        p = next((Path(self.temp.name)/'blobs').iterdir())
        p.write_bytes(b'changed')
        with self.assertRaises(CompatibilityError):
            self.mgr.verify_release(self.mgr.get_release('base'))

    def test_unknown_artifact_blocks(self):
        with self.assertRaises(CompatibilityError):
            self.mgr.create_release('bad', {**self.components,'vision':'8.0.0'})

    def test_incompatible_module_rollback_blocked(self):
        self._make()
        self.mgr.register_artifact('strategy','3.0.0',b'future',requires={'poker_math':'2.0.0'})
        with self.assertRaises(CompatibilityError):
            self.mgr.draft_module_rollback('point','strategy','3.0.0','draft-fail')

    def test_default_fails_closed(self):
        self._make()
        with self.assertRaises(UnsafeSwitch): self.mgr.activate('point')
        self.assertIsNone(self.mgr.status()['active'])

    def test_multi_generation_restore(self):
        self._make()
        self.safe = True; self.mgr.activate('point')
        for i in range(1,5):
            n = f'release{i}'; cp = f'checkpoint{i}'
            self.mgr.create_release(n, {**self.components,'strategy':'1.1.0'})
            self.mgr.create_checkpoint(cp,n,test_report={'release_id':n,'passed':True,'total_tests':1,'failures':0},
                                       approved_by='unit-tests',parent='point' if i==1 else f'checkpoint{i-1}')
            self.mgr.activate(cp)
        previous = self.mgr.activate('point')
        self.assertEqual(previous['release_id'],'base')
        self.assertEqual(len(self.mgr.status()['checkpoints']), 5)
        self.assertTrue(self.mgr.verify_audit()['ok'])

    def test_model_pin_needs_explicit_verification(self):
        self._make(model='example-gpt-model')
        self.safe=True
        with self.assertRaises(CompatibilityError): self.mgr.activate('point')
        self.assertEqual(self.mgr.activate('point',available_models={'example-gpt-model'})['release_id'],'base')

    def test_failing_evidence_not_approved(self):
        self.mgr.create_release('base',self.components)
        with self.assertRaises(RegistryError):
            self.mgr.create_checkpoint('point','base',test_report={'release_id':'base','passed':False,'total_tests':2,'failures':1},approved_by='unit')

    def test_no_mutation_when_unsafe(self):
        self._make()
        self.safe=True; self.mgr.activate('point')
        self.safe=False
        with self.assertRaises(UnsafeSwitch): self.mgr.activate('point')
        self.assertEqual(self.mgr.status()['active']['checkpoint_id'],'point')

    def test_unknown_test_report_fails(self):
        self.mgr.create_release('base',self.components)
        with self.assertRaises(RegistryError):
            self.mgr.create_checkpoint('point','base',test_report={},approved_by='unit')

    def test_draft_module_never_activated(self):
        self._make(); self.safe=True; self.mgr.activate('point')
        draft=self.mgr.draft_module_rollback('point','strategy','1.1.0','candidate1')
        self.assertEqual(draft['components']['strategy'],'1.1.0')
        self.assertEqual(self.mgr.status()['active']['release_id'],'base')
        with self.assertRaises(RegistryError): self.mgr.activate('candidate1')

    def test_audit_tamper_detected(self):
        self._make()
        logfile=Path(self.temp.name)/'audit.jsonl'
        body=logfile.read_text().replace('checkpoint_created','checkpoint_forged')
        logfile.write_text(body)
        with self.assertRaises(AuditError): self.mgr.verify_audit()

    def test_audit_damage_blocks_further_write(self):
        self._make()
        logfile=Path(self.temp.name)/'audit.jsonl'
        logfile.write_bytes(logfile.read_bytes().replace(b'checkpoint_created', b'checkpoint_forged'))
        with self.assertRaises(AuditError):
            self.mgr.register_artifact('vision','1.0.0',b'ok')

    def test_no_file_path_traversal(self):
        with self.assertRaises(RegistryError): self.mgr.create_release('../escape', self.components)

    def test_production_gate_rejects_lab_only(self):
        self._make(); self.safe=True
        production = VersionRegistry(self.temp.name, safe_to_switch=lambda: True)
        with self.assertRaises(RegistryError): production.activate('point')

    def test_missing_test_evidence_blocks_switch(self):
        self._make(); self.safe=True
        checkpoint=self.mgr.get_checkpoint('point')
        (Path(self.temp.name)/'blobs'/checkpoint['test_report_hash']).unlink()
        with self.assertRaises(RegistryError): self.mgr.activate('point')

    def test_two_thread_artifact_register(self):
        def worker(_): return self.mgr.register_artifact('vision','1.0.0',b'image-tools')
        with ThreadPoolExecutor(max_workers=6) as pool:
            ret=list(pool.map(worker,range(12)))
        self.assertEqual(len({x['sha256'] for x in ret}),1)
        self.assertEqual(self.mgr.status()['artifact_count'],5)

class DemoContracts(unittest.TestCase):
    def test_policy_is_replaceable_and_no_real_bets(self):
        obs=TableObservation(game='holdem_nl',street='flop',hero_cards=('As','Kd'),board_cards=('Ks','5c','2s'),
         pot=Decimal('.30'),to_call=Decimal('.10'),seated_players=6,active_players=2,
         confidence=1,is_replay=False,frame_sequence=20)
        report=SandboxRunner(ExactOdds(),ConservativeWaitPolicy()).analyze(obs)
        self.assertEqual(report['pot_odds'],'0.25')
        self.assertEqual(report['action'],'wait')

if __name__ == '__main__': unittest.main()
