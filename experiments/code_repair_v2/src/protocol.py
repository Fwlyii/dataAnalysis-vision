"""Frozen public-only feedback projections for the extension experiment."""
from __future__ import annotations

import copy
import json

ARMS = ['resample', 'self_review', 'pass_fail', 'diagnostic', 'counterexample', 'multi_counterexample']
ARM_NAMES = {'resample':'独立重采样','self_review':'自行检查','pass_fail':'仅通过状态',
             'diagnostic':'语法与运行诊断','counterexample':'单个失败反例','multi_counterexample':'多反例与测试摘要'}
INSTRUCTION = ('Review your previous implementation against the original task. Correct any correctness issue '
               'you find; otherwise preserve the working implementation. Return the complete implementation '
               'in one Python code block, including required imports. Preserve the specified interface.')
CASE_FIELDS = ('case_index','input','expected','actual','error_type','error_message')
DIAGNOSTIC_FIELDS = ('kind','stage','error_type','error_message','line','column','source_line','candidate_traceback')


def initial_prompt(task):
    return ('Implement the following Python programming task. Return the complete implementation '
            'in one Python code block, including required imports. Preserve the specified interface.\n\n' + task['prompt'])


def _project(failure, fields):
    return {key:copy.deepcopy(failure[key]) for key in fields if key in failure}


def feedback_message(arm, evaluation):
    """Never accesses held-out outcomes or reference code, including when present."""
    if arm not in ARMS or arm == 'resample':
        raise ValueError('This arm has no revision feedback: ' + str(arm))
    if arm == 'self_review':
        return INSTRUCTION
    public = evaluation['public']
    if public.get('complete') is False:
        raise ValueError('Incomplete diagnostic execution cannot be used as feedback')
    feedback = {'diagnostic_status':'PASS' if public['passed'] else 'FAIL'}
    failures = public.get('failures') or ([public['first_failure']] if public.get('first_failure') else [])
    if not public['passed']:
        if not failures:
            raise ValueError('A diagnostic failure must have a recorded cause')
        if arm == 'diagnostic':
            feedback['diagnostic'] = _project(failures[0], DIAGNOSTIC_FIELDS)
        elif arm == 'counterexample':
            feedback['first_failure'] = _project(failures[0], CASE_FIELDS)
        elif arm == 'multi_counterexample':
            feedback['failures'] = [_project(f, CASE_FIELDS) for f in failures[:3]]
    if arm == 'multi_counterexample':
        feedback['test_summary'] = {key:public[key] for key in ('total_cases','passed_cases','failed_cases','cases_checked','blocked_cases','unchecked_cases') if key in public}
    return 'Diagnostic test feedback:\n' + json.dumps(feedback,ensure_ascii=False) + '\n\n' + INSTRUCTION


def extract_code(text):
    import re
    blocks = re.findall(r'```(?:python|py)?\s*\n(.*?)```', text, re.S|re.I)
    return '\n\n'.join(block.strip() for block in blocks) if blocks else text.strip()
