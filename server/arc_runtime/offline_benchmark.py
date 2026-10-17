"""Run manual-labeled visual hint benchmark against locally owned test images.

Does not include, upload or persist originals. Benchmarks no OCR and no wagers.
Usage: python -m arc_runtime.offline_benchmark /path/to/screenshot_dir
"""
import json
from pathlib import Path
from .frame_hints import fingerprint, hint

TRAIN = {
    'cash_lobby':['1261.jpg'],
    'buyin_dialog':['1265.jpg'],
    'live_table':['1263.jpg','1269.jpg','1273.jpg'],
    'raise_panel':['1271.jpg'],
    'table_menu':['1321.jpg','1343.jpg'],
    'player_stats':['1329.jpg','1331.jpg'],
    'history':['1335.jpg'],
    'replay':['1339.jpg'],
    'replay_menu':['1341.jpg'],
    'disconnected':['1333.jpg'],
}
EVAL = {
    'live_table':['1267.jpg','1279.jpg','1281.jpg','1291.jpg','1299.jpg',
                  '1303.jpg','1305.jpg','1309.jpg','1313.jpg','1315.jpg','1317.jpg','1319.jpg'],
    'history':['1337.jpg'],
    'table_menu':['1321.jpg'],
    'player_stats':['1329.jpg'],
    'replay':['1339.jpg'],
    'disconnected':['1333.jpg'],
    'buyin_dialog':['1265.jpg'],
    'cash_lobby':['1261.jpg'],
}

def build(root: Path)->dict:
    prototypes={label:[fingerprint((root/file).read_bytes()) for file in samples if (root/file).exists()]
                for label,samples in TRAIN.items()}
    prototypes={k:v for k,v in prototypes.items() if v}
    if len(prototypes)<5:raise ValueError('insufficient_training_material')
    return {'schema':'arc.visual_hints.v1','prototypes':prototypes}

def evaluate(root:Path,payload:dict)->dict:
    records=[]
    for expected,images in EVAL.items():
        for f in images:
            if not (root/f).is_file():continue
            p=hint((root/f).read_bytes(),payload['prototypes'])
            records.append({'name':f,'expected':expected,'predicted':p['scene_hint'],
                            'distance':p['distance'],'correct':p['scene_hint']==expected})
    return {'evaluated':len(records),'correct':sum(x['correct'] for x in records),
            'abstained':sum(x['predicted']=='unknown' for x in records),
            'results':records,'caveat':'Color-based hints only; not a reliable vision model or source of action commands'}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('--output',default='visual_hints.json')
    args=parser.parse_args(); root=Path(args.source)
    doc=build(root);report=evaluate(root,doc)
    Path(args.output).write_text(json.dumps(doc,separators=(',',':')),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
