"""Feedback information boundaries; fixtures are deliberately synthetic."""
import json
import unittest
from experiments.code_repair_v2.src.protocol import feedback_message,INSTRUCTION

class FeedbackProtocolTests(unittest.TestCase):
    def setUp(self):
        failure={'case_index':0,'input':'VISIBLE_INPUT','expected':'VISIBLE_EXPECTED','actual':'VISIBLE_ACTUAL',
                 'error_type':'NameError','error_message':'name is not defined','kind':'runtime','stage':'call',
                 'line':3,'column':8,'source_line':'return missing(x)',
                 'candidate_traceback':[{'line':3,'function':'solve','source_line':'return missing(x)'}]}
        self.evaluation={'public':{'passed':False,'complete':True,'total_cases':5,'passed_cases':1,'failed_cases':4,
                                  'cases_checked':5,'blocked_cases':0,'unchecked_cases':0,
                                  'first_failure':failure,'failures':[dict(failure,case_index=i,input=f'VISIBLE_{i}') for i in range(4)]},
                         'hidden':{'input':'HIDDEN_CANARY','expected':'HIDDEN_EXPECTED_CANARY','passed':True},'canonical_solution':'REFERENCE_CANARY'}

    def projected(self,arm):
        return json.loads(feedback_message(arm,self.evaluation).split('\n\n')[0].split('\n',1)[1])

    def test_all_feedback_excludes_holdout_and_reference(self):
        for arm in ['self_review','pass_fail','diagnostic','counterexample','multi_counterexample']:
            text=feedback_message(arm,self.evaluation)
            self.assertNotIn('HIDDEN',text);self.assertNotIn('REFERENCE_CANARY',text)

    def test_self_review_has_no_execution_information(self):
        self.assertEqual(feedback_message('self_review',{}),INSTRUCTION)

    def test_status_does_not_reveal_cases_or_diagnostics(self):
        self.assertEqual(self.projected('pass_fail'),{'diagnostic_status':'FAIL'})

    def test_diagnostics_contains_location_but_no_oracle_examples(self):
        value=self.projected('diagnostic')['diagnostic']
        self.assertEqual(value['line'],3);self.assertEqual(value['source_line'],'return missing(x)')
        self.assertFalse(set(value)&{'input','expected','actual'})

    def test_single_example_excludes_enriched_stack(self):
        value=self.projected('counterexample')['first_failure']
        self.assertIn('input',value);self.assertIn('expected',value)
        self.assertNotIn('candidate_traceback',value);self.assertNotIn('line',value)

    def test_multi_example_is_bounded_and_counts_are_actual(self):
        value=self.projected('multi_counterexample')
        self.assertEqual(len(value['failures']),3)
        self.assertEqual(value['test_summary']['passed_cases'],1)
        self.assertEqual(value['test_summary']['cases_checked'],5)

    def test_incomplete_execution_cannot_be_presented_as_full_test_summary(self):
        self.evaluation['public']['complete']=False
        with self.assertRaises(ValueError):feedback_message('multi_counterexample',self.evaluation)

    def test_independent_resampling_never_accepts_feedback(self):
        with self.assertRaises(ValueError):feedback_message('resample',self.evaluation)

if __name__=='__main__':unittest.main()
