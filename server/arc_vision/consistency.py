"""Semantic cross-checks for an extracted screen, independent of screen reader.

Distinguishes fully verified, incomplete, and self-contradictory observations.
No OCR, no automation, no financial authorization.
"""
from __future__ import annotations
import math
from arc_poker_math.holdem import InvalidCards,parse_cards

SCREENS_WITH_BOARD={'table_playing','action_controls','raise_panel','showdown','replay'}
BLOCKING={'disconnected','replay','session_history','unknown'}


def assess_screen(screen:dict, *, is_overlay:bool=False) -> dict:
    errors=[];warnings=[]
    if not isinstance(screen,dict):
        return {'quality':'rejected','errors':['not_an_object'],'warnings':[],
                'safe_to_infer_cards':False,'action':None}
    state=screen.get('screen','unknown')
    variant=screen.get('variant','unknown')
    hero=screen.get('hero_cards',[])
    board=screen.get('board_cards',[])
    try:
        if variant!='holdem_nl':
            warnings.append('variant_not_confirmed_holdem')
        parse_cards(hero,allowed_counts={0,2})
        parse_cards(board,allowed_counts={0,3,4,5})
        parse_cards(tuple(hero)+tuple(board))
    except InvalidCards as exc:
        errors.append(str(exc))
    if state not in SCREENS_WITH_BOARD and board:
        errors.append('board_outside_playing_scene')
    if state in BLOCKING or is_overlay:
        warnings.append('not_live_unobscured_table')
    if len(hero)!=2:
        warnings.append('hero_cards_not_confirmed')
    pot=screen.get('pot')
    if pot is not None and (type(pot) not in (int,float) or not math.isfinite(pot) or pot<0):
        errors.append('invalid_pot')
    if screen.get('is_hero_turn') is True and state not in ('action_controls','raise_panel'):
        # Be conservative; models often mistake pre-action rows for the hero's turn.
        warnings.append('turn_not_confirmed_by_scene')
    if screen.get('visible_buttons') and (state in BLOCKING or is_overlay):
        warnings.append('buttons_in_blocked_scene')
    quality='rejected' if errors else ('incomplete' if warnings else 'consistent')
    return {'quality':quality,'errors':errors,'warnings':warnings,
            'safe_to_infer_cards':not errors and len(hero)==2 and variant=='holdem_nl'
                                  and state in SCREENS_WITH_BOARD and state not in BLOCKING and not is_overlay,
            'action':None}
