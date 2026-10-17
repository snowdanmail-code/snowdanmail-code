"""v1.7 conservative *display label* recognition, not time remaining.

Recognizes known '30 с' / '60 с' stopwatch labels from an anonymized
170x170 timer neighborhood or a supported full-size screenshot. No OCR,
network, model calls, coordinates or wager authorization.

IMPORTANT: A displayed label can indicate a time bank / time-control setting;
it is NOT validated as the live countdown to the end of a betting decision.
"""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
from .stopwatch import StopwatchCue


class TimerDigitReader:
    VERSION = '1.7.0'
    BLOCKED = StopwatchCue.BLOCKED
    KNOWN = {'live_table', 'raise_panel', 'unknown'}

    def __init__(self, *, max_error=.24, min_margin=.07):
        if not isinstance(max_error,(int,float)) or not 0 < max_error <= .4:
            raise ValueError('invalid_error_limit')
        if not isinstance(min_margin,(int,float)) or not 0 < min_margin <= .3:
            raise ValueError('invalid_margin')
        self.max_error=float(max_error)
        self.min_margin=float(min_margin)
        root=Path(__file__).parent/'assets'
        self.templates={}
        for value in (30,60):
            img=cv2.imread(str(root/f'timer_digit_{value}_v17.png'),cv2.IMREAD_GRAYSCALE)
            if img is None or img.shape!=(23,12):
                raise ValueError('missing_digit_template')
            self.templates[value]=(img>127).astype(np.uint8)
        self.stopwatch=StopwatchCue()

    @classmethod
    def _result(cls, status, value=None, error=None, margin=None):
        return {
            'version':cls.VERSION,
            'status':status,
            'displayed_label_seconds':value,
            'recognition_error':round(float(error),4) if error is not None else None,
            'recognition_margin':round(float(margin),4) if margin is not None else None,
            'seconds_remaining':None,
            'countdown_verified':False,
            'turn_verified':False,
            'authorized_actions':[],
            'money_actions_enabled':False,
        }

    def _classify(self, glyph):
        if glyph.shape!=(23,12):
            return self._result('UNSUPPORTED_GLYPH')
        errors={value:float(np.mean(glyph!=ref)) for value,ref in self.templates.items()}
        ranked=sorted(errors.items(),key=lambda item:item[1])
        value,err=ranked[0]
        margin=ranked[1][1]-err
        if err > self.max_error or margin < self.min_margin:
            return self._result('AMBIGUOUS_DIGITS',error=err,margin=margin)
        return self._result('DISPLAY_LABEL_READ',value,err,margin)

    @staticmethod
    def _scene(screen_state):
        if not isinstance(screen_state,str):raise ValueError('invalid_scene')
        if screen_state in TimerDigitReader.BLOCKED:return 'BLOCKED_SCENE'
        if screen_state not in TimerDigitReader.KNOWN:return 'UNKNOWN_SCENE'
        return None

    def read_crop(self, image, *, screen_state='live_table'):
        """170x170 pixel neighborhood of the bottom-right timer from recorded video.

        Uses a fixed crop *only for this normalized reference format*; all
        unknown layouts must abstain rather than assume the coordinate applies.
        """
        block=self._scene(screen_state)
        if block:return self._result(block)
        if not isinstance(image,np.ndarray) or image.ndim!=3 or image.shape!=(170,170,3):
            return self._result('UNSUPPORTED_GEOMETRY')
        gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
        # Bright circle interior, checked outside the digits to reject the
        # background and empty/occluded controls.
        if float(gray[84:93,59:93].mean()) <= 110 or float(gray[116:122,78:91].mean()) <= 105:
            return self._result('NO_RELIABLE_TIMER')
        glyph=cv2.resize((gray[97:117,55:67]<125).astype(np.uint8),
                         (12,23),interpolation=cv2.INTER_NEAREST)
        return self._classify(glyph)

    def read(self, image, *, screen_state='unknown'):
        """Read from full screen in already supported 709x1536 layout.

        The old stopwatch-presence detector anchors the crop. Numbers beyond
        30/60, geometry drift or occlusions return unknown. This does not
        authorize touching the screen, and does NOT measure elapsed time.
        """
        block=self._scene(screen_state)
        if block:return self._result(block)
        if image is None or not isinstance(image,np.ndarray) or image.ndim!=3 or image.shape[2]!=3:
            raise ValueError('invalid_image')
        h,w=image.shape[:2]
        if h<500 or w<240 or not .38<=w/h<=.80:
            return self._result('UNSUPPORTED_GEOMETRY')
        frame=cv2.resize(image,StopwatchCue.CANONICAL,interpolation=cv2.INTER_AREA)
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        roi=gray[1260:1430,500:670]
        match=cv2.matchTemplate(roi,self.stopwatch.template,cv2.TM_CCOEFF_NORMED)
        _,score,_,loc=cv2.minMaxLoc(match)
        if score < self.stopwatch.threshold:
            return self._result('NO_RELIABLE_TIMER')
        x,y=500+loc[0],1260+loc[1]
        crop=gray[y:y+89,x:x+94]
        if crop.shape!=(89,94):return self._result('UNSUPPORTED_GEOMETRY')
        # Extract the *first* of two printed digits in the calibrated 709 px
        # layout. Resize to the portable glyph format used for lab frames.
        # More themes/fonts must be calibrated separately.
        glyph=cv2.resize((crop[42:62,25:35]<125).astype(np.uint8),
                         (12,23),interpolation=cv2.INTER_NEAREST)
        return self._classify(glyph)


class LabelStabilizer:
    """Per-session advisory vote; conflicts, stale frames and gaps reset it."""
    def __init__(self, min_frames=2, max_gap_ms=1800):
        if type(min_frames) is not int or not 2<=min_frames<=6 or type(max_gap_ms) is not int or not 1<=max_gap_ms<=10000:
            raise ValueError('invalid_stabilizer')
        self.min_frames=min_frames
        self.max_gap_ms=max_gap_ms
        self._last=None

    def update(self, *, session_id, sequence, captured_ms, reading):
        if (not isinstance(session_id,str) or not session_id or type(sequence) is not int or sequence<0 or
            type(captured_ms) is not int or captured_ms<0 or not isinstance(reading,dict)):
            raise ValueError('invalid_update')
        value=reading.get('displayed_label_seconds') if reading.get('status')=='DISPLAY_LABEL_READ' else None
        prev=self._last
        if prev is not None and prev['session']==session_id and (sequence<=prev['sequence'] or captured_ms<=prev['captured_ms']):
            return {'status':'OUT_OF_ORDER_IGNORED','displayed_label_seconds':None,
                    'seconds_remaining':None,'timer_verified':False,
                    'authorized_actions':[],'money_actions_enabled':False}
        consecutive=(prev is not None and prev['session']==session_id and
                     sequence>prev['sequence'] and
                     0<captured_ms-prev['captured_ms']<=self.max_gap_ms and
                     value is not None and value==prev['value'])
        count=(prev['count']+1) if consecutive else (1 if value is not None else 0)
        self._last={'session':session_id,'sequence':sequence,'captured_ms':captured_ms,'value':value,'count':count}
        return {'status':'STABLE_DISPLAY_LABEL' if count>=self.min_frames else 'UNCONFIRMED_DISPLAY_LABEL',
                'displayed_label_seconds':value if count>=self.min_frames else None,
                'seconds_remaining':None,'timer_verified':False,'authorized_actions':[],
                'money_actions_enabled':False}
