"""Holdout journal/stream tests with explicitly synthetic, isolated toy batches."""
from contextlib import redirect_stdout
import copy
import io
import json
from pathlib import Path
import pickle
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.code_repair_v2.src import holdout


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def known_result(config, task, code, oracle, include_holdout=False, *, run_dir=None, record_id=None):
    assert include_holdout is True
    assert config["holdout_stop_on_failure"] is True
    assert config["evaluation_timeout_s"] == 300
    assert config["split_time_budget_s"] == 295
    assert config["cpu_limit_s"] == 295
    assert run_dir is not None and record_id
    def split(count):
        return {"passed": True, "complete": True, "outcome_known": True,
                "scan_complete": True, "total_cases": count, "cases_checked": count,
                "passed_cases": count, "failed_cases": 0, "unchecked_cases": 0,
                "failures": [], "first_failure": None}
    return {"sandboxed": True, "public": split(len(task["base_input"])),
            "hidden": split(len(task["plus_input"])), "full_pass": True,
            "evaluation_seconds": .001}


class HoldoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="synthetic-holdout-only-")
        self.base = Path(self.temp.name)
        self.out = self.base / "run"
        self.out.mkdir()
        (self.out / "oracles").mkdir()
        self.config = {"synthetic": True, "batch_id": "synthetic-holdout-only", "run_dir": str(self.out),
            "models": ["ToyModel"], "replicates": 1, "arms": ["self_review", "counterexample"],
            "rounds": 5, "maximum_physical_responses": 9, "maximum_measured_holdouts": 3,
            "holdout_concurrency": 2, "holdout_timeout_s": 300, "python_executable": sys.executable}
        self.path = self.base / "config.json"
        self.path.write_text(json.dumps(self.config))
        self.sha = holdout.digest(self.path.read_bytes())
        self.task = {"task_id": "Toy/0", "entry_point": "solve", "prompt": "def solve(x):\n",
                     "canonical_solution": "    return x\n", "base_input": [[0], [1]],
                     "plus_input": [[9], [10]], "atol": 0}
        split = {"task_id": "Toy/0", "reference_spec_sha256": "toy-reference-spec",
                 "public_inputs_sha256": "toy-public-hash", "holdout_inputs_sha256": "toy-hidden-hash"}
        self.manifest = {"dataset_sha256": "synthetic-dataset-hash", "split_manifest_sha256": "synthetic-split-hash",
                         "task_splits": [split]}
        runtime_sha = holdout.canonical_sha256(holdout.runtime_identity(self.config))
        plan = {"batch_id": self.config["batch_id"], "config_sha256": self.sha,
                "reference_source_hashes": holdout.source_hashes(), "reference_code_sha256": "synthetic-reference-code-hash",
                "runtime_sha256": runtime_sha, "dataset_sha256": self.manifest["dataset_sha256"],
                "task_ids": ["Toy/0"], "expected_requests": 9, "manifest": self.manifest}
        (self.out / "plan.json").write_text(json.dumps(plan))
        (self.out / "reference-preflight.json").write_text(json.dumps({"complete": True, "config_sha256": self.sha}))
        self.oracle_path = self.out / "oracles/Toy_0.pkl"
        oracle = {"base": {"outputs": [0, 1], "times": [.00001, .00001]},
                  "plus": {"outputs": [9, 10], "times": [.00001, .00001]}}
        self.oracle_path.write_bytes(pickle.dumps(oracle))
        metadata = {**{key: value for key, value in plan.items() if key in ("config_sha256", "dataset_sha256", "reference_code_sha256", "runtime_sha256")},
                    **split, "canonical_code_sha256": holdout.digest((self.task["prompt"] + self.task["canonical_solution"]).encode()),
                    "public_cases": 2, "holdout_cases": 2, "reference_pass": True, "sandboxed": True,
                    "oracle_sha256": holdout.digest(self.oracle_path.read_bytes())}
        self.oracle_path.with_suffix(".json").write_text(json.dumps(metadata))
        self.responses = []
        for round_ in range(5):
            for arm in (["seed"] if round_ == 0 else self.config["arms"]):
                code = "def solve(x):\n    return x\n"
                self.responses.append({"record_id": f"ToyModel|Toy/0|rep0|{arm}|{round_}",
                    "batch_id": self.config["batch_id"], "config_sha256": self.sha,
                    "model": "ToyModel", "task_id": "Toy/0", "replicate": 0, "arm": arm, "round": round_,
                    "code": code, "code_sha256": holdout.digest(code.encode()), "response": {"model": "ToyModel"}})
        write_rows(self.out / "responses.jsonl", self.responses)
        self.loader = patch.object(holdout, "load_benchmark", return_value=([self.task], self.manifest))
        self.loader.start()

    def tearDown(self):
        self.loader.stop()
        self.temp.cleanup()

    def run_once(self, evaluator=known_result, **runner_options):
        with patch.object(holdout, "evaluate_resolved", side_effect=evaluator) as mocked, redirect_stdout(io.StringIO()):
            state = holdout.HoldoutRunner(self.path, poll_seconds=.02, **runner_options).run()
        return state, mocked.call_count

    def test_only_seed_and_finals_written_and_resume_has_no_duplicates(self):
        state, count = self.run_once()
        self.assertEqual((count, state["measured"], state["source_responses"]), (3, 3, 9))
        self.assertTrue(state["complete"])
        rows = holdout.read_journal(self.out / "holdout-evaluations.jsonl")
        self.assertEqual({row["round"] for row in rows}, {0, 4})
        self.assertEqual(len({row["record_id"] for row in rows}), 3)
        state, count = self.run_once()
        self.assertEqual(count, 0)
        self.assertEqual(state["by_model"]["ToyModel"], {"measured": 3, "passed": 3, "failed": 0})

    def test_unknowns_are_separate_events_and_can_be_retried(self):
        def mixed(config, task, code, oracle, include_holdout=False, **kwargs):
            result = known_result(config, task, code, oracle, include_holdout, **kwargs)
            mixed.calls += 1
            if mixed.calls == 1:
                result["hidden"]["complete"] = False
                result.pop("full_pass")
                result["infrastructure_status"] = "synthetic-infrastructure-timeout"
            return result
        mixed.calls = 0
        state, count = self.run_once(mixed)
        self.assertEqual((state["measured"], state["pending_available"], state["failed"]), (2, 1, 0))
        self.assertEqual(len(holdout.read_journal(self.out / "holdout-evaluations.jsonl")), 2)
        events = holdout.read_journal(self.out / "holdout-events.jsonl")
        self.assertEqual(sum(event["event_type"] == "holdout_unknown" for event in events), 1)
        state, count = self.run_once()
        self.assertEqual(count, 1)
        self.assertTrue(state["complete"])
        self.assertEqual((state["unknown_attempts"], state["unknown_unresolved"]), (1, 0))

    def test_all_rounds_reuses_endpoints_and_default_reuses_expanded_journal(self):
        state, count = self.run_once()
        self.assertEqual(count, 3)
        state, count = self.run_once(all_rounds=True, concurrency=1)
        self.assertEqual((count, state["measured"], state["expected_holdouts"]), (6, 9, 9))
        self.assertTrue(state["complete"])
        self.assertEqual(state["scheduler_concurrency"], 1)
        self.assertEqual(state["measured_primary_holdouts"], 3)
        rows = holdout.read_journal(self.out / "holdout-evaluations.jsonl")
        self.assertEqual(len({row["record_id"] for row in rows}), 9)
        self.assertEqual({row["round"] for row in rows}, set(range(5)))
        scope = json.loads((self.out / "holdout-scope.json").read_text())
        self.assertTrue(scope["all_rounds_requested"])
        self.assertEqual(scope["expected_primary_measurements"], 3)
        self.assertFalse(scope["used_for_model_feedback"])
        self.assertFalse(scope["used_for_candidate_selection"])
        state, count = self.run_once()
        self.assertEqual((count, state["measured"], state["expected_holdouts"]), (0, 3, 3))
        self.assertTrue(state["complete"])
        self.assertEqual(len(holdout.read_journal(self.out / "holdout-evaluations.jsonl")), 9)
        self.assertTrue(json.loads((self.out / "holdout-scope.json").read_text())["all_rounds_requested"])

    def test_fresh_all_rounds_measures_every_physical_candidate(self):
        state, count = self.run_once(all_rounds=True)
        self.assertEqual((count, state["measured"], state["source_responses"]), (9, 9, 9))
        self.assertEqual(state["measurement_scope"], "all_rounds")
        self.assertTrue(state["complete"])

    def test_duplicate_source_identity_stops_without_scoring(self):
        with (self.out / "responses.jsonl").open("a") as handle:
            handle.write(json.dumps(self.responses[0]) + "\n")
        with self.assertRaisesRegex(holdout.IntegrityError, "Duplicate source"):
            self.run_once()
        self.assertFalse((self.out / "holdout-evaluations.jsonl").read_text())

    def test_oracle_hash_tampering_is_not_a_measured_failure(self):
        self.oracle_path.write_bytes(b"synthetic-broken-oracle")
        with self.assertRaisesRegex(holdout.IntegrityError, "checksum"):
            self.run_once()
        self.assertFalse((self.out / "holdout-evaluations.jsonl").read_text())

    def test_code_hash_tampering_stops_before_scoring(self):
        bad = copy.deepcopy(self.responses)
        bad[-1]["code"] += "# changed after saving\n"
        write_rows(self.out / "responses.jsonl", bad)
        with self.assertRaisesRegex(holdout.IntegrityError, "code checksum"):
            self.run_once()

    def test_unsandboxed_result_is_integrity_failure(self):
        def unsafe(*args, **kwargs):
            result = known_result(*args, **kwargs)
            result["sandboxed"] = False
            return result
        with self.assertRaisesRegex(holdout.IntegrityError, "not sandboxed"):
            self.run_once(unsafe)

    def test_once_does_not_chase_responses_appended_after_startup(self):
        write_rows(self.out / "responses.jsonl", self.responses[:1])
        def growing(*args, **kwargs):
            with (self.out / "responses.jsonl").open("a") as handle:
                handle.write("".join(json.dumps(row) + "\n" for row in self.responses[1:]))
            return known_result(*args, **kwargs)
        state, count = self.run_once(growing)
        self.assertEqual((count, state["source_responses"], state["measured"]), (1, 1, 1))
        self.assertFalse(state["complete"])
        state, count = self.run_once()
        self.assertEqual(count, 2)
        self.assertTrue(state["complete"])

    def test_watch_observes_new_responses_then_exits_at_precommitted_counts(self):
        write_rows(self.out / "responses.jsonl", self.responses[:1])
        def growing(*args, **kwargs):
            if not growing.written:
                growing.written = True
                with (self.out / "responses.jsonl").open("a") as handle:
                    handle.write("".join(json.dumps(row) + "\n" for row in self.responses[1:]))
            return known_result(*args, **kwargs)
        growing.written = False
        with patch.object(holdout, "evaluate_resolved", side_effect=growing), redirect_stdout(io.StringIO()):
            state = holdout.HoldoutRunner(self.path, poll_seconds=.02).run(watch=True)
        self.assertTrue(state["complete"])
        self.assertEqual((state["source_responses"], state["measured"]), (9, 3))

    def test_lock_prevents_a_second_holdout_writer(self):
        runner = holdout.HoldoutRunner(self.path)
        try:
            with self.assertRaisesRegex(RuntimeError, "Another holdout"):
                holdout.HoldoutRunner(self.path)
        finally:
            runner.close()

    def test_confirmed_public_resource_failure_is_measured_without_faking_hidden(self):
        def resource_failed(*args, **kwargs):
            result = known_result(*args, **kwargs)
            result["public"].update(passed=False, scan_complete=False, cases_checked=0,
                                    passed_cases=0, failed_cases=0, unchecked_cases=2,
                                    candidate_resource_violation=True)
            result["hidden"].update(passed=False, complete=False, outcome_known=False,
                                    scan_complete=False, cases_checked=0, passed_cases=0,
                                    failed_cases=0, unchecked_cases=2, not_evaluated=True)
            result["full_pass"] = False
            return result
        state, count = self.run_once(resource_failed)
        self.assertEqual((state["measured"], state["failed"], state["unknown_attempts"]), (3, 3, 0))
        for row in holdout.read_journal(self.out / "holdout-evaluations.jsonl"):
            self.assertEqual(row["public"]["cases_checked"], 0)
            self.assertFalse(row["hidden"]["complete"])
            self.assertTrue(row["hidden"]["not_evaluated"])

    def test_task_pass_cannot_be_recorded_without_both_full_scans(self):
        def unscanned(*args, **kwargs):
            result = known_result(*args, **kwargs)
            result["public"].update(scan_complete=False, cases_checked=1)
            return result
        with self.assertRaisesRegex(holdout.IntegrityError, "did not scan"):
            self.run_once(unscanned)

    def test_real_toy_evaluation_inside_the_sandbox(self):
        with redirect_stdout(io.StringIO()):
            state = holdout.HoldoutRunner(self.path, poll_seconds=.02).run()
        self.assertTrue(state["complete"])
        self.assertEqual(state["passed"], 3)
        self.assertTrue(all(row["sandboxed"] for row in holdout.read_journal(self.out / "holdout-evaluations.jsonl")))


class TailTests(unittest.TestCase):
    def test_partial_line_waits_for_completion_without_counting_it_twice(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-tail-") as name:
            path = Path(name) / "responses.jsonl"
            path.write_bytes(b'{"record_id":"one"}\n{"record_id":')
            tail = holdout.ResponseTail(path)
            self.assertEqual([row["record_id"] for row, _ in tail.poll()], ["one"])
            self.assertTrue(tail.buffer)
            with path.open("ab") as handle:
                handle.write(b'"two"}\n')
            self.assertEqual([row["record_id"] for row, _ in tail.poll()], ["two"])
            self.assertFalse(tail.buffer)
            self.assertEqual(list(tail.poll()), [])

    def test_truncation_of_append_only_source_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="synthetic-tail-") as name:
            path = Path(name) / "responses.jsonl"
            path.write_text('{"record_id":"one"}\n')
            tail = holdout.ResponseTail(path)
            list(tail.poll())
            path.write_text("")
            with self.assertRaisesRegex(holdout.IntegrityError, "truncated"):
                list(tail.poll())


if __name__ == "__main__":
    unittest.main()
