import unittest
from dataclasses import replace
from lab_strategy.engine import (LabSpot,build_study,ev_call,ev_bet,make_gpt_brief,validate_lab_choice)

BASE = LabSpot(pot=100,to_call=0,effective_stack=300,equity=.18,
    estimated_fold_probability=.65,opponents=1,position='late',street='turn',
    board_threat=.6,blocker_relevance=.7,villain_observations=100)

class StrategyLabTest(unittest.TestCase):
    def test_can_consider_evidence_based_bluff(self):
        st=build_study(BASE)
        self.assertTrue(any(l.intent=='bluff' for l in st.lines))
        self.assertEqual(st.baseline_id,'bluff_33')
    def test_without_blockers_no_bluff(self):
        self.assertFalse(any(l.intent=='bluff' for l in build_study(replace(BASE,blocker_relevance=.1)).lines))
    def test_no_bluff_out_of_position(self):
        self.assertFalse(any(l.intent=='bluff' for l in build_study(replace(BASE,position='early')).lines))
    def test_no_bluff_multiway(self):
        self.assertFalse(any(l.intent=='bluff' for l in build_study(replace(BASE,opponents=3)).lines))
    def test_no_bluff_thin_sample(self):
        self.assertFalse(any(l.intent=='bluff' for l in build_study(replace(BASE,villain_observations=3)).lines))
    def test_no_bluff_low_fold_rate(self):
        self.assertFalse(any(l.intent=='bluff' for l in build_study(replace(BASE,estimated_fold_probability=.30)).lines))
    def test_can_value_bet(self):
        st=build_study(replace(BASE,equity=.88))
        self.assertTrue(any(l.intent=='value' for l in st.lines))
    def test_check_if_unclear(self):
        st=build_study(replace(BASE,reliable_observation=False))
        self.assertEqual(st.lines,())
        self.assertIsNone(st.baseline_id)
        with self.assertRaises(ValueError):make_gpt_brief(st)
    def test_face_bet_fold_and_call(self):
        st=build_study(replace(BASE,to_call=30,equity=.4))
        self.assertEqual({l.action for l in st.lines},{'fold','call'})
        self.assertAlmostEqual([l.simplified_ev for l in st.lines if l.action=='call'][0],22)
    def test_call_math(self):
        self.assertAlmostEqual(ev_call(.25,100,20),10)
    def test_bet_math(self):
        self.assertAlmostEqual(ev_bet(0,100,50,.6),40)
    def test_cap_bet_by_stack(self):
        st=build_study(replace(BASE,equity=.80,effective_stack=25))
        self.assertTrue(all(l.chips<=25 for l in st.lines))
        self.assertEqual(len([l for l in st.lines if l.action=='bet']),1)
    def test_bad_input_rejected(self):
        for replacement in ({'equity':1.1},{'estimated_fold_probability':float('nan')},
                            {'pot':0},{'opponents':0},{'position':'dealer'},
                            {'to_call':350},{'villain_observations':-1}):
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):build_study(replace(BASE,**replacement))
    def test_brief_never_executes(self):
        b=make_gpt_brief(build_study(BASE))
        self.assertFalse(b['execution_allowed'])
        self.assertEqual(b['mode'],'offline_synthetic_poker_study')
        self.assertEqual(len(b['candidates']),4)
    def test_validate_model_choice(self):
        st=build_study(BASE)
        result=validate_lab_choice(st,{'candidate_id':'bluff_33','reason':'credible line',
                  'confidence':.5,'bluff_considerations':'opponent can fold'})
        self.assertFalse(result['execution_allowed'])
        self.assertEqual(result['real_game_actions'],[])
    def test_reject_unknown_choice(self):
        st=build_study(BASE)
        with self.assertRaises(ValueError):
            validate_lab_choice(st,{'candidate_id':'all_in','reason':'bad',
                      'confidence':.9,'bluff_considerations':'none'})
    def test_reject_extra_fields(self):
        st=build_study(BASE)
        with self.assertRaises(ValueError):
            validate_lab_choice(st,{'candidate_id':'check','reason':'test',
             'confidence':.8,'bluff_considerations':'no', 'send_to_1win':True})
    def test_reject_bad_confidence(self):
        st=build_study(BASE)
        with self.assertRaises(ValueError):
            validate_lab_choice(st,{'candidate_id':'check','reason':'test',
             'confidence':float('nan'),'bluff_considerations':'no'})

if __name__=='__main__':unittest.main()
