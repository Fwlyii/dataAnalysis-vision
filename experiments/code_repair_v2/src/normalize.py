"""Export a complete real repair batch into the existing 21-column format.

This offline supplement writes a separate output directory. It never opens the
legacy all_records.csv.gz, calls a model, or executes candidate code. Physical
seeds appear once; independent-initial replication stays in anonymous lineage.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile

from scripts.cleaning.build_unified_features import FIELDS
from .analyze import ROOT, SECRET, audit, indexed, observed, position, strong_observed
from .dataset import FULL_SHA256
from .prepare import source_hashes
from .protocol import ARMS


MODELS = {"Qwen/Qwen2.5-7B-Instruct": "qwen", "Qwen/Qwen3-8B": "qwen3"}
BENCHMARK = "HumanEvalPlus-Full-v0.1.10"
METRIC = "base_and_full_disjoint_holdout_pass_v2"
EXPERIMENT = "code_repair_v2"
LINEAGE_FIELDS = ("record_id", "replicate_id", "arm", "round", "public_pass", "full_pass", "code_sha256")
OUTPUT_NAMES = {"unified-records.csv.gz", "lineage.csv", "field-statistics.csv", "metadata.json"}


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def resolve(value):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def pseudonym(batch, kind, value):
    return digest(json.dumps([EXPERIMENT, batch, kind, value], ensure_ascii=False,
                             separators=(",", ":")).encode())[:24]


def cell(value):
    return "" if value is None else str(value).lower() if isinstance(value, bool) else value


def optional_number(value, label, *, integer=False):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid recorded " + label)
    if integer:
        if not float(value).is_integer():
            raise ValueError("A recorded Token count is not an integer")
        return int(value)
    return value


def utc(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid recorded timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Recorded timestamp has no timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def token_counts(row):
    usage = row.get("usage") or (row.get("response") or {}).get("usage") or {}
    if not isinstance(usage, dict):
        raise ValueError("Invalid provider usage")
    values = [optional_number(usage.get(name), name, integer=True)
              for name in ("prompt_tokens", "completion_tokens", "total_tokens")]
    if all(value is not None for value in values) and values[0] + values[1] != values[2]:
        raise ValueError("Inconsistent recorded Token accounting")
    return values[:2]


def parse_rows(blob, name):
    if blob and not blob.endswith(b"\n"):
        raise ValueError("Incomplete JSONL tail: " + name)
    try:
        values = [json.loads(line) for line in blob.splitlines() if line.strip()]
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid saved JSONL: " + name) from error
    if not all(isinstance(value, dict) for value in values):
        raise ValueError("Saved JSONL rows must be objects")
    return indexed(values, name)


def validate_score(score, row, config_sha, *, strong=False):
    if (score.get("config_sha256") != config_sha or score.get("sandboxed") is not True
            or any(score.get(key) != row[key] for key in ("model", "task_id", "replicate", "arm", "round"))):
        raise ValueError("Evaluation identity/configuration/sandbox mismatch")
    if score.get("code_sha256") not in ((row["code_sha256"],) if strong else (None, row["code_sha256"])):
        raise ValueError("Evaluation belongs to a different candidate")
    if strong:
        known_failure = any(isinstance(score.get(name), dict) and score[name].get("complete") is True
                            and score[name].get("outcome_known") is not False
                            and score[name].get("passed") is False for name in ("public", "hidden"))
        if not strong_observed(score) or (score["full_pass"] is False and not known_failure):
            raise ValueError("Unknown strong result; no score is imputed")
        names = ("public", "hidden") if score["full_pass"] else ()
    else:
        if score.get("public", {}).get("complete") is not True or not observed(score):
            raise ValueError("Unknown original public result; no score is imputed")
        names = ("public",) if score["public"]["passed"] else ()
    for name in names:
        split = score.get(name) or {}
        if (split.get("complete") is not True or split.get("scan_complete") is not True
                or not isinstance(split.get("total_cases"), int)
                or split.get("cases_checked") != split["total_cases"]):
            raise ValueError("A passing evaluation must scan every test")


def write_csv(path, fields, rows, *, compressed=False):
    def write(stream):
        writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: cell(row.get(key)) for key in fields} for row in rows)
    if compressed:
        # Empty gzip filename and mtime=0 remove path/time-dependent headers.
        with path.open("wb") as binary:
            with gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0) as compressed_file:
                with io.TextIOWrapper(compressed_file, encoding="utf-8", newline="") as stream:
                    write(stream)
    else:
        with path.open("w", encoding="utf-8", newline="") as stream:
            write(stream)


def normalize(config_path, output):
    config_path = resolve(config_path)
    config_blob = config_path.read_bytes()
    config = json.loads(config_blob)
    config_sha = digest(config_blob)
    batch = config.get("batch_id")
    if config.get("synthetic", False) is not False or not isinstance(batch, str) or not re.fullmatch(r"[\w.-]+", batch):
        raise ValueError("Only an explicit real batch can be normalized")
    if SECRET.search(json.dumps(config, ensure_ascii=False)):
        raise ValueError("Configuration contains a credential-like value")
    if config.get("benchmark_version") != "v0.1.10":
        raise ValueError("This exporter requires the full v0.1.10 benchmark")
    run = resolve(config["run_dir"])
    output = resolve(output)
    if output == run or run in output.parents or output == ROOT / "data" or (ROOT / "data") in output.parents:
        raise ValueError("Use a separate output directory outside frozen data and collection")
    if output.exists():
        if not output.is_dir() or set(path.name for path in output.iterdir()) - OUTPUT_NAMES:
            raise ValueError("Output directory contains unrelated files")
        if (output / "metadata.json").is_file():
            previous = json.loads((output / "metadata.json").read_bytes())
            if previous.get("batch_id") != batch or previous.get("schema") != "code-repair-unified-supplement-v1":
                raise ValueError("Output belongs to another batch")
    names = ("plan.json", "reference-preflight.json", "responses.jsonl", "evaluations.jsonl", "holdout-evaluations.jsonl")
    try:
        blobs = {name: (run / name).read_bytes() for name in names}
    except OSError as error:
        raise ValueError("All plan, public and full-round strong files are required") from error
    plan, preflight = [json.loads(blobs[name]) for name in names[:2]]
    if (plan.get("batch_id") != batch or plan.get("config_sha256") != config_sha
            or preflight.get("complete") is not True or preflight.get("config_sha256") != config_sha):
        raise ValueError("A complete matching frozen reference plan is required")
    if (config.get("dataset_sha256") != FULL_SHA256 or plan.get("dataset_sha256") != FULL_SHA256
            or plan.get("manifest", {}).get("dataset_sha256") != FULL_SHA256):
        raise ValueError("Full benchmark provenance differs from its pinned source")
    if plan.get("reference_source_hashes") != source_hashes():
        raise ValueError("Frozen evaluation/protocol source differs from the batch")
    tasks, models, arms = plan.get("task_ids"), config.get("models"), config.get("arms")
    repeats = config.get("replicates")
    repeats = list(range(repeats)) if isinstance(repeats, int) and not isinstance(repeats, bool) and repeats > 0 else repeats
    rounds = config.get("rounds")
    if (not isinstance(tasks, list) or not tasks or len(set(tasks)) != len(tasks)
            or not all(isinstance(task, str) and task for task in tasks)
            or config.get("expected_tasks") != len(tasks)
            or not isinstance(models, list) or not models or len(set(models)) != len(models)
            or not set(models).issubset(MODELS) or arms != list(ARMS)
            or not isinstance(repeats, list) or not repeats or len(set(repeats)) != len(repeats)
            or not all(isinstance(repeat, int) and not isinstance(repeat, bool) and repeat >= 0 for repeat in repeats)
            or not isinstance(rounds, int) or isinstance(rounds, bool) or rounds != 5):
        raise ValueError("Invalid planned full paired repair matrix")
    expected_positions = [(model, task, repeat, arm, round_)
                          for task in tasks for model in models for repeat in repeats
                          for round_ in range(rounds) for arm in (["seed"] if round_ == 0 else arms)]
    if (config.get("maximum_physical_responses") != len(expected_positions)
            or plan.get("expected_requests") != len(expected_positions)):
        raise ValueError("Planned physical count differs from its paired matrix")
    raw, public, strong = [parse_rows(blobs[name], name) for name in names[2:]]
    if len(raw) != len(expected_positions) or set(public) != set(raw) or set(strong) != set(raw):
        raise ValueError("Incomplete physical/public/full-round strong collection")
    by_position = {}
    for rid, row in raw.items():
        try:
            key = position(row)
            correct_rid = f'{row["model"]}|{row["task_id"]}|rep{row["replicate"]}|{row["arm"]}|{row["round"]}'
            code_sha = digest(row["code"].encode())
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError("Invalid saved physical candidate") from error
        if (rid != correct_rid or row.get("batch_id") != batch or row.get("config_sha256") != config_sha
                or not isinstance(row.get("round"), int) or isinstance(row.get("round"), bool)
                or not isinstance(row.get("replicate"), int) or isinstance(row.get("replicate"), bool)
                or row.get("code_sha256") != code_sha or key in by_position):
            raise ValueError("Physical response identity/configuration/code checksum mismatch")
        by_position[key] = row
        validate_score(public[rid], row, config_sha)
        validate_score(strong[rid], row, config_sha, strong=True)
    if set(by_position) != set(expected_positions):
        raise ValueError("Physical collection does not match every planned position")
    audit_counts = audit(config, raw, public, by_position, config_sha)
    ids = {rid: pseudonym(batch, "record", rid) for rid in raw}
    questions = {task: pseudonym(batch, "question", task) for task in tasks}
    if len(set(ids.values())) != len(ids) or len(set(questions.values())) != len(questions):
        raise ValueError("Anonymous identity collision")
    rows, lineage = [], []
    missing = Counter()
    for key in expected_positions:
        source = by_position[key]
        rid, round_, arm = source["record_id"], source["round"], source["arm"]
        parent = source.get("parent_id")
        if round_ == 0 or arm == "resample":
            expected_parent = None
        else:
            expected_parent = by_position[(source["model"], source["task_id"], source["replicate"],
                                            "seed" if round_ == 1 else arm, round_ - 1)]["record_id"]
        seed = by_position[(source["model"], source["task_id"], source["replicate"], "seed", 0)]["record_id"]
        if parent != expected_parent or (parent is not None and parent not in ids) or source.get("shared_seed_id") != seed:
            raise ValueError("Invalid shared seed or preceding physical parent")
        incoming, outgoing = token_counts(source)
        finish = source.get("finish_reason") or None
        if finish is not None and not isinstance(finish, str):
            raise ValueError("Invalid finish reason")
        result = {"record_id": ids[rid], "experiment_id": EXPERIMENT, "model_id": MODELS[source["model"]],
                  "benchmark": BENCHMARK, "question_key": questions[source["task_id"]], "prompt_id": None,
                  "timestamp": utc(source.get("timestamp")), "input_tokens": incoming, "output_tokens": outgoing,
                  "latency_seconds": optional_number(source.get("seconds"), "latency"), "finish_reason": finish,
                  "is_truncated": finish == "length" if finish else None, "metric_name": METRIC,
                  "metric_value": int(strong[rid]["full_pass"]), "environment_excluded": False,
                  "document_count": None, "evidence_position": None, "independent_sample": None,
                  "revision_round": round_, "feedback_type": arm, "parent_record_key": ids.get(parent)}
        rows.append(result)
        missing.update(field for field in FIELDS if result[field] is None)
        lineage.append({"record_id": ids[rid], "replicate_id": source["replicate"], "arm": arm, "round": round_,
                        "public_pass": public[rid]["public"]["passed"], "full_pass": strong[rid]["full_pass"],
                        "code_sha256": source["code_sha256"]})
    descriptions = dict(FIELDS)
    descriptions['feedback_type'] = ('category/null', '/'.join(['seed', *arms]),
                                      'Recorded feedback strategy in this extension batch')
    descriptions['revision_round'] = ('integer/null',
        'Recorded subsequent-generation round;0 is the shared initial program;resample rounds are independent',
        'Design version index;not the independent-initial replicate')
    statistics = [{"field": field, "type": description[0], "meaning": description[1],
                   "missing_policy": description[2], "records": len(rows), "missing_count": missing[field],
                   "missing_rate": missing[field] / len(rows)} for field, description in descriptions.items()]
    if SECRET.search(json.dumps([rows, lineage], ensure_ascii=False)):
        raise ValueError("Credential-like value cannot enter anonymous export")
    # Validate first, then stage only this supplement's four output files.
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".repair-normalize-", dir=output.parent))
    try:
        write_csv(staging / "unified-records.csv.gz", FIELDS, rows, compressed=True)
        write_csv(staging / "lineage.csv", LINEAGE_FIELDS, lineage)
        write_csv(staging / "field-statistics.csv", statistics[0], statistics)
        metadata = {
            "schema": "code-repair-unified-supplement-v1", "batch_id": batch, "synthetic": False,
            "complete": True, "benchmark": BENCHMARK, "experiment_id": EXPERIMENT, "metric_name": METRIC,
            "records": len(rows), "physical_seeds": sum(row["revision_round"] == 0 for row in rows),
            "planned_tasks": len(tasks), "models": [MODELS[model] for model in models],
            "replicates_per_task_model": len(repeats), "arms": arms, "rounds": rounds,
            "fields": list(FIELDS), "lineage_fields": list(LINEAGE_FIELDS),
            "counts_by_model": dict(Counter(row["model_id"] for row in rows)),
            "counts_by_feedback": dict(Counter(row["feedback_type"] for row in rows)),
            "metric_counts": {"passed": sum(row["metric_value"] for row in rows),
                              "failed": sum(not row["metric_value"] for row in rows), "unknown": 0},
            "missing_counts": {field: missing[field] for field in FIELDS},
            "config_sha256": config_sha, "source_sha256": {name: digest(blob) for name, blob in blobs.items()},
            "dataset_sha256": FULL_SHA256,
            "normalizer_source_sha256": digest(Path(__file__).read_bytes()),
            "assets_sha256": {name: digest((staging / name).read_bytes()) for name in sorted(OUTPUT_NAMES - {"metadata.json"})},
            "api_calls": 0, "generated_code_executed": False,
            "null_policy": "Empty CSV cells are null; no missing Token count or unresolved outcome is replaced with zero.",
            "identity_policy": "Batch-scoped SHA-256 pseudonyms; physical seeds appear once; parent keys refer to exported physical responses.",
            "replicate_policy": "Independent initial replicate is in lineage.replicate_id; independent_sample is null. revision_round is the recorded design version, not the replicate.",
            "metric_policy": "Full v0.1.10 public plus disjoint held-out task verdict; distinct from the historical Mini score. No cross-metric pooling.",
            "public_policy": "lineage.public_pass preserves original public feedback; strong rechecks never rewrite it.",
            "legacy_policy": "The historical unified table is neither opened nor modified.",
            "integrity_checks": audit_counts,
        }
        (staging / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        if config_path.read_bytes() != config_blob or any((run / name).read_bytes() != blob for name, blob in blobs.items()):
            raise ValueError("Source files changed during normalization")
        output.mkdir(parents=True, exist_ok=True)
        for name in sorted(OUTPUT_NAMES):
            (staging / name).replace(output / name)
    finally:
        shutil.rmtree(staging)
    return {"batch_id": batch, "records": len(rows), "physical_seeds": metadata["physical_seeds"],
            "metric_name": METRIC, "output": str(output), "api_calls": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(normalize(args.config, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
