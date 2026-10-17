"""Offline read-only glyph recognizer for fixed-layout 1win Hold'em screenshots.

Privacy: the checked-in atlas contains monochrome glyph masks only. The reader does
not save frames, read chat messages, connect to 1win or issue input commands.
Confidence is a simple template similarity diagnostic, NOT a calibrated posterior.
Unsupported geometry, incomplete template coverage and darkened cards abstain.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import cv2
import numpy as np

WIDTH, HEIGHT = 709, 1536
_ALLOWED_STATES = frozenset({'live_table', 'showdown', 'unknown'})
_BLOCKED_STATES = frozenset({'replay','disconnected','menu','buyin_dialog','lobby',
                             'overlay','session_history','raise_panel'})


class InvalidScreenshot(ValueError):
    pass


def _extract_mask(image: np.ndarray, x: int, y: int, part: str) -> tuple[np.ndarray, float]:
    region = ((x + 3, y + 3, x + 43, y + 36) if part == 'rank'
              else (x + 2, y + 34, x + 40, y + 68))
    x0, y0, x1, y1 = region
    piece = image[y0:y1, x0:x1]
    bg = image[y+15:y+43,x+48:x+65]
    if piece.shape[:2] != ((33,40) if part=='rank' else (34,38)) or bg.size == 0:
        raise InvalidScreenshot('card_crop_outside_frame')
    background = float(np.median(cv2.cvtColor(bg, cv2.COLOR_BGR2GRAY)))
    grey = cv2.cvtColor(piece, cv2.COLOR_BGR2GRAY)
    return (grey < background-48).astype(np.uint8), background


def _similarity(left: np.ndarray, right: np.ndarray) -> float:
    both = int(np.count_nonzero(np.logical_and(left, right)))
    either = int(np.count_nonzero(np.logical_or(left, right)))
    return both / max(either,1)


class TemplateCardReader:
    def __init__(self, atlas_path: str | Path | None = None):
        atlas_path = Path(atlas_path or Path(__file__).with_name('glyph_atlas.json'))
        contents = json.loads(atlas_path.read_text(encoding='utf-8'))
        if contents.get('schema_version')!='1.0.0' or contents.get('canonical_size')!=[WIDTH,HEIGHT]:
            raise ValueError('incompatible_glyph_atlas')
        self.templates = {}
        for seat in ('board','hero'):
            self.templates[seat] = {}
            for part in ('rank','suit'):
                keys=contents[seat][part]
                required={'s','h','d','c'} if part=='suit' else set()
                if not required.issubset(keys):
                    raise ValueError('incomplete_suit_atlas')
                dims=(33,40) if part=='rank' else (34,38)
                self.templates[seat][part]={
                    label:[np.asarray(a,dtype=np.uint8).reshape(dims).astype(bool) for a in samples]
                    for label,samples in keys.items()
                }

    def _classify(self, mask: np.ndarray, seat: str, part: str) -> dict:
        candidates=sorted([
            (max(_similarity(mask.astype(bool), template) for template in samples),label)
            for label,samples in self.templates[seat][part].items()
        ], reverse=True)
        if not candidates:
            return {'value':None, 'reason':'no_templates'}
        first_score, first_label = candidates[0]
        second = candidates[1][0] if len(candidates)>1 else 0
        absolute_threshold = .83 if part=='rank' else .91
        margin_threshold = .15 if part=='rank' else .105
        if first_score < absolute_threshold or first_score-second < margin_threshold:
            return {'value':None, 'reason':'glyph_ambiguous',
                    'similarity':round(first_score,3),'margin':round(first_score-second,3)}
        return {'value':first_label,'similarity':round(first_score,3)}

    def read_card(self,image:np.ndarray, *, index:int, seat:str) -> dict:
        if seat not in ('board','hero'):
            raise ValueError('invalid_seat')
        if index<0 or index>=(5 if seat=='board' else 2):
            raise ValueError('invalid_card_index')
        x,y=(123+93*index,716) if seat=='board' else (347+73*index,1167)
        rank_mask,lightness=_extract_mask(image,x,y,'rank')
        if lightness<185:
            return {'card':None, 'status':'not_visible', 'reason':'empty_or_dimmed_slot'}
        suit_mask,_=_extract_mask(image,x,y,'suit')
        rank=self._classify(rank_mask,seat,'rank')
        suit=self._classify(suit_mask,seat,'suit')
        if rank['value'] is None or suit['value'] is None:
            return {'card':None,'status':'uncertain', 'reason':'unrecognized_glyph',
                    'rank':rank,'suit':suit}
        return {'card':rank['value']+suit['value'],'status':'recognized',
                'rank_similarity':rank['similarity'], 'suit_similarity':suit['similarity']}

    def read(self,frame:bytes, *, screen_state:str='unknown') -> dict:
        if screen_state not in _ALLOWED_STATES | _BLOCKED_STATES:
            raise InvalidScreenshot('unknown_screen_state')
        if len(frame)<200 or len(frame)>650_000 or not frame.startswith(b'\xff\xd8'):
            raise InvalidScreenshot('invalid_jpeg_size_or_signature')
        if screen_state in _BLOCKED_STATES:
            return {'quality':'abstain','reason':'screen_state_blocked','screen_state':screen_state,
                    'hero_cards':[], 'board_cards':[], 'action':None}
        raw=np.frombuffer(frame,dtype=np.uint8)
        if cv2.haveImageReader is None:  # defensive static compatibility
            raise InvalidScreenshot('decoder_unavailable')
        image=cv2.imdecode(raw,cv2.IMREAD_COLOR)
        if image is None:
            raise InvalidScreenshot('cannot_decode_image')
        return self.read_image(image, screen_state=screen_state)

    def read_image(self, image: np.ndarray, *, screen_state: str='unknown') -> dict:
        """Read a previously decoded BGR frame; permits single JPEG decoding per snapshot."""
        if screen_state not in _ALLOWED_STATES | _BLOCKED_STATES:
            raise InvalidScreenshot('unknown_screen_state')
        if screen_state in _BLOCKED_STATES:
            return {'quality':'abstain','reason':'screen_state_blocked','screen_state':screen_state,
                    'hero_cards':[], 'board_cards':[], 'action':None}
        if not isinstance(image,np.ndarray) or image.ndim != 3 or image.shape[2]!=3:
            raise InvalidScreenshot('invalid_decoded_image')
        h,w=image.shape[:2]
        if w<450 or h<800 or w>2160 or h>4600 or abs(w/h-WIDTH/HEIGHT)>.008:
            return {'quality':'abstain','reason':'unsupported_geometry','size':[w,h],
                    'hero_cards':[], 'board_cards':[], 'action':None}
        if (w,h)!=(WIDTH,HEIGHT):
            image=cv2.resize(image,(WIDTH,HEIGHT),interpolation=cv2.INTER_AREA)
        # All visible cards must be confirmed. Never fill in hidden information.
        hero=[self.read_card(image,index=j,seat='hero') for j in range(2)]
        board=[self.read_card(image,index=j,seat='board') for j in range(5)]
        visible_board=[s['card'] for s in board if s['status']=='recognized']
        uncertain_any=any(s['status']=='uncertain' for s in board+hero)
        # A partially darkened visible board is deliberately treated as incomplete.
        board_holes=any(s['status']=='not_visible' for s in board[:len(visible_board)])
        if len(visible_board) not in (0,3,4,5):
            board_holes=True
        # While no hand is dealt, empty hole slots are normal, not a broken capture.
        hero_cards=[s['card'] for s in hero if s['status']=='recognized']
        if len(set(hero_cards+visible_board)) != len(hero_cards+visible_board):
            uncertain_any=True
        # Incomplete atlas coverage expected for 8+ rank/suit combinations not seen in training.
        quality=('complete' if not uncertain_any and not board_holes and len(hero_cards)==2
                 else 'abstain')
        return {'quality':quality,
                'reason':None if quality=='complete' else 'incomplete_or_unverified_cards',
                'screen_state':screen_state,
                'hero_cards':hero_cards if quality=='complete' else [],
                'board_cards':visible_board if quality=='complete' else [],
                'raw_observation':{'hero':hero,'board':board},
                'action':None,'money_actions_enabled':False,
                'reader_version':'arc_fixed_glyph_v1.1.0'}
