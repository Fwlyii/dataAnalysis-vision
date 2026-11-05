"""Isolated v2 evaluation worker; launch only through evaluator.py."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import pickle
import resource
import sys
import time
import traceback
import warnings

sys.path.insert(0, sys.argv[3])
import numpy as np
from evalplus.eval import is_floats
from evalplus.eval._special_oracle import _poly
from evalplus.eval.utils import reliability_guard, swallow_io, time_limit, TimeoutException

CANDIDATE = "<candidate>"


def short(value, limit):
    try:
        text = repr(value)
    except BaseException:
        return "<unrepresentable>"
    return text[:limit] + ("...[truncated]" if len(text) > limit else "")


def matches(entry, inp, actual, expected, atol):
    if entry == "find_zero":
        return bool(abs(_poly(*inp, actual)) <= atol)
    exact = actual == expected
    if isinstance(exact, np.ndarray):
        exact = bool(exact.all())
    if atol == 0 and is_floats(expected):
        atol = 1e-6
    if not exact and atol != 0:
        if type(actual) != type(expected):
            return False
        if isinstance(expected, (list, tuple)) and len(actual) != len(expected):
            return False
        return bool(np.allclose(actual, expected, rtol=1e-7, atol=atol))
    return bool(exact)


def failure(exc=None, *, code, kind, stage, index=None, inp=None, expected=None, actual=None, repr_limit=1200):
    frames = []
    if exc is not None and exc.__traceback__:
        lines = code.splitlines()
        for frame in traceback.extract_tb(exc.__traceback__):
            if frame.filename == CANDIDATE:
                frames.append({
                    "filename": CANDIDATE,
                    "function": frame.name, "line": frame.lineno,
                    "column": frame.colno + 1 if getattr(frame, "colno", None) is not None else None,
                    "source_line": lines[frame.lineno - 1] if 0 < frame.lineno <= len(lines) else None,
                })
    frames = frames[-8:]
    line = getattr(exc, "lineno", None) if kind == "syntax" else (frames[-1]["line"] if frames else None)
    column = getattr(exc, "offset", None) if kind == "syntax" else (frames[-1]["column"] if frames else None)
    source_line = getattr(exc, "text", None) if kind == "syntax" else (frames[-1]["source_line"] if frames else None)
    return {
        "kind": kind, "stage": stage, "case_index": index,
        "input": short(inp, repr_limit) if index is not None else None,
        "expected": short(expected, repr_limit) if index is not None else None,
        "actual": short(actual, repr_limit) if index is not None else None,
        "error_type": type(exc).__name__ if exc is not None else "OutputMismatch",
        "error_message": str(exc)[:1000] if exc is not None else "Returned output differs from the diagnostic oracle.",
        "line": line, "column": column, "source_line": source_line.strip() if source_line else None,
        "candidate_traceback": frames,
        "location_convention": "1-based line and column",
    }


def blank(total):
    return {
        "passed": False, "total_cases": total, "passed_cases": 0,
        "failed_cases": 0, "cases_checked": 0, "unchecked_cases": total,
        "blocked_cases": 0, "failures": [], "first_failure": None,
        "error_counts": {}, "complete": False, "scan_complete": False,
        "outcome_known": False, "early_stopped": False,
    }


def append_failure(report, item, maximum):
    if report["first_failure"] is None:
        report["first_failure"] = item
    key = item["kind"]
    report["error_counts"][key] = report["error_counts"].get(key, 0) + 1
    # Prefer representatives of distinct error types; fill remaining slots with
    # distinct test inputs, rather than duplicating one repeated input.
    signature = (item["kind"], item["error_type"], item["input"], item["expected"], item["actual"])
    existing = [(value["kind"], value["error_type"], value["input"], value["expected"], value["actual"]) for value in report["failures"]]
    if signature in existing:
        return
    if len(report["failures"]) < maximum:
        report["failures"].append(item)
    elif item["kind"] not in {value["kind"] for value in report["failures"]} and maximum > 1:
        kinds = [value["kind"] for value in report["failures"]]
        # Keep the first failure stable and replace a redundant broad category.
        # A later NameError must not evict the only semantic counterexample.
        for index in range(len(kinds) - 1, 0, -1):
            if kinds.count(kinds[index]) > 1:
                report["failures"][index] = item
                break


def check(fn, task, inputs, oracle, code, options, progress, stop_on_failure=False):
    report = blank(len(inputs))
    if len(oracle["outputs"]) != len(inputs) or len(oracle["times"]) != len(inputs):
        raise ValueError("Oracle/input lengths differ.")
    start = time.monotonic()
    for index, (inp, expected, reference_time) in enumerate(zip(inputs, oracle["outputs"], oracle["times"])):
        if time.monotonic() - start > options["split_time_budget_s"]:
            report["infrastructure_status"] = "split_time_budget_exhausted"
            break
        actual = None
        item = None
        seconds = min(options["maximum_case_timeout_s"], max(options["minimum_case_timeout_s"], options["timeout_factor"] * reference_time))
        try:
            with time_limit(seconds), swallow_io():
                actual = fn(*copy.deepcopy(inp))
        except BaseException as exc:
            item = failure(exc, code=code, kind="timeout" if isinstance(exc, TimeoutException) else "runtime", stage="call", index=index, inp=inp, expected=expected, actual=actual, repr_limit=options["repr_limit"])
        if item is None:
            try:
                with time_limit(seconds), swallow_io():
                    correct = matches(task["entry_point"], inp, actual, expected, task["atol"])
            except BaseException:
                correct = False  # Invalid returned structure is an output error.
            if not correct:
                item = failure(code=code, kind="output_mismatch", stage="compare", index=index, inp=inp, expected=expected, actual=actual, repr_limit=options["repr_limit"])
        report["cases_checked"] += 1
        report["unchecked_cases"] -= 1
        if item is None:
            report["passed_cases"] += 1
        else:
            report["failed_cases"] += 1
            append_failure(report, item, options["max_feedback_failures"])
        if report["cases_checked"] % 20 == 0 or len(inputs) < 20:
            progress(report)
        if item is not None and stop_on_failure:
            report["early_stopped"] = report["unchecked_cases"] > 0
            break
    report["scan_complete"] = report["cases_checked"] == len(inputs)
    report["outcome_known"] = report["scan_complete"] or (stop_on_failure and report["failed_cases"] > 0)
    report["complete"] = report["outcome_known"]
    report["passed"] = report["scan_complete"] and report["failed_cases"] == 0
    progress(report)
    return report


def main():
    payload = pickle.loads(Path(sys.argv[1]).read_bytes())
    task, options = payload["task"], payload["options"]
    reference = payload["mode"] == "reference"
    result_handle = Path(sys.argv[2]).open("wb")
    oracle_handle = Path(payload["oracle_output"]).open("wb") if reference else None
    resource.setrlimit(resource.RLIMIT_CPU, (options["cpu_limit_s"], options["cpu_limit_s"]))
    maximum_file = (512 if reference else 8) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_FSIZE, (maximum_file, maximum_file))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    reliability_guard(maximum_memory_bytes=None)
    result = {}

    def emit():
        blob = json.dumps(result, ensure_ascii=False).encode()
        result_handle.seek(0); result_handle.write(blob); result_handle.truncate(); result_handle.flush()

    code = task["prompt"] + task["canonical_solution"] if reference else payload["code"]
    namespace = {"__name__": "candidate"}
    stage = "syntax"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tree = ast.parse(code, filename=CANDIDATE)
            stage = "load"
            with time_limit(options["load_timeout_s"]), swallow_io():
                exec(compile(tree, CANDIDATE, "exec"), namespace)
            fn = namespace[task["entry_point"]]
            if not callable(fn):
                raise TypeError("The required entry point is not callable.")
    except BaseException as exc:
        if reference:
            result["reference_error"] = type(exc).__name__ + ": " + str(exc)[:1000]
        else:
            item = failure(exc, code=code, kind="syntax" if stage == "syntax" else "timeout" if isinstance(exc, TimeoutException) else "load", stage=stage, repr_limit=options["repr_limit"])
            for name, inputs in [("public", task["base_input"]), ("hidden", task.get("plus_input", []))]:
                if name == "hidden" and not payload["include_holdout"]:
                    continue
                report = blank(len(inputs))
                report.update({"complete": True, "outcome_known": True, "blocked_cases": len(inputs), "failed_cases": len(inputs), "first_failure": item, "failures": [item], "error_counts": {item["kind"]: len(inputs)}, "load_failed": True})
                result[name] = report
            if payload["include_holdout"]:
                result["full_pass"] = False
        emit()
        return
    if reference:
        oracle = {}
        try:
            for name, inputs in [("base", task["base_input"]), ("plus", task.get("plus_input", []))]:
                outputs, times = [], []
                for inp in inputs:
                    begin = time.monotonic()
                    with time_limit(options["reference_case_timeout_s"]), swallow_io():
                        value = fn(*copy.deepcopy(inp))
                    times.append(time.monotonic() - begin)
                    outputs.append(value)
                oracle[name] = {"outputs": outputs, "times": times}
            oracle_handle.write(pickle.dumps(oracle)); oracle_handle.close()
            result["reference_pass"] = True
            result["case_counts"] = {name: len(value["outputs"]) for name, value in oracle.items()}
        except BaseException as exc:
            result["reference_error"] = type(exc).__name__ + ": " + str(exc)[:1000]
        emit()
        return
    for output_name, oracle_name, inputs in [("public", "base", task["base_input"]), ("hidden", "plus", task.get("plus_input", []))]:
        if output_name == "hidden" and not payload["include_holdout"]:
            continue
        def progress(report):
            result[output_name] = report
            emit()
        result[output_name] = check(fn, task, inputs, payload["oracle"][oracle_name], code, options, progress,
                                    stop_on_failure=output_name == "hidden" and options["holdout_stop_on_failure"])
    if payload["include_holdout"] and result["public"]["complete"] and result["hidden"]["complete"]:
        result["full_pass"] = bool(result["public"]["passed"] and result["hidden"]["passed"])
    emit()


if __name__ == "__main__":
    main()
