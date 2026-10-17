"""Local, read-only scene-to-math bridge for Texas Hold'em laboratory reviews.

The screen state supplied by callers is never authorization to gamble. Card
inference, money inference, and exact five-card hand ranking remain separate,
replaceable modules. We do not infer opponent holdings or bet instructions.
"""
from __future__ import annotations
import cv2
import numpy as np
from arc_vision.card_reader import TemplateCardReader,InvalidScreenshot
from arc_vision.money_reader import TemplateMoneyReader,MoneyReadError
from arc_poker_math.holdem import best_hand,InvalidCards

class CompositeObserver:
    def __init__(self, card_reader=None, money_reader=None):
        self.cards=card_reader or TemplateCardReader()
        self.money=money_reader or TemplateMoneyReader()

    def read(self,jpeg,*,screen_state='unknown'):
        if not isinstance(screen_state,str):raise ValueError('invalid_scene')
        # Explicit screen state hints are not independently authenticated. All
        # results are observational only, never permission to interact with UI.
        if not isinstance(jpeg,(bytes,bytearray)) or len(jpeg)<250 or len(jpeg)>650_000 or not jpeg.startswith(b'\xff\xd8'):
            raise InvalidScreenshot('invalid_jpeg')
        image=cv2.imdecode(np.frombuffer(jpeg,dtype=np.uint8),cv2.IMREAD_COLOR)
        if image is None:
            raise InvalidScreenshot('cannot_decode_image')
        cards=self.cards.read_image(image,screen_state=screen_state)
        amounts=self.money.read_image(image,screen_state=screen_state)
        hand=None
        if cards.get('quality')=='complete' and len(cards.get('board_cards',[])) in (3,4,5):
            try:hand=best_hand(cards['hero_cards'],cards['board_cards'])
            except (InvalidCards,ValueError):pass
        quality='partial'
        if cards.get('quality')=='complete' and amounts['pot']['status']=='recognized':
            quality='measured'
        elif cards.get('quality')!='complete' and amounts['pot']['status']!='recognized':
            quality='abstain'
        return {'mode':'local_visual_measurement','quality':quality,
                'screen_state':screen_state,'cards':cards,'amounts':amounts,
                'known_made_hand':hand,
                'money_actions_enabled':False,'action':None,
                'can_place_wager':False,'training_mode_only':True,
                'limitations':['unknown_opponent_range','visual_measurement_not_fully_calibrated',
                               'no_verified_turn_or_seat_identity']}
