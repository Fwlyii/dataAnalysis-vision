"""Temporary structural fixtures for anonymous normalization; no model calls.

False synthetic flags intentionally exercise the formal-export boundary. These
fixture verdicts are not research data and never leave TemporaryDirectory.
"""
import copy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.code_repair_v2.src import normalize as module
from experiments.code_repair_v2.src.protocol import ARMS, feedback_message
from scripts.cleaning.build_unified_features import FIELDS


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="normalizer-structural-fixture-only-")
        self.base = Path(self.temp.name)
        self.run = self.base / "raw"
        self.run.mkdir()
        self.output = self.base / "normalized"
        self.config_path = self.base / "config.json"
        self.config = {"synthetic": False, "batch_id": "normalizer-structural-fixture-only",
                       "run_dir": str(self.run), "benchmark_version": "v0.1.10", "expected_tasks": 2,
                       "dataset_sha256": module.FULL_SHA256,
                       "models": list(module.MODELS), "arms": list(ARMS), "replicates": 2,
                       "rounds": 5, "maximum_physical_responses": 200}
        write_json(self.config_path, self.config)
        self.config_sha = module.digest(self.config_path.read_bytes())
        self.plan = {"batch_id": self.config["batch_id"], "config_sha256": self.config_sha,
                     "task_ids": ["RAW_TASK_SENTINEL/0", "RAW_TASK_SENTINEL/1"],
                     "expected_requests": 200, "reference_source_hashes": module.source_hashes(),
                     "dataset_sha256": module.FULL_SHA256, "manifest": {"dataset_sha256": module.FULL_SHA256}}
        write_json(self.run / "plan.json", self.plan)
        write_json(self.run / "reference-preflight.json", {"complete": True, "config_sha256": self.config_sha})
        self.responses, self.public, self.strong = [], [], []
        by_position, scores = {}, {}
        for task_index, task in enumerate(self.plan["task_ids"]):
            for model in self.config["models"]:
                for repeat in range(2):
                    for round_ in range(5):
                        for arm in (["seed"] if round_ == 0 else ARMS):
                            rid = f"{model}|{task}|rep{repeat}|{arm}|{round_}"
                            code = f"def f(x):\n    return x + {round_}\n"
                            passed = task_index == 1 or (round_ > 0 and arm == "diagnostic")
                            failure = None if passed else {"kind": "output_mismatch", "stage": "test",
                                "case_index": 0, "input": "(1,)", "expected": "2", "actual": "1",
                                "error_type": "OutputMismatch", "error_message": "Fixture mismatch",
                                "line": None, "column": None, "candidate_traceback": []}
                            public = {"complete": True, "outcome_known": True, "scan_complete": True,
                                      "passed": passed, "total_cases": 1, "cases_checked": 1,
                                      "passed_cases": int(passed), "failed_cases": int(not passed),
                                      "failures": [] if passed else [failure], "first_failure": failure}
                            identity = {"record_id": rid, "model": model, "task_id": task,
                                        "replicate": repeat, "arm": arm, "round": round_}
                            evaluation = {**identity, "public": public, "sandboxed": True,
                                          "config_sha256": self.config_sha}
                            messages = [{"role": "user", "content": "RAW_REQUEST_SENTINEL: implement f."}]
                            parent = None
                            feedback = None
                            if round_ and arm != "resample":
                                key = (model, task, repeat, "seed" if round_ == 1 else arm, round_ - 1)
                                previous = by_position[key]
                                parent = previous["record_id"]
                                feedback = feedback_message(arm, scores[key])
                                messages = previous["request"]["messages"] + [
                                    {"role": "assistant", "content": previous["content"]},
                                    {"role": "user", "content": feedback}]
                            row = {**identity, "batch_id": self.config["batch_id"], "config_sha256": self.config_sha,
                                   "shared_seed_id": f"{model}|{task}|rep{repeat}|seed|0", "parent_id": parent,
                                   "feedback": feedback, "request": {"messages": messages},
                                   "content": "```python\n" + code + "```", "code": code,
                                   "code_sha256": module.digest(code.encode()), "response": {"model": model},
                                   "timestamp": "2026-11-05T10:15:30+08:00", "seconds": .5,
                                   "finish_reason": "stop", "usage": {"prompt_tokens": 10, "completion_tokens": 5,
                                                                                      "total_tokens": 15}}
                            hidden_pass = passed and not (arm == "diagnostic" and round_ == 2)
                            hidden = {"complete": True, "outcome_known": True, "passed": hidden_pass,
                                      "scan_complete": hidden_pass, "total_cases": 2,
                                      "cases_checked": 2 if hidden_pass else 1,
                                      "passed_cases": 2 if hidden_pass else 0,
                                      "failed_cases": 0 if hidden_pass else 1}
                            self.responses.append(row)
                            self.public.append(evaluation)
                            self.strong.append({**copy.deepcopy(evaluation), "hidden": hidden,
                                                "full_pass": passed and hidden_pass,
                                                "code_sha256": row["code_sha256"]})
                            by_position[model, task, repeat, arm, round_] = row
                            scores[model, task, repeat, arm, round_] = evaluation
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        for name, rows in (("responses.jsonl", self.responses), ("evaluations.jsonl", self.public),
                           ("holdout-evaluations.jsonl", self.strong)):
            write_rows(self.run / name, rows)

    def read_output(self):
        with gzip.open(self.output / "unified-records.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        with (self.output / "lineage.csv").open(encoding="utf-8", newline="") as stream:
            lineage = list(csv.DictReader(stream))
        return fields, rows, lineage, json.loads((self.output / "metadata.json").read_text())

    def assert_rejected(self, pattern=None):
        with self.assertRaisesRegex(ValueError, pattern or "."):
            module.normalize(self.config_path, self.output)
        self.assertFalse(self.output.exists())

    def test_shared_seed_is_one_physical_row_and_the_exact_21_field_order_is_preserved(self):
        result = module.normalize(self.config_path, self.output)
        fields, rows, lineage, metadata = self.read_output()
        self.assertEqual(fields, list(FIELDS))
        self.assertEqual(len(fields), 21)
        self.assertEqual((len(rows), len(lineage), result["records"]), (200, 200, 200))
        self.assertEqual(len({row["record_id"] for row in rows}), 200)
        seeds = [row for row in rows if row["feedback_type"] == "seed"]
        self.assertEqual(len(seeds), 2 * 2 * 2)
        self.assertEqual(metadata["physical_seeds"], 8)
        self.assertTrue(all(row["revision_round"] == "0" for row in seeds))
        self.assertTrue(all(row["independent_sample"] == "" for row in rows))
        self.assertEqual({row["replicate_id"] for row in lineage}, {"0", "1"})
        self.assertEqual({row["model_id"] for row in rows}, {"qwen", "qwen3"})
        self.assertEqual({row["benchmark"] for row in rows}, {"HumanEvalPlus-Full-v0.1.10"})
        self.assertEqual({row["metric_name"] for row in rows}, {"base_and_full_disjoint_holdout_pass_v2"})
        self.assertEqual({row["timestamp"] for row in rows}, {"2026-11-05T02:15:30+00:00"})
        self.assertEqual({row["experiment_id"] for row in rows}, {"code_repair_v2"})

    def test_parent_keys_resolve_to_the_same_exported_physical_pseudonyms(self):
        module.normalize(self.config_path, self.output)
        _, rows, _, _ = self.read_output()
        exported = {row["record_id"]: row for row in rows}
        for source in self.responses:
            anonymous = module.pseudonym(self.config["batch_id"], "record", source["record_id"])
            row = exported[anonymous]
            expected_parent = module.pseudonym(self.config["batch_id"], "record", source["parent_id"]) if source["parent_id"] else ""
            self.assertEqual(row["parent_record_key"], expected_parent)
            if expected_parent:
                self.assertIn(expected_parent, exported)
            self.assertEqual(row["question_key"], module.pseudonym(self.config["batch_id"], "question", source["task_id"]))
        self.assertEqual(len({row["question_key"] for row in rows}), 2)
        other_batch = module.pseudonym("other-batch", "record", self.responses[0]["record_id"])
        self.assertNotIn(other_batch, exported)

    def test_metric_uses_strong_verdict_and_keeps_original_public_pass_in_lineage(self):
        module.normalize(self.config_path, self.output)
        _, rows, lineage, _ = self.read_output()
        row_by_id = {row["record_id"]: row for row in rows}
        gaps = [row for row in lineage if row["public_pass"] == "true" and row["full_pass"] == "false"]
        self.assertTrue(gaps)
        self.assertTrue(all(row_by_id[row["record_id"]]["metric_value"] == "0" for row in gaps))

    def test_frozen_load_failure_tags_do_not_block_normalization_or_count_as_executed_cases(self):
        # A final candidate has no descendants whose previously saved feedback
        # would need changing. Its suite is logically failed before input calls.
        target = next(row for row in self.public if row["round"] == 4 and row["arm"] == "self_review")
        target["public"].update(load_failed=True, passed=False, complete=True, outcome_known=True,
                                 scan_complete=False, cases_checked=0, passed_cases=0, failed_cases=1,
                                 blocked_cases=1, unchecked_cases=1)
        target["public"]["first_failure"].update(kind="load", stage="load", error_type="ModuleNotFoundError")
        self.save()
        module.normalize(self.config_path, self.output)
        _, rows, lineage, metadata = self.read_output()
        anonymous = module.pseudonym(self.config["batch_id"], "record", target["record_id"])
        self.assertEqual(next(row for row in rows if row["record_id"] == anonymous)["metric_value"], "0")
        self.assertEqual(next(row for row in lineage if row["record_id"] == anonymous)["public_pass"], "false")
        checks = metadata["integrity_checks"]
        self.assertEqual(checks["load_failed_programs"], 1)
        self.assertEqual(checks["load_failed_logical_case_labels"], 1)
        self.assertEqual(checks["actual_cases_checked"], 199)
        self.assertEqual(checks["actual_failed_cases"], sum(
            row["public"]["failed_cases"] for row in self.public if row is not target))

    def test_missing_tokens_remain_null_and_partial_usage_is_not_discarded(self):
        self.responses[0].pop("usage")
        self.responses[1]["usage"] = {"prompt_tokens": 10}
        self.responses[2]["usage"] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.save()
        module.normalize(self.config_path, self.output)
        _, rows, _, metadata = self.read_output()
        self.assertEqual((rows[0]["input_tokens"], rows[0]["output_tokens"]), ("", ""))
        self.assertEqual((rows[1]["input_tokens"], rows[1]["output_tokens"]), ("10", ""))
        self.assertEqual((rows[2]["input_tokens"], rows[2]["output_tokens"]), ("0", "0"))
        self.assertEqual(metadata["missing_counts"]["input_tokens"], 1)
        self.assertEqual(metadata["missing_counts"]["output_tokens"], 2)
        with (self.output / "field-statistics.csv").open() as stream:
            stats = list(csv.DictReader(stream))
        self.assertEqual(next(row for row in stats if row["field"] == "output_tokens")["missing_count"], "2")

    def test_unknown_strong_result_is_rejected_instead_of_becoming_zero(self):
        self.strong[0].pop("full_pass")
        self.strong[0]["public"].update(complete=False, outcome_known=False)
        self.strong[0]["hidden"].update(complete=False, outcome_known=False)
        self.save()
        self.assert_rejected("Unknown strong")

    def test_unknown_original_public_result_is_rejected_even_when_strong_result_is_known(self):
        self.public[0]["public"].update(complete=False, outcome_known=False)
        self.save()
        self.assert_rejected("Unknown original public")

    def test_missing_intermediate_strong_measurement_blocks_export(self):
        self.strong.pop(next(i for i, row in enumerate(self.strong) if row["round"] == 2))
        self.save()
        self.assert_rejected("Incomplete")

    def test_incomplete_physical_matrix_and_duplicated_seed_are_rejected(self):
        original = copy.deepcopy(self.responses)
        self.responses.pop()
        self.save()
        self.assert_rejected("Incomplete")
        self.responses = original + [copy.deepcopy(original[0])]
        self.save()
        self.assert_rejected("Duplicate")

    def test_parent_from_another_task_or_missing_parent_is_rejected(self):
        target = next(row for row in self.responses if row["round"] == 1 and row["arm"] == "diagnostic")
        for parent in ("nonexistent-parent", self.responses[-1]["record_id"]):
            with self.subTest(parent_type="missing" if parent == "nonexistent-parent" else "wrong-task"):
                target["parent_id"] = parent
                self.save()
                self.assert_rejected("integrity|parent")

    def test_cross_batch_scores_or_wrong_code_hash_cannot_be_reused(self):
        self.strong[0]["config_sha256"] = "wrong-batch-hash"
        self.save()
        self.assert_rejected("mismatch")
        self.strong[0]["config_sha256"] = self.config_sha
        self.strong[0]["code_sha256"] = "f" * 64
        self.save()
        self.assert_rejected("different candidate")

    def test_gzip_and_metadata_hashes_are_deterministic_without_raw_payloads(self):
        legacy = self.base / "all_records.csv.gz"
        legacy.write_bytes(b"LEGACY_UNIFIED_SENTINEL_DO_NOT_CHANGE")
        original_sources = {path.name: path.read_bytes() for path in self.run.iterdir()}
        module.normalize(self.config_path, self.output)
        first = {path.name: path.read_bytes() for path in self.output.iterdir()}
        module.normalize(self.config_path, self.output)
        second = {path.name: path.read_bytes() for path in self.output.iterdir()}
        self.assertEqual(first, second)
        self.assertEqual(first["unified-records.csv.gz"][4:8], b"\0\0\0\0")
        metadata = json.loads(first["metadata.json"])
        for name, sha in metadata["assets_sha256"].items():
            self.assertEqual(hashlib.sha256(first[name]).hexdigest(), sha)
        self.assertEqual(metadata["source_sha256"], {name: module.digest(blob) for name, blob in original_sources.items()})
        public_text = gzip.decompress(first["unified-records.csv.gz"]) + b"".join(
            blob for name, blob in first.items() if name != "unified-records.csv.gz")
        for sentinel in (b"RAW_TASK_SENTINEL", b"RAW_REQUEST_SENTINEL", b"def f("):
            self.assertNotIn(sentinel, public_text)
        self.assertEqual(legacy.read_bytes(), b"LEGACY_UNIFIED_SENTINEL_DO_NOT_CHANGE")
        self.assertEqual(original_sources, {path.name: path.read_bytes() for path in self.run.iterdir()})

    def test_synthetic_origin_never_exports_and_existing_unrelated_files_are_preserved(self):
        self.config["synthetic"] = True
        write_json(self.config_path, self.config)
        self.assert_rejected("real batch")
        self.config["synthetic"] = False
        write_json(self.config_path, self.config)
        self.output.mkdir()
        sentinel = self.output / "all_records.csv.gz"
        sentinel.write_bytes(b"untouched")
        with self.assertRaisesRegex(ValueError, "unrelated"):
            module.normalize(self.config_path, self.output)
        self.assertEqual(sentinel.read_bytes(), b"untouched")


if __name__ == "__main__":
    unittest.main()
