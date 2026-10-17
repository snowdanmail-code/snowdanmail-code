"""Offline data benchmark. The fixture set contains near-duplicate game states.

Never interpret measured figures as accuracy on truly unseen games or as a
safety guarantee for betting. No game interaction, API key or network needed.
"""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
from statistics import median
import time
import cv2
import numpy as np
from arc_vision.card_reader import TemplateCardReader


def run(folder: str | Path, *, quality: int | None = None):
    folder=Path(folder)
    gold=json.loads((folder/'gold.json').read_text(encoding='utf-8'))
    reader=TemplateCardReader()
    complete_correct=0;complete_total=0;abstain_correct=0;abstain_total=0
    false_confident=0;durations=[];total_bytes=0;predictions=[]
    training_overlap=[]
    for entry in gold['entries']:
        data=(folder/entry['image']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:
            raise ValueError('tampered_benchmark_fixture')
        if quality is not None:
            img=cv2.imdecode(np.frombuffer(data,np.uint8),cv2.IMREAD_COLOR)
            ok,enc=cv2.imencode('.jpg',img,[cv2.IMWRITE_JPEG_QUALITY,quality])
            if not ok:raise ValueError('jpeg_encode_failed')
            data=enc.tobytes()
        total_bytes+=len(data)
        now=time.perf_counter()
        result=reader.read(data,screen_state='live_table')
        durations.append((time.perf_counter()-now)*1000)
        if entry['expected']=='complete':
            complete_total+=1
            good=(result['quality']=='complete' and result['hero_cards']==entry['hero'] and
                  result['board_cards']==entry['board'])
            complete_correct+=good
        else:
            abstain_total+=1
            good=result['quality']=='abstain'
            abstain_correct+=good
        if result['quality']=='complete' and not good:false_confident+=1
        if entry['id'] in ('1315',): training_overlap.append(entry['id'])
        predictions.append({'id':entry['id'],'expected':entry['expected'],
                            'actual':result['quality'],'passed':bool(good)})
    return {'quality_setting':quality if quality else 'source_jpeg',
            'gold_frames':len(predictions),'positive_total':complete_total,
            'positive_correct':complete_correct,'negative_total':abstain_total,
            'negative_correct':abstain_correct,'false_confident':false_confident,
            'mean_image_bytes':round(total_bytes/len(predictions)),
            'median_local_cpu_ms':round(median(durations),2),
            'training_overlap_ids':training_overlap,
            'independent_hands':False,'claims_generalization':False,
            'predictions':predictions}

if __name__=='__main__':
    import sys
    dataset=sys.argv[1]
    print(json.dumps([run(dataset,quality=q) for q in (None,55,75,88)],indent=2))
