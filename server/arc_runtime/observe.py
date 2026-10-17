"""Fail-closed observation state machine, independent of GPT and action execution.

Accepts typed scene snapshots from replaceable image interpreters. An observation
is a claim, not a command. No real-money or external-gesture effects.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

SCENES = frozenset(('cash_lobby','buyin_dialog','table_unseated','seat_selection',
                    'table_waiting','table_playing','action_controls','raise_panel',
                    'showdown','replay','session_history','disconnected','unknown'))
TABLE_SCENES = frozenset(('table_waiting','table_playing','action_controls','raise_panel','showdown'))

class InvalidObservation(ValueError): pass


def normalize(raw: dict, *, max_age_ms: int) -> dict:
    if not isinstance(raw,dict) or set(raw) != {'screen','confidence','game','frame_sequence',
        'frame_age_ms','is_replay','seated_players','active_players','hero_seated','hand_active'}:
        raise InvalidObservation('invalid_observation_fields')
    scene=raw['screen']
    if scene not in SCENES: raise InvalidObservation('unknown_scene_enum')
    if type(raw['confidence']) not in (int,float) or not 0 <= raw['confidence'] <= 1:
        raise InvalidObservation('invalid_confidence')
    if raw['game'] not in ('holdem_nl','omaha_pl','unknown'):
        raise InvalidObservation('invalid_game')
    if type(raw['frame_sequence']) is not int or not 0 <= raw['frame_sequence'] < 10**12:
        raise InvalidObservation('invalid_sequence')
    if type(raw['frame_age_ms']) is not int or not 0 <= raw['frame_age_ms'] <= 3600000:
        raise InvalidObservation('invalid_age')
    if type(raw['is_replay']) is not bool: raise InvalidObservation('invalid_replay')
    for key in ('hero_seated','hand_active'):
        if raw[key] is not None and type(raw[key]) is not bool:
            raise InvalidObservation(f'invalid_{key}')
    for key in ('seated_players','active_players'):
        n=raw[key]
        if n is not None and (type(n) is not int or not 0 <= n <= 10):
            raise InvalidObservation(f'invalid_{key}')
    seated, active = raw['seated_players'],raw['active_players']
    if seated is not None and active is not None and active>seated:
        raise InvalidObservation('players_contradiction')
    if raw['is_replay'] and scene!='replay':
        raise InvalidObservation('replay_flag_contradiction')
    if scene == 'replay' and not raw['is_replay']:
        raise InvalidObservation('missing_replay_flag')
    # Non-playing scene cannot claim current hand. Restrict to no assertions;
    # don't force LLM to invent hero status for lobby/seat dialog.
    if scene in ('cash_lobby','buyin_dialog','session_history','disconnected') and raw['hand_active'] is True:
        raise InvalidObservation('hand_contradiction')
    if raw['frame_age_ms']>max_age_ms: raise InvalidObservation('stale_frame')
    return raw


@dataclass
class Track:
    last_sequence: int = -1
    candidate: str = 'unknown'
    count: int = 0
    stable: str = 'unknown'
    should_leave_after_hand: bool = False


class Observer:
    def __init__(self, policy:dict):
        self.policy=policy
        self.tracks:dict[str,Track]={}

    def reset(self):
        self.tracks.clear()

    def evaluate(self,session: str,obs:dict) -> dict:
        if not isinstance(session,str) or not 8 <= len(session) <= 64 or not all(c.isalnum() or c=='-' for c in session):
            raise InvalidObservation('invalid_session')
        obs=normalize(obs,max_age_ms=self.policy['frame_max_age_ms'])
        if session not in self.tracks and len(self.tracks) >= 64:
            # Fixed upper bound. Evict oldest session; no unbounded memory growth.
            self.tracks.pop(next(iter(self.tracks)))
        track=self.tracks.setdefault(session,Track())
        seq=obs['frame_sequence']
        if seq<=track.last_sequence:
            raise InvalidObservation('duplicate_or_out_of_order_frame')
        track.last_sequence=seq
        scene=obs['screen']
        # Never trust unknown, obscured or low confidence enough to persist.
        usable=(obs['confidence']>=self.policy['min_confidence'] and
            obs['game']!='omaha_pl' and scene!='unknown')
        if scene in ('replay','disconnected') or not usable:
            track.candidate='unknown';track.count=0;track.stable='unknown'
            track.should_leave_after_hand=False
            return self._report(obs,track,'hold', 'replay_or_disconnect' if scene in ('replay','disconnected') else 'unreliable_screen')
        if scene!=track.candidate:
            track.candidate=scene; track.count=1
        else:
            track.count+=1
        if track.count >= self.policy['stable_frames']:
            track.stable=scene
        if track.stable!=scene:
            return self._report(obs,track,'hold','await_stable_frame')
        if obs['game']!='holdem_nl' and scene in TABLE_SCENES:
            return self._report(obs,track,'hold','variant_unconfirmed')
        # A table with only 2 *seated* players must be left after the hand, not
        # merely because only two people remain active in the pot.
        if scene in TABLE_SCENES and obs['hero_seated'] is True and obs['seated_players']==2:
            track.should_leave_after_hand=True
        elif scene in TABLE_SCENES and obs['seated_players'] is not None and obs['seated_players']>=3:
            track.should_leave_after_hand=False
        if (track.should_leave_after_hand and obs['hand_active'] is False and
            scene == 'table_waiting' and obs['seated_players']==2):
            # Advisory only: never emits click targets or navigates app.
            return self._report(obs,track,'review_table_exit','only_two_seated_after_hand')
        return self._report(obs,track,'observe','stable_observation')

    @staticmethod
    def _report(obs,track,recommendation,reason):
        return {'scene':obs['screen'],'stable_scene':track.stable,'recommendation':recommendation,
                'reason':reason,'exit_candidate_after_hand':track.should_leave_after_hand,
                'frame_sequence':obs['frame_sequence'],'money_actions_enabled':False,
                'tap_command':None}
