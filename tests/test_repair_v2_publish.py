"""Publication-boundary tests using temporary structural fixtures only.

The false synthetic flag below deliberately exercises the real-export schema;
the counts are fixtures, not research measurements. Nothing is exported outside
TemporaryDirectory. These tests make no API calls or candidate executions.
"""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.code_repair_v2.src.publish import publish
from scripts.cleaning.build_unified_features import FIELDS


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class PublishBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="publisher-structural-fixture-only-")
        self.base = Path(self.temp.name)
        self.rejected_attempts = 0
        self.source, self.legacy, self.app = [self.base / name for name in ("new-report", "old-report", "app")]
        self.source.mkdir()
        self.legacy.mkdir()
        self.app.mkdir()
        self.evidence = {
            "schema": "course-code-repair-extension-v1", "batch_id": "structural-fixture-only",
            "synthetic": False, "status": "complete", "models": ["Model-A", "Model-B"],
            "model_labels": {"Model-A": "A", "Model-B": "B"},
            "arms": [{"id": arm, "label": arm} for arm in (
                "resample", "self_review", "pass_fail", "diagnostic", "counterexample", "multi_counterexample")],
            "rounds": 5, "repeats_per_task": 3,
            "planned_tasks": 164, "task_clusters": 164, "public_task_clusters": 164,
            "strong_trajectory_task_clusters": 164, "strong_trajectory_complete": True,
            "saved_physical_responses": 24600,
            "coverage": {"complete": True, "planned_tasks": 164, "task_clusters": 164,
                         "public_task_clusters": 164, "strong_trajectory_task_clusters": 164,
                         "expected_physical_responses": 24600, "saved_physical_responses": 24600,
                         "missing_count": 0, "public_cases": 1570, "holdout_cases": 122459},
            "summary": [], "public_curves": [], "strong_curves": [], "strong_endpoints": [],
            "contrasts": [], "initial_error_support": [], "planned_endpoint_bounds": [],
            "planned_contrast_bounds": [], "scope_notes": ["STRUCTURAL TEST FIXTURE ONLY"],
            "examples": [{"category": "diagnostic_repair", "anonymous_task": "Tfixture012345",
                          "model": "Model-A", "before_code": "def f():\n    return 0\n",
                          "after_code": "def f():\n    return 1\n",
                          "before_public": {"passed": False}, "after_public": {"passed": True}}],
        }
        entries = [
            ("strong-endpoints", "01-strong-endpoints.svg", "summary.csv"),
            ("public-trajectories", "02-public-trajectories.svg", "public-curves.csv"),
            ("repair-regression", "03-repair-regression.svg", "summary.csv"),
            ("cost-quality", "04-cost-quality.svg", "summary.csv"),
            ("initial-error-support", "05-initial-error-support.svg", "initial-error-support.csv"),
            ("strong-trajectories", "06-strong-trajectories.svg", "strong-curves.csv"),
        ]
        self.manifest = {"batch_id": self.evidence["batch_id"], "synthetic": False,
                         "figures": [{"id": key, "file": name, "data_file": data,
                                      "title": "STRUCTURAL TEST FIXTURE ONLY"} for key, name, data in entries]}
        for item in self.manifest["figures"]:
            self.svg(self.source / item["file"])
            (self.source / item["data_file"]).write_text("model,arm,programs\nModel-A,diagnostic,492\n")
        self.checks = {
            "schema": "legacy-code-repair-strong-reevaluation-v1", "complete": True,
            "source_records": 5576, "source_initial_programs": 328, "known_results": 5576,
            "full_holdout_inputs": 122459, "model_api_calls": 0, "feedback_changed": False,
            "source_sha256": "a" * 64, "dataset_sha256": "b" * 64,
            "interpretation": "Retrospective only; original public feedback retained.",
            "evaluation_settings": {"python_executable": "PRIVATE_LOCAL_PATH_SENTINEL"},
        }
        self.legacy_manifest = {
            "batch_id": "legacy-full-recheck", "synthetic": False, "complete": True,
            "figures": [{"id": "legacy-mini-full-final", "file": "01-mini-full-final.svg",
                         "data_file": "legacy-vs-strong-summary.csv", "title": "Legacy structural fixture"}],
        }
        self.svg(self.legacy / "01-mini-full-final.svg")
        (self.legacy / "legacy-vs-strong-summary.csv").write_text(
            "model,arm,tasks,planned_tasks\nModel-A,resample,164,164\n")
        (self.legacy / "legacy-vs-strong-curves.csv").write_text(
            "model,arm,round,task_clusters\nModel-A,resample,0,164\n")
        self.save()
        for directory in (self.source, self.legacy):
            (directory / "responses.jsonl").write_text("RAW_RESPONSE_SENTINEL\n")
            (directory / "examples.json").write_text('{"task_id":"RAW_TASK_SENTINEL"}')
            (directory / "private-resource-audit.jsonl").write_text("PRIVATE_AUDIT_SENTINEL\n")

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def svg(path):
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
                        '<title>STRUCTURAL TEST FIXTURE ONLY</title><path d="M1 19L19 1"/></svg>')

    def save(self):
        write_json(self.source / "app-evidence.json", self.evidence)
        write_json(self.source / "figure-manifest.json", self.manifest)
        write_json(self.legacy / "strong-checks.json", self.checks)
        write_json(self.legacy / "figure-manifest.json", self.legacy_manifest)

    def assert_rejected(self):
        self.rejected_attempts += 1
        destination = self.base / ("rejected-output-" + str(self.rejected_attempts))
        with self.assertRaises(ValueError):
            publish(self.source, self.legacy, destination)
        self.assertFalse((destination / "data/code-feedback-extension.json").exists())
        self.assertFalse((destination / "assets/research-extension").exists())
        self.assertFalse(destination.exists())

    def unified_fixture(self):
        """Schema/hash fixture only; no actual research rows are manufactured."""
        directory = self.source / "unified-format"
        directory.mkdir()
        assets = {
            "unified-records.csv.gz": gzip.compress((",".join(FIELDS) + "\n").encode(), mtime=0),
            "lineage.csv": b"record_id,replicate_id,arm,round,public_pass,full_pass,code_sha256\n",
            "field-statistics.csv": b"field,type,meaning,missing_policy,records,missing_count,missing_rate\n",
        }
        for name, blob in assets.items():
            (directory / name).write_bytes(blob)
        (directory / "responses.jsonl").write_text("PRIVATE_UNIFIED_RAW_SENTINEL\n")
        metadata = {
            "schema": "code-repair-unified-supplement-v1", "synthetic": False, "complete": True,
            "batch_id": self.evidence["batch_id"], "records": 24600, "physical_seeds": 984,
            "planned_tasks": 164, "replicates_per_task_model": 3, "fields": list(FIELDS),
            "metric_name": "base_and_full_disjoint_holdout_pass_v2",
            "assets_sha256": {name: hashlib.sha256(blob).hexdigest() for name, blob in assets.items()},
            "null_policy": "Empty cell is null; no zero imputation.",
            "replicate_policy": "Replicate in lineage; independent_sample remains null.",
            "source_local_path": "PRIVATE_UNIFIED_METADATA_PATH_SENTINEL",
        }
        write_json(directory / "metadata.json", metadata)
        return directory, metadata

    def test_verified_unified_metadata_is_bundled_without_copying_private_sources(self):
        directory, metadata = self.unified_fixture()
        publish(self.source, self.legacy, self.app)
        bundle = json.loads((self.app / "data/code-feedback-extension.json").read_text())
        supplement = bundle["unifiedFormat"]
        self.assertEqual(supplement["batch_id"], self.evidence["batch_id"])
        self.assertEqual((supplement["records"], supplement["physical_seeds"]), (24600, 984))
        self.assertEqual(supplement["fields"], list(FIELDS))
        self.assertEqual(supplement["assets_sha256"], metadata["assets_sha256"])
        self.assertEqual(bundle["provenance"]["unified_metadata_sha256"],
                         hashlib.sha256((directory / "metadata.json").read_bytes()).hexdigest())
        self.assertNotIn("source_local_path", supplement)
        files = [path for path in self.app.rglob("*") if path.is_file()]
        exported = b"".join(path.read_bytes() for path in files)
        self.assertNotIn(b"PRIVATE_UNIFIED_RAW_SENTINEL", exported)
        self.assertNotIn(b"PRIVATE_UNIFIED_METADATA_PATH_SENTINEL", exported)
        self.assertFalse(any(path.name == "responses.jsonl" for path in files))

    def test_unified_batch_count_and_exact_21_field_schema_fail_before_target_writes(self):
        directory, original = self.unified_fixture()
        changes = [
            lambda m: m.update(batch_id="different-batch"),
            lambda m: m.update(records=24599),
            lambda m: m.update(schema="unverified-schema"),
            lambda m: m.update(fields=list(reversed(FIELDS))),
            lambda m: m.update(fields=list(FIELDS)[:-1]),
            lambda m: m.update(complete=False),
            lambda m: m.update(synthetic=True),
        ]
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                metadata = copy.deepcopy(original)
                change(metadata)
                write_json(directory / "metadata.json", metadata)
                self.assert_rejected()

    def test_unified_assets_require_all_three_exact_names_and_matching_hashes(self):
        directory, original = self.unified_fixture()
        changes = [
            lambda m: m["assets_sha256"].update({"unified-records.csv.gz": "0" * 64}),
            lambda m: m["assets_sha256"].pop("lineage.csv"),
            lambda m: m["assets_sha256"].update({"responses.jsonl": hashlib.sha256(
                (directory / "responses.jsonl").read_bytes()).hexdigest()}),
        ]
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                metadata = copy.deepcopy(original)
                change(metadata)
                write_json(directory / "metadata.json", metadata)
                self.assert_rejected()

    def test_complete_real_schema_exports_only_anonymous_bundle_and_declared_local_assets(self):
        (self.app / "unrelated.txt").write_text("existing app remains intact")
        result = publish(self.source, self.legacy, self.app)
        bundle_path = self.app / "data/code-feedback-extension.json"
        bundle = json.loads(bundle_path.read_text())
        self.assertEqual((result["responses"], result["task_clusters"], result["figures"]), (24600, 164, 6))
        self.assertEqual(bundle["schema"], "course-code-feedback-publication-v1")
        self.assertEqual(bundle["evidence"], self.evidence)
        self.assertEqual(bundle["legacyEvidence"]["checks"]["known_results"], 5576)
        self.assertFalse(bundle["legacyEvidence"]["checks"]["feedback_changed"])
        self.assertEqual(bundle["legacyEvidence"]["summary"][0]["tasks"], "164")
        self.assertEqual(bundle["legacyEvidence"]["curves"][0]["round"], "0")
        expected = {f"assets/research-extension/{item[key]}" for item in self.manifest["figures"]
                    for key in ("file", "data_file")}
        expected |= {f"assets/research-extension/legacy/{item[key]}" for item in self.legacy_manifest["figures"]
                     for key in ("file", "data_file")}
        expected |= {"data/code-feedback-extension.json", "unrelated.txt"}
        actual = {str(path.relative_to(self.app)) for path in self.app.rglob("*") if path.is_file()}
        self.assertEqual(actual, expected)
        for name, checksum in bundle["provenance"]["assets"].items():
            path = self.app / "assets/research-extension" / name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), checksum)
        self.assertEqual(bundle["provenance"]["evidence_sha256"],
                         hashlib.sha256((self.source / "app-evidence.json").read_bytes()).hexdigest())
        public_bytes = b"".join(path.read_bytes() for path in self.app.rglob("*") if path.is_file())
        for sentinel in (b"RAW_RESPONSE_SENTINEL", b"RAW_TASK_SENTINEL", b"PRIVATE_AUDIT_SENTINEL",
                         b"PRIVATE_LOCAL_PATH_SENTINEL"):
            self.assertNotIn(sentinel, public_bytes)

    def test_synthetic_or_unverified_origin_is_never_publishable(self):
        for flag in (True, None, "false"):
            with self.subTest(flag=flag):
                self.evidence["synthetic"] = flag
                self.save()
                self.assert_rejected()

    def test_partial_coverage_or_missing_paired_task_cannot_publish(self):
        original = copy.deepcopy(self.evidence)
        changes = [
            lambda e: e.update(status="partial_complete_blocks_only"),
            lambda e: e["coverage"].update(complete=False),
            lambda e: e["coverage"].update(missing_count=1),
            lambda e: e.update(task_clusters=163),
            lambda e: e.update(public_task_clusters=163),
            lambda e: e["coverage"].update(task_clusters=163),
            lambda e: e["coverage"].update(strong_trajectory_task_clusters=163),
            lambda e: e["coverage"].update(saved_physical_responses=24599),
            lambda e: e.update(saved_physical_responses=24599),
        ]
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                self.evidence = copy.deepcopy(original)
                change(self.evidence)
                self.save()
                self.assert_rejected()

    def test_missing_intermediate_strong_measurements_cannot_publish_even_with_complete_endpoints(self):
        self.evidence["strong_trajectory_complete"] = False
        self.save()
        self.assert_rejected()
        self.evidence.update(strong_trajectory_complete=True, strong_trajectory_task_clusters=163)
        self.save()
        self.assert_rejected()

    def test_cross_batch_or_synthetic_figures_cannot_publish(self):
        self.manifest["batch_id"] = "different-batch"
        self.save()
        self.assert_rejected()
        self.manifest.update(batch_id=self.evidence["batch_id"], synthetic=True)
        self.save()
        self.assert_rejected()

    def test_a_complete_flag_with_zero_measured_programs_is_not_real_evidence(self):
        self.evidence.update(planned_tasks=0, task_clusters=0, public_task_clusters=0,
                             strong_trajectory_task_clusters=0, saved_physical_responses=0)
        self.evidence["coverage"].update(planned_tasks=0, task_clusters=0, public_task_clusters=0,
                                         strong_trajectory_task_clusters=0,
                                         expected_physical_responses=0, saved_physical_responses=0)
        self.save()
        self.assert_rejected()

    def test_equal_saved_and_expected_counts_must_still_match_the_paired_design(self):
        self.evidence["saved_physical_responses"] = 24599
        self.evidence["coverage"].update(saved_physical_responses=24599,
                                         expected_physical_responses=24599)
        self.save()
        self.assert_rejected()

    def test_planned_design_dimensions_require_positive_integers(self):
        original = copy.deepcopy(self.evidence)
        for field, value in (("planned_tasks", None), ("planned_tasks", True),
                             ("repeats_per_task", 0), ("rounds", 1)):
            with self.subTest(field=field, value=value):
                self.evidence = copy.deepcopy(original)
                self.evidence[field] = value
                self.save()
                self.assert_rejected()

    def test_raw_identifiers_or_credentials_inside_evidence_are_rejected(self):
        original = copy.deepcopy(self.evidence)
        changes = [
            lambda e: e["examples"][0].update(task_id="RAW_TASK_SENTINEL"),
            lambda e: e["examples"][0].update(record_ids=["RAW_RECORD_SENTINEL"]),
            lambda e: e.update(request={"messages": [{"content": "RAW_REQUEST_SENTINEL"}]}),
            lambda e: e.update(api_key="CREDENTIAL_SENTINEL_NOT_A_REAL_KEY"),
        ]
        for number, change in enumerate(changes):
            with self.subTest(case=number):
                self.evidence = copy.deepcopy(original)
                change(self.evidence)
                self.save()
                with self.assertRaises(ValueError):
                    publish(self.source, self.legacy, self.app)

    def test_credential_like_text_is_rejected_even_without_a_sensitive_field_name(self):
        original = copy.deepcopy(self.evidence)
        for text in ("sk-STRUCTURALFIXTUREONLY123456789", "Bearer STRUCTURALFIXTUREONLY123456789"):
            with self.subTest(text_type=text.split(" ")[0].split("-")[0]):
                self.evidence = copy.deepcopy(original)
                self.evidence["scope_notes"].append(text)
                self.save()
                self.assert_rejected()

    def test_anonymity_gate_covers_imported_legacy_rows_and_figure_metadata(self):
        summary = self.legacy / "legacy-vs-strong-summary.csv"
        original = summary.read_text()
        summary.write_text("model,arm,record_id\nModel-A,resample,RAW_RECORD_SENTINEL\n")
        self.assert_rejected()
        summary.write_text(original)
        self.manifest["figures"][0]["title"] = "sk-STRUCTURALFIXTUREONLY123456789"
        self.save()
        self.assert_rejected()

    def test_missing_or_duplicate_scientific_figure_does_not_publish_a_subset(self):
        self.manifest["figures"] = self.manifest["figures"][:-1]
        self.save()
        self.assert_rejected()
        self.manifest["figures"].append(copy.deepcopy(self.manifest["figures"][0]))
        self.save()
        self.assert_rejected()

    def test_assets_must_exist_be_svg_and_stay_within_the_report(self):
        first = self.manifest["figures"][0]
        original = first["file"]
        for name in ("missing.svg", "../outside.svg"):
            with self.subTest(name=name):
                first["file"] = name
                self.save()
                self.assert_rejected()
        first["file"] = original
        self.save()
        (self.source / original).write_text("<html/>")
        self.assert_rejected()

    def test_partial_legacy_recheck_is_not_merged_into_a_complete_new_batch(self):
        self.checks["complete"] = False
        self.save()
        self.assert_rejected()
        self.checks.update(complete=True, known_results=5575)
        self.save()
        self.assert_rejected()

    def test_synthetic_or_incomplete_legacy_figure_is_not_publishable(self):
        self.legacy_manifest["synthetic"] = True
        self.save()
        self.assert_rejected()
        self.legacy_manifest.update(synthetic=False, complete=False)
        self.save()
        self.assert_rejected()


if __name__ == "__main__":
    unittest.main()
