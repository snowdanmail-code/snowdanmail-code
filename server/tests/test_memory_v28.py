import tempfile
import unittest
from pathlib import Path
from arc_player.memory import ObservedAction, OpponentMemory, AppendOnlyEvidence

class TestMemory(unittest.TestCase):
    def test_unknown_player(self):
        self.assertEqual(OpponentMemory().report('new')['reliability'],'insufficient')

    def test_one_fold_not_high_confidence(self):
        m=OpponentMemory();m.observe(ObservedAction('h01','flop','opponent-a','fold',True),sequence=2)
        r=m.report('opponent-a')
        self.assertEqual(r['faced_bet_samples'],1)
        self.assertLess(r['fold_to_bet_smoothed'],1)
        self.assertEqual(r['reliability'],'insufficient')

    def test_replay_ignored(self):
        m=OpponentMemory(); ev=ObservedAction('h01','turn','player-x','raise',False)
        self.assertTrue(m.observe(ev,sequence=4))
        self.assertFalse(m.observe(ev,sequence=4))
        self.assertEqual(m.report('player-x')['sample_actions'],1)

    def test_multiple_hands_evidence(self):
        m=OpponentMemory()
        for i in range(31):
            m.observe(ObservedAction('h'+str(i),'flop','anon','fold' if i%2 else 'call',True),sequence=1)
        r=m.report('anon')
        self.assertEqual(r['faced_bet_samples'],31)
        self.assertEqual(r['reliability'],'limited_evidence')

    def test_ledger_append_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'moves.jsonl')
            l=AppendOnlyEvidence(p)
            digest=l.append({'hand':'h1','action':'call'})
            self.assertEqual(AppendOnlyEvidence(p).verify(),digest)

    def test_ledger_tamper_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'moves.jsonl'
            l=AppendOnlyEvidence(str(p)); l.append({'hand':'h1','action':'call'})
            p.write_text(p.read_text().replace('call','raise'))
            with self.assertRaisesRegex(ValueError,'ledger_modified'):
                AppendOnlyEvidence(str(p))

    def test_ledger_external_modification(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'moves.jsonl'
            l=AppendOnlyEvidence(str(p));l.append({'hand':'h1'})
            p.write_text(p.read_text()+'{}\n')
            with self.assertRaises(ValueError):l.append({'hand':'h2'})

    def test_invalid_event(self):
        with self.assertRaises(ValueError):
            ObservedAction('h01','flop','anon','steal',True).validate()

if __name__=='__main__':unittest.main()
