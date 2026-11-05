"""Version-two Python evaluation, always inside the macOS execution sandbox.

This module does not make model requests.  Public evaluation payloads exclude
the reference implementation, hidden inputs, and hidden oracle outputs.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import pickle
import signal
import subprocess
import sys
import tempfile
import time

import psutil

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "project.json").is_file())
WORKER = Path(__file__).with_name("worker.py").resolve()
DEFAULT_VENDOR = ROOT / "experiments/code_repair/vendor"


@lru_cache(maxsize=4)
def _interpreter_prefixes(python):
    result = subprocess.run(
        [python, "-I", "-c", "import sys,json;print(json.dumps([sys.prefix,sys.base_prefix]))"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=15,
        env={"PATH": "/usr/bin:/bin", "PYTHONNOUSERSITE": "1"},
    )
    return tuple(Path(value).resolve() for value in json.loads(result.stdout))


def _task_projection(task, include_holdout, reference):
    keys = ["task_id", "entry_point", "base_input", "atol"]
    if include_holdout or reference:
        keys.append("plus_input")
    if reference:
        keys.extend(["prompt", "canonical_solution"])
    result = {key: copy.deepcopy(task[key]) for key in keys if key in task}
    result.setdefault("base_input", [])
    result.setdefault("atol", 0)
    return result


def _resource_interruption(task, include_holdout, reason, partial=None):
    """Never turn an unfinished process into a measured passing candidate."""
    result = partial or {}
    failure = {
        "kind": "timeout" if "timeout" in reason or "cpu" in reason else "resource",
        "stage": "worker_resource_limit", "case_index": None,
        "input": None, "expected": None, "actual": None,
        "error_type": reason, "error_message": reason,
        "line": None, "column": None, "source_line": None,
        "candidate_traceback": [],
    }
    for name, inputs in [("public", task.get("base_input", [])), ("hidden", task.get("plus_input", []))]:
        if name == "hidden" and not include_holdout:
            continue
        split = result.setdefault(name, {
            "passed": False, "total_cases": len(inputs), "passed_cases": 0,
            "failed_cases": 0, "cases_checked": 0, "failures": [],
            "first_failure": None, "complete": False,
        })
        if not split.get("complete", False):
            split["passed"] = False
            split["complete"] = False
            split["scan_complete"] = False
            split["unchecked_cases"] = max(0, len(inputs) - split.get("cases_checked", 0))
            split["infrastructure_status"] = reason
            split["resource_failure"] = failure
            if not split.get("first_failure"):
                split["first_failure"] = failure
                split["failures"] = [failure]
    result["infrastructure_status"] = reason
    result.pop("full_pass", None)
    return result


def _run(config, task, code=None, oracle=None, include_holdout=False, reference=False):
    sandbox = Path("/usr/bin/sandbox-exec")
    if sys.platform != "darwin" or not sandbox.is_file():
        raise RuntimeError("This evaluator requires the macOS sandbox; no unsandboxed fallback is provided.")
    python = Path(config.get("python_executable", sys.executable)).absolute()
    if not python.is_file():
        raise RuntimeError("Evaluation Python interpreter is missing.")
    vendor = Path(config.get("evalplus_source", DEFAULT_VENDOR))
    vendor = (ROOT / vendor).resolve() if not vendor.is_absolute() else vendor.resolve()
    if not (vendor / "evalplus/eval/utils.py").is_file():
        raise RuntimeError("The frozen EvalPlus evaluator dependency is missing.")
    timeout = float(config.get("reference_timeout_s", 180) if reference else config.get("evaluation_timeout_s", 60))
    if timeout <= 0:
        raise ValueError("Evaluation timeout must be positive.")
    memory_mb = float(config.get("memory_limit_mb", 768))
    if memory_mb <= 0:
        raise ValueError("Evaluation memory limit must be positive.")
    projected_task = _task_projection(task, include_holdout, reference)
    projected_oracle = None
    if oracle is not None:
        names = ("base", "plus") if include_holdout else ("base",)
        projected_oracle = {name: copy.deepcopy(oracle[name]) for name in names}
    options = {
        "minimum_case_timeout_s": float(config.get("minimum_case_timeout_s", 1.0)),
        "maximum_case_timeout_s": float(config.get("maximum_case_timeout_s", 10.0)),
        "reference_case_timeout_s": float(config.get("reference_case_timeout_s", 10.0)),
        "timeout_factor": float(config.get("timeout_factor", 20.0)),
        "load_timeout_s": float(config.get("load_timeout_s", 5.0)),
        "max_feedback_failures": min(3, max(1, int(config.get("max_feedback_failures", 3)))),
        "holdout_stop_on_failure": bool(config.get("holdout_stop_on_failure", False)),
        "repr_limit": min(4000, max(80, int(config.get("repr_limit", 1200)))),
        "cpu_limit_s": int(config.get("reference_cpu_limit_s", math.ceil(timeout)) if reference else config.get("cpu_limit_s", math.ceil(timeout))),
        "split_time_budget_s": max(.01, float(config.get("split_time_budget_s", timeout - 2))),
    }
    with tempfile.TemporaryDirectory(prefix="course-code-repair-v2-") as temp:
        job = Path(temp).resolve()
        payload_path, result_path, oracle_path = [job / name for name in ("payload.pkl", "result.json", "oracle.pkl")]
        payload_path.write_bytes(pickle.dumps({
            "mode": "reference" if reference else "candidate", "task": projected_task,
            "code": code, "oracle": projected_oracle, "include_holdout": bool(include_holdout),
            "oracle_output": str(oracle_path), "options": options,
        }))
        quote = lambda value: json.dumps(str(value))
        # Resolve the chosen interpreter's environment without inheriting secrets.
        prefixes = _interpreter_prefixes(str(python))
        allowed = [*prefixes, vendor, job, Path("/System"), Path("/usr"), Path("/Library/Apple"), Path("/private/etc")]
        rules = " ".join(f"(subpath {quote(path)})" for path in dict.fromkeys(allowed))
        profile = (
            '(version 1)\n(deny default)\n(import "system.sb")\n'
            '(allow process*)\n(allow sysctl-read)\n(allow file-read-metadata)\n'
            f'(allow file-read* {rules} (literal {quote(WORKER)}) (subpath "/dev"))\n'
            f'(allow file-write* (subpath {quote(job)}) (literal "/dev/null"))\n'
            '(deny network*)\n'
        )
        command = [str(sandbox), "-p", profile, str(python), "-I", "-X", "utf8", str(WORKER), str(payload_path), str(result_path), str(vendor)]
        start = time.monotonic()
        proc = subprocess.Popen(
            command, cwd=job, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
            env={"PATH": "/usr/bin:/bin", "TMPDIR": str(job), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
        )
        interrupted = None
        while proc.poll() is None:
            if time.monotonic() - start > timeout:
                interrupted = "wall_timeout"
            try:
                if psutil.Process(proc.pid).memory_info().rss > memory_mb * 1024 * 1024:
                    interrupted = "memory_limit"
            except psutil.Error:
                pass
            if interrupted:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                break
            time.sleep(.025)
        _, stderr = proc.communicate()
        result = None
        if result_path.exists():
            try:
                result = json.loads(result_path.read_text())
            except (ValueError, OSError):
                pass  # A kill may interrupt the last progress write.
        if interrupted is None and proc.returncode in (-signal.SIGKILL, -signal.SIGXCPU):
            interrupted = "cpu_or_process_resource_limit"
        if reference:
            if interrupted or not result or result.get("reference_error") or not oracle_path.is_file():
                message = interrupted or (result or {}).get("reference_error") or stderr.decode(errors="replace")[-1500:]
                raise RuntimeError("Reference preflight failed: " + str(message))
            return pickle.loads(oracle_path.read_bytes())
        if interrupted:
            result = _resource_interruption(projected_task, include_holdout, interrupted, result)
        elif proc.returncode != 0 or not result:
            raise RuntimeError(f"Isolated evaluator infrastructure failed (exit {proc.returncode}): " + stderr.decode(errors="replace")[-1500:])
        result["evaluation_seconds"] = round(time.monotonic() - start, 4)
        result["sandboxed"] = True
        result["evaluator_version"] = "repair-v2-full-diagnostic-scan-1"
        return result


def prepare_reference(config, task):
    """Preflight the canonical solution and return serializable test oracles."""
    return _run(config, task, include_holdout=True, reference=True)


def evaluate(config, task, code, oracle, include_holdout=False):
    """Evaluate a candidate without a model API call or unsandboxed execution."""
    return _run(config, task, code=code, oracle=oracle, include_holdout=include_holdout)
