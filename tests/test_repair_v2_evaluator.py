"""Real sandbox checks using only deliberately authored toy programs; no APIs."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("repair_v2_evaluator", ROOT / "experiments/code_repair_v2/src/evaluator.py")
evaluator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluator)


def task(base=None, hidden=None, solution="    return x\n", entry="solve", prompt="def solve(x):\n", atol=0):
    return {"task_id": "Toy/identity", "prompt": prompt, "canonical_solution": solution,
            "entry_point": entry, "base_input": base if base is not None else [[0], [1], [2]],
            "plus_input": hidden if hidden is not None else [[99]], "atol": atol}


@unittest.skipUnless(sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file(), "macOS sandbox is required")
class RepairV2EvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = {"python_executable": sys.executable, "evaluation_timeout_s": 10,
                      "reference_timeout_s": 20, "memory_limit_mb": 768,
                      "minimum_case_timeout_s": .08, "maximum_case_timeout_s": .15}
        cls.identity = task()
        cls.oracle = evaluator.prepare_reference(cls.config, cls.identity)

    def run_code(self, code, holdout=False, case=None, oracle=None, config=None):
        return evaluator.evaluate(config or self.config, case or self.identity, code,
                                  oracle or self.oracle, include_holdout=holdout)

    def test_all_public_cases_scanned_and_real_counts(self):
        result = self.run_code("def solve(x):\n    return x if x == 0 else -1\n")
        public = result["public"]
        self.assertTrue(result["sandboxed"])
        self.assertTrue(public["complete"])
        self.assertEqual((public["cases_checked"], public["passed_cases"], public["failed_cases"]), (3, 1, 2))
        self.assertEqual(public["first_failure"]["kind"], "output_mismatch")
        self.assertEqual(public["first_failure"]["error_type"], "OutputMismatch")
        self.assertIsNone(public["first_failure"]["line"])
        self.assertEqual(public["first_failure"]["candidate_traceback"], [])

    def test_public_pass_does_not_expose_or_score_hidden(self):
        code = "def solve(x):\n    return x if x < 10 else -1\n"
        public_only = self.run_code(code)
        self.assertTrue(public_only["public"]["passed"])
        self.assertNotIn("hidden", public_only)
        self.assertNotIn("full_pass", public_only)
        scored = self.run_code(code, holdout=True)
        self.assertTrue(scored["public"]["passed"])
        self.assertFalse(scored["hidden"]["passed"])
        self.assertFalse(scored["full_pass"])
        self.assertEqual(scored["hidden"]["first_failure"]["input"], "[99]")

    def test_optional_hidden_early_stop_has_known_failure_and_honest_counts(self):
        case = task(base=[[0], [1], [2]], hidden=[[99], [100], [101]])
        oracle = evaluator.prepare_reference(self.config, case)
        code = "def solve(x):\n    return x if x < 10 else -1\n"
        result = self.run_code(code, True, case, oracle, {**self.config, "holdout_stop_on_failure": True})
        self.assertEqual(result["public"]["cases_checked"], 3)
        self.assertTrue(result["public"]["scan_complete"])
        hidden = result["hidden"]
        self.assertEqual((hidden["cases_checked"], hidden["passed_cases"], hidden["failed_cases"]), (1, 0, 1))
        self.assertEqual(hidden["unchecked_cases"], 2)
        self.assertTrue(hidden["early_stopped"])
        self.assertTrue(hidden["outcome_known"])
        self.assertTrue(hidden["complete"])
        self.assertFalse(hidden["scan_complete"])
        self.assertFalse(result["full_pass"])
        all_passed = self.run_code("def solve(x):\n    return x\n", True, case, oracle, {**self.config, "holdout_stop_on_failure": True})
        self.assertTrue(all_passed["full_pass"])
        self.assertEqual(all_passed["hidden"]["cases_checked"], 3)
        self.assertFalse(all_passed["hidden"]["early_stopped"])

    def test_default_payload_has_no_reference_or_hidden_inputs(self):
        case = task(base=[[0]], hidden=[[17001]], solution="    return True\n")
        oracle = evaluator.prepare_reference(self.config, case)
        code = '''def solve(x):
    import pickle, io
    with io.open("payload.pkl", "rb") as handle:
        payload = pickle.load(handle)
    return ("canonical_solution" not in payload["task"]
            and "plus_input" not in payload["task"]
            and "plus" not in payload["oracle"])
'''
        result = self.run_code(code, case=case, oracle=oracle)
        self.assertTrue(result["public"]["passed"])
        self.assertNotIn("17001", json.dumps(result))

    def test_syntax_line_and_column_without_fake_test_execution(self):
        result = self.run_code("def solve(x)\n    return x\n")
        public = result["public"]
        self.assertTrue(public["complete"])
        self.assertFalse(public["scan_complete"])
        self.assertEqual(public["cases_checked"], 0)
        self.assertEqual(public["blocked_cases"], 3)
        self.assertEqual(public["first_failure"]["kind"], "syntax")
        self.assertEqual(public["first_failure"]["line"], 1)
        self.assertGreater(public["first_failure"]["column"], 0)

    def test_runtime_traceback_contains_only_candidate_frames(self):
        code = "def helper(x):\n    return missing_name + x\ndef solve(x):\n    return helper(x)\n"
        result = self.run_code(code)
        public = result["public"]
        self.assertEqual(public["failed_cases"], 3)
        self.assertEqual(public["cases_checked"], 3)
        failure = public["first_failure"]
        self.assertEqual(failure["kind"], "runtime")
        self.assertEqual(failure["error_type"], "NameError")
        self.assertEqual(failure["line"], 2)
        self.assertEqual([frame["function"] for frame in failure["candidate_traceback"]], ["solve", "helper"])
        self.assertNotIn("worker.py", json.dumps(failure))

    def test_load_error_classified_separately(self):
        result = self.run_code("import missing_course_toy_module\ndef solve(x):\n    return x\n")
        failure = result["public"]["first_failure"]
        self.assertEqual(failure["kind"], "load")
        self.assertEqual(failure["error_type"], "ModuleNotFoundError")
        self.assertEqual(failure["line"], 1)
        self.assertEqual(result["public"]["cases_checked"], 0)

    def test_candidate_assertion_is_a_runtime_exception_not_output_mismatch(self):
        result = self.run_code("def solve(x):\n    raise AssertionError('candidate assertion')\n")
        first = result["public"]["first_failure"]
        self.assertEqual(first["kind"], "runtime")
        self.assertEqual(first["error_type"], "AssertionError")
        self.assertEqual(first["line"], 2)
        self.assertGreater(first["column"], 0)

    def test_candidate_raised_syntax_error_is_not_a_parse_error(self):
        result = self.run_code("raise SyntaxError('raised while loading')\ndef solve(x):\n    return x\n")
        first = result["public"]["first_failure"]
        self.assertEqual(first["kind"], "load")
        self.assertEqual(first["line"], 1)

    def test_diverse_failures_and_per_case_timeout_all_scan(self):
        case = task(base=[[0], [1], [2], [3], [4]])
        oracle = evaluator.prepare_reference(self.config, case)
        code = '''def solve(x):
    if x == 1:
        return 9
    if x == 2:
        return absent_name
    if x == 3:
        while True:
            pass
    return x if x == 0 else -2
'''
        public = self.run_code(code, case=case, oracle=oracle)["public"]
        self.assertTrue(public["complete"])
        self.assertEqual((public["cases_checked"], public["passed_cases"], public["failed_cases"]), (5, 1, 4))
        self.assertEqual(len(public["failures"]), 3)
        self.assertEqual({failure["kind"] for failure in public["failures"]}, {"output_mismatch", "runtime", "timeout"})

    def test_late_runtime_error_does_not_evict_only_semantic_failure(self):
        case = task(base=[[0], [1], [2], [3], [4], [5]])
        oracle = evaluator.prepare_reference(self.config, case)
        code = '''def solve(x):
    if x == 0:
        raise NameError("missing first")
    if x == 1:
        raise IndexError("missing index")
    if x == 2:
        raise TypeError("wrong type")
    if x == 3:
        return -1
    if x == 4:
        raise ValueError("later runtime")
    while True:
        pass
'''
        public = self.run_code(code, case=case, oracle=oracle)["public"]
        self.assertEqual(public["first_failure"]["error_type"], "NameError")
        self.assertEqual({failure["kind"] for failure in public["failures"]}, {"output_mismatch", "runtime", "timeout"})
        self.assertEqual(public["cases_checked"], 6)

    def test_resource_interruption_is_unknown_not_a_passing_result(self):
        config = {**self.config, "evaluation_timeout_s": .02}
        result = self.run_code("def solve(x):\n    return x\n", config=config)
        self.assertFalse(result["public"]["complete"])
        self.assertEqual(result["infrastructure_status"], "wall_timeout")
        self.assertNotIn("full_pass", result)

    def test_special_polynomial_oracle_and_float_tolerance(self):
        polynomial = task(base=[[[0, 1]]], hidden=[[[-2, 1]]], entry="find_zero",
                          prompt="def find_zero(xs):\n", solution="    return -xs[0] / xs[1]\n", atol=1e-6)
        oracle = evaluator.prepare_reference(self.config, polynomial)
        result = self.run_code("def find_zero(xs):\n    return -xs[0] / xs[1] + 1e-8\n", True, polynomial, oracle)
        self.assertTrue(result["full_pass"])

    def test_candidate_cannot_read_other_files_or_parent_secret(self):
        with tempfile.TemporaryDirectory(prefix="repair-v2-outside-") as outer:
            outside = Path(outer) / "private-sentinel.txt"
            outside.write_text("outside payload must stay unreadable")
            case = task(base=[[0]], hidden=[], solution="    return True\n")
            oracle = evaluator.prepare_reference(self.config, case)
            code = f'''def solve(x):
    import os, io
    try:
        io.open({str(outside)!r}).read()
    except PermissionError:
        return "SILICONFLOW_API_KEY" not in os.environ
    return False
'''
            self.assertTrue(self.run_code(code, case=case, oracle=oracle)["public"]["passed"])

    def test_network_access_is_denied(self):
        case = task(base=[[0]], hidden=[], solution="    return True\n")
        oracle = evaluator.prepare_reference(self.config, case)
        code = '''def solve(x):
    import socket
    try:
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)
    except PermissionError:
        return True
    except Exception:
        return False
    return False
'''
        self.assertTrue(self.run_code(code, case=case, oracle=oracle)["public"]["passed"])


if __name__ == "__main__":
    unittest.main()
