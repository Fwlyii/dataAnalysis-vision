"""Resource outcome decisions with mocked interruptions and one real sandbox toy."""
from __future__ import annotations

import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.code_repair_v2.src import resource_policy as policy
from experiments.code_repair_v2.src.evaluator import prepare_reference


TASK = {"task_id": "Toy/identity", "prompt": "def solve(x):\n", "canonical_solution": "    return x\n",
        "entry_point": "solve", "base_input": [[0], [1], [2]], "plus_input": [[99]], "atol": 0}
ORACLE = {"base": {"outputs": [0, 1, 2], "times": [.001] * 3},
          "plus": {"outputs": [99], "times": [.001]}}
CODE = "def solve(x):\n    return x\n"


def passed(total=3):
    return {"passed": True, "complete": True, "scan_complete": True, "outcome_known": True,
            "total_cases": total, "cases_checked": total, "passed_cases": total, "failed_cases": 0,
            "unchecked_cases": 0, "blocked_cases": 0, "failures": [], "first_failure": None}


def interruption(reason="memory_limit", total=3, checked=0, failures=0):
    failure = {"kind": "resource", "stage": "worker_resource_limit", "error_type": reason,
               "error_message": reason, "case_index": None, "input": None, "expected": None,
               "actual": None, "candidate_traceback": []}
    first = ({**failure, "kind": "output_mismatch", "error_type": "OutputMismatch", "input": "[0]"}
             if failures else failure)
    return {"passed": False, "complete": False, "scan_complete": False, "outcome_known": False,
            "total_cases": total, "cases_checked": checked, "passed_cases": checked-failures,
            "failed_cases": failures, "unchecked_cases": total-checked, "blocked_cases": 0,
            "infrastructure_status": reason, "resource_failure": failure,
            "first_failure": first, "failures": [first]}


def result(public=None, hidden=None):
    value = {"public": public or passed(), "sandboxed": True, "evaluation_seconds": .1}
    if hidden is not None:
        value["hidden"] = hidden
    return value


class ResourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)
        self.config = {"memory_limit_mb": 768, "evaluation_timeout_s": 60}

    def tearDown(self):
        self.temp.cleanup()

    def call(self, answers, holdout=False):
        with patch.object(policy, "evaluate", side_effect=copy.deepcopy(answers)) as mock:
            actual = policy.evaluate_resolved(self.config, TASK, CODE, ORACLE,
                                             include_holdout=holdout, run_dir=self.run, record_id="toy")
        return actual, mock

    def audit(self):
        return [json.loads(line) for line in (self.run / "resource-audit.jsonl").read_text().splitlines()]

    def test_complete_public_pass_needs_no_retest_or_audit_and_no_fake_full_pass(self):
        actual, mock = self.call([result()])
        self.assertEqual(mock.call_count, 1)
        self.assertTrue(actual["public"]["passed"])
        self.assertNotIn("full_pass", actual)
        self.assertFalse((self.run / "resource-audit.jsonl").exists())

    def test_observed_partial_failure_settles_fail_without_fabricating_counts(self):
        raw = result(interruption(checked=2, failures=1), interruption(total=1))
        actual, mock = self.call([raw], True)
        self.assertEqual(mock.call_count, 1)
        self.assertTrue(actual["public"]["complete"])
        self.assertTrue(actual["public"]["outcome_known"])
        self.assertFalse(actual["public"]["scan_complete"])
        self.assertEqual([actual["public"][k] for k in ("cases_checked", "passed_cases", "failed_cases", "unchecked_cases")], [2, 1, 1, 1])
        self.assertFalse(actual["hidden"]["complete"])
        self.assertFalse(actual["full_pass"])
        self.assertEqual(self.audit()[0]["evaluations"][0]["result"], raw)

    def test_repeated_memory_requires_canonical_control_and_preserves_real_zero_counts(self):
        raw = result(interruption(), interruption(total=1))
        control = result(passed(), passed(1))
        actual, mock = self.call([raw, control, raw], True)
        self.assertEqual(mock.call_count, 3)
        self.assertEqual(mock.call_args_list[1].args[2], TASK["prompt"] + TASK["canonical_solution"])
        self.assertTrue(all(call.kwargs["include_holdout"] for call in mock.call_args_list))
        self.assertFalse(actual["full_pass"])
        self.assertEqual(actual["public"]["first_failure"]["error_type"], "MemoryLimitExceeded")
        self.assertEqual(actual["public"]["first_failure"]["kind"], "runtime")
        self.assertEqual(actual["public"]["first_failure"]["stage"], "resource_limit")
        self.assertEqual(actual["public"]["failed_cases"], 0)
        self.assertEqual(actual["public"]["cases_checked"], 0)
        self.assertEqual(actual["public"]["unchecked_cases"], 3)
        self.assertFalse(actual["hidden"]["complete"])
        self.assertTrue(actual["hidden"]["not_evaluated"])
        log = self.audit()[0]
        self.assertEqual(len(log["evaluations"]), 2)
        self.assertTrue(log["canonical_control"]["passed_same_scope"])
        self.assertEqual(log["canonical_baseline"]["canonical_code_sha256"], hashlib.sha256(CODE.encode()).hexdigest())
        for evaluation in log["evaluations"]:
            self.assertEqual(evaluation["result_sha256"], policy._digest(evaluation["result"]))

    def test_repeated_wall_limit_has_distinct_error_type(self):
        raw = result(interruption("wall_timeout"))
        actual, _ = self.call([raw, result(), raw])
        self.assertEqual(actual["public"]["first_failure"]["error_type"], "WallTimeLimitExceeded")

    def test_unknown_cpu_or_sigkill_is_never_called_candidate_failure(self):
        raw = result(interruption("cpu_or_process_resource_limit"))
        actual, mock = self.call([raw])
        self.assertEqual(mock.call_count, 1)
        self.assertFalse(actual["public"]["complete"])
        self.assertNotIn("full_pass", actual)
        self.assertEqual(actual["resource_resolution"]["decision"], "unresolved_infrastructure_interruption")

    def test_other_infrastructure_budget_exhaustion_remains_unknown(self):
        actual, mock = self.call([result(interruption("split_time_budget_exhausted"))])
        self.assertEqual(mock.call_count, 1)
        self.assertFalse(actual["public"]["complete"])
        self.assertNotIn("full_pass", actual)

    def test_failing_canonical_control_prevents_resource_attribution(self):
        raw = result(interruption())
        actual, mock = self.call([raw, result(interruption())])
        self.assertEqual(mock.call_count, 2)
        self.assertFalse(actual["public"]["complete"])
        self.assertNotIn("full_pass", actual)
        self.assertEqual(actual["resource_resolution"]["decision"], "canonical_control_failed_or_incomplete")

    def test_recovered_retest_returns_the_real_result(self):
        actual, mock = self.call([result(interruption()), result(), result()])
        self.assertEqual(mock.call_count, 3)
        self.assertTrue(actual["public"]["passed"])
        self.assertEqual(actual["public"]["cases_checked"], 3)
        self.assertNotIn("full_pass", actual)
        self.assertEqual(actual["resource_resolution"]["decision"], "completed_candidate_retest")

    def test_different_retest_interruption_stays_unknown(self):
        actual, _ = self.call([result(interruption()), result(), result(interruption("cpu_or_process_resource_limit"))])
        self.assertFalse(actual["public"]["complete"])
        self.assertNotIn("full_pass", actual)
        self.assertEqual(actual["resource_resolution"]["decision"], "nonreproduced_resource_interruption")

    def test_hidden_resource_failure_never_rewrites_passed_public_split(self):
        raw = result(passed(), interruption(total=1))
        actual, mock = self.call([raw, result(passed(), passed(1)), raw], True)
        self.assertEqual(mock.call_count, 3)
        self.assertEqual(actual["public"], passed())
        self.assertTrue(actual["hidden"]["complete"])
        self.assertFalse(actual["hidden"]["scan_complete"])
        self.assertEqual(actual["hidden"]["first_failure"]["error_type"], "MemoryLimitExceeded")
        self.assertFalse(actual["full_pass"])

    def test_resource_attribution_uses_retest_split_when_failure_moves_to_hidden(self):
        initial = result(interruption(), interruption(total=1))
        retest = result(passed(), interruption(total=1))
        actual, _ = self.call([initial, result(passed(), passed(1)), retest], True)
        self.assertEqual(actual["public"], passed())
        self.assertFalse(actual["hidden"]["passed"])
        self.assertEqual(actual["resource_resolution"]["normalized_split"], "hidden")
        self.assertFalse(actual["full_pass"])

    def test_hidden_observed_failure_needs_no_control_or_retest(self):
        actual, mock = self.call([result(passed(), interruption(total=2, checked=1, failures=1))], True)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(actual["public"], passed())
        self.assertTrue(actual["hidden"]["complete"])
        self.assertEqual(actual["hidden"]["cases_checked"], 1)
        self.assertFalse(actual["full_pass"])

    def test_full_pass_requires_both_complete_passing_splits(self):
        actual, _ = self.call([result(passed(), passed(1))], True)
        self.assertTrue(actual["full_pass"])

    def test_threaded_audit_has_one_valid_json_record_per_interruption(self):
        raw = result(interruption("cpu_or_process_resource_limit"))
        with patch.object(policy, "evaluate", side_effect=lambda *a, **kw: copy.deepcopy(raw)):
            with ThreadPoolExecutor(max_workers=8) as pool:
                actual = list(pool.map(lambda i: policy.evaluate_resolved(self.config, TASK, CODE, ORACLE,
                    run_dir=self.run, record_id=str(i)), range(16)))
        logs = self.audit()
        self.assertEqual(len(logs), 16)
        self.assertEqual({row["record_id"] for row in logs}, {str(i) for i in range(16)})
        self.assertEqual(len({row["audit_id"] for row in logs}), 16)

    @unittest.skipUnless(sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file(), "macOS sandbox required")
    def test_real_sandbox_toy_preserves_complete_result(self):
        config = {"python_executable": sys.executable, "evaluation_timeout_s": 10,
                  "reference_timeout_s": 15, "memory_limit_mb": 768}
        oracle = prepare_reference(config, TASK)
        actual = policy.evaluate_resolved(config, TASK, CODE, oracle,
                                         include_holdout=True, run_dir=self.run, record_id="real-toy")
        self.assertTrue(actual["sandboxed"])
        self.assertTrue(actual["full_pass"])
        self.assertEqual(actual["public"]["cases_checked"], 3)
        self.assertEqual(actual["hidden"]["cases_checked"], 1)


if __name__ == "__main__":
    unittest.main()
