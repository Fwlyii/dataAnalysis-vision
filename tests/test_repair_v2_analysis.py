"""Synthetic-only tests of denominators, missingness and public/hidden separation.

These tests do not call models or execute candidate programs. Their temporary
fixtures are labelled synthetic and cannot be exported into actual reports.
"""
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.code_repair_v2.src.analyze import ARMS, ClusterBootstrap, analyze, audit, observed, strong_observed, select_examples
from experiments.code_repair_v2.src.protocol import feedback_message


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows))


def outcome(task, arm, repeat, round_):
    if task == 0:
        return not (arm == 'resample' and round_ > 0)
    if task == 3:
        return True
    if round_ == 0:
        return False
    if arm == 'self_review':
        return task == 1 and repeat == 0 and round_ >= 2
    if arm == 'pass_fail':
        return task == 1 and round_ >= 2
    if arm == 'diagnostic':
        return task == 2
    if arm == 'counterexample':
        return round_ >= 2
    if arm == 'multi_counterexample':
        return task == 1 or (repeat != 2 and round_ >= 3)
    return False


def fixture(base):
    config = {'synthetic':True, 'batch_id':'synthetic-analysis-only', 'models':['Model-A','Model-B'],
              'replicates':3, 'arms':list(ARMS), 'rounds':5,
              'run_dir':str(base/'raw'), 'bootstrap':{'resamples':300,'seed':13}}
    path=base/'config.json';path.write_text(json.dumps(config,sort_keys=True)+'\n')
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    raw=base/'raw';raw.mkdir()
    (raw/'plan.json').write_text(json.dumps({'task_ids':[f'Toy/{i}' for i in range(4)],'config_sha256':sha}))
    responses,evaluations,holdouts=[],[],[]
    by_key,score_key={},{}
    for model in config['models']:
        for task in range(4):
            for repeat in range(3):
                for round_ in range(5):
                    for arm in (['seed'] if round_==0 else ARMS):
                        rid=f'{model}|Toy/{task}|{repeat}|{arm}|{round_}'
                        seed=f'{model}|Toy/{task}|{repeat}|seed|0'
                        passed=outcome(task,arm,repeat,round_)
                        kind='runtime' if task==2 else 'output_mismatch'
                        failure=None if passed else {'kind':kind,'stage':'runtime' if task==2 else 'test',
                            'case_index':0,'input':'(1,)','expected':'1','actual':'None' if task==2 else '-1',
                            'error_type':'NameError' if task==2 else 'AssertionError',
                            'error_message':'missing_name is not defined' if task==2 else 'output mismatch',
                            'line':2 if task==2 else None,'column':None,
                            'candidate_traceback':[{'line':2,'function':'f'}] if task==2 else []}
                        public={'complete':True,'outcome_known':True,'scan_complete':True,'passed':passed,
                            'total_cases':1,'cases_checked':1,'passed_cases':int(passed),'failed_cases':int(not passed),
                            'failures':[] if passed else [failure],'first_failure':failure}
                        meta={'record_id':rid,'model':model,'task_id':f'Toy/{task}','replicate':repeat,
                              'arm':arm,'round':round_,'sandboxed':True,'evaluation_seconds':.01}
                        ev={**meta,'public':public}
                        messages=[{'role':'user','content':f'SYNTHETIC ONLY: return 1 for task {task}.'}]
                        parent=None;feedback=None
                        if round_ and arm!='resample':
                            key=(model,task,repeat,'seed' if round_==1 else arm,round_-1)
                            previous=by_key[key];parent=previous['record_id']
                            feedback=feedback_message(arm,score_key[key])
                            messages=previous['request']['messages']+[
                                {'role':'assistant','content':previous['content']}, {'role':'user','content':feedback}]
                        code='def f(x):\n    return '+('1' if passed else 'missing_name' if task==2 else '-1')
                        row={**{key:value for key,value in meta.items() if key not in {'sandboxed','evaluation_seconds'}},
                            'batch_id':config['batch_id'],'parent_id':parent,'shared_seed_id':seed,
                            'feedback':feedback,'request':{'messages':messages},'response':{'model':model},
                            'content':'```python\n'+code+'\n```','code':code,
                            'usage':{'prompt_tokens':10*(round_+1),'completion_tokens':5,'total_tokens':10*(round_+1)+5},
                            'finish_reason':'stop','config_sha256':sha}
                        responses.append(row);evaluations.append(ev)
                        by_key[model,task,repeat,arm,round_]=row;score_key[model,task,repeat,arm,round_]=ev
                        if round_ in (0,4):
                            hidden_pass=passed and task!=3
                            holdouts.append({**meta,'public':public,'hidden':{'passed':hidden_pass,
                                'complete':True,'outcome_known':True,'scan_complete':hidden_pass,
                                'early_stopped':not hidden_pass,'total_cases':20,'cases_checked':20 if hidden_pass else 1,
                                'passed_cases':20 if hidden_pass else 0,'failed_cases':0 if hidden_pass else 1,
                                'unchecked_cases':0 if hidden_pass else 19},'full_pass':passed and hidden_pass})
    write_rows(raw/'responses.jsonl',responses);write_rows(raw/'evaluations.jsonl',evaluations)
    write_rows(raw/'holdout-evaluations.jsonl',holdouts)
    return path,responses,evaluations,holdouts


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'work').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='synthetic-analysis-',dir=ROOT/'work')
        self.base=Path(self.temp.name)
        self.config,self.responses,self.evaluations,self.holdouts=fixture(self.base)

    def tearDown(self):
        self.temp.cleanup()

    def run_analysis(self, partial=False):
        with redirect_stdout(io.StringIO()):
            return analyze(self.config, output=self.base/'report', allow_partial=partial)

    def test_complete_blocks_keep_tasks_as_independent_unit(self):
        result=self.run_analysis()
        self.assertEqual(result['task_clusters'],4)
        self.assertEqual(result['saved_physical_responses'],600)
        self.assertEqual(len(result['summary']),12)
        row=next(row for row in result['summary'] if row['model']=='Model-A' and row['arm']=='counterexample')
        self.assertEqual((row['programs'],row['initial_success'],row['final_success']),(12,3,9))
        self.assertEqual((row['initial_failures'],row['repaired']),(9,6))
        self.assertEqual((row['initial_visible_failures'],row['visible_repaired']),(6,6))
        self.assertEqual(row['final_public_pass_hidden_fail'],3)
        contrast=next(row for row in result['contrasts'] if row['model']=='__pooled__' and row['arm']=='counterexample' and row['baseline']=='resample')
        self.assertEqual((contrast['task_clusters'],contrast['paired_programs']),(4,24))
        self.assertAlmostEqual(contrast['delta_pp'],75.0)
        self.assertEqual(len(result['strong_endpoints']),24)
        self.assertEqual({row['round'] for row in result['strong_endpoints']},{0,4})
        bound=next(row for row in result['planned_contrast_bounds'] if row['model']=='__pooled__'
                   and row['arm']=='counterexample' and row['baseline']=='resample')
        self.assertEqual((bound['worst_case_delta_pp'],bound['best_case_delta_pp']),(75.0,75.0))

    def test_stopping_intermediate_strong_results_stay_unknown(self):
        result=self.run_analysis()
        row=next(row for row in result['summary'] if row['model']=='Model-A' and row['arm']=='diagnostic')
        self.assertIsNone(row['stopping_strong_rate'])
        self.assertLess(row['stopping_strong_measured_programs'],row['programs'])
        self.assertTrue({'diagnostic_repair', 'semantic_repair', 'regression'}
                        .issubset(result['missing_example_categories']))
        self.assertFalse(any(row['category']=='diagnostic_repair' for row in result['examples']))

    def test_real_schema_snapshot_preserves_missing_case_categories_without_raw_case_ids(self):
        # Exercise the real-export schema only inside this synthetic temporary
        # test directory. No fixture snapshot enters app/ or actual reports.
        config = json.loads(self.config.read_text())
        config['synthetic'] = False
        self.config.write_text(json.dumps(config, sort_keys=True) + '\n')
        sha = hashlib.sha256(self.config.read_bytes()).hexdigest()
        plan_path = self.base / 'raw/plan.json'
        plan = json.loads(plan_path.read_text())
        plan['config_sha256'] = sha
        plan_path.write_text(json.dumps(plan))
        for row in self.responses:
            row['config_sha256'] = sha
        write_rows(self.base / 'raw/responses.jsonl', self.responses)
        result = self.run_analysis()
        snapshot = json.loads((self.base / 'report/app-evidence.json').read_text())
        self.assertEqual(snapshot['missing_example_categories'], result['missing_example_categories'])
        self.assertIn('diagnostic_repair', snapshot['missing_example_categories'])
        for example in snapshot['examples']:
            self.assertIn('anonymous_task', example)
            self.assertNotIn('task_id', example)
            self.assertNotIn('record_ids', example)

    def test_heldout_early_failure_is_a_known_task_failure(self):
        score={'public':{'passed':True,'complete':True},'hidden':{'passed':False,'complete':True,
               'outcome_known':True,'scan_complete':False,'early_stopped':True},'full_pass':False}
        self.assertTrue(strong_observed(score))
        self.assertFalse(observed({'public':{'passed':False,'complete':False}}))
        self.assertFalse(strong_observed({'public':{'passed':True,'complete':True},'full_pass':False}))

    def test_known_public_failure_settles_joint_failure_without_imputing_hidden(self):
        score={'public':{'passed':False,'complete':True,'outcome_known':True,'scan_complete':False,
                         'cases_checked':0,'failed_cases':0,'candidate_resource_violation':True},
               'hidden':{'passed':False,'complete':False,'outcome_known':False,'cases_checked':0},
               'full_pass':False}
        self.assertTrue(strong_observed(score))
        score['full_pass']=True
        self.assertFalse(strong_observed(score))
        score['public'].update(passed=True,scan_complete=True)
        self.assertFalse(strong_observed(score))

    def test_strong_trajectories_require_complete_all_arm_task_blocks(self):
        complete=[]
        for ev in self.evaluations:
            passed=ev['public']['passed'] and ev['task_id']!='Toy/3'
            complete.append({**ev,'hidden':{'passed':passed,'complete':True,'outcome_known':True,
                             'scan_complete':passed},'full_pass':passed})
        write_rows(self.base/'raw/holdout-evaluations.jsonl',complete)
        result=self.run_analysis()
        self.assertEqual(result['strong_trajectory_task_clusters'],4)
        self.assertTrue(result['strong_trajectory_complete'])
        self.assertEqual(len(result['strong_curves']),60)
        self.assertTrue(all(row['programs']==12 for row in result['strong_curves']))
        self.assertEqual(len(json.loads((self.base/'report/figure-manifest.json').read_text())['figures']),6)
        # One intermediate unknown removes the entire task from this cohort,
        # while leaving the precommitted endpoint cohort unchanged.
        complete.pop(next(i for i,r in enumerate(complete) if r['task_id']=='Toy/2' and r['round']==2))
        write_rows(self.base/'raw/holdout-evaluations.jsonl',complete)
        result=self.run_analysis()
        self.assertEqual((result['task_clusters'],result['strong_trajectory_task_clusters']),(4,3))
        self.assertFalse(result['strong_trajectory_complete'])
        self.assertTrue(all(row['programs']==9 for row in result['strong_curves']))

    def test_response_and_http_attempt_counts_remain_distinct(self):
        attempts=[{'record_id':row['record_id'],'attempt':1} for row in self.responses]
        attempts += [{'record_id':self.responses[0]['record_id'],'attempt':1}]
        # Retry counters can reset after resume; the same physical ID still
        # identifies one actual extra transport attempt.
        write_rows(self.base/'raw/attempts.jsonl',attempts)
        result=self.run_analysis()
        self.assertEqual(result['request_accounting']['http_attempts'],601)
        self.assertEqual(result['request_accounting']['successful_responses'],600)
        self.assertEqual(result['request_accounting']['transport_retries'],1)
        self.assertTrue(result['coverage']['complete'])

    def test_missing_strong_endpoint_excludes_whole_task_not_only_model(self):
        missing=self.holdouts.pop()
        write_rows(self.base/'raw/holdout-evaluations.jsonl',self.holdouts)
        result=self.run_analysis(partial=True)
        self.assertEqual(result['task_clusters'],3)
        self.assertEqual(result['public_task_clusters'],4)
        self.assertTrue(all(row['programs']==9 for row in result['summary']))
        self.assertEqual(result['status'],'partial_complete_blocks_only')
        bound=next(row for row in result['planned_endpoint_bounds'] if row['model']==missing['model']
                   and row['arm']==missing['arm'] and row['round']==4)
        self.assertEqual(bound['unknown'],1)
        self.assertEqual(bound['planned_programs'],12)
        self.assertAlmostEqual(bound['best_case_rate']-bound['worst_case_rate'],1/12)
        integrity=json.loads((self.base/'report/integrity.json').read_text())
        self.assertEqual(integrity['missing_count'],1)
        self.assertEqual(integrity['missing'][0]['record_id'],missing['record_id'])

    def test_infrastructure_unknown_does_not_count_as_a_failure(self):
        row=self.evaluations[-1]
        row['public']={**row['public'],'passed':False,'complete':False,'outcome_known':False}
        self.holdouts=[row for row in self.holdouts if row['record_id']!=self.evaluations[-1]['record_id']]
        write_rows(self.base/'raw/evaluations.jsonl',self.evaluations)
        write_rows(self.base/'raw/holdout-evaluations.jsonl',self.holdouts)
        result=self.run_analysis(partial=True)
        self.assertEqual((result['task_clusters'],result['public_task_clusters']),(3,3))
        self.assertTrue(all(row['programs']==9 for row in result['summary']))

    def test_feedback_tampering_is_rejected(self):
        row=next(row for row in self.responses if row['arm']=='diagnostic' and row['round']==1)
        row['feedback']+='\nHIDDEN OUTCOME: PASS'
        write_rows(self.base/'raw/responses.jsonl',self.responses)
        with self.assertRaisesRegex(ValueError,'feedback differs'):
            self.run_analysis()

    def test_strong_recheck_never_rewrites_the_original_public_feedback(self):
        row=next(row for row in self.holdouts if row['model']=='Model-A' and row['task_id']=='Toy/2'
                 and row['replicate']==0 and row['round']==0)
        row['public']={**row['public'],'passed':True,'passed_cases':1,'failed_cases':0,
                       'failures':[],'first_failure':None}
        # The replay still fails the heldout, so full_pass remains false.
        write_rows(self.base/'raw/holdout-evaluations.jsonl',self.holdouts)
        result=self.run_analysis()
        summary=next(row for row in result['summary'] if row['model']=='Model-A' and row['arm']=='diagnostic')
        self.assertEqual(summary['initial_public_recheck_changes'],1)
        original=next(row for row in result['public_curves'] if row['model']=='Model-A'
                      and row['arm']=='diagnostic' and row['round']==0)
        self.assertEqual(original['passed_programs'],6)

    def test_protocol_and_candidate_code_hash_mismatches_are_rejected(self):
        self.responses[0]['code_sha256']='0'*64
        write_rows(self.base/'raw/responses.jsonl',self.responses)
        with self.assertRaisesRegex(ValueError,'code SHA-256 mismatch'):
            self.run_analysis()

    def test_synthetic_outputs_are_watermarked_and_never_app_snapshots(self):
        self.run_analysis()
        self.assertFalse((self.base/'report/app-evidence.json').exists())
        figures=json.loads((self.base/'report/figure-manifest.json').read_text())['figures']
        self.assertEqual(len(figures),5)
        for figure in figures:
            path=self.base/'report'/figure['file']
            root=ET.parse(path).getroot()
            self.assertEqual(root.tag,'{http://www.w3.org/2000/svg}svg')
            self.assertIn('合成自测数据',path.read_text())
            width,height=float(root.attrib['width']),float(root.attrib['height'])
            for element in root.iter():
                for key in ['x','x1','x2','cx']:
                    if key in element.attrib:
                        self.assertTrue(-1<=float(element.attrib[key])<=width+1,(figure,key,element.attrib))
                for key in ['y','y1','y2','cy']:
                    if key in element.attrib:
                        self.assertTrue(-1<=float(element.attrib[key])<=height+1,(figure,key,element.attrib))

    def test_small_cluster_counts_do_not_invent_confidence_intervals(self):
        bootstrap=ClusterBootstrap(['one-task'],draws=100)
        self.assertIsNone(bootstrap.mean({'one-task':1.0}))
        self.assertIsNone(bootstrap.ratio({'one-task':0},{'one-task':0}))


class AuditCaseCountTests(unittest.TestCase):
    """Logical suite failure labels are separate from executed-input counts."""
    def load_failure(self):
        return {'passed':False, 'complete':True, 'outcome_known':True, 'scan_complete':False,
                'load_failed':True, 'total_cases':3, 'cases_checked':0, 'passed_cases':0,
                'failed_cases':3, 'blocked_cases':3, 'unchecked_cases':3,
                'first_failure':{'kind':'load', 'error_type':'ModuleNotFoundError'}}

    def run_audit(self, public):
        row = {'record_id':'fixture', 'model':'M', 'task_id':'Toy/0', 'replicate':0, 'arm':'seed',
               'round':0, 'code':'def f():\n    return 1\n', 'request':{'messages':[]}}
        return audit({}, {'fixture':row}, {'fixture':{'public':public, 'sandboxed':True}},
                     {('M', 'Toy/0', 0, 'seed', 0):row}, 'fixture-config-hash')

    def test_valid_load_failure_is_known_program_failure_with_zero_executed_inputs(self):
        counts = self.run_audit(self.load_failure())
        self.assertEqual(counts['complete_public_verdicts'], 1)
        self.assertEqual(counts['load_failed_programs'], 1)
        self.assertEqual(counts['load_failed_logical_case_labels'], 3)
        self.assertEqual(counts['load_failed_blocked_inputs'], 3)
        self.assertEqual((counts['actual_cases_checked'], counts['actual_passed_cases'], counts['actual_failed_cases']),
                         (0, 0, 0))

    def test_load_failure_rejects_fabricated_counts_or_passing_unknown_verdicts(self):
        invalid = [('cases_checked', 1), ('passed_cases', 1), ('failed_cases', 2),
                   ('blocked_cases', 2), ('unchecked_cases', 2), ('total_cases', 0),
                   ('failed_cases', True), ('passed', True), ('scan_complete', True),
                   ('complete', False), ('outcome_known', False)]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                public = self.load_failure()
                public[field] = value
                with self.assertRaisesRegex(ValueError, 'invalid load-failure'):
                    self.run_audit(public)

    def test_normal_runtime_failure_still_requires_checked_equals_passed_plus_failed(self):
        public = {'passed':False, 'complete':True, 'outcome_known':True, 'scan_complete':True,
                  'total_cases':3, 'cases_checked':3, 'passed_cases':1, 'failed_cases':2,
                  'blocked_cases':0, 'unchecked_cases':0,
                  'first_failure':{'kind':'runtime', 'error_type':'NameError'}}
        counts = self.run_audit(public)
        self.assertEqual((counts['actual_cases_checked'], counts['actual_passed_cases'], counts['actual_failed_cases']),
                         (3, 1, 2))
        self.assertEqual(counts.get('load_failed_programs', 0), 0)
        public['cases_checked'] = 0
        with self.assertRaisesRegex(ValueError, 'tested case counts do not sum'):
            self.run_audit(public)

    def test_confirmed_resource_failure_with_zero_scanned_cases_remains_valid(self):
        public = {'passed':False, 'complete':True, 'outcome_known':True, 'scan_complete':False,
                  'total_cases':3, 'cases_checked':0, 'passed_cases':0, 'failed_cases':0,
                  'blocked_cases':0, 'unchecked_cases':3, 'candidate_resource_violation':True,
                  'first_failure':{'kind':'runtime', 'stage':'resource_limit', 'error_type':'MemoryLimitExceeded'}}
        counts = self.run_audit(public)
        self.assertEqual(counts['audited_candidate_resource_failures'], 1)
        self.assertEqual(counts['actual_cases_checked'], 0)
        self.assertEqual(counts['actual_failed_cases'], 0)
        self.assertEqual(counts.get('load_failed_programs', 0), 0)


class ExampleSelectionTests(unittest.TestCase):
    """Saved-step semantics only; no files, model calls, or aggregate effects."""
    def setUp(self):
        self.chains = {}
        self.public = {}
        self.strong = {}

    def add_chain(self, arm, public_values, strong_values, *, kinds=None, model='M', task='Toy/0', repeat=0):
        kinds = kinds or ['output_mismatch'] * len(public_values)
        sequence = []
        for index, (passed, strong_pass, kind) in enumerate(zip(public_values, strong_values, kinds)):
            rid = f'{model}|{task}|{repeat}|{arm}|{index}'
            error_type = {'syntax':'SyntaxError', 'runtime':'NameError', 'load':'MissingEntryPoint',
                          'timeout':'TimeoutError', 'output_mismatch':'OutputMismatch'}.get(kind, 'Unknown')
            failure = None if passed else {'kind':kind, 'stage':kind, 'case_index':0,
                'input':'(1,)', 'expected':'2', 'actual':'1', 'error_type':error_type,
                'error_message':'Synthetic saved error', 'line':2, 'column':1, 'candidate_traceback':[]}
            public = {'passed':passed, 'complete':True, 'outcome_known':True, 'scan_complete':True,
                      'total_cases':1, 'cases_checked':1, 'passed_cases':int(passed),
                      'failed_cases':int(not passed), 'failures':[] if passed else [failure],
                      'first_failure':failure}
            code = f'def f(x):\n    return x + {index}\n'
            row = {'record_id':rid, 'code':code, 'round':index, 'feedback':None}
            if index and arm != 'resample':
                row['feedback'] = feedback_message(arm, self.public[sequence[-1]['record_id']])
            sequence.append(row)
            self.public[rid] = {'public':public}
            if strong_pass is None:
                self.strong[rid] = {'public':copy.deepcopy(public),
                                    'hidden':{'passed':False, 'complete':False, 'outcome_known':False}}
            else:
                strong_public = copy.deepcopy(public)
                if strong_pass:
                    strong_public.update(passed=True)
                self.strong[rid] = {'public':strong_public, 'hidden':{'passed':strong_pass,
                    'complete':True, 'outcome_known':True, 'scan_complete':strong_pass}, 'full_pass':strong_pass}
        self.chains[model, task, repeat, arm] = sequence
        return sequence

    def select(self, *, models=('M',), arms=('diagnostic',), tasks=('Toy/0',), repeats=(0,)):
        return select_examples(list(models), list(arms), list(repeats), list(tasks),
            lambda model, task, repeat, arm: self.chains[model, task, repeat, arm],
            lambda row: self.public[row['record_id']], lambda row: self.strong[row['record_id']])

    def test_early_public_improvement_is_not_a_strong_repair_and_later_real_step_is_used(self):
        self.add_chain('counterexample', [False, True, True, False, True], [False, False, False, False, True])
        examples, missing = self.select(arms=('counterexample',))
        repair = next(row for row in examples if row['category']=='semantic_repair')
        self.assertEqual((repair['before_round'], repair['after_round']), (3, 4))
        self.assertEqual((repair['before_strong_pass'], repair['after_strong_pass']), (False, True))
        self.assertEqual(repair['actual_feedback'], self.chains['M', 'Toy/0', 0, 'counterexample'][4]['feedback'])

    def test_regression_uses_hidden_quality_drop_before_the_later_public_failure(self):
        self.add_chain('self_review', [True, True, False, False, False], [True, False, False, False, False])
        examples, _ = self.select(arms=('self_review',))
        regression = next(row for row in examples if row['category']=='regression')
        self.assertEqual((regression['before_round'], regression['after_round']), (0, 1))
        self.assertEqual((regression['before_strong_pass'], regression['after_strong_pass']), (True, False))
        self.assertTrue(regression['before_public']['passed'])
        self.assertTrue(regression['after_public']['passed'])

    def test_intermediate_real_syntax_feedback_can_support_a_diagnostic_case(self):
        sequence = self.add_chain('diagnostic', [False, False, False, True, True],
                                  [False, False, False, True, True],
                                  kinds=['output_mismatch', 'output_mismatch', 'syntax', 'runtime', 'runtime'])
        examples, _ = self.select()
        diagnostic = next(row for row in examples if row['category']=='diagnostic_repair')
        self.assertEqual((diagnostic['before_round'], diagnostic['after_round']), (2, 3))
        self.assertEqual(diagnostic['before_public']['first_failure']['error_type'], 'SyntaxError')
        self.assertEqual(diagnostic['actual_feedback'], feedback_message('diagnostic', self.public[sequence[2]['record_id']]))
        self.assertIn('SyntaxError', diagnostic['actual_feedback'])
        sequence[3]['feedback'] += '\nFabricated extra compiler feedback'
        examples, missing = self.select()
        self.assertIn('diagnostic_repair', missing)
        self.assertFalse(any(row['category']=='diagnostic_repair' for row in examples))

    def test_self_review_or_status_only_cannot_be_presented_as_error_or_counterexample_feedback(self):
        for arm in ('self_review', 'pass_fail', 'resample'):
            with self.subTest(arm=arm):
                self.add_chain(arm, [False, True, True, True, True], [False, True, True, True, True],
                               kinds=['runtime'] * 5)
                examples, missing = self.select(arms=(arm,))
                self.assertTrue({'diagnostic_repair', 'semantic_repair'}.issubset(missing))
                self.assertFalse(any(row['category'].endswith('_repair') for row in examples))
        self.add_chain('diagnostic', [False, True, True, True, True], [False, True, True, True, True])
        _, missing = self.select()
        self.assertIn('semantic_repair', missing)

    def test_unknown_intermediate_strong_results_do_not_become_failure_or_verified_repair(self):
        self.add_chain('diagnostic', [False, False, True, True, True], [False, None, True, True, True],
                       kinds=['runtime'] * 5)
        examples, missing = self.select()
        self.assertIn('diagnostic_repair', missing)
        self.assertFalse(any(row['category']=='diagnostic_repair' for row in examples))

    def test_selection_is_fixed_order_and_chooses_the_earliest_qualified_step(self):
        for task in ('Toy/first', 'Toy/second'):
            for model in ('Preferred', 'Other'):
                self.add_chain('diagnostic', [False, True, False, True, True], [False, True, False, True, True],
                               kinds=['runtime'] * 5, model=model, task=task)
        arguments = {'models':('Preferred', 'Other'), 'tasks':('Toy/first', 'Toy/second')}
        first, _ = self.select(**arguments)
        again, _ = self.select(**arguments)
        self.assertEqual(first, again)
        selected = next(row for row in first if row['category']=='diagnostic_repair')
        self.assertEqual((selected['model'], selected['task_id'], selected['before_round'], selected['after_round']),
                         ('Preferred', 'Toy/first', 0, 1))

    def test_public_pass_with_unknown_hidden_result_is_not_a_hidden_gap_case(self):
        sequence = self.add_chain('resample', [True] * 5, [True, True, True, True, None])
        _, missing = self.select(arms=('resample',))
        self.assertIn('diagnostic_hidden_gap', missing)
        final = sequence[-1]['record_id']
        self.strong[final] = {'public':{'passed':True, 'complete':True},
                              'hidden':{'passed':False, 'complete':True}, 'full_pass':False}
        examples, _ = self.select(arms=('resample',))
        gap = next(row for row in examples if row['category']=='diagnostic_hidden_gap')
        self.assertEqual(gap['after_round'], 4)
        self.assertTrue(gap['after_public']['passed'])
        self.assertFalse(gap['after_strong_pass'])


if __name__=='__main__':
    unittest.main()
