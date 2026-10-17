import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from test_runtime import make_registry,obs
from arc_runtime.service import ObserverService

class Concurrency(unittest.TestCase):
    def test_parallel_sessions_do_not_corrupt_profile(self):
        with tempfile.TemporaryDirectory() as d:
            reg=make_registry(d)
            svc=ObserverService(d,allow_lab=True)
            def call(i):
                return svc.observe('session-'+str(i+100000),obs())
            with ThreadPoolExecutor(max_workers=6) as pool:
                results=list(pool.map(call,range(20)))
            self.assertEqual(len(results),20)
            self.assertTrue(all(r['runtime']['policy_version']=='0.8.0' for r in results))
            self.assertTrue(all(r['observation']['tap_command'] is None for r in results))
    def test_large_number_of_sessions_is_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            svc=ObserverService(d,allow_lab=True)
            make_registry(d)
            for i in range(150):
                svc.observe('session-'+str(100000+i),obs())
            self.assertLessEqual(len(svc._observer.tracks),64)
