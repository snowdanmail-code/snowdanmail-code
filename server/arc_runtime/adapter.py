"""Lossless-minded adapter: sparse GPT screen observations -> typed scene.

Never invent seated count, total player participation or hand activity when
not visible in v0.5 screen schema. Without direct evidence, exit cannot fire.
"""
from lobby_agent import validate_screen


def from_gpt_screen(observation:dict, *,frame_sequence:int, frame_age_ms:int)->dict:
    item=validate_screen(observation)
    scene=item['screen']
    scenes = {'cash_lobby','buyin_dialog','table_waiting','table_playing',
              'action_controls','raise_panel','showdown','replay','disconnected',
              'table_unseated','seat_selection','session_history'}
    if scene not in scenes: scene='unknown'
    variant=item['variant']
    game=variant if variant in ('holdem_nl','omaha_pl') else 'unknown'
    if variant == 'five_card_omaha_pl': game='omaha_pl'
    # The model's hero-stack is not evidence of a seated count.
    # Some table renderings show a hero avatar even when not seated.
    return {'screen':scene, 'confidence':item['confidence'], 'game':game,
            'frame_sequence':frame_sequence,'frame_age_ms':frame_age_ms,
            'is_replay':scene=='replay', 'seated_players':None,
            'active_players':None, 'hero_seated':None,'hand_active':None}
