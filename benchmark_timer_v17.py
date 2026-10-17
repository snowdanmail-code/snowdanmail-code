"""Offline lab benchmark, using pre-extracted user clips; NOT generalization test."""
from pathlib import Path
import json,cv2,numpy as np,time
from statistics import median
from arc_turn.timer_digits import TimerDigitReader

root=Path('/mnt/data/arc_v17_work')
reader=TimerDigitReader()
result={'version':'1.7.0','scope':'CPU-only offline timer label reading',
        'independent_validation':False,'confirmed_remaining_seconds':0,
        'source':'previously supplied screen recordings (same sessions as template sources)',
        'recordings':{},'full_screen_samples':{},'latency_ms':{}}
for series,expected in [('a',30),('b',60)]:
    frames=sorted((root/f'timer_video_{series}').glob(f'{series}_*.jpg'))
    counts={'all_frames':len(frames),'icon_candidates':0,'label_read':0,'correct_known':0,'wrong_known':0,'abstain_on_icon_candidates':0,'without_icon_no_label':0}
    for path in frames:
        im=cv2.imread(str(path));gray=cv2.cvtColor(im,cv2.COLOR_BGR2GRAY)
        icon = float(gray[84:93,59:93].mean())>110 and float(gray[116:122,78:91].mean())>105
        r=reader.read_crop(im)
        if icon:
            counts['icon_candidates']+=1
            if r['status']=='DISPLAY_LABEL_READ':
                counts['label_read']+=1
                if r['displayed_label_seconds']==expected:counts['correct_known']+=1
                else:counts['wrong_known']+=1
            else:counts['abstain_on_icon_candidates']+=1
        elif r['status']!='DISPLAY_LABEL_READ':counts['without_icon_no_label']+=1
        else:raise RuntimeError(f'Unexpected false timer {path}')
        if r['seconds_remaining'] is not None:raise RuntimeError('Countdown falsely claimed')
    result['recordings'][series]=counts
for n,expected in [(1297,30),(1315,30),(1299,None),(1317,None),(1303,None)]:
    img=cv2.imread(f'/mnt/data/{n}.jpg')
    pred=reader.read(img,screen_state='live_table')
    result['full_screen_samples'][str(n)]={'expected_display_label':expected,'recognized':pred['displayed_label_seconds'],'status':pred['status']}
    assert pred['displayed_label_seconds']==expected
# Isolate local CPU, exclude image capture / uplink / GPT / touch.
for mode,images in [('crop',[cv2.imread(str(root/'timer_video_a/a_0176.jpg')),cv2.imread(str(root/'timer_video_b/b_0070.jpg'))]),
                    ('full',[cv2.imread('/mnt/data/1297.jpg')])]:
    results=[]
    for i in range(100):
        st=time.perf_counter()
        if mode=='crop':reader.read_crop(images[i%len(images)])
        else:reader.read(images[0],screen_state='live_table')
        results.append((time.perf_counter()-st)*1000)
    result['latency_ms'][mode]={'n':100,'median':round(float(median(results)),4),'p95':round(float(np.percentile(results,95)),4)}
result['caveats']=['Training exemplars and test clips overlap in recording/visual design; accuracy on new screens is unknown.',
                    'Only known printed 30 and 60 labels; cannot estimate actual seconds until action deadline.',
                    'Network latency, GPT requests and end-to-end Android operation are excluded.']
output=Path('/mnt/data/AI-Remote-Control-v1.7/BENCHMARK_TIMER_v1.7.json')
output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
