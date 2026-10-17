"""Fast, conservative detector for button-colour cues in captured Hold'em UI.

Only detects coloured areas at known, normalized layout positions. A match
IS NOT proof of whose turn it is; it is NEVER an execution authorization.
"""
from __future__ import annotations
import cv2
import numpy as np

NON_LIVE = frozenset({'showdown','replay','disconnected','menu','buyin_dialog',
    'lobby','overlay','session_history'})

class TurnCueReader:
    VERSION = '0.1.0'

    @staticmethod
    def _fraction(region,kind):
        hue,sat,val = region[:,:,0],region[:,:,1],region[:,:,2]
        valid=(sat>65)&(val>60)
        if kind=='red':mask=((hue<12)|(hue>=170))&valid
        elif kind=='green':mask=(hue>=35)&(hue<94)&valid
        elif kind=='amber':mask=(hue>=11)&(hue<36)&valid
        else:raise ValueError('invalid_color')
        return round(float(mask.mean()),3)

    def read_image(self, image, *, screen_state='unknown'):
        if not isinstance(screen_state,str):raise ValueError('invalid_scene')
        if not isinstance(image,np.ndarray) or image.ndim!=3 or image.shape[2]!=3:
            raise ValueError('invalid_bgr_image')
        h,w=image.shape[:2]
        if h<500 or w<240 or not 0.38<=w/h<=0.80:
            return self._report('UNSUPPORTED_GEOMETRY',screen_state,{})
        if screen_state in NON_LIVE:
            return self._report('BLOCKED_SCENE',screen_state,{})
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
        y1,y2=int(h*.92),int(h*.98)
        color_probs={}
        for key,x,color in (('fold_region',.17,'red'),('middle_region',.50,'green'),
                            ('right_region',.83,'amber')):
            x1,x2=int(w*(x-.09)),int(w*(x+.09))
            color_probs[key]=self._fraction(hsv[y1:y2,x1:x2],color)
        active=(color_probs['fold_region']>=.30 and
                color_probs['middle_region']>=.30 and
                color_probs['right_region']>=.30)
        # Rightmost gold 'confirm' button with grey left/middle can indicate
        # an open sizing panel, but never proves a real bet opportunity.
        raise_panel=(color_probs['right_region']>=.27 and
                     color_probs['fold_region']<.08 and
                     color_probs['middle_region']<.08)
        if active:cue='ACTIVE_COLOUR_TRIAD'
        elif raise_panel:cue='RIGHT_GOLD_ONLY'
        elif max(color_probs.values())<.08:cue='NO_ACTIVE_COLOUR_CUES'
        else:cue='AMBIGUOUS_COLOURS'
        if cue=='ACTIVE_COLOUR_TRIAD' and screen_state=='raise_panel':
            cue='SCENE_CONFLICT'
        if cue=='RIGHT_GOLD_ONLY' and screen_state=='live_table':
            cue='SCENE_CONFLICT'
        return self._report(cue,screen_state,color_probs)

    @staticmethod
    def _report(cue,scene,scores):
        return {'module':'turn_cues','version':'0.1.0','cue':cue,'screen_hint':scene,
                'colour_fractions':scores,'turn_verified':False,
                'authorized_actions':[],'wager_enabled':False,
                'limitations':['colour_is_not_turn_proof','unverified_app_scene',
                               'no_button_text_or_timer_ocr']}
