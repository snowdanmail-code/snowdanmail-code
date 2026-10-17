"""Conservative *visual presence* cue for the stopwatch.

This detects a cropped cue only at the known normalized UI region. It never
reads actual seconds, verifies turn ownership, or authorizes actions. The
match is deliberately selective; on unknown skins/layouts it abstains.
"""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np

class StopwatchCue:
    VERSION='1.6.0'
    CANONICAL=(709,1536)
    BLOCKED={'replay','showdown','menu','overlay','disconnected','lobby','buyin_dialog','session_history'}
    def __init__(self, glyph_path=None, threshold=.82):
        if type(threshold) not in (float,int) or not .5 <= threshold <= 1.0:
            raise ValueError('invalid_threshold')
        if glyph_path is None:glyph_path=Path(__file__).parent/'assets'/'stopwatch_glyph_v1.png'
        self.template=cv2.imread(str(glyph_path),cv2.IMREAD_GRAYSCALE)
        if self.template is None or self.template.shape!=(89,94):
            raise ValueError('invalid_glyph')
        self.threshold=float(threshold)

    @staticmethod
    def _result(status,score=None):
        return {'version':'1.6.0','cue':status,'similarity':score,
                'seconds_remaining':None,'timer_verified':False,
                'turn_verified':False,'authorized_actions':[],
                'money_actions_enabled':False}

    def read(self,image,*,screen_state='unknown'):
        if not isinstance(screen_state,str):raise ValueError('invalid_scene')
        if image is None or not isinstance(image,np.ndarray) or image.ndim!=3 or image.shape[2]!=3:
            raise ValueError('invalid_image')
        h,w=image.shape[:2]
        if h<500 or w<240 or not 0.38 <= w/h <= .80:
            return self._result('UNSUPPORTED_GEOMETRY')
        if screen_state in self.BLOCKED:
            return self._result('BLOCKED_SCENE')
        if screen_state not in {'live_table','raise_panel','unknown'}:
            return self._result('UNKNOWN_SCENE')
        frame=cv2.resize(image,self.CANONICAL,interpolation=cv2.INTER_AREA)
        crop=cv2.cvtColor(frame[1260:1430,500:670],cv2.COLOR_BGR2GRAY)
        match=cv2.matchTemplate(crop,self.template,cv2.TM_CCOEFF_NORMED)
        score=round(float(match.max()),4)
        if score>=self.threshold:
            return self._result('STOPWATCH_ICON_CANDIDATE',score)
        return self._result('NO_RELIABLE_STOPWATCH_ICON',score)
