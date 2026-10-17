"""Reproducible LOCAL CPU and JPEG throughput benchmark. No real gameplay claims."""
import argparse
import json
from pathlib import Path
from statistics import median
import time
import cv2
from arc_vision.combined_observer import CompositeObserver
from arc_vision.card_reader import TemplateCardReader
from arc_vision.money_reader import TemplateMoneyReader

def stats(values):
    x=sorted(values)
    return {'p50_ms':round(median(x),2),'p95_ms':round(x[max(0,(len(x)*95+99)//100-1)],2),
            'max_ms':round(x[-1],2),'min_ms':round(x[0],2)}

def run(paths,iterations=12):
    observer=CompositeObserver();cards=TemplateCardReader();money=TemplateMoneyReader()
    measurements={'composite_single_decode':[],'legacy_separate_decodes':[],
                  'jpeg_decode':[],'jpeg_encode_q55':[],'jpeg_encode_q75':[]}
    sizes=[]
    for path in paths:
        jpeg=Path(path).read_bytes()
        for k in range(iterations):
            t=time.perf_counter();image=cv2.imdecode(__import__('numpy').frombuffer(jpeg,dtype='uint8'),cv2.IMREAD_COLOR)
            if image is None:raise ValueError(path)
            measurements['jpeg_decode'].append((time.perf_counter()-t)*1000)
            for quality in (55,75):
                t=time.perf_counter();ok,buf=cv2.imencode('.jpg',image,[cv2.IMWRITE_JPEG_QUALITY,quality])
                if not ok:raise ValueError('encode_failure')
                measurements[f'jpeg_encode_q{quality}'].append((time.perf_counter()-t)*1000)
                if k==0:sizes.append({'file':Path(path).name,'quality':quality,'jpeg_bytes':len(buf)})
            t=time.perf_counter();observer.read(jpeg,screen_state='live_table')
            measurements['composite_single_decode'].append((time.perf_counter()-t)*1000)
            t=time.perf_counter();cards.read(jpeg,screen_state='live_table');money.read(jpeg,screen_state='live_table')
            measurements['legacy_separate_decodes'].append((time.perf_counter()-t)*1000)
    return {'units':'milliseconds','host':'this offline test container, NOT Android',
            'frames':len(paths),'repeat_per_frame':iterations,
            'cold_start_excluded':False,'results':{k:stats(v) for k,v in measurements.items()},
            'jpeg_payload_sizes':sizes,'caveats':['Not network RTT or GPT API latency',
               'No real action execution or native Android benchmark',
               'Templates are tested on known fixtures; accuracy on new layouts unverified']}

if __name__=='__main__':
    arg=argparse.ArgumentParser();arg.add_argument('files',nargs='+');arg.add_argument('--repeats',type=int,default=12)
    a=arg.parse_args()
    print(json.dumps(run(a.files,a.repeats),ensure_ascii=False,indent=2))
