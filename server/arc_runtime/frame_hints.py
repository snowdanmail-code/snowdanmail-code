"""Privacy-minimal offline visual hints (never an authority for taps or money).

Pillow is optional. Stores only very low-res mean RGB fingerprints of supplied
screenshots, not screenshots, names or text. This purposely cannot read cards,
stakes, opponents, or account information. Always gate by GPT confirmation.
"""
from __future__ import annotations
from math import sqrt
import json
from pathlib import Path

W, H = 12, 24


def fingerprint(data:bytes)->list[int]:
    from PIL import Image
    from io import BytesIO
    with Image.open(BytesIO(data)) as im:
        # Approximate portrait aspect; reject files that are not our screen shape.
        if im.width < 200 or im.height < 300 or not (.40 <= im.width / im.height <= .55):
            raise ValueError('unexpected_image_geometry')
        im=im.convert('RGB').resize((W,H),Image.Resampling.BOX)
        return [channel for rgb in im.getdata() for channel in rgb]


def distance(a:list[int],b:list[int])->float:
    if len(a)!= W*H*3 or len(b)!=len(a): raise ValueError('feature_length_mismatch')
    # More weight for header / controls because the table body looks similar
    # across replay/live modes; still only a soft scene hint.
    weighted=0;den=0
    for p in range(W*H):
        y=p//W
        weight=2.4 if y<4 or y>=20 else 1.0
        for k in range(3):
            d=(a[3*p+k]-b[3*p+k])/255
            weighted+=weight*d*d
            den+=weight
    return sqrt(weighted/den)


def hint(data:bytes, prototypes:dict, *, threshold:float=.19, separation:float=.012)->dict:
    f=fingerprint(data)
    values=[]
    for label,refs in prototypes.items():
        if not isinstance(label,str) or not isinstance(refs,list): raise ValueError('bad_prototypes')
        for r in refs:
            if not isinstance(r,list) or len(r)!=W*H*3 or any(type(x) is not int or not 0<=x<=255 for x in r):
                raise ValueError('bad_fingerprint')
            values.append((distance(f,r),label))
    if not values:return {'scene_hint':'unknown','distance':None,'evidence':'no_prototypes'}
    values.sort()
    best,scene=values[0]
    other=min((score for score,category in values if category!=scene),default=1.0)
    if best>threshold or other-best<separation:
        return {'scene_hint':'unknown','distance':round(best,4),'evidence':'weak_visual_match'}
    return {'scene_hint':scene,'distance':round(best,4),'evidence':'low_res_color_signature_only'}


def load_prototypes(path:str|Path)->dict:
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    if payload.get('schema')!='arc.visual_hints.v1' or not isinstance(payload.get('prototypes'),dict):
        raise ValueError('bad_signature_document')
    return payload['prototypes']
