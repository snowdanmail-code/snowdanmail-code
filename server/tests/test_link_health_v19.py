import math
import threading
import unittest
from arc_telemetry.link_health import ObservationLinkHealth, LinkHealthError


class LinkHealthTests(unittest.TestCase):
    def setUp(self):
        self.obj = ObservationLinkHealth(window=8, min_samples=4)

    def rec(self, seq, outcome='ok', rtt=100, transport='wifi', at=None):
        return self.obj.record(sequence=seq, seen_at_ms=1000+seq if at is None else at,
                               outcome=outcome, rtt_ms=rtt if outcome == 'ok' else None,
                               transport=transport)

    def test_uncalibrated_then_healthy(self):
        self.assertEqual(self.obj.summary()['state'], 'UNCALIBRATED')
        for i in range(1,5):
            self.rec(i)
        s=self.obj.summary()
        self.assertEqual((s['state'],s['samples'],s['p95_rtt_ms']),('HEALTHY',4,100.0))
        self.assertEqual(s['suggested_observation_interval_ms'],500)
        self.assertFalse(s['money_actions_enabled'])

    def test_failure_backoff_and_recovery(self):
        for i in range(1,5): self.rec(i)
        self.rec(5,'timeout')
        self.assertEqual(self.obj.summary()['state'],'DEGRADED')
        self.rec(6,'transport_error')
        self.rec(7,'timeout')
        self.assertEqual(self.obj.summary()['state'],'UNRELIABLE')
        self.assertEqual(self.obj.summary()['suggested_observation_interval_ms'],5000)
        self.rec(8,'ok')
        self.assertEqual(self.obj.summary()['state'],'UNRELIABLE')
        self.rec(9,'ok')
        self.assertEqual(self.obj.summary()['state'],'UNRELIABLE')
        self.rec(10,'ok')
        self.assertEqual(self.obj.summary()['state'],'HEALTHY')

    def test_slow_successes(self):
        for i in range(1,5): self.rec(i,rtt=1900)
        self.assertEqual(self.obj.summary()['state'],'DEGRADED')
        self.rec(5,rtt=4000)
        self.assertEqual(self.obj.summary()['state'],'UNRELIABLE')

    def test_out_of_order_rejected_without_stats_change(self):
        self.rec(3)
        original=self.obj.summary()
        self.assertEqual(self.rec(3)['status'],'REJECT_DUPLICATE_OR_OLD')
        self.assertEqual(self.rec(2)['status'],'REJECT_DUPLICATE_OR_OLD')
        self.assertEqual(self.obj.summary(),original)
        rejected=self.rec(4,at=1000)
        self.assertEqual(rejected['status'],'REJECT_CLOCK_REGRESSION')
        self.assertEqual(self.obj.summary(),original)
        self.assertEqual(self.rec(4)['status'],'RECORDED')

    def test_transport_change_resets_distribution(self):
        for i in range(1,5): self.rec(i,rtt=3800)
        self.assertEqual(self.obj.summary()['state'],'UNRELIABLE')
        self.rec(5,transport='cellular')
        s=self.obj.summary()
        self.assertEqual(s['samples'],1)
        self.assertEqual(s['state'],'UNCALIBRATED')
        self.assertEqual(s['transport'],'cellular')

    def test_bounded_memory(self):
        for i in range(1,80): self.rec(i,rtt=i*10)
        self.assertEqual(self.obj.summary()['samples'],8)

    def test_invalid_input(self):
        for values in [dict(sequence=True),dict(sequence=-1),dict(seen_at_ms=-4),
                       dict(outcome='any'),dict(transport='vpn'),dict(rtt_ms=math.nan),
                       dict(rtt_ms=math.inf),dict(rtt_ms=True),dict(rtt_ms=-2),
                       dict(rtt_ms=None)]:
            kwargs=dict(sequence=1,seen_at_ms=1000,outcome='ok',rtt_ms=50,transport='wifi')
            kwargs.update(values)
            with self.subTest(values=values), self.assertRaises(LinkHealthError):
                ObservationLinkHealth().record(**kwargs)

    def test_thread_safety_and_read_only_contract(self):
        results=[]
        def worker(i): results.append(self.rec(i))
        ts=[threading.Thread(target=worker,args=(i,)) for i in range(1,50)]
        for t in ts:t.start()
        for t in ts:t.join()
        self.assertEqual(len(results),49)
        self.assertTrue(all(r.get('action') is None and not r['money_actions_enabled'] for r in results))

if __name__ == '__main__': unittest.main()
