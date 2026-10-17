"""Conservative timeline verifier for *provided* vision observations.

Works with structured fields extracted by a replaceable vision model. Does not
recognize images itself. It never produces Android commands or monetary actions.
Invalid transitions are rejected without mutating the previous trusted snapshot.
"""
from __future__ import annotations
from dataclasses import dataclass,field
from arc_poker_math.holdem import parse_cards, InvalidCards

PHASES={'waiting':0,'preflop':1,'flop':2,'turn':3,'river':4,'showdown':5}
EXPECTED_BOARD={'waiting':0,'preflop':0,'flop':3,'turn':4,'river':5}

@dataclass
class State:
    last_seq:int=-1
    hand_id:str|None=None
    phase:str='waiting'
    board:tuple[str,...]=()
    hero:tuple[str,...]=()
    confirmed:bool=False
    paused:bool=False

class HandTimeline:
    def __init__(self):
        self.state=State()

    def reset(self):
        self.state=State()

    def observe(self, *,frame_seq:int,hand_id:str,phase:str,
                hero_cards:list[str],board_cards:list[str],
                overlay:bool=False,connected:bool=True,
                playback:bool=False,variant:str='holdem_nl') -> dict:
        prev=self.state
        if type(frame_seq) is not int or frame_seq<=prev.last_seq:
            return self._result('rejected','duplicate_or_out_of_order',prev)
        if not isinstance(hand_id,str) or not (4 <= len(hand_id) <= 32) or not hand_id.isalnum():
            return self._result('rejected','invalid_hand_id',prev)
        if phase not in PHASES:
            return self._result('rejected','invalid_phase',prev)
        if variant!='holdem_nl':
            return self._result('ignored','not_texas_holdem',prev)
        if overlay or not connected or playback:
            # Advance sequence to prevent reuse of a frame after an overlay.
            prev.last_seq=frame_seq
            prev.paused=True
            reason='replay' if playback else ('disconnected' if not connected else 'overlay')
            return self._result('paused',reason,prev)
        try:
            hero=parse_cards(hero_cards,allowed_counts={0,2})
            board=parse_cards(board_cards,allowed_counts={0,3,4,5})
            parse_cards(hero+board)
        except InvalidCards as err:
            return self._result('rejected','cards_'+str(err),prev)
        if phase in EXPECTED_BOARD and len(board)!=EXPECTED_BOARD[phase]:
            return self._result('rejected','phase_board_mismatch',prev)
        new_hand=hand_id!=prev.hand_id
        if new_hand:
            # New hand is accepted only if fully identified; first frame may
            # start on flop when the recorder skipped earlier frames.
            if prev.hand_id is not None and prev.phase!='showdown' and phase!='waiting':
                # Switching IDs midhand can be expected after a fold. This is
                # a warning, not a card claim or permission to take action.
                warning='hand_transition_unseen'
            else:
                warning=None
            self.state=State(last_seq=frame_seq,hand_id=hand_id,phase=phase,
                             board=board,hero=hero,confirmed=True,paused=False)
            return self._result('accepted',warning or 'new_hand',self.state)
        if prev.paused:
            # A replay/overlay disconnection requires a new stable observation;
            # do not infer continued continuity from one frame.
            prev.last_seq=frame_seq
            prev.paused=False
            prev.confirmed=False
            return self._result('needs_confirmation','resync_after_pause',prev)
        if PHASES[phase]<PHASES[prev.phase] and not (phase=='waiting' and prev.phase=='showdown'):
            return self._result('rejected','street_regressed',prev)
        if prev.hero and hero and hero!=prev.hero:
            return self._result('rejected','hero_cards_changed',prev)
        if prev.board and board[:len(prev.board)]!=prev.board:
            return self._result('rejected','board_changed',prev)
        prev.last_seq=frame_seq
        prev.phase=phase
        if hero: prev.hero=hero
        prev.board=board
        prev.confirmed=True
        return self._result('accepted','consistent_progression',prev)

    @staticmethod
    def _result(status,reason,state):
        return {'status':status,'reason':reason,'hand_id':state.hand_id,
                'phase':state.phase,'board_cards':list(state.board),
                'hero_cards':list(state.hero),'frame_sequence':state.last_seq,
                'observation_only':True,'tap_command':None,
                'can_place_wager':False,'confidence_not_guaranteed':True}
