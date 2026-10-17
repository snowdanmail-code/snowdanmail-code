"""Reproducible LOCAL CPU microbenchmark + synthetic link transitions, not Internet/GPT RTT."""
import json
import statistics
import time
from pathlib import Path
from server.arc_telemetry.link_health import ObservationLinkHealth


def run():
    health=ObservationLinkHealth(window=64,min_samples=15)
    cases=[]
    seq=0
    now=1_000_000
    for name, outcome, latency, count in (
        ('warmup','ok',130,20),
        ('one_timeout','timeout',None,1),
        ('outage','transport_error',None,4),
        ('recovery','ok',150,4),
        ('jitter','ok',2400,22),
        ('change_to_cellular','ok',280,1),
    ):
        vals=[]
        for i in range(count):
            seq += 1
            now += 100
            kw={'sequence':seq,'seen_at_ms':now,'outcome':outcome,'rtt_ms':latency}
            if name=='change_to_cellular':kw['transport']='cellular'
            else:kw['transport']='wifi'
            before=time.perf_counter_ns()
            r=health.record(**kw)
            vals.append((time.perf_counter_ns()-before)/1e6)
        cases.append({'scenario':name,'observations':count,
                      'state_after':r['state'],'interval_after_ms':r['suggested_observation_interval_ms'],
                      'local_cpu_median_ms':round(statistics.median(vals),4),
                      'p95_observed_rtt_ms':r['p95_rtt_ms']})
    return {'mode':'offline_no_network','not_measured':['Android capture','JPEG encode','real network RTT','GPT inference','Android APK'],
            'samples':seq,'cases':cases,'money_actions_enabled':False}

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False,indent=2))
