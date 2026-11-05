"""Retrospective-score bookkeeping tests; no candidate execution or API calls."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from experiments.code_repair_v2.src.legacy_reevaluate import ARMS, summarize, without_hidden_answers


class LegacyAnalysisTests(unittest.TestCase):
    def test_hidden_case_payload_is_not_exported(self):
        value={'public':{'passed':True},'hidden':{'passed':False,'complete':True,'cases_checked':1,
               'first_failure':{'input':'SEALED_INPUT_SENTINEL','expected':'SEALED_ANSWER_SENTINEL'},
               'failures':[{'actual':'SEALED_ACTUAL_SENTINEL'}]},'full_pass':False}
        output=without_hidden_answers(value)
        self.assertFalse(output['hidden']['passed'])
        self.assertEqual(output['hidden']['cases_checked'],1)
        self.assertEqual(len(output['hidden']['failure_payload_sha256']),64)
        self.assertNotIn('SEALED_',json.dumps(output))
        self.assertIn('first_failure',value['hidden'])  # Original object was not mutated.

    def test_stronger_tests_do_not_retroactively_choose_a_delivery_version(self):
        raw,old,scores=[],{},{}
        for task in range(2):
            for round_ in range(5):
                for arm in (['seed'] if round_==0 else ARMS):
                    rid=f'Model|Toy/{task}|{arm}|{round_}'
                    raw.append({'record_id':rid,'model':'Model','task_id':f'Toy/{task}','arm':arm,'round':round_})
                    # Both old public and Mini passed the seed; the stronger
                    # holdout catches task1 except in the final version.
                    old[rid]={'full_pass':True,'diagnostic_pass':True,'hidden_pass':True}
                    passed=task==0 or round_==4
                    scores[rid]={'public':{'passed':True,'complete':True},
                                 'hidden':{'passed':passed,'complete':True},'full_pass':passed}
        manifest={'legacy_reference_spec':'SYNTHETIC ONLY','totals':{'holdout_count':40}}
        (ROOT/'work').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='synthetic-legacy-analysis-',dir=ROOT/'work') as folder:
            out=Path(folder)
            summarize(raw,old,scores,out,manifest,{'synthetic':True})
            import csv
            with (out/'legacy-vs-strong-summary.csv').open(encoding='utf-8-sig') as stream:
                rows=list(csv.DictReader(stream))
            self.assertTrue(all(row['strong_final_pass']=='2' for row in rows))
            # The old diagnostic policy selects the SEED, not the newly-correct
            # final version; otherwise this would incorrectly report2.
            self.assertTrue(all(row['old_first_diagnostic_pass_policy_strong_success']=='1' for row in rows))
            with (out/'legacy-vs-strong-curves.csv').open(encoding='utf-8-sig') as stream:
                curves=list(csv.DictReader(stream))
            self.assertEqual(len(curves),20)
            self.assertTrue(all(row['task_clusters']=='2' for row in curves))
            self.assertTrue(all(row['strong_rate']=='0.5' for row in curves if row['round']=='0'))
            self.assertTrue(all(row['strong_rate']=='1.0' for row in curves if row['round']=='4'))


if __name__=='__main__':
    unittest.main()
