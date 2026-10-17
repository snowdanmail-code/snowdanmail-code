import unittest
from dataclasses import replace
from arc_player.core import (Action, GameSnapshot, Proposal, AutonomySession,
                             DecisionGate, DecisionRejected, OperatorStop)
from arc_player.lab import ControlledPlayChipExecutor
from arc_player.gpt import parse_proposal, encode_snapshot

NOW = 1000.0

def snap(**kwargs):
    s = GameSnapshot(hand_id='h001', revision=2, captured_at=NOW-0.2,
       player_turn=True, game_mode='PLAY_CHIPS_NO_VALUE', screen='TABLE',
       street='flop', player_cards=('Ah', 'Kh'), community_cards=('Qh', 'Jh', '2c'),
       pot=120, stack=1600, to_call=20, min_raise_total=60, max_raise_total=500,
       allowed=frozenset({Action.FOLD, Action.CALL, Action.RAISE}),
       confidence=.995, verification_frames=2, table_id='test-table', other_players=3)
    return replace(s, **kwargs)

class FixedStrategy:
    def __init__(self, action=Action.CALL, chips=20, intent='defense'):
        self.action=action;self.chips=chips;self.intent=intent
    def decide(self, state):
        return Proposal(state.hand_id, state.revision, self.action, self.chips, .94,
                        'Reasoned simulator test', self.intent)

class StopStrategy(FixedStrategy):
    def __init__(self):
        super().__init__()
        self.session=None
    def decide(self, state):
        self.session.stop()
        return super().decide(state)

class TestSafetyProtocol(unittest.TestCase):
    def create(self, strateg=None, limit=200):
        exe=ControlledPlayChipExecutor()
        session=AutonomySession(strateg or FixedStrategy(),exe,DecisionGate(max_single_commit=limit),clock=lambda: NOW)
        return session,exe

    def test_call_full_cycle(self):
        session,exe=self.create(); act=session.step(snap())
        self.assertEqual(act.action,Action.CALL)
        self.assertEqual(act.total_chips,20)
        self.assertEqual(len(exe.history),1)
        self.assertIn('issued_not_confirmed',session.jsonl())

    def test_raise_and_bluff(self):
        session,exe=self.create(FixedStrategy(Action.RAISE,90,'bluff'))
        self.assertEqual(session.step(snap()).intent,'bluff')
        self.assertEqual(exe.history[0].total_chips,90)

    def test_free_check(self):
        session,exe=self.create(FixedStrategy(Action.CHECK,0,'check'))
        st=snap(to_call=0,allowed=frozenset({Action.CHECK,Action.BET}),min_raise_total=30)
        self.assertEqual(session.step(st).action,Action.CHECK)

    def test_duplicate_turn_no_second_action(self):
        session,exe=self.create(); session.step(snap())
        with self.assertRaisesRegex(DecisionRejected,'duplicate_turn'): session.step(snap())
        self.assertEqual(len(exe.history),1)

    def test_new_revision_continues(self):
        session,exe=self.create();session.step(snap())
        session.step(snap(revision=3))
        self.assertEqual(len(exe.history),2)

    def test_no_monetary_mode(self):
        session,exe=self.create()
        with self.assertRaisesRegex(DecisionRejected,'not_confirmed_play_chips'):
            session.step(snap(game_mode='cash'))
        self.assertFalse(exe.history)

    def test_no_turn(self):
        session,exe=self.create()
        with self.assertRaisesRegex(DecisionRejected,'not_players_turn'):
            session.step(snap(player_turn=False))

    def test_aging(self):
        session,exe=self.create()
        with self.assertRaisesRegex(DecisionRejected,'stale_frame'):
            session.step(snap(captured_at=NOW-4))

    def test_card_collision(self):
        session,exe=self.create()
        with self.assertRaisesRegex(DecisionRejected,'cards_missing_or_duplicate'):
            session.step(snap(community_cards=('Ah','Jh','2c')))

    def test_one_frame(self):
        session,exe=self.create()
        with self.assertRaisesRegex(DecisionRejected,'insufficient_observation'):
            session.step(snap(verification_frames=1))

    def test_ambiguous_chips(self):
        session,exe=self.create()
        with self.assertRaisesRegex(DecisionRejected,'inconsistent_chips'):
            session.step(snap(to_call=1700))

    def test_free_call_illegal(self):
        session,exe=self.create()
        with self.assertRaisesRegex(DecisionRejected,'illegal_call_when_free'):
            session.step(snap(to_call=0))

    def test_invalid_raise_below_min(self):
        session,exe=self.create(FixedStrategy(Action.RAISE,40))
        with self.assertRaisesRegex(DecisionRejected,'raise_outside_observed_limits'):
            session.step(snap())
        self.assertFalse(exe.history)

    def test_operator_limit(self):
        session,exe=self.create(FixedStrategy(Action.RAISE,400), limit=200)
        with self.assertRaisesRegex(DecisionRejected,'operator_chips_limit'):
            session.step(snap())

    def test_wrong_action(self):
        session,exe=self.create(FixedStrategy(Action.CHECK,0))
        with self.assertRaisesRegex(DecisionRejected,'illegal_action'):
            session.step(snap())

    def test_stop_before(self):
        session,exe=self.create();session.stop()
        with self.assertRaises(OperatorStop):session.step(snap())
        self.assertFalse(exe.history)

    def test_stop_after_model(self):
        st=StopStrategy();session,exe=self.create(st);st.session=session
        with self.assertRaises(OperatorStop):session.step(snap())
        self.assertFalse(exe.history)

    def test_gpt_requires_all_fields(self):
        with self.assertRaisesRegex(DecisionRejected,'gpt_schema_mismatch'):
            parse_proposal({'action':'raise'})

    def test_gpt_accepts_valid_schema(self):
        decision=dict(hand_id='h001',revision=2,action='raise',total_chips=90,
                      confidence=.94,reason='Value and blockers',intent='bluff')
        self.assertEqual(parse_proposal(decision).action,Action.RAISE)

    def test_gpt_invalid_action(self):
        decision=dict(hand_id='h001',revision=2,action='all_in',total_chips=90,
                      confidence=.94,reason='test',intent='value')
        with self.assertRaisesRegex(DecisionRejected,'gpt_action_field'):
            parse_proposal(decision)

    def test_observation_not_model_private_info(self):
        self.assertNotIn('opponent_hole_cards', encode_snapshot(snap()))

if __name__=='__main__': unittest.main()
