"""Freeze a new repair batch and preflight all canonical references in a sandbox.

Run: python -m experiments.code_repair_v2.src.prepare --config CONFIG.json
No API calls are made. Existing batches/caches are reused only after their
configuration, benchmark, source code, runtime and oracle hashes are verified.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import pickle
import subprocess
import sys
import time

from .dataset import ROOT, load_benchmark
from .evaluator import prepare_reference
from .protocol import ARMS


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def canonical_sha256(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"), allow_nan=False).encode("utf-8"))


def resolve(value) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def source_hashes() -> dict[str, str]:
    own = Path(__file__).parent
    paths = [own / name for name in ("dataset.py", "evaluator.py", "worker.py", "protocol.py", "prepare.py")]
    paths.extend(ROOT / "experiments/code_repair/vendor" / name for name in (
        "SOURCE.json", "evalplus/eval/__init__.py", "evalplus/eval/_special_oracle.py", "evalplus/eval/utils.py"))
    return {str(path.relative_to(ROOT)): sha256(path.read_bytes()) for path in paths}


def runtime_identity(config: dict) -> dict:
    python = str(Path(config.get("python_executable", sys.executable)).absolute())
    script = (
        "import sys,json,numpy,psutil;"
        "print(json.dumps({'executable':sys.executable,'python':sys.version,"
        "'platform':sys.platform,'numpy':numpy.__version__,'psutil':psutil.__version__}))"
    )
    result = subprocess.run([python, "-I", "-c", script], check=True, timeout=30,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={"PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1"})
    return json.loads(result.stdout)


def replicate_ids(config: dict) -> list:
    value = config.get("replicates", 3)
    result = list(range(value)) if isinstance(value, int) and not isinstance(value, bool) else value
    if not isinstance(result, list) or not result or len({str(item) for item in result}) != len(result):
        raise ValueError("replicates must be a positive count or a nonempty unique list")
    return result


def valid_oracle(oracle, task: dict) -> bool:
    if not isinstance(oracle, dict) or not {"base", "plus"}.issubset(oracle):
        return False
    for name, inputs in (("base", task["base_input"]), ("plus", task["plus_input"])):
        split = oracle[name]
        if not isinstance(split, dict):
            return False
        outputs, times = split.get("outputs"), split.get("times")
        if not isinstance(outputs, list) or not isinstance(times, list):
            return False
        if len(outputs) != len(inputs) or len(times) != len(inputs):
            return False
        if not all(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0 for value in times):
            return False
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    config_path = resolve(args.config)
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object")
    for private in ("api_key", "api_keys", "authorization", "secret"):
        if config.get(private):
            raise ValueError("Do not put credentials in a frozen experiment configuration")
    if not isinstance(config.get("batch_id"), str) or not config["batch_id"].strip():
        raise ValueError("A new explicit batch_id is required")
    if not config.get("run_dir"):
        raise ValueError("A new run_dir is required; no legacy output directory is assumed")
    run_dir = resolve(config["run_dir"])
    legacy = ROOT / "data/raw/code_repair"
    if run_dir == ROOT or run_dir == legacy or legacy in run_dir.parents:
        raise ValueError("Reference preparation must not write into the frozen legacy data batch")
    models = config.get("models", [])
    arms = config.get("arms", ARMS)
    repeats = replicate_ids(config)
    rounds = config.get("rounds", 5)
    if not isinstance(models, list) or not models or not all(isinstance(model, str) and model for model in models):
        raise ValueError("models must be a nonempty list of model identifiers")
    if len(models) != len(set(models)):
        raise ValueError("models must be unique")
    if not isinstance(arms, list) or not arms or len(arms) != len(set(arms)) or not set(arms).issubset(ARMS):
        raise ValueError("arms must be a unique nonempty subset of the implemented feedback arms")
    if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 2:
        raise ValueError("rounds includes the initial version and must be at least 2")
    concurrency = config.get("reference_concurrency", config.get("evaluation_concurrency", 4))
    if not isinstance(concurrency, int) or not 1 <= concurrency <= 16:
        raise ValueError("reference_concurrency must be between 1 and 16")
    tasks, manifest = load_benchmark(config)
    config_hash = sha256(config_bytes)
    sources = source_hashes()
    code_hash = canonical_sha256(sources)
    runtime = runtime_identity(config)
    runtime_hash = canonical_sha256(runtime)
    run_dir.mkdir(parents=True, exist_ok=True)
    lock = (run_dir / ".prepare.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError("Another process is preparing this batch") from exc
    plan_path = run_dir / "plan.json"
    plan = {
        "schema": "code-repair-extension-plan-v2",
        "batch_id": config["batch_id"],
        "config_path": str(config_path),
        "config_sha256": config_hash,
        "dataset_sha256": manifest["dataset_sha256"],
        "reference_code_sha256": code_hash,
        "reference_source_hashes": sources,
        "runtime": runtime,
        "runtime_sha256": runtime_hash,
        "manifest": manifest,
        "task_ids": [task["task_id"] for task in tasks],
        "models": models,
        "replicates": config.get("replicates", 3),
        "replicate_ids": repeats,
        "arms": arms,
        "rounds": rounds,
        "expected_requests": len(tasks) * len(models) * len(repeats) * (1 + len(arms) * (rounds - 1)),
        "reference_preflight_required": True,
    }
    fingerprint_fields = (
        "batch_id", "config_sha256", "dataset_sha256", "reference_code_sha256",
        "runtime_sha256", "task_ids", "models", "replicate_ids", "arms", "rounds", "expected_requests",
    )
    if plan_path.exists():
        previous = json.loads(plan_path.read_text())
        mismatched = [field for field in fingerprint_fields if previous.get(field) != plan[field]]
        if mismatched:
            raise ValueError("Existing frozen batch differs; create a new run_dir. Fields: " + ", ".join(mismatched))
        plan = previous
    else:
        if any((run_dir / name).exists() for name in ("responses.jsonl", "evaluations.jsonl")):
            raise ValueError("Refusing to adopt an existing collection without its matching frozen plan")
        oracle_dir = run_dir / "oracles"
        if oracle_dir.is_dir() and any(oracle_dir.iterdir()):
            raise ValueError("Refusing to adopt unproven reference caches without a matching frozen plan")
        plan["prepared_at_utc"] = timestamp()
        atomic_json(plan_path, plan)
    oracle_dir = run_dir / "oracles"
    oracle_dir.mkdir(exist_ok=True)
    splits = {row["task_id"]: row for row in manifest["task_splits"]}
    references, errors = [], []
    started = time.monotonic()
    status_path = run_dir / "reference-preflight.json"

    def write_status():
        complete = len(references) == len(tasks) and not errors
        status = {
            "schema": "code-repair-reference-preflight-v2", "batch_id": config["batch_id"],
            "updated_at_utc": timestamp(), "complete": complete,
            "config_sha256": config_hash, "dataset_sha256": manifest["dataset_sha256"],
            "reference_code_sha256": code_hash, "runtime_sha256": runtime_hash,
            "expected_tasks": len(tasks), "reference_complete": len(references),
            "references": sorted(references, key=lambda row: int(row["task_id"].split("/")[-1])),
            "errors": errors, "api_calls": 0,
            "public_cases": manifest["totals"]["public_count"],
            "holdout_cases": manifest["totals"]["holdout_count"],
            "seconds": round(time.monotonic() - started, 3),
        }
        atomic_json(status_path, status)
        return status

    def one(task: dict) -> dict:
        tid = task["task_id"]
        stem = tid.replace("/", "_")
        cache = oracle_dir / (stem + ".pkl")
        metadata_path = oracle_dir / (stem + ".json")
        split = splits[tid]
        expected = {
            "task_id": tid, "config_sha256": config_hash,
            "dataset_sha256": manifest["dataset_sha256"],
            "reference_code_sha256": code_hash, "runtime_sha256": runtime_hash,
            "reference_spec_sha256": split["reference_spec_sha256"],
            "public_inputs_sha256": split["public_inputs_sha256"],
            "holdout_inputs_sha256": split["holdout_inputs_sha256"],
            "canonical_code_sha256": sha256((task["prompt"] + task["canonical_solution"]).encode("utf-8")),
            "public_cases": len(task["base_input"]), "holdout_cases": len(task["plus_input"]),
        }
        if cache.exists() or metadata_path.exists():
            if not cache.is_file() or not metadata_path.is_file():
                # An interrupted atomic pair is not silently assumed valid.
                raise ValueError("Incomplete reference cache pair: " + tid)
            metadata = json.loads(metadata_path.read_text())
            if any(metadata.get(key) != value for key, value in expected.items()) or metadata.get("reference_pass") is not True:
                raise ValueError("Reference metadata/protocol mismatch: " + tid)
            blob = cache.read_bytes()
            if sha256(blob) != metadata.get("oracle_sha256"):
                raise ValueError("Reference oracle hash mismatch: " + tid)
            if not valid_oracle(pickle.loads(blob), task):
                raise ValueError("Reference oracle shape/count mismatch: " + tid)
            return {**metadata, "cache_reused": True}
        if source_hashes() != sources:
            raise RuntimeError("Evaluation source changed after protocol freeze")
        begin = time.monotonic()
        oracle = prepare_reference(config, task)
        if source_hashes() != sources:
            raise RuntimeError("Evaluation source changed during canonical execution")
        if not valid_oracle(oracle, task):
            raise ValueError("Reference execution returned incomplete test outputs: " + tid)
        blob = pickle.dumps(oracle, protocol=pickle.HIGHEST_PROTOCOL)
        temporary = cache.with_name(cache.name + f".{os.getpid()}.tmp")
        temporary.write_bytes(blob)
        temporary.replace(cache)
        metadata = {
            **expected, "reference_pass": True, "sandboxed": True,
            "oracle_sha256": sha256(blob), "oracle_size_bytes": len(blob),
            "prepared_at_utc": timestamp(),
            "reference_seconds": round(time.monotonic() - begin, 4),
        }
        atomic_json(metadata_path, metadata)
        return {**metadata, "cache_reused": False}

    write_status()
    print(json.dumps({"stage": "reference_preflight", "batch_id": config["batch_id"],
                      "tasks": len(tasks), "public_cases": manifest["totals"]["public_count"],
                      "holdout_cases": manifest["totals"]["holdout_count"],
                      "expected_requests": plan["expected_requests"], "api_calls": 0}), flush=True)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        pending = {pool.submit(one, task): task["task_id"] for task in tasks}
        for future in as_completed(pending):
            try:
                references.append(future.result())
            except Exception as exc:
                errors.append({"task_id": pending[future], "error": type(exc).__name__ + ": " + str(exc)[:1800]})
            status = write_status()
            finished = len(references) + len(errors)
            if finished % 10 == 0 or finished == len(tasks):
                print(json.dumps({"stage": "reference_preflight", "reference_complete": len(references),
                                  "reference_errors": len(errors), "expected_tasks": len(tasks),
                                  "cache_reused": sum(row["cache_reused"] for row in references),
                                  "seconds": status["seconds"], "api_calls": 0}), flush=True)
    if source_hashes() != sources:
        errors.append({"task_id": None, "error": "Evaluation source changed during reference preparation"})
    status = write_status()
    print(json.dumps({"reference_preflight": "complete" if status["complete"] else "failed",
                      "tasks": len(tasks), "errors": len(errors), "api_calls": 0,
                      "status_path": str(status_path)}), flush=True)
    return 0 if status["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
