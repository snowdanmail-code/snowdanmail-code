"""Deterministic offline latency trace scenarios (not Android measurements)."""
from .trace import TraceLedger, STAGES

SIMULATED_DURATIONS_MS={
    'normal': (25,18,110,12,520,105,35),
    'slow_model': (35,30,190,25,4600,175,60),
    'jitter': (80,22,650,22,1250,590,100),
}

def replay_traces(rows=30):
    ledger=TraceLedger(max_sessions=3,window=1000,min_samples=10,max_age_ms=7000)
    outputs=[]
    now=100000
    for i in range(rows):
        scenario=('normal','slow_model','jitter')[i%3]
        latencies=SIMULATED_DURATIONS_MS[scenario]
        session_id='offline-test-session'
        start=now
        # capture and receive timeline are a single synthetic clock.
        got=ledger.begin(session_id=session_id,sequence=i+1,captured_ms=start,received_ms=start,scene='live_table')
        assert got['status']=='TRACKING'
        current=start
        for stage,duration in zip(STAGES,latencies):
            current+=duration
            ledger.stage(session_id=session_id,sequence=i+1,stage=stage,
                         duration_ms=duration,observed_at_ms=current)
        result=ledger.complete(session_id=session_id,sequence=i+1,completed_ms=current)
        outputs.append({'scenario':scenario,'result':result['status'],'e2e_ms':result['total_ms']})
        now=current+100
    return {'description':'Deterministic OFFLINE simulated durations, NOT Android/GPT measurements',
            'summary':ledger.summary(),'cases':outputs,
            'live_android_network_tested':False,'openai_api_tested':False,
            'execution_enabled':False}
