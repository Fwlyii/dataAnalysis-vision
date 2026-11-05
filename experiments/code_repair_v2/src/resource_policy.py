"""Resolve interrupted evaluation outcomes without modifying the frozen worker.

Measured test failures establish task failure even when a later scan is
interrupted. A parent-observed memory/wall limit is attributed to the candidate
only after a same-budget canonical control passes and the candidate repeats the
same limit. Per-test counts are never imputed. Every interruption, control and
retest is preserved in a local append-only resource audit; no model APIs or
credentials are accessed by this module.
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pickle
import threading
import uuid

from .evaluator import evaluate


POLICY_VERSION = "repair-v2-resource-outcome-clarification-1"
_AUDIT_LOCK = threading.Lock()
_CONFIRMABLE = {"memory_limit": "MemoryLimitExceeded", "wall_timeout": "WallTimeLimitExceeded"}
_BUDGET_KEYS = (
    "python_executable", "evalplus_source", "evaluation_timeout_s", "memory_limit_mb",
    "minimum_case_timeout_s", "maximum_case_timeout_s", "reference_case_timeout_s",
    "timeout_factor", "load_timeout_s", "max_feedback_failures",
    "holdout_stop_on_failure", "repr_limit", "cpu_limit_s", "split_time_budget_s",
)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _code_hash(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _names(include_holdout):
    return ("public", "hidden") if include_holdout else ("public",)


def _known_failure(split):
    return isinstance(split, dict) and split.get("passed") is False and (
        split.get("complete") is True or split.get("outcome_known") is True
    )


def _overall(result, include_holdout):
    """A demonstrated failing split settles FAIL; PASS needs both full splits."""
    if any(_known_failure(result.get(name)) for name in ("public", "hidden")):
        result["full_pass"] = False
    elif include_holdout and all(
        isinstance(result.get(name), dict) and result[name].get("complete") is True
        and result[name].get("passed") is True for name in ("public", "hidden")
    ):
        result["full_pass"] = True
    else:
        result.pop("full_pass", None)
    return result


def _incomplete_names(result, include_holdout):
    return [name for name in _names(include_holdout)
            if not isinstance(result.get(name), dict) or result[name].get("complete") is not True]


def _observed_failures(result, include_holdout):
    normalized = []
    for name in _names(include_holdout):
        split = result.get(name)
        if (isinstance(split, dict) and split.get("complete") is not True
                and split.get("failed_cases", 0) > 0):
            split.update({"passed": False, "complete": True, "outcome_known": True,
                          "scan_complete": False,
                          "outcome_resolution": "observed_test_failure_before_interruption"})
            normalized.append(name)
    return normalized


def _reason(result, split_name):
    split = result.get(split_name) or {}
    resource = split.get("resource_failure") or {}
    return split.get("infrastructure_status") or resource.get("error_type") or result.get("infrastructure_status")


def _scope_passes(result, include_holdout):
    for name in _names(include_holdout):
        split = result.get(name)
        if not isinstance(split, dict) or split.get("complete") is not True or split.get("passed") is not True:
            return False
        if split.get("scan_complete") is not True and split.get("cases_checked") != split.get("total_cases"):
            return False
    return True


def _canonical_metadata(run_dir, task, oracle):
    code = task["prompt"] + task["canonical_solution"]
    metadata = {
        "task_id": task["task_id"], "canonical_code_sha256": _code_hash(code),
        "public_inputs_sha256": _digest(task.get("base_input", [])),
        "holdout_inputs_sha256": _digest(task.get("plus_input", [])),
        "oracle_sha256": hashlib.sha256(pickle.dumps(oracle, protocol=pickle.HIGHEST_PROTOCOL)).hexdigest(),
    }
    path = Path(run_dir) / "oracles" / (task["task_id"].replace("/", "_") + ".json")
    if path.is_file():
        blob = path.read_bytes()
        recorded = json.loads(blob)
        metadata["preflight_metadata_sha256"] = hashlib.sha256(blob).hexdigest()
        metadata["preflight_metadata"] = recorded
        metadata["preflight_canonical_hash_matches"] = recorded.get("canonical_code_sha256") == metadata["canonical_code_sha256"]
    else:
        metadata["preflight_metadata"] = None
        metadata["preflight_canonical_hash_matches"] = None
    return metadata


def _append_audit(run_dir, entry):
    path = Path(run_dir) / "resource-audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(entry, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"
    # The thread lock protects concurrent local workers; flock also protects a
    # separate holdout process appending to the same run's audit.
    with _AUDIT_LOCK, path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle, fcntl.LOCK_UN)


def _normalized_resource_failure(result, split_name, reason):
    split = result[split_name]
    failure = copy.deepcopy(split.get("resource_failure") or {})
    failure.update({
        "kind": "runtime", "stage": "resource_limit", "error_type": _CONFIRMABLE[reason],
        "error_message": ("Candidate exceeded the unchanged " + reason
                          + " budget on two executions; the canonical same-scope control passed."),
    })
    for key in ("case_index", "input", "expected", "actual", "line", "column", "source_line"):
        failure.setdefault(key, None)
    failure.setdefault("candidate_traceback", [])
    split.update({"passed": False, "complete": True, "outcome_known": True,
                  "scan_complete": False, "candidate_resource_violation": True,
                  "outcome_resolution": "replicated_candidate_resource_violation",
                  "resource_failure": failure, "first_failure": copy.deepcopy(failure),
                  "failures": [copy.deepcopy(failure)]})
    # No checked/passed/failed/blocked/unchecked count is changed. If the public
    # process stopped, a placeholder hidden report is explicitly unmeasured.
    if split_name == "public" and isinstance(result.get("hidden"), dict):
        hidden = result["hidden"]
        if hidden.get("complete") is not True and hidden.get("cases_checked", 0) == 0:
            hidden["not_evaluated"] = True
            hidden["outcome_known"] = False
    return failure


def evaluate_resolved(config, task, code, oracle, *, include_holdout=False, run_dir, record_id):
    """Evaluate with conservative, audited resource-outcome resolution.

    Unknown SIGKILL/CPU interruption and unrelated infrastructure failures remain
    unknown. A recovered retest is returned as its real result. The helper never
    reads credentials and calls only the existing sandbox evaluator.
    """
    budget = {key: config[key] for key in _BUDGET_KEYS if key in config}
    entry = {
        "schema": "repair-v2-resource-audit-v1", "policy_version": POLICY_VERSION,
        "audit_id": str(uuid.uuid4()), "record_id": record_id, "task_id": task["task_id"],
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "include_holdout": bool(include_holdout), "candidate_code_sha256": _code_hash(code),
        "evaluation_budget": budget, "evaluation_budget_sha256": _digest(budget),
        "evaluations": [], "canonical_control": None,
    }

    def record(stage, result):
        entry["evaluations"].append({"stage": stage, "result_sha256": _digest(result),
                                      "result": copy.deepcopy(result)})

    def finish(result, decision, **details):
        result = _overall(result, include_holdout)
        resolution = {"policy_version": POLICY_VERSION, "audit_id": entry["audit_id"],
                      "decision": decision, **details}
        result["resource_resolution"] = resolution
        entry.update({"decision": decision, "resolution": resolution,
                      "resolved_result_sha256": _digest(result)})
        _append_audit(run_dir, entry)
        return result

    try:
        initial = evaluate(config, task, code, oracle, include_holdout=include_holdout)
    except Exception as exc:
        entry["decision"] = "initial_infrastructure_exception"
        entry["exception"] = {"type": type(exc).__name__, "message": str(exc)[:2000]}
        _append_audit(run_dir, entry)
        raise
    result = copy.deepcopy(initial)
    incomplete = _incomplete_names(result, include_holdout)
    if not incomplete:
        return _overall(result, include_holdout)
    record("initial", initial)
    observed = _observed_failures(result, include_holdout)
    if observed:
        return finish(result, "observed_test_failure_before_interruption", normalized_splits=observed)
    if any(_known_failure(result.get(name)) for name in _names(include_holdout)):
        return finish(result, "task_failure_already_observed")
    split_name = incomplete[0]
    reason = _reason(result, split_name)
    if reason not in _CONFIRMABLE:
        return finish(result, "unresolved_infrastructure_interruption", reason=reason)

    baseline = _canonical_metadata(run_dir, task, oracle)
    entry["canonical_baseline"] = baseline
    if baseline["preflight_canonical_hash_matches"] is False:
        return finish(result, "canonical_preflight_metadata_mismatch", reason=reason)
    canonical_code = task["prompt"] + task["canonical_solution"]
    try:
        control = evaluate(config, task, canonical_code, oracle, include_holdout=include_holdout)
    except Exception as exc:
        entry["canonical_control"] = {"exception": {"type": type(exc).__name__, "message": str(exc)[:2000]}}
        return finish(result, "canonical_control_infrastructure_exception", reason=reason)
    entry["canonical_control"] = {"result_sha256": _digest(control), "result": copy.deepcopy(control),
                                    "passed_same_scope": _scope_passes(control, include_holdout)}
    if not _scope_passes(control, include_holdout):
        return finish(result, "canonical_control_failed_or_incomplete", reason=reason)
    try:
        retry = evaluate(config, task, code, oracle, include_holdout=include_holdout)
    except Exception as exc:
        entry["retest_exception"] = {"type": type(exc).__name__, "message": str(exc)[:2000]}
        return finish(result, "candidate_retest_infrastructure_exception", reason=reason)
    record("candidate_retest", retry)
    retried = copy.deepcopy(retry)
    observed = _observed_failures(retried, include_holdout)
    if observed:
        return finish(retried, "observed_failure_on_retest", normalized_splits=observed, retried=True)
    pending = _incomplete_names(retried, include_holdout)
    if not pending or any(_known_failure(retried.get(name)) for name in _names(include_holdout)):
        return finish(retried, "completed_candidate_retest", retried=True)
    affected = pending[0]
    if _reason(retried, affected) != reason:
        return finish(retried, "nonreproduced_resource_interruption", initial_reason=reason,
                      retest_reason=_reason(retried, affected), retried=True)
    _normalized_resource_failure(retried, affected, reason)
    return finish(retried, "confirmed_candidate_resource_violation", normalized_split=affected,
                  reason=reason, retried=True, canonical_control_passed=True)
