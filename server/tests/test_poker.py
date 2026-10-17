import os
import unittest
from poker_agent import verify_poker_plan, InvalidPokerPlan
from poker_session import PokerBudget


def plan(action='check', **kw):
    d=dict(action=action,is_hero_turn=True,is_table_visible=True,readability='clear',
           observed_cost=0.0,observed_stack=100.0,confidence=0.99,street='flop',reason='Example')
    d.update(kw)
    return d


class PokerPlanTests(unittest.TestCase):
    def test_sufficient_check(self):
        self.assertEqual(verify_poker_plan(plan())['action'],'check')
    def test_obscured_wait(self):
        self.assertEqual(verify_poker_plan(plan(readability='unclear'))['action'],'wait')
    def test_not_your_turn(self):
        self.assertEqual(verify_poker_plan(plan(is_hero_turn=False))['action'],'wait')
    def test_not_poker(self):
        self.assertEqual(verify_poker_plan(plan(is_table_visible=False))['action'],'wait')
    def test_confidence_too_low(self):
        self.assertEqual(verify_poker_plan(plan(confidence=.94))['action'],'wait')
    def test_unknown_street(self):
        self.assertEqual(verify_poker_plan(plan(street='unknown'))['action'],'wait')
    def test_call_denied_by_default(self):
        self.assertEqual(verify_poker_plan(plan('call',observed_cost=10))['action'],'wait')
    def test_call_under_cap(self):
        self.assertEqual(verify_poker_plan(plan('call',observed_cost=10),max_action_chips=20,remaining_chips=50)['action'],'call')
    def test_raise_above_cap(self):
        self.assertEqual(verify_poker_plan(plan('raise',observed_cost=30),max_action_chips=20,remaining_chips=50)['action'],'wait')
    def test_overremaining(self):
        self.assertEqual(verify_poker_plan(plan('call',observed_cost=10),max_action_chips=20,remaining_chips=5)['action'],'wait')
    def test_nan_rejected(self):
        with self.assertRaises(InvalidPokerPlan): verify_poker_plan(plan(confidence=float('nan')))
    def test_extra_fields_rejected(self):
        with self.assertRaises(InvalidPokerPlan): verify_poker_plan(plan(injection='touch anywhere'))
    def test_string_amount_rejected(self):
        with self.assertRaises(InvalidPokerPlan): verify_poker_plan(plan(observed_cost='999'))

class BudgetTests(unittest.TestCase):
    def test_reservation_and_replay(self):
        b=PokerBudget()
        r=b.reserve('session',1,'call',4,max_chips=10)
        self.assertEqual(r['charged_chips'],4)
        with self.assertRaisesRegex(ValueError,'replayed_frame'):
            b.reserve('session',1,'call',4,max_chips=10)
    def test_cumulative_cap(self):
        b=PokerBudget()
        b.reserve('session',1,'call',6,max_chips=10)
        with self.assertRaisesRegex(ValueError,'budget_limit'):
            b.reserve('session',2,'call',5,max_chips=10)
    def test_step_cap(self):
        b=PokerBudget()
        b.reserve('session',1,'check',0,max_actions=1)
        with self.assertRaisesRegex(ValueError,'action_limit'):
            b.reserve('session',2,'fold',0,max_actions=1)
    def test_wait_not_charged(self):
        b=PokerBudget()
        self.assertEqual(b.reserve('session',1,'wait',0,max_chips=0)['issued_actions'],0)
    def test_session_expires(self):
        now=[0.0]
        b=PokerBudget(clock=lambda:now[0])
        b.reserve('session',1,'check',0)
        now[0]=601
        with self.assertRaisesRegex(ValueError,'session_expired'):
            b.reserve('session',2,'check',0)

if __name__=='__main__': unittest.main()

class MoreBudgetTests(unittest.TestCase):
    def test_duplicate_suppression(self):
        now=[0.0]; b=PokerBudget(clock=lambda:now[0])
        b.reserve('s',1,'call',2,max_chips=20)
        now[0]=2.0
        with self.assertRaisesRegex(ValueError,'duplicate_action_cooldown'):
            b.reserve('s',2,'call',2,max_chips=20)
    def test_repeat_after_cooldown(self):
        now=[0.0]; b=PokerBudget(clock=lambda:now[0])
        b.reserve('s',1,'check',0)
        now[0]=9.0
        self.assertEqual(b.reserve('s',2,'check',0)['issued_actions'],2)
