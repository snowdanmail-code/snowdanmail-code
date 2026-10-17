"""Maintainer utility: generate PRIVATE cropped-card benchmarks from owned screenshots.

Needs explicit image directory. Does not package or reproduce opponent profiles.
"""
from __future__ import annotations
from pathlib import Path
import cv2
import json
import hashlib
import numpy as np

# Independently hand-labelled states from user-provided screens. Not for training.
GOLD={
 '1289':{'hero':['5c','8s'],'board':['3s','2s','3h'],'expected':'abstain'},
 '1291':{'hero':['5c','8s'],'board':['3s','2s','3h','Ts','Qd'],'expected':'abstain'},
 '1301':{'hero':['4d','Qd'],'board':['2h','Ts','Qc'],'expected':'complete'},
 '1307':{'hero':['4d','Qd'],'board':['2h','Ts','Qc','Jc','Qs'],'expected':'complete'},
 '1295':{'hero':['5c','8s'],'board':['3s','2s','3h','Ts','Qd'],'expected':'abstain'},
 '1319':{'hero':['4d','Qd'],'board':['2h','Ts','Qc','Jc','Qs'],'expected':'abstain'},
 '1281':{'hero':[],'board':[],'expected':'abstain'},
 '1285':{'hero':['5c','8s'],'board':[],'expected':'complete'},
 '1297':{'hero':['4d','Qd'],'board':[],'expected':'complete'},
 '1315':{'hero':['5h','7h'],'board':['3s','5d','Js'],'expected':'complete'},
 '1317':{'hero':['5h','7h'],'board':['3s','5d','Js','3d','As'],'expected':'abstain'},
}

def write_fixtures(source, output):
    source=Path(source);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    entries=[]
    for fid,labels in GOLD.items():
        path=source/(fid+'.jpg')
        src=cv2.imread(str(path))
        if src is None or src.shape[:2]!=(1536,709):
            raise ValueError('missing_or_unexpected_source:'+fid)
        dst=np.zeros_like(src)
        # Only two card regions: player/opponent names and avatars not copied.
        dst[708:850,115:595]=src[708:850,115:595]
        dst[1164:1240,346:501]=src[1164:1240,346:501]
        encoded=cv2.imencode('.jpg',dst,[cv2.IMWRITE_JPEG_QUALITY,92])[1].tobytes()
        name='cards_'+fid+'.jpg'
        (output/name).write_bytes(encoded)
        entries.append({'id':fid,'image':name,'sha256':hashlib.sha256(encoded).hexdigest(),**labels})
    (output/'gold.json').write_text(json.dumps({'schema':'1.0','entries':entries},indent=2),encoding='utf-8')
    return len(entries)

if __name__=='__main__':
    import sys
    print(write_fixtures(sys.argv[1],sys.argv[2]))
