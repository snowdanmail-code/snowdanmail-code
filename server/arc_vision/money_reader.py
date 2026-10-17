"""Opt-in image-only money recognizer. No general OCR, no screen control.

Use narrowly calibrated ROIs and manually labelled white-on-grey digits. A bad
capture, overlay, another font, missing digit template or ambiguous glyph ABSTAINS.
The output is cents, never a value interpreted as authorization to gamble.
"""
from __future__ import annotations
import json,re
from pathlib import Path
import cv2
import numpy as np

TARGET_SHAPE=(709,1536)

class MoneyReadError(ValueError): pass


def _glyph_mask(piece):
    h,w=piece.shape
    if h not in (17,18,19) or w not in range(4,12):return None
    tile=np.zeros((19,13),dtype=np.uint8)
    tile[(19-h)//2:(19-h)//2+h,(13-w)//2:(13-w)//2+w]=piece
    return tile.astype(bool)


def _score(a,b):
    intersection=np.count_nonzero(a & b)
    union=np.count_nonzero(a | b)
    return intersection/max(union,1)


class TemplateMoneyReader:
    def __init__(self,atlas_path=None):
        doc=json.loads(Path(atlas_path or Path(__file__).with_name('money_glyphs.json')).read_text())
        if doc.get('schema')!='1.0' or doc.get('size')!=[19,13]:raise MoneyReadError('incompatible_money_atlas')
        self.templates={k:[np.array(v,dtype=bool).reshape(19,13) for v in values]
                        for k,values in doc['templates'].items()}

    def _digit(self,mask):
        possible=sorted([(max(_score(mask,t) for t in samples),symbol)
                        for symbol,samples in self.templates.items()],reverse=True)
        if not possible:return None
        score,symbol=possible[0]
        gap=score-possible[1][0] if len(possible)>1 else score
        # conservative: future font differences and missing 9 intentionally abstain
        return symbol if score>=0.83 and gap>=0.11 else None

    @staticmethod
    def _canonical(image):
        if image is None or len(image.shape)!=3:raise MoneyReadError('invalid_image')
        height,width=image.shape[:2]
        if (width,height)==TARGET_SHAPE:return image
        if width<450 or height<800 or width>2160 or height>4600 or abs(width/height-709/1536)>0.008:
            raise MoneyReadError('unsupported_geometry')
        return cv2.resize(image,TARGET_SHAPE,interpolation=cv2.INTER_AREA)

    def _read_region(self,image,region,*,required_dollar=True):
        x0,y0,x1,y1=region
        if x0<0 or x1>709 or y0<0 or y1>1536 or x0>=x1 or y0>=y1:
            return {'status':'abstain','reason':'invalid_region','cents':None}
        gray=cv2.cvtColor(image[y0:y1,x0:x1],cv2.COLOR_BGR2GRAY)
        binary=(gray>170).astype(np.uint8)
        _,_,stats,_=cv2.connectedComponentsWithStats(binary,8)
        boxes=sorted([(int(x+x0),int(y+y0),int(w),int(h),int(a))
                      for x,y,w,h,a in stats[1:] if a>=3],key=lambda b:b[0])
        # trailing dollar sign extends below and above digit band.
        dollars=[b for b in boxes if b[3] in range(21,26) and b[2] in range(8,12)]
        if required_dollar and len(dollars)!=1:
            return {'status':'abstain','reason':'missing_currency_marker','cents':None}
        dollar=dollars[0] if dollars else None
        if dollar is None:return {'status':'abstain','reason':'currency_not_verified','cents':None}
        # Label is a single inline text string; do not pick separated unrelated numbers.
        digits=[b for b in boxes if 16<=b[3]<=19 and 4<=b[2]<=11 and b[0]<dollar[0]]
        periods=[b for b in boxes if b[2] in (1,2,3) and b[3] in (1,2,3)
                 and b[0]<dollar[0] and b[1]>=dollar[1]+13]
        if len(digits) not in (1,3,4) or not (0<len(periods)<=1 or len(digits)==1):
            return {'status':'abstain','reason':'invalid_number_shape','cents':None}
        if len(digits)>1 and len(periods)!=1:
            return {'status':'abstain','reason':'decimal_not_verified','cents':None}
        if digits[-1][0]+digits[-1][2]>dollar[0]-3 or digits[0][0]<x0+1:
            return {'status':'abstain','reason':'glyph_overlap','cents':None}
        chars=[]
        for x,y,w,h,_ in digits:
            piece=binary[y-y0:y-y0+h,x-x0:x-x0+w]
            mask=_glyph_mask(piece)
            char=self._digit(mask) if mask is not None else None
            if char is None:
                return {'status':'abstain','reason':'unverified_digit','cents':None}
            chars.append(char)
        if len(digits)==1:
            cents=int(chars[0])*100
        else:
            dotx=periods[0][0]
            nleft=sum(1 for b in digits if b[0]<dotx)
            if nleft<1 or len(digits)-nleft!=2:
                return {'status':'abstain','reason':'decimal_position_invalid','cents':None}
            cents=int(''.join(chars[:nleft]))*100+int(''.join(chars[nleft:]))
        if cents>100_000:
            return {'status':'abstain','reason':'out_of_calibrated_range','cents':None}
        return {'status':'recognized','reason':None,'cents':cents,
                'amount':f'{cents//100}.{cents%100:02d}',
                'method':'fixed_roi_glyph_templates',
                'confidence_calibrated':False}

    def read_pot(self,image,*,screen_state='live_table'):
        if screen_state!='live_table':return {'status':'abstain','reason':'screen_state_blocked','cents':None}
        image=self._canonical(image)
        # Header presence: confirm visible white label above the amount.
        label=cv2.cvtColor(image[643:668,320:392],cv2.COLOR_BGR2GRAY)
        if int(np.count_nonzero(label>185))<45:
            return {'status':'abstain','reason':'bank_label_missing_or_dimmed','cents':None}
        # Small calibrated pill (no sidebars, animations, camera scaling beyond aspect ratio).
        return self._read_region(image,(306,669,404,697))

    def read_central_chips(self,image,*,screen_state='live_table'):
        """Visual central chip pile (NOT necessarily a player's wager)."""
        if screen_state!='live_table':return {'status':'abstain','reason':'screen_state_blocked','cents':None}
        image=self._canonical(image)
        for region in [(306,891,404,932),(306,879,404,920)]:
            value=self._read_region(image,region)
            if value['status']=='recognized':return value
        return {'status':'abstain','reason':'no_verified_central_chip_label','cents':None}

    def read(self,frame,*,screen_state='live_table'):
        if not isinstance(frame,(bytes,bytearray)) or len(frame)<250 or len(frame)>650_000 or not frame.startswith(b'\xff\xd8'):
            raise MoneyReadError('invalid_jpeg')
        image=cv2.imdecode(np.frombuffer(frame,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None:raise MoneyReadError('invalid_jpeg_decode')
        return self.read_image(image, screen_state=screen_state)

    def read_image(self,image,*,screen_state='live_table'):
        """Process a decoded BGR frame; reuse the same decode for cards and amounts."""
        return {'pot':self.read_pot(image,screen_state=screen_state),
                'central_chips':self.read_central_chips(image,screen_state=screen_state),
                'money_actions_enabled':False,'action':None,'version':'v1.2.0'}
