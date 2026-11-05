"""Offline, task-clustered analysis of the extended feedback experiment.

No API calls and no execution of candidate programs. Public diagnostic curves
and strong held-out endpoint scores are kept separate. Only complete paired
task blocks enter comparative estimates; unfinished blocks remain in integrity
and coverage reports. Run ``python analyze.py --help`` for the CLI.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import difflib
import hashlib
import html
import importlib
import json
import math
from pathlib import Path
import random
import re
import statistics
import sys


ROOT = next(p for p in Path(__file__).resolve().parents if (p / "project.json").is_file())
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ARMS = ("resample", "self_review", "pass_fail", "diagnostic", "counterexample", "multi_counterexample")
ZH = {"resample": "独立重采样", "self_review": "自行检查", "pass_fail": "仅通过状态",
      "diagnostic": "错误定位诊断", "counterexample": "单个失败反例", "multi_counterexample": "多个失败反例"}
COLORS = {"resample": "#b5c7d0", "self_review": "#f4cf84", "pass_fail": "#76ccff",
          "diagnostic": "#d6c3ff", "counterexample": "#ff967f", "multi_counterexample": "#61e6d3"}
KEYS = ("model", "task_id", "replicate", "arm", "round")
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,})")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def records(path):
    path = Path(path)
    if not path.exists():
        return []
    values = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                values.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path}:{number}: {error.msg}") from error
    return values


def digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def indexed(rows, label):
    result = {}
    for row in rows:
        identity = row.get("record_id")
        if not identity:
            raise ValueError(f"Missing record_id in {label}")
        if identity in result:
            raise ValueError(f"Duplicate record_id in {label}: {identity}")
        result[identity] = row
    return result


def position(row):
    return (row["model"], row["task_id"], int(row.get("replicate", 0)), row["arm"], int(row["round"]))


def observed(score):
    public = (score or {}).get("public") or {}
    return (public.get("complete", True) is not False and public.get("outcome_known", True) is not False
            and isinstance(public.get("passed"), bool))


def split_observed(split):
    return (isinstance(split, dict) and split.get("complete", True) is not False
            and split.get("outcome_known", True) is not False and isinstance(split.get("passed"), bool))


def hidden_failure(score):
    hidden = (score or {}).get("hidden")
    return split_observed(hidden) and hidden["passed"] is False


def strong_observed(score):
    if not isinstance(score, dict) or not isinstance(score.get("full_pass"), bool):
        return False
    splits = [score.get(name) for name in ("public", "hidden")]
    if all(split_observed(split) for split in splits):
        joint = all(split["passed"] for split in splits)
        if score["full_pass"] != joint:
            raise ValueError("full_pass contradicts known public/held-out outcomes")
    if score["full_pass"] is False:
        # One demonstrated failing split settles the conjunction. Unexecuted
        # hidden inputs remain unknown and are never imputed as failed cases.
        return any(split_observed(split) and split["passed"] is False for split in splits)
    return all(split_observed(split) and split["passed"] is True
               and split.get("scan_complete", True) is not False for split in splits)


def public_pass(score):
    return bool(score["public"]["passed"])


def full_pass(score):
    if not strong_observed(score):
        return None
    return score["full_pass"]


def failure_kind(score):
    if not observed(score):
        return "unmeasured"
    if public_pass(score):
        return "pass"
    failure = score["public"].get("first_failure") or {}
    kind = failure.get("kind") or failure.get("failure_kind")
    if kind:
        return kind
    error = failure.get("error_type", "unknown")
    if error in {"SyntaxError", "IndentationError", "TabError"}:
        return "syntax"
    if error == "AssertionError":
        return "output_mismatch"
    if "timeout" in error.lower():
        return "timeout"
    return failure.get("stage") or "runtime"


def usage(row):
    value = row.get("usage") or (row.get("response") or {}).get("usage") or {}
    incoming, outgoing, total = (value.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
    if not all(isinstance(number, (int, float)) and number >= 0 for number in (incoming, outgoing, total)):
        return None
    if incoming + outgoing != total:
        raise ValueError(f"Inconsistent Token accounting: {row['record_id']}")
    return (incoming, outgoing, total)


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list))
                             else str(value).lower() if isinstance(value, bool) else value for key, value in row.items()})


class ClusterBootstrap:
    """Draw task clusters once, preserving repeats and models inside each task."""
    def __init__(self, task_ids, draws=5000, seed=20261105):
        self.tasks = list(task_ids)
        self.draws = draws
        self.indices = None
        self.np = None
        if len(self.tasks) < 2:
            return
        try:
            import numpy as np
            self.np = np
            self.indices = np.random.default_rng(seed).integers(0, len(self.tasks), size=(draws, len(self.tasks)))
        except ImportError:
            rng = random.Random(seed)
            self.indices = [[rng.randrange(len(self.tasks)) for _ in self.tasks] for _ in range(draws)]

    def ratio(self, numerator, denominator):
        """Ratio of cluster sums, rather than an unweighted mean of per-task ratios."""
        if self.indices is None:
            return None
        num = [numerator.get(task, 0.0) for task in self.tasks]
        den = [denominator.get(task, 0.0) for task in self.tasks]
        if not sum(den):
            return None
        if self.np is not None:
            np = self.np
            a = np.asarray(num)[self.indices].sum(axis=1)
            b = np.asarray(den)[self.indices].sum(axis=1)
            values = a[b > 0] / b[b > 0]
            if not len(values):
                return None
            return [float(number) for number in np.quantile(values, [.025, .975])]
        values = []
        for indices in self.indices:
            b = sum(den[index] for index in indices)
            if b:
                values.append(sum(num[index] for index in indices) / b)
        if not values:
            return None
        values.sort()
        return [quantile(values, .025), quantile(values, .975)]

    def mean(self, values):
        return self.ratio(values, {task: 1 for task in self.tasks})


def quantile(sorted_values, probability):
    x = probability * (len(sorted_values) - 1)
    left, right = math.floor(x), math.ceil(x)
    return sorted_values[left] * (right - x) + sorted_values[right] * (x - left) if left != right else sorted_values[left]


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.fmean(values) if values else None


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def task_ratio(observations, numerator, denominator, bootstrap):
    a, b = defaultdict(float), defaultdict(float)
    for row in observations:
        a[row["task_id"]] += numerator(row)
        b[row["task_id"]] += denominator(row)
    return ratio(sum(a.values()), sum(b.values())), bootstrap.ratio(a, b)


def display_model(config, model):
    return config.get("model_names", {}).get(model, model.split("/")[-1])


def resolve_tasks(config, plan, raw):
    if isinstance(plan.get("task_ids"), list):
        return [str(task) for task in plan["task_ids"]]
    if isinstance(plan.get("tasks"), list):
        return [task["task_id"] if isinstance(task, dict) else str(task) for task in plan["tasks"]]
    if isinstance(config.get("task_ids"), list):
        return list(config["task_ids"])
    values = {row["task_id"] for row in raw.values()}
    return sorted(values, key=lambda task: (int(task.split("/")[-1]) if task.split("/")[-1].isdigit() else task))


def audit(config, raw, evaluations, by_position, configuration_sha):
    from experiments.code_repair_v2.src.protocol import feedback_message
    counts = Counter()
    errors = []
    for identity, row in raw.items():
        if SECRET.search(json.dumps(row, ensure_ascii=False)):
            raise ValueError("Possible credential in saved response; stop export")
        if row.get("config_sha256") and row["config_sha256"] != configuration_sha:
            errors.append({"record_id": identity, "error": "config_sha256 mismatch"})
        score = evaluations.get(identity)
        expected_code_sha = hashlib.sha256(row["code"].encode()).hexdigest()
        if row.get("code_sha256") not in (None, expected_code_sha):
            errors.append({"record_id": identity, "error": "saved code SHA-256 mismatch"})
        if score is not None:
            if score.get("config_sha256") not in (None, configuration_sha):
                errors.append({"record_id": identity, "error": "evaluation config_sha256 mismatch"})
            if score.get("code_sha256") not in (None, expected_code_sha):
                errors.append({"record_id": identity, "error": "evaluation belongs to different code"})
            if any(score.get(key, row.get(key, 0)) != row.get(key, 0) for key in KEYS):
                errors.append({"record_id": identity, "error": "evaluation condition differs from response"})
            if not score.get("sandboxed"):
                errors.append({"record_id": identity, "error": "unsandboxed evaluation"})
            else:
                counts["sandboxed_evaluations"] += 1
            public = score.get("public") or {}
            load_failed = public.get("load_failed") is True
            if load_failed:
                values = [public.get(key) for key in ("total_cases", "cases_checked", "passed_cases",
                                                       "failed_cases", "blocked_cases", "unchecked_cases")]
                valid_counts = (all(isinstance(value, int) and not isinstance(value, bool) and value >= 0
                                    for value in values)
                                and values[0] > 0 and values[1] == values[2] == 0
                                and values[3] == values[4] == values[5] == values[0])
                if (not valid_counts or public.get("passed") is not False
                        or public.get("scan_complete") is not False or public.get("complete") is not True
                        or public.get("outcome_known") is not True):
                    errors.append({"record_id": identity, "error": "invalid load-failure case counts or verdict"})
                else:
                    counts["load_failed_programs"] += 1
                    counts["load_failed_logical_case_labels"] += public["failed_cases"]
                    counts["load_failed_blocked_inputs"] += public["blocked_cases"]
                    # Frozen load failures label the entire suite as failed,
                    # blocked and unchecked without executing its inputs.
                    counts["actual_cases_checked"] += 0
                    counts["actual_passed_cases"] += 0
                    counts["actual_failed_cases"] += 0
            if observed(score):
                counts["complete_public_verdicts"] += 1
                if public.get("candidate_resource_violation") is True:
                    counts["audited_candidate_resource_failures"] += 1
                if score.get("resource_resolution"):
                    counts["resource_resolution_" + score["resource_resolution"]["decision"]] += 1
                if public["passed"] and public.get("scan_complete", True) is False:
                    errors.append({"record_id": identity, "error": "public PASS without a complete scan"})
                checked = public.get("cases_checked")
                passed, failed = public.get("passed_cases"), public.get("failed_cases")
                if not load_failed and all(isinstance(value, int) for value in (checked, passed, failed)):
                    if checked != passed + failed:
                        errors.append({"record_id": identity, "error": "tested case counts do not sum"})
                    else:
                        counts["actual_cases_checked"] += checked
                        counts["actual_passed_cases"] += passed
                        counts["actual_failed_cases"] += failed
            else:
                counts["unknown_public_verdicts"] += 1
            if strong_observed(score):
                hidden = score.get("hidden") or {}
                if hidden.get("passed") and hidden.get("scan_complete", True) is False:
                    errors.append({"record_id": identity, "error": "held-out PASS without a complete scan"})
                full_pass(score)
                counts["complete_strong_verdicts"] += 1
        cost = usage(row)
        counts["usage_available" if cost is not None else "usage_missing"] += 1
        if (row.get("response") or {}).get("model") not in (None, row["model"]):
            errors.append({"record_id": identity, "error": "provider returned different model"})
        arm, round_ = row["arm"], int(row["round"])
        seed = by_position.get((row["model"], row["task_id"], int(row.get("replicate", 0)), "seed", 0))
        if seed and row.get("shared_seed_id") not in (None, seed["record_id"]):
            errors.append({"record_id": identity, "error": "shared seed mismatch"})
        if round_ == 0 or arm == "resample":
            if row.get("parent_id") is not None or row.get("feedback") is not None:
                errors.append({"record_id": identity, "error": "independent request carries parent/feedback"})
            if seed and row.get("request", {}).get("messages") != seed.get("request", {}).get("messages"):
                errors.append({"record_id": identity, "error": "independent request differs from initial prompt"})
            counts["independent_requests"] += 1
            continue
        previous_arm = "seed" if round_ == 1 else arm
        parent = by_position.get((row["model"], row["task_id"], int(row.get("replicate", 0)), previous_arm, round_ - 1))
        if not parent or parent["record_id"] != row.get("parent_id"):
            errors.append({"record_id": identity, "error": "parent identity mismatch"})
            continue
        parent_score = evaluations.get(parent["record_id"])
        if not observed(parent_score):
            errors.append({"record_id": identity, "error": "revision used an unknown parent diagnostic"})
            continue
        # Deliberately omit hidden results from the object passed to the builder.
        expected_feedback = feedback_message(arm, {"public": parent_score["public"]})
        if row.get("feedback") != expected_feedback:
            errors.append({"record_id": identity, "error": "feedback differs from public-only projection"})
        expected_messages = parent["request"]["messages"] + [
            {"role": "assistant", "content": parent["content"]},
            {"role": "user", "content": expected_feedback}]
        if row.get("request", {}).get("messages") != expected_messages:
            errors.append({"record_id": identity, "error": "arm-specific history differs"})
        counts["verified_parent_and_public_feedback"] += 1
    if errors:
        raise ValueError("Protocol integrity failed: " + json.dumps(errors[:10], ensure_ascii=False))
    return dict(counts)


def analyze(config_path, run_dir=None, output=None, allow_partial=False):
    config_path = Path(config_path).resolve()
    config = load_json(config_path)
    location = run_dir or config.get("run_dir") or config.get("raw_output")
    if not location:
        raise ValueError("config.run_dir or --run-dir is required")
    run_dir = Path(location)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    plan = load_json(run_dir / "plan.json") if (run_dir / "plan.json").is_file() else {}
    batch = config.get("batch_id") or plan.get("batch_id") or run_dir.name
    if not re.fullmatch(r"[\w.-]+", batch):
        raise ValueError("batch_id must be a safe single path component")
    output = Path(output or ROOT / "reports/code_repair_extension" / batch).resolve()
    synthetic = config.get("synthetic", False)
    if synthetic and not output.is_relative_to((ROOT / "work").resolve()):
        raise ValueError("Synthetic fixture results are restricted to work/, never real reports or app snapshots")
    output.mkdir(parents=True, exist_ok=True)
    configuration_sha = digest(config_path)
    if plan.get("config_sha256") and plan["config_sha256"] != configuration_sha:
        raise ValueError("Frozen plan/config SHA-256 mismatch")
    raw = indexed(records(run_dir / "responses.jsonl"), "responses")
    diagnostic_evaluations = indexed(records(run_dir / "evaluations.jsonl"), "evaluations")
    evaluations = dict(diagnostic_evaluations)
    holdouts = indexed(records(run_dir / "holdout-evaluations.jsonl"), "holdout evaluations")
    for identity, score in holdouts.items():
        if identity not in raw:
            raise ValueError("Held-out evaluation has no saved response: " + identity)
        evaluations[identity] = {**evaluations.get(identity, {}), **score}
    by_position = {}
    for row in raw.values():
        key = position(row)
        if key in by_position:
            raise ValueError("Duplicate model/task/repeat/arm/round: " + str(key))
        by_position[key] = row
    models = list(config.get("models") or sorted({row["model"] for row in raw.values()}))
    arms = list(config.get("arms") or ARMS)
    if len(set(arms)) != len(arms) or any(arm not in ARMS for arm in arms):
        raise ValueError("Unexpected or duplicated feedback arms")
    repetitions = config.get("replicates", 3)
    repetitions = list(range(repetitions)) if isinstance(repetitions, int) else list(repetitions)
    rounds = int(config.get("rounds", 5))
    tasks = resolve_tasks(config, plan, raw)
    expected = len(tasks) * len(models) * len(repetitions) * (1 + len(arms) * (rounds - 1))
    if len(set(tasks)) != len(tasks):
        raise ValueError("Duplicate planned tasks")
    for row in raw.values():
        if (row["model"] not in models or row["task_id"] not in tasks
                or int(row.get("replicate", 0)) not in repetitions
                or int(row["round"]) not in range(rounds)
                or (int(row["round"]) == 0 and row["arm"] != "seed")
                or (int(row["round"]) > 0 and row["arm"] not in arms)):
            raise ValueError("Saved response is outside the frozen experiment plan: " + row["record_id"])
    coverage, missing = [], []
    for task in tasks:
        absent, unknown, strong_missing, trajectory_missing = [], [], [], []
        for model in models:
            for repeat in repetitions:
                for round_ in range(rounds):
                    for arm in (["seed"] if round_ == 0 else arms):
                        row = by_position.get((model, task, repeat, arm, round_))
                        key = {"model": model, "task_id": task, "replicate": repeat, "arm": arm, "round": round_}
                        if row is None:
                            absent.append(key)
                            trajectory_missing.append(key)
                            continue
                        original_score = diagnostic_evaluations.get(row["record_id"])
                        score = evaluations.get(row["record_id"])
                        if not observed(original_score):
                            unknown.append({**key, "record_id": row["record_id"]})
                        if round_ in (0, rounds - 1) and not strong_observed(score):
                            strong_missing.append({**key, "record_id": row["record_id"]})
                        if not strong_observed(score):
                            trajectory_missing.append({**key, "record_id": row["record_id"]})
        public_complete = not absent and not unknown
        coverage.append({"task_id": task, "public_block_complete": public_complete,
                         "strong_endpoint_block_complete": public_complete and not strong_missing,
                         "strong_trajectory_block_complete": public_complete and not trajectory_missing,
                         "missing_responses": len(absent), "unknown_public_verdicts": len(unknown),
                         "missing_strong_endpoints": len(strong_missing),
                         "missing_strong_trajectory_verdicts": len(trajectory_missing)})
        missing.extend({**item, "reason": reason} for reason, items in [
            ("response_missing", absent), ("public_unknown", unknown), ("strong_endpoint_missing", strong_missing)] for item in items)
    # Strong re-execution may expose nondeterministic code or a resource-policy
    # difference. It must never rewrite what the model actually saw earlier.
    integrity_counts = audit(config, raw, diagnostic_evaluations, by_position, configuration_sha)
    for identity, heldout in holdouts.items():
        if heldout.get("config_sha256") not in (None, configuration_sha):
            raise ValueError("Held-out evaluation config_sha256 mismatch: " + identity)
        if heldout.get("sandboxed") is not True:
            raise ValueError("Unsandboxed held-out re-evaluation: " + identity)
        expected_code_sha = hashlib.sha256(raw[identity]["code"].encode()).hexdigest()
        if heldout.get("code_sha256") not in (None, expected_code_sha):
            raise ValueError("Held-out result belongs to different candidate code: " + identity)
        if any(heldout.get(key, raw[identity].get(key, 0)) != raw[identity].get(key, 0) for key in KEYS):
            raise ValueError("Held-out evaluation condition differs from its response: " + identity)
        if strong_observed(heldout):
            full_pass(heldout)
            if heldout["public"]["passed"] and heldout["public"].get("scan_complete", True) is False:
                raise ValueError("Rechecked public PASS without a complete scan: " + identity)
            hidden = heldout.get("hidden") or {}
            if hidden.get("passed") and hidden.get("scan_complete", True) is False:
                raise ValueError("Held-out PASS without a complete scan: " + identity)
    integrity_counts["strong_sidecar_verdicts"] = sum(strong_observed(row) for row in holdouts.values())
    public_tasks = [row["task_id"] for row in coverage if row["public_block_complete"]]
    main_tasks = [row["task_id"] for row in coverage if row["strong_endpoint_block_complete"]]
    strong_curve_tasks = [row["task_id"] for row in coverage if row["strong_trajectory_block_complete"]]
    integrity = {"schema": "course-code-repair-extension-integrity-v1", "batch_id": batch,
                 "synthetic": synthetic, "complete": not missing, "expected_physical_responses": expected,
                 "saved_physical_responses": len(raw), "planned_independent_tasks": len(tasks),
                 "paired_public_task_clusters": len(public_tasks), "paired_strong_task_clusters": len(main_tasks),
                 "paired_strong_trajectory_task_clusters": len(strong_curve_tasks),
                 "models": models, "replicates": repetitions, "arms": arms, "rounds": rounds,
                 "missing_count": len(missing), "checks": integrity_counts, "config_sha256": configuration_sha,
                 "source_sha256": {name: digest(run_dir / name) for name in [
                     "responses.jsonl", "evaluations.jsonl", "holdout-evaluations.jsonl", "plan.json",
                     "attempts.jsonl", "operational-amendment-1.json", "resource-audit.jsonl"]},
                 "missing": missing, "coverage": coverage,
                 "statistical_unit": "task; models and independent initial repeats stay within the same task cluster",
                 "unknown_verdict_policy": "Incomplete or unmeasured tests are missing, never scored as failures."}
    write_json(output / "integrity.json", integrity)
    write_csv(output / "coverage.csv", coverage)
    if missing and not allow_partial:
        raise ValueError(f"Incomplete paired experiment ({len(missing)} missing/unknown items); integrity written. Use --partial for labelled complete-block monitoring.")
    if not raw:
        raise ValueError("No saved responses; no figures or invented results were generated")
    bootstrap_config = config.get("bootstrap") or {}
    draws, seed = int(bootstrap_config.get("resamples", 5000)), int(bootstrap_config.get("seed", 20261105))
    public_bootstrap = ClusterBootstrap(public_tasks, draws, seed)
    main_bootstrap = ClusterBootstrap(main_tasks, draws, seed)
    strong_curve_bootstrap = ClusterBootstrap(strong_curve_tasks, draws, seed)

    def trajectory(model, task, repeat, arm):
        return [by_position[(model, task, repeat, "seed" if index == 0 else arm, index)] for index in range(rounds)]

    def score(row):
        return diagnostic_evaluations[row["record_id"]]

    def strong_score(row):
        return evaluations[row["record_id"]]

    summaries, curves, strong_curves, endpoints, features, initial_support, transitions = [], [], [], [], [], [], Counter()
    outcome_rows = {}
    for model in models:
        support = Counter()
        for task in public_tasks:
            for repeat in repetitions:
                row = by_position[(model, task, repeat, "seed", 0)]
                support[failure_kind(score(row))] += 1
        initial_support.extend({"model": model, "model_label": display_model(config, model), "error_kind": kind,
                                "initial_programs": count, "task_clusters": len(public_tasks),
                                "repeats_per_task": len(repetitions)} for kind, count in sorted(support.items()))
        for arm in arms:
            for round_ in range(rounds):
                strong_observations = []
                for task in strong_curve_tasks:
                    for repeat in repetitions:
                        seq = trajectory(model, task, repeat, arm)
                        strong_observations.append({"task_id": task, "passed": full_pass(strong_score(seq[round_]))})
                rate, interval = task_ratio(strong_observations, lambda item: item["passed"], lambda item: 1,
                                            strong_curve_bootstrap)
                strong_curves.append({"model": model, "model_label": display_model(config, model), "arm": arm,
                    "round": round_, "metric": "base_and_strong_holdout_pass", "task_clusters": len(strong_curve_tasks),
                    "initial_repeats": len(repetitions), "programs": len(strong_observations),
                    "passed_programs": sum(item["passed"] for item in strong_observations), "rate": rate,
                    "ci_low": interval[0] if interval else None, "ci_high": interval[1] if interval else None})
            public_sequences = [trajectory(model, task, repeat, arm) for task in public_tasks for repeat in repetitions]
            for round_ in range(rounds):
                observations = []
                cumulative_costs, cumulative_calls = [], []
                for seq in public_sequences:
                    current, ev = seq[round_], score(seq[round_])
                    passed = public_pass(ev)
                    observations.append({"task_id": current["task_id"], "passed": passed})
                    previous = score(seq[round_ - 1]) if round_ else None
                    cost_items = [usage(item) for item in seq[:round_ + 1]]
                    chain = tuple(sum(item[index] for item in cost_items) for index in range(3)) if all(item is not None for item in cost_items) else None
                    cumulative_costs.append(chain)
                    cumulative_calls.append(round_ + 1)
                    features.append({"model": model, "task_id": current["task_id"], "replicate": current.get("replicate", 0),
                        "arm": arm, "round": round_, "public_pass": passed, "strong_full_pass": full_pass(strong_score(current)),
                        "strong_outcome_known": strong_observed(strong_score(current)),
                        "holdout_cases_checked": (strong_score(current).get("hidden") or {}).get("cases_checked"),
                        "holdout_outcome_known": split_observed(strong_score(current).get("hidden")),
                        "error_kind": failure_kind(ev),
                        "passed_cases": ev["public"].get("passed_cases"), "failed_cases": ev["public"].get("failed_cases"),
                        "cases_checked": ev["public"].get("cases_checked"), "total_cases": ev["public"].get("total_cases"),
                        "public_load_failed": ev["public"].get("load_failed", False),
                        "public_scan_complete": ev["public"].get("scan_complete"),
                        "blocked_cases": ev["public"].get("blocked_cases"),
                        "unchecked_cases": ev["public"].get("unchecked_cases"),
                        "executed_failed_cases": 0 if ev["public"].get("load_failed") is True else ev["public"].get("failed_cases"),
                        "input_tokens": cost_items[-1][0] if cost_items[-1] is not None else None,
                        "output_tokens": cost_items[-1][1] if cost_items[-1] is not None else None,
                        "cumulative_tokens": chain[2] if chain is not None else None,
                        "physical_record_id": current["record_id"], "shared_seed": round_ == 0})
                    if previous is not None:
                        transitions[model, arm, round_, failure_kind(previous), failure_kind(ev)] += 1
                rate, interval = task_ratio(observations, lambda item: item["passed"], lambda item: 1, public_bootstrap)
                curves.append({"model": model, "model_label": display_model(config, model), "arm": arm, "round": round_,
                    "metric": "public_diagnostic_pass", "task_clusters": len(public_tasks),
                    "initial_repeats": len(repetitions), "programs": len(observations),
                    "passed_programs": sum(item["passed"] for item in observations), "rate": rate,
                    "ci_low": interval[0] if interval else None, "ci_high": interval[1] if interval else None,
                    "mean_cumulative_tokens": mean([item[2] if item else None for item in cumulative_costs]),
                    "token_chains_missing": sum(item is None for item in cumulative_costs)})
            observations = []
            for task in main_tasks:
                for repeat in repetitions:
                    seq = trajectory(model, task, repeat, arm)
                    scores = [score(row) for row in seq]
                    strong_initial, strong_final = strong_score(seq[0]), strong_score(seq[-1])
                    initial, final = full_pass(strong_initial), full_pass(strong_final)
                    first_public_pass = next((index for index, ev in enumerate(scores) if public_pass(ev)), rounds - 1)
                    stopped = strong_score(seq[first_public_pass])
                    token_items = [usage(item) for item in seq]
                    chain = tuple(sum(item[index] for item in token_items) for index in range(3)) if all(item is not None for item in token_items) else None
                    stopped_items = token_items[:first_public_pass + 1]
                    stopped_cost = sum(item[2] for item in stopped_items) if all(item is not None for item in stopped_items) else None
                    observations.append({"task_id": task, "replicate": repeat, "initial": initial, "final": final,
                        "initial_public": public_pass(scores[0]), "final_public": public_pass(scores[-1]),
                        "initial_kind": failure_kind(scores[0]), "final_kind": failure_kind(scores[-1]),
                        "initial_hidden_only": public_pass(scores[0]) and hidden_failure(strong_initial),
                        "final_hidden_only": public_pass(scores[-1]) and hidden_failure(strong_final),
                        "initial_public_recheck_changed": public_pass(scores[0]) != public_pass(strong_initial),
                        "final_public_recheck_changed": public_pass(scores[-1]) != public_pass(strong_final),
                        "ever_public": any(public_pass(ev) for ev in scores),
                        "stop_round": first_public_pass, "stopped_full_pass": full_pass(stopped),
                        "stop_calls": first_public_pass + 1, "stop_tokens": stopped_cost,
                        "total_calls": rounds, "input_tokens": chain[0] if chain else None,
                        "output_tokens": chain[1] if chain else None, "total_tokens": chain[2] if chain else None})
            outcome_rows[model, arm] = observations
            final_rate, final_ci = task_ratio(observations, lambda item: item["final"], lambda item: 1, main_bootstrap)
            initial_rate, initial_ci = task_ratio(observations, lambda item: item["initial"], lambda item: 1, main_bootstrap)
            net, net_ci = task_ratio(observations, lambda item: int(item["final"]) - int(item["initial"]), lambda item: 1, main_bootstrap)
            repaired, repaired_ci = task_ratio(observations, lambda item: not item["initial"] and item["final"], lambda item: not item["initial"], main_bootstrap)
            visible_repair, visible_ci = task_ratio(observations, lambda item: not item["initial_public"] and item["final"], lambda item: not item["initial_public"], main_bootstrap)
            regressed, regressed_ci = task_ratio(observations, lambda item: item["initial"] and not item["final"], lambda item: item["initial"], main_bootstrap)
            stopping_complete = all(item["stopped_full_pass"] is not None for item in observations)
            summary = {"model": model, "model_label": display_model(config, model), "arm": arm, "arm_label": ZH[arm],
                "task_clusters": len(main_tasks), "repeats_per_task": len(repetitions), "programs": len(observations),
                "initial_success": sum(item["initial"] for item in observations),
                "initial_rate": initial_rate, "initial_ci": initial_ci,
                "final_success": sum(item["final"] for item in observations), "final_rate": final_rate, "final_ci": final_ci,
                "net_gain_pp": net * 100 if net is not None else None,
                "net_gain_ci_pp": [v * 100 for v in net_ci] if net_ci else None,
                "initial_failures": sum(not item["initial"] for item in observations),
                "repaired": sum(not item["initial"] and item["final"] for item in observations),
                "repair_rate": repaired, "repair_ci": repaired_ci,
                "initial_visible_failures": sum(not item["initial_public"] for item in observations),
                "visible_repaired": sum(not item["initial_public"] and item["final"] for item in observations),
                "visible_repair_rate": visible_repair, "visible_repair_ci": visible_ci,
                "initial_correct": sum(item["initial"] for item in observations),
                "regressed": sum(item["initial"] and not item["final"] for item in observations),
                "regression_rate": regressed, "regression_ci": regressed_ci,
                "initial_hidden_only_failures": sum(item["initial_hidden_only"] for item in observations),
                "final_public_pass_hidden_fail": sum(item["final_hidden_only"] for item in observations),
                "initial_public_recheck_changes": sum(item["initial_public_recheck_changed"] for item in observations),
                "final_public_recheck_changes": sum(item["final_public_recheck_changed"] for item in observations),
                "ever_public_pass_rate": mean([float(item["ever_public"]) for item in observations]),
                "first_public_pass_mean_calls": mean([item["stop_calls"] for item in observations]),
                "first_public_pass_mean_tokens": mean([item["stop_tokens"] for item in observations]),
                "stopping_strong_measured_programs": sum(item["stopped_full_pass"] is not None for item in observations),
                "stopping_strong_rate": mean([float(item["stopped_full_pass"]) for item in observations]) if stopping_complete and observations else None,
                "stopping_policy_note": "Strong stopping accuracy is reported only when every publicly-selected version has a strong evaluation; hidden scores never select versions.",
                "mean_chain_input_tokens": mean([item["input_tokens"] for item in observations]),
                "mean_chain_output_tokens": mean([item["output_tokens"] for item in observations]),
                "mean_chain_total_tokens": mean([item["total_tokens"] for item in observations]),
                "token_chains_missing": sum(item["total_tokens"] is None for item in observations)}
            summaries.append(summary)
            for round_, rate, interval, count in [(0, initial_rate, initial_ci, summary["initial_success"]),
                                                 (rounds - 1, final_rate, final_ci, summary["final_success"])]:
                endpoints.append({"model": model, "arm": arm, "round": round_, "metric": "base_and_strong_holdout_pass",
                    "task_clusters": len(main_tasks), "programs": len(observations), "passed_programs": count,
                    "rate": rate, "ci_low": interval[0] if interval else None, "ci_high": interval[1] if interval else None})

    contrasts = []
    comparisons = [(arm, baseline) for arm in arms for baseline in arms if arms.index(arm) > arms.index(baseline)]
    for model in models + ["__pooled__"]:
        selected_models = models if model == "__pooled__" else [model]
        for arm, baseline in comparisons:
            task_differences, wins, losses, ties, pairs = defaultdict(list), 0, 0, 0, 0
            for current_model in selected_models:
                a, b = outcome_rows[current_model, arm], outcome_rows[current_model, baseline]
                b_index = {(row["task_id"], row["replicate"]): row for row in b}
                for row in a:
                    control = b_index[row["task_id"], row["replicate"]]
                    difference = int(row["final"]) - int(control["final"])
                    task_differences[row["task_id"]].append(difference)
                    wins += difference > 0; losses += difference < 0; ties += difference == 0; pairs += 1
            averaged = {task: statistics.fmean(values) for task, values in task_differences.items()}
            interval = main_bootstrap.mean(averaged)
            contrasts.append({"model": model, "arm": arm, "baseline": baseline, "policy": "final_strong_holdout",
                "task_clusters": len(main_tasks), "paired_programs": pairs,
                "arm_wins": wins, "baseline_wins": losses, "ties": ties,
                "task_mean_arm_wins": sum(value > 0 for value in averaged.values()),
                "task_mean_baseline_wins": sum(value < 0 for value in averaged.values()),
                "delta_pp": mean(list(averaged.values())) * 100 if averaged else None,
                "ci_low_pp": interval[0] * 100 if interval else None,
                "ci_high_pp": interval[1] * 100 if interval else None,
                "interval_note": "95% task-cluster bootstrap; exploratory pairwise intervals, no multiplicity adjustment"})

    # Intention-to-evaluate bounds retain the planned denominator. Unknowns are
    # not scored as failures: both logically possible extremes are shown.
    endpoint_bounds, contrast_bounds = [], []

    def endpoint_value(model, task, repeat, arm, round_):
        row=by_position.get((model,task,repeat,"seed" if round_==0 else arm,round_))
        return full_pass(evaluations.get(row["record_id"])) if row and strong_observed(evaluations.get(row["record_id"])) else None

    for model in models + ["__pooled__"]:
        selected_models=models if model=="__pooled__" else [model]
        planned=len(tasks)*len(repetitions)*len(selected_models)
        for arm in arms:
            for round_ in (0,rounds-1):
                values=[endpoint_value(current_model,task,repeat,arm,round_) for current_model in selected_models
                        for task in tasks for repeat in repetitions]
                passed=sum(value is True for value in values)
                failed=sum(value is False for value in values)
                unknown=planned-passed-failed
                endpoint_bounds.append({"model":model,"arm":arm,"round":round_,"planned_task_clusters":len(tasks),
                    "planned_programs":planned,"known_pass":passed,"known_fail":failed,"unknown":unknown,
                    "worst_case_rate":ratio(passed,planned),"best_case_rate":ratio(passed+unknown,planned),
                    "method":"Logical missing-outcome bounds; neither extreme is an observed score or confidence interval"})
        for arm,baseline in comparisons:
            lower=upper=unknown_pairs=0
            for current_model in selected_models:
                for task in tasks:
                    for repeat in repetitions:
                        a=endpoint_value(current_model,task,repeat,arm,rounds-1)
                        b=endpoint_value(current_model,task,repeat,baseline,rounds-1)
                        lower+=(int(a) if a is not None else 0)-(int(b) if b is not None else 1)
                        upper+=(int(a) if a is not None else 1)-(int(b) if b is not None else 0)
                        unknown_pairs+=a is None or b is None
            contrast_bounds.append({"model":model,"arm":arm,"baseline":baseline,"planned_task_clusters":len(tasks),
                "planned_paired_programs":planned,"pairs_with_unknown":unknown_pairs,
                "worst_case_delta_pp":lower/planned*100 if planned else None,
                "best_case_delta_pp":upper/planned*100 if planned else None,
                "method":"Logical missing-outcome bounds, not a significance test or confidence interval"})
    examples, missing_example_categories = select_examples(models, arms, repetitions, main_tasks, trajectory, score, strong_score)
    attempt_rows = records(run_dir / "attempts.jsonl") if (run_dir / "attempts.jsonl").is_file() else None
    attempted_ids = {row["record_id"] for row in attempt_rows} if attempt_rows is not None else None
    request_accounting = {"successful_responses": len(raw),
        "http_attempts": len(attempt_rows) if attempt_rows is not None else None,
        "transport_retries": len(attempt_rows) - len(attempted_ids) if attempt_rows is not None else None,
        "attempted_requests_without_saved_response": len(attempted_ids - raw.keys()) if attempted_ids is not None else None,
        "method": "Every persisted HTTP attempt is counted; retries are additional attempts for the same physical record_id, including resumed attempts."}
    manifest_totals = (plan.get("manifest") or {}).get("totals") or {}
    results = {"schema": "course-code-repair-extension-v1", "batch_id": batch, "synthetic": synthetic,
        "status": "complete" if not missing else "partial_complete_blocks_only", "models": models,
        "model_labels": {model: display_model(config, model) for model in models},
        "arms": [{"id": arm, "label": ZH[arm]} for arm in arms], "rounds": rounds,
        "planned_tasks": len(tasks), "task_clusters": len(main_tasks), "public_task_clusters": len(public_tasks),
        "strong_trajectory_task_clusters": len(strong_curve_tasks),
        "strong_trajectory_complete": len(strong_curve_tasks) == len(tasks),
        "repeats_per_task": len(repetitions), "saved_physical_responses": len(raw),
        "coverage": {"complete": integrity["complete"], "planned_tasks": len(tasks), "task_clusters": len(main_tasks),
            "public_task_clusters": len(public_tasks), "strong_trajectory_task_clusters": len(strong_curve_tasks),
            "expected_physical_responses": expected, "saved_physical_responses": len(raw),
            "missing_count": len(missing), "public_cases": manifest_totals.get("public_count"),
            "holdout_cases": manifest_totals.get("holdout_count")},
        "request_accounting": request_accounting,
        "generation_settings": {key: config.get(key) for key in ("temperature", "top_p", "max_tokens", "qwen3_enable_thinking")},
        "execution_settings": {key: config.get(key) for key in ("evaluation_timeout_s", "holdout_timeout_s", "memory_limit_mb", "minimum_case_timeout_s", "maximum_case_timeout_s", "timeout_factor")},
        "benchmark_version": config.get("benchmark_version"),
        "primary_metric": "Final code simultaneously passes all public diagnostics and the stronger held-out inputs.",
        "ci_method": "95% paired percentile bootstrap over task clusters, preserving model and independent-initial repetitions within each task.",
        "bootstrap": {"resamples": draws, "seed": seed},
        "summary": summaries, "public_curves": curves, "strong_curves": strong_curves, "strong_endpoints": endpoints,
        "contrasts": contrasts, "initial_error_support": initial_support,
        "planned_endpoint_bounds":endpoint_bounds,"planned_contrast_bounds":contrast_bounds,
        "examples": examples, "missing_example_categories": missing_example_categories,
        "scope_notes": ["Repeated initial programs do not increase the number of independent tasks.",
                        "Public diagnostic curves are not held-out correctness curves.",
                        "Current-version success, ever-public success and public-selected stopping are different metrics.",
                        "A selected intermediate version without a strong evaluation has unknown strong correctness.",
                        "Original public feedback is retained when strong re-execution changes a public outcome; recheck differences are reported separately.",
                        "A demonstrated failing split settles joint task failure; unexecuted held-out cases are still unmeasured, with no imputed case failures.",
                        "No effect or significance is promised; negative and model-dependent results remain in the report."]}
    write_json(output / "results.json", results)
    write_json(output / "examples.json", {"examples": examples, "unavailable_categories": missing_example_categories})
    write_csv(output / "summary.csv", summaries)
    write_csv(output / "public-curves.csv", curves)
    write_csv(output / "strong-curves.csv", strong_curves)
    write_csv(output / "strong-endpoints.csv", endpoints)
    write_csv(output / "contrasts.csv", contrasts)
    write_csv(output / "planned-endpoint-bounds.csv",endpoint_bounds)
    write_csv(output / "planned-contrast-bounds.csv",contrast_bounds)
    write_csv(output / "initial-error-support.csv", initial_support)
    write_csv(output / "features.csv", features)
    write_csv(output / "error-transitions.csv", [{"model": m, "arm": a, "round": r, "from": before, "to": after, "count": count}
        for (m, a, r, before, after), count in sorted(transitions.items())])
    # Publishable aggregate snapshot excludes raw record keys, timestamps and task IDs.
    if not synthetic:
        snapshot = {key: value for key, value in results.items() if key != "examples"}
        snapshot["examples"] = [{**{key: value for key, value in example.items() if key not in {"task_id", "record_ids"}},
            "anonymous_task": "T" + hashlib.sha256((batch + "|" + example["task_id"]).encode()).hexdigest()[:12]} for example in examples]
        write_json(output / "app-evidence.json", snapshot)
    figures = build_figures(output, results)
    write_json(output / "figure-manifest.json", {"batch_id": batch, "synthetic": synthetic, "figures": figures})
    (output / "findings.md").write_text(report_markdown(results, integrity), encoding="utf-8")
    print(json.dumps({"batch_id": batch, "status": results["status"], "physical_responses": len(raw),
        "paired_task_clusters": len(main_tasks), "public_task_clusters": len(public_tasks),
        "missing_items": len(missing), "figures": len(figures), "output": str(output)}, ensure_ascii=False))
    return results


def select_examples(models, arms, repeats, tasks, trajectory, score, strong_score):
    from experiments.code_repair_v2.src.protocol import feedback_message

    examples, unavailable = [], []
    categories = ["diagnostic_repair", "semantic_repair", "regression", "diagnostic_hidden_gap"]
    for category in categories:
        selected = None
        preferred = ["diagnostic", "multi_counterexample", "counterexample", "self_review", "pass_fail", "resample"]
        if category == "regression":
            preferred = ["self_review", "diagnostic", "multi_counterexample", "counterexample", "pass_fail", "resample"]
        elif category == "diagnostic_repair":
            preferred = ["diagnostic"]
        elif category == "semantic_repair":
            preferred = ["multi_counterexample", "counterexample"]
        for model in models:
            if selected:
                break
            for arm in [value for value in preferred if value in arms]:
                if selected:
                    break
                for task in tasks:
                    if selected:
                        break
                    for repeat in repeats:
                        seq = trajectory(model, task, repeat, arm)
                        if len(seq) < 2:
                            continue
                        scores = [score(row) for row in seq]
                        strong_scores = [strong_score(row) for row in seq]
                        strong_values = [full_pass(value) for value in strong_scores]
                        initial, final = strong_values[0], strong_values[-1]
                        after = None
                        if category in {"diagnostic_repair", "semantic_repair"}:
                            for index in range(1, len(seq)):
                                previous = scores[index - 1]
                                if (strong_values[index - 1] is not False or strong_values[index] is not True
                                        or not observed(previous) or public_pass(previous)):
                                    continue
                                kind = failure_kind(previous)
                                if (category == "diagnostic_repair" and kind not in {"syntax", "load", "runtime", "timeout"}
                                        or category == "semantic_repair" and kind != "output_mismatch"):
                                    continue
                                # Classify the displayed step, using only the original
                                # public result that actually produced its feedback.
                                try:
                                    expected_feedback = feedback_message(arm, {"public": previous["public"]})
                                except (KeyError, TypeError, ValueError):
                                    continue
                                if seq[index].get("feedback") == expected_feedback:
                                    after = index
                                    break
                        elif category == "regression":
                            if initial is True and final is False:
                                after = next((index for index in range(1, len(seq))
                                              if strong_values[index - 1] is True and strong_values[index] is False), None)
                        else:
                            if (observed(scores[-1]) and public_pass(scores[-1]) and final is False
                                    and hidden_failure(strong_scores[-1])):
                                after = len(seq) - 1
                        if after is None:
                            continue
                        before = after - 1
                        selected = {"category": category, "model": model, "task_id": task, "replicate": repeat,
                            "arm": arm, "before_round": before, "after_round": after,
                            "record_ids": [seq[before]["record_id"], seq[after]["record_id"]],
                            "before_code": seq[before]["code"], "after_code": seq[after]["code"],
                            "diff": "\n".join(difflib.unified_diff(seq[before]["code"].splitlines(), seq[after]["code"].splitlines(),
                                fromfile="before.py", tofile="after.py", lineterm="")),
                            "actual_feedback": seq[after].get("feedback"),
                            "before_public": scores[before]["public"], "after_public": scores[after]["public"],
                            "before_strong_pass": strong_values[before], "after_strong_pass": strong_values[after],
                            "initial_strong_pass": initial, "final_strong_pass": final,
                            "selection_note": "Fixed-order illustrative trace. Repair/regression requires an adjacent observed strong-test transition; repair feedback is the original public projection. Not an estimate of typical effect."}
                        break
        if selected:
            examples.append(selected)
        else:
            unavailable.append(category)
    return examples, unavailable


class Figure:
    def __init__(self, title, subtitle, height=660, synthetic=False):
        self.height = height
        self.synthetic = synthetic
        self.parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc"><title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(subtitle)}</desc><rect width="1200" height="{height}" fill="#fffdf9"/><style>text{{font-family:"PingFang SC","Microsoft YaHei",sans-serif;font-variant-numeric:tabular-nums}}</style>']
        self.text(42, 45, title, 28, weight=650)
        self.text(42, 77, subtitle, 15, color="#526574")
        self.line(42, 99, 1158, 99, "#d9e2e6")
        if synthetic:
            self.text(1150, 43, "合成自测数据", 18, color="#a43d38", anchor="end")

    def text(self, x, y, text, size=15, color="#142b3d", weight=None, anchor="start"):
        self.parts.append(f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" fill="{color}" text-anchor="{anchor}"' + (f' font-weight="{weight}"' if weight else '') + '>' + html.escape(str(text)) + '</text>')

    def line(self, x1, y1, x2, y2, color="#d9e2e6", width=1, dash=None):
        self.parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{width}"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')

    def dot(self, x, y, color, radius=5, outline=False):
        self.parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{"#fffdf9" if outline else color}" stroke="{color}" stroke-width="2"/>')

    def rect(self, x, y, width, height, color):
        self.parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(0,width):.2f}" height="{max(0,height):.2f}" rx="2" fill="{color}"/>')

    def marker(self, x, y, color, kind, size=5):
        if kind == 'circle':
            self.dot(x, y, color, size)
        elif kind == 'square':
            self.parts.append(f'<rect x="{x-size:.2f}" y="{y-size:.2f}" width="{2*size}" height="{2*size}" fill="#fffdf9" stroke="{color}" stroke-width="2"/>')
        elif kind in ('triangle', 'diamond'):
            points = [(x,y-size-1),(x+size+1,y+size),(x-size-1,y+size)] if kind == 'triangle' else [(x,y-size-1),(x+size+1,y),(x,y+size+1),(x-size-1,y)]
            vertices = ' '.join(f'{a:.2f},{b:.2f}' for a,b in points)
            self.parts.append(f'<polygon points="{vertices}" fill="#fffdf9" stroke="{color}" stroke-width="2"/>')
        elif kind == 'plus':
            self.line(x-size-1,y,x+size+1,y,color,2.4)
            self.line(x,y-size-1,x,y+size+1,color,2.4)
        else:
            self.line(x-size,y-size,x+size,y+size,color,2.4)
            self.line(x-size,y+size,x+size,y-size,color,2.4)

    def footer(self, batch, note):
        self.text(42, self.height - 49, note, 13, color="#526574")
        benchmark = '合成自测' if self.synthetic else 'HumanEval+ Full v0.1.10'
        self.text(42, self.height - 23, "来源：" + benchmark + "，代码反馈补充实验 / " + batch, 12, color="#526574")

    def save(self, path):
        # Presentation palette only; all positions, values and evidence stay intact.
        svg = "".join(self.parts) + '</svg>'
        palette = {"#fffdf9":"#042735", "#142b3d":"#f5fbff", "#526574":"#b5d1de",
                   "#d9e2e6":"#315361", "#a43d38":"#ff967f", "#a44b42":"#ff967f"}
        for original, optical in palette.items():
            svg = svg.replace(original, optical)
        Path(path).write_text(svg, encoding="utf-8")


def percent(value, digits=1):
    return "—" if value is None else f"{value*100:.{digits}f}%"


def build_figures(output, results):
    figures, summaries = [], results["summary"]
    rows = [row for row in summaries if row["programs"]]
    if not rows:
        return figures
    models, arms = results["models"], [item["id"] for item in results["arms"]]
    synthetic, batch = results["synthetic"], results["batch_id"]
    note = f'{results["task_clusters"]}道独立题 × {results["repeats_per_task"]}份初稿；95%区间按题目聚类。'
    height = 195 + len(models) * (100 + len(arms) * 53)
    figure = Figure("反馈带来的变化，用更强保留测试检验", note, height, synthetic)
    y = 135
    for model in models:
        figure.text(42, y, results["model_labels"][model], 22, weight=650)
        left, right = 260, 1030
        for tick in (0, 25, 50, 75, 100):
            x = left + (right-left)*tick/100
            figure.line(x, y+22, x, y+35+len(arms)*53, "#e3e9eb")
            figure.text(x, y+17, str(tick)+"%", 12, color="#526574", anchor="middle")
        y += 54
        for arm in arms:
            row = next(item for item in rows if item["model"] == model and item["arm"] == arm)
            figure.text(50, y+5, ZH[arm], 16)
            a, b = left + row["initial_rate"]*(right-left), left + row["final_rate"]*(right-left)
            figure.line(a, y, b, y, COLORS[arm], 3)
            figure.dot(a, y, "#526574", 5, True)
            if row["final_ci"]:
                lo, hi = [left + value*(right-left) for value in row["final_ci"]]
                figure.line(lo, y, hi, y, COLORS[arm], 1.7)
                figure.line(lo, y-6, lo, y+6, COLORS[arm], 1.7)
                figure.line(hi, y-6, hi, y+6, COLORS[arm], 1.7)
            figure.dot(b, y, COLORS[arm], 6)
            figure.text(1150, y+5, f'{row["final_success"]}/{row["programs"]}  {percent(row["final_rate"])}', 14, COLORS[arm], anchor="end")
            y += 53
        y += 46
    figure.footer(batch, "空心点＝共同初稿；实心点＝第4次后续生成。重采样各次独立；份数不增加独立题。")
    figure.save(output / "01-strong-endpoints.svg")
    figures.append({"id":"strong-endpoints", "file":"01-strong-endpoints.svg", "title":"强保留测试的初稿与终稿对照", "data_file":"summary.csv"})

    # A fixed display rule shared by both trajectory plots, independent of which
    # treatment wins: observed pooled range +5pp, ten-point ticks, >=30pp span.
    rates = [row['rate']*100 for key in ('public_curves','strong_curves') for row in results.get(key,[]) if row.get('rate') is not None]
    axis_low = max(0, math.floor((min(rates)-5)/10)*10) if rates else 0
    axis_high = min(100, math.ceil((max(rates)+5)/10)*10) if rates else 100
    if axis_high-axis_low < 30:
        axis_low=max(0,axis_low-math.ceil((30-axis_high+axis_low)/10)*10)
        axis_high=min(100,axis_low+30)
        axis_low=max(0,axis_high-30)
    markers = dict(zip(ARMS,('circle','square','triangle','diamond','plus','cross')))
    dashes = dict(zip(ARMS,('3 5','10 5','2 4','8 4 2 4',None,'12 3')))
    for curve_key, task_key, filename, figure_id, title, subtitle, footer, data_file in [
        ("public_curves", "public_task_clusters", "02-public-trajectories.svg", "public-trajectories",
         "公开诊断测试的五版轨迹", "这些曲线仅表示公开诊断测试通过率。",
         "只连接五个实际版本；公开诊断通过率与强保留测试质量分开呈现。", "public-curves.csv"),
        ("strong_curves", "strong_trajectory_task_clusters", "06-strong-trajectories.svg", "strong-trajectories",
         "强保留测试的五版轨迹", "全模型、全初稿、全反馈、全版本均有强测结果的同一批题。",
         "每个点均来自实际强测；只用公开反馈选版本，强测结果不进入模型反馈。", "strong-curves.csv")]:
        public_rows = results.get(curve_key, [])
        if not public_rows or not results.get(task_key):
            continue
        figure = Figure(title, f'{results[task_key]}道配对题；纵轴{axis_low}%–{axis_high}%（两图同范围）。' + subtitle, 180+len(models)*430, synthetic)
        top = 140
        for model in models:
            figure.text(42, top, results["model_labels"][model], 22, weight=650)
            for index, arm in enumerate(arms):
                x, y = 470+(index%3)*225, top-9+(index//3)*25
                figure.line(x,y,x+23,y,COLORS[arm],2.5,dashes[arm]);figure.marker(x+11.5,y,COLORS[arm],markers[arm],4);figure.text(x+31,y+5,ZH[arm],13)
            left, right, bottom = 100, 1125, top+324
            plot_top = top+57
            for tick in range(axis_low,axis_high+1,10):
                y = bottom - (bottom-plot_top)*(tick-axis_low)/(axis_high-axis_low)
                figure.line(left,y,right,y)
                figure.text(left-15,y+5,str(tick)+"%",13,color="#526574",anchor="end")
            for round_ in range(results["rounds"]):
                x = left+(right-left)*round_/(results["rounds"]-1)
                figure.text(x,bottom+26,str(round_),14,anchor="middle")
            shared_seed = None
            for arm in arms:
                points = sorted([item for item in public_rows if item["model"]==model and item["arm"]==arm], key=lambda item:item["round"])
                previous = None
                for item in points:
                    if item["rate"] is None:
                        continue
                    x = left+(right-left)*item["round"]/(results["rounds"]-1)
                    y = bottom-(bottom-plot_top)*(item["rate"]*100-axis_low)/(axis_high-axis_low)
                    if previous:
                        figure.line(*previous,x,y,COLORS[arm],2.8,dashes[arm])
                    if item['round'] == 0:shared_seed = (x,y)
                    else:figure.marker(x,y,COLORS[arm],markers[arm],4)
                    previous=(x,y)
            if shared_seed:figure.dot(*shared_seed,'#526574',6,True)
            figure.text((left+right)/2,bottom+55,"后续生成轮次（0＝共同初稿）",14,anchor="middle")
            top += 430
        figure.footer(batch,footer)
        figure.save(output / filename)
        figures.append({"id":figure_id,"file":filename,"title":title,"data_file":data_file})

    figure = Figure("修好多少，也要看改坏多少", "两种条件比例分开展示，分母分别为初稿错误与初稿正确。", 190+len(models)*(90+len(arms)*48), synthetic)
    y=140
    for model in models:
        figure.text(42,y,results["model_labels"][model],22,weight=650)
        figure.text(320,y,"初错修复率",16);figure.text(780,y,"初对回退率",16)
        y+=40
        for arm in arms:
            row=next(item for item in rows if item["model"]==model and item["arm"]==arm)
            figure.text(50,y+5,ZH[arm],15)
            for key,count,denominator,left,color in [("repair_rate","repaired","initial_failures",320,COLORS[arm]),("regression_rate","regressed","initial_correct",780,"#a44b42")]:
                if row[key] is not None:
                    figure.rect(left,y-12,row[key]*230,18,color)
                figure.text(left+245,y+3,f'{row[count]}/{row[denominator]}  {percent(row[key])}',13,color)
            y+=48
        y+=50
    figure.footer(batch,"初稿与终稿均以公开诊断＋强保留测试判定；分母为0时保持缺失。")
    figure.save(output / "03-repair-regression.svg")
    figures.append({"id":"repair-regression","file":"03-repair-regression.svg","title":"初错修复与初对回退","data_file":"summary.csv"})

    figure = Figure("质量收益与总调用成本一起比较", "横轴包括初稿及四次后续生成的输入与输出Token；模型分别展示。", 200+len(models)*370, synthetic)
    top=130
    maximum=max((item["mean_chain_total_tokens"] or 0 for item in rows),default=1)*1.12 or 1
    for model in models:
        figure.text(42,top,results["model_labels"][model],22,weight=650)
        left,right,bottom=110,1120,top+265
        for tick in (0,25,50,75,100):
            yy=bottom-(bottom-(top+35))*tick/100
            figure.line(left,yy,right,yy);figure.text(left-15,yy+5,str(tick)+"%",13,color="#526574",anchor="end")
        for index in range(5):
            x=left+(right-left)*index/4
            figure.text(x,bottom+24,f'{maximum*index/4:,.0f}',13,color="#526574",anchor="middle")
        points=[]
        for index,arm in enumerate(arms):
            row=next(item for item in rows if item["model"]==model and item["arm"]==arm)
            if row["mean_chain_total_tokens"] is None:
                continue
            x=left+(right-left)*row["mean_chain_total_tokens"]/maximum
            y=bottom-(bottom-(top+35))*row["final_rate"]
            points.append((index,arm,x,y))
            figure.marker(x,y,COLORS[arm],markers[arm],5)
        labels=[]
        for index,arm,x,y in points:
            options=[(12,-10),(12,21),(-22,-10),(-22,21),(25,-25),(-35,-25),(25,36),(-35,36),(42,5),(-52,5)]
            choice=None
            for dx,dy in options:
                a,b=x+dx,y+dy
                box=(a-3,b-15,a+12,b+4)
                if box[0]<left or box[2]>right or box[1]<top+35 or box[3]>bottom:
                    continue
                if any(box[0]<old[2]+4 and box[2]>old[0]-4 and box[1]<old[3]+4 and box[3]>old[1]-4 for old in labels):
                    continue
                if any(box[0]-5<px<box[2]+5 and box[1]-5<py<box[3]+5 for _,_,px,py in points):
                    continue
                choice=(a,b,box);break
            if choice is None:
                a,b=right-20,top+51+index*25
                choice=(a,b,(a-3,b-15,a+12,b+4))
            a,b,box=choice;labels.append(box)
            figure.line(x,y,a+4,b-6,COLORS[arm],1)
            figure.rect(box[0],box[1],box[2]-box[0],box[3]-box[1],'#fffdf9')
            figure.text(a,b,str(index+1),14,COLORS[arm],weight=650)
        figure.text((left+right)/2,bottom+52,"每份初稿对应的一条五版路径，平均总Token",14,anchor="middle")
        top+=370
    for index,arm in enumerate(arms):
        figure.text(45+(index%3)*380,figure.height-91+(index//3)*22,f'{index+1}  {ZH[arm]}',13,COLORS[arm])
    figure.footer(batch,"纵轴为终稿强测试通过率；输入历史与反馈长度均计入成本。编号对应下方策略。")
    figure.save(output / "04-cost-quality.svg")
    figures.append({"id":"cost-quality","file":"04-cost-quality.svg","title":"强测试质量与调用成本","data_file":"summary.csv"})
    support = results["initial_error_support"]
    kinds = ["syntax", "load", "runtime", "timeout", "output_mismatch"]
    kinds += sorted({item["error_kind"] for item in support} - set(kinds) - {"pass"})
    names = {"syntax":"语法错误", "load":"加载错误", "runtime":"运行异常",
             "timeout":"执行超时", "output_mismatch":"输出不匹配"}
    figure = Figure("修复之前，先看实际错误样本有多少", f'{results["public_task_clusters"]}道完整公开配对题；按真实初稿统计，不把修改轮次当新样本。',
                    190+len(models)*(80+len(kinds)*38), synthetic)
    maximum = max([item["initial_programs"] for item in support if item["error_kind"]!="pass"] or [1]) or 1
    top=140
    for model in models:
        subset={item["error_kind"]:item["initial_programs"] for item in support if item["model"]==model}
        total=sum(subset.values())
        figure.text(42,top,results["model_labels"][model],22,weight=650)
        figure.text(1150,top,f'诊断通过 {subset.get("pass",0)} / {total} 份初稿',14,color="#526574",anchor="end")
        y=top+41
        for kind in kinds:
            count=subset.get(kind,0)
            figure.text(50,y+5,names.get(kind,kind),15)
            figure.rect(270,y-12,count/maximum*640,18,"#c55e43")
            figure.text(940,y+3,f'{count} 份  /  {total} 份初稿',14,color="#526574")
            y+=38
        top+=80+len(kinds)*38
    figure.footer(batch,"类别来自初稿公开诊断；隐藏失败不冒充编译或运行错误。0表示该完整公开队列中未观测到。")
    figure.save(output / "05-initial-error-support.svg")
    figures.append({"id":"initial-error-support","file":"05-initial-error-support.svg","title":"初始可见错误的真实支持数","data_file":"initial-error-support.csv"})
    return figures


def report_markdown(results, integrity):
    state = "完整结果" if results["status"] == "complete" else "进行中：仅完整配对块"
    if results["synthetic"]:
        state = "合成自测，禁止作为实验结果"
    lines = [f'# 代码反馈补充实验：{state}', '',
        f'批次 `{results["batch_id"]}`。计划{results["planned_tasks"]}道独立题，当前公开配对{results["public_task_clusters"]}题、强测试配对{results["task_clusters"]}题；每题每模型{results["repeats_per_task"]}份独立初稿。',
        f'已保存{results["saved_physical_responses"]}条物理响应，计划{integrity["expected_physical_responses"]}条。重复初稿与多模型不增加独立题目数。', '',
        '主指标为第4次后续生成，同时通过公开诊断与强保留测试。独立重采样各次只接收原题，其他策略沿本组历史继续生成。中间轮只测公开诊断时，不能画成强测试曲线。95%区间按题目聚类，保留同题全部模型与重复。', '',
        '| 模型 | 反馈 | 初稿强测 | 终稿强测 | 终稿95%区间 | 初错修复 | 初对回退 | 总Token |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    g=results.get('generation_settings') or {}
    e=results.get('execution_settings') or {}
    if all(isinstance(g.get(key),(int,float)) for key in ('temperature','top_p','max_tokens')):
        thinking = '开启' if g.get('qwen3_enable_thinking') is True else '关闭' if g.get('qwen3_enable_thinking') is False else '未记录'
        lines[5:5] = [f'生成设置：temperature={g["temperature"]}，top_p={g["top_p"]}，单次输出上限{g["max_tokens"]} Token；Qwen3额外思考模式{thinking}。', '']
    if all(isinstance(e.get(key),(int,float)) for key in ('memory_limit_mb','holdout_timeout_s')):
        lines[5:5] = [f'执行设置：每程序内存上限{e["memory_limit_mb"]} MB，完整保留验证墙钟上限{e["holdout_timeout_s"]}秒；逐例限时与参考计时按固定协议执行。', '']
    for row in results["summary"]:
        ci=row["final_ci"]
        interval=f'[{percent(ci[0])}, {percent(ci[1])}]' if ci else '不足以估计'
        lines.append(f'| {row["model_label"]} | {row["arm_label"]} | {row["initial_success"]}/{row["programs"]} | {row["final_success"]}/{row["programs"]} | {interval} | {row["repaired"]}/{row["initial_failures"]} | {row["regressed"]}/{row["initial_correct"]} | {row["mean_chain_total_tokens"]:.0f} |' if row["mean_chain_total_tokens"] is not None else f'| {row["model_label"]} | {row["arm_label"]} | {row["initial_success"]}/{row["programs"]} | {row["final_success"]}/{row["programs"]} | {interval} | {row["repaired"]}/{row["initial_failures"]} | {row["regressed"]}/{row["initial_correct"]} | 未完整记录 |')
    lines += ['', '## 反馈相对单反例的配对比较', '',
        '| 模型 | 反馈 | 配对程序份数 | 赢 / 输 | 差值 pp | 95%区间 pp |', '|---|---|---:|---:|---:|---:|']
    for row in results["contrasts"]:
        if 'counterexample' not in {row["arm"], row["baseline"]} or row["model"]=='__pooled__':
            continue
        row=dict(row)
        if row["arm"]=='counterexample':
            row["arm"]=row["baseline"]
            row["arm_wins"],row["baseline_wins"]=row["baseline_wins"],row["arm_wins"]
            row["delta_pp"]=-row["delta_pp"] if row["delta_pp"] is not None else None
            row["ci_low_pp"],row["ci_high_pp"]=(
                (-row["ci_high_pp"],-row["ci_low_pp"]) if row["ci_low_pp"] is not None else (None,None))
        label=results["model_labels"][row["model"]]
        delta=f'{row["delta_pp"]:+.2f}' if row["delta_pp"] is not None else '—'
        ci=f'[{row["ci_low_pp"]:+.2f}, {row["ci_high_pp"]:+.2f}]' if row["ci_low_pp"] is not None else '—'
        lines.append(f'| {label} | {ZH[row["arm"]]} | {row["paired_programs"]} | {row["arm_wins"]}/{row["baseline_wins"]} | {delta} | {ci} |')
    lines += ['', '区间属于预先规定的探索性两两比较，未做多重比较校正；不要把接近零的小差值概括为普遍优势。', '',
        '## 评测与范围', '',
        '- 当前成功、历轮曾通过公开测试、首次公开通过即停止分别报告。隐藏结果不参与选择版本。',
        '- 中间停止版本没有强测时，停止策略强测试成功率保持未知，不能借终稿结果补值。',
        f'- 全五版强测使用独立严格配对队列：{results["strong_trajectory_task_clusters"]}/{results["planned_tasks"]}题；公开曲线与强测曲线分别标注。公开已知失败可以确定联合任务失败，未执行的保留输入仍为未测。',
        '- 基础设施中断或不完整评测保持缺失；不按模型成败剔题。完整块监测的分母和缺失记录见integrity.json。',
        '- planned-endpoint-bounds.csv与planned-contrast-bounds.csv保留原计划分母，给未知结果两种极端下的逻辑上下界；这些不是实测失败，也不是置信区间。',
        '- 反馈逐条从父版本public对象重建，隐藏输入和结果不进入构造器；父版本与各组完整历史均核验。',
        '- cases_checked统计实际逐例执行。加载失败时，原failed_cases是整套输入的逻辑失败标签，与blocked_cases、unchecked_cases重叠；特征表另列executed_failed_cases，主通过率按程序计数。',
        '- 例子按可观察的结果规则确定性选择，只用于解释机制，不代表平均效果。不存在的错误或回退类别不编造。',
        '- 置信区间按题目聚类；单题或零分母不能支撑区间推断。', '',
        '## 真实案例', '']
    for example in results["examples"]:
        labels = {True: '通过', False: '失败', None: '未测'}
        lines += [f'### {example["category"]}：{results["model_labels"][example["model"]]} / {example["task_id"]}', '',
            f'第{example["replicate"]+1}份初稿，{ZH[example["arm"]]}，版本{example["before_round"]+1}→{example["after_round"]+1}。该步强测：{labels[example["before_strong_pass"]]}→{labels[example["after_strong_pass"]]}；整链初稿／终稿：{labels[example["initial_strong_pass"]]}／{labels[example["final_strong_pass"]]}。', '',
            '实际传入的反馈：', '```text', example.get("actual_feedback") or '无执行反馈（独立重采样）', '```', '',
            '代码差异：', '```diff', example["diff"] or '(代码文本未改变)', '```', '']
    if results["missing_example_categories"]:
        lines += ['未观测到可用示例的类别：'+', '.join(results["missing_example_categories"])+ '。', '']
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", type=Path)
    source.add_argument("--figures-only", type=Path, metavar="RESULTS_JSON",
                        help="redraw native SVGs from aggregate results.json; no raw responses required")
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--partial", action="store_true", help="monitor only complete paired task blocks and label missing data")
    args = parser.parse_args()
    if args.figures_only:
        results = load_json(args.figures_only)
        if results.get("schema") != "course-code-repair-extension-v1":
            parser.error("--figures-only requires an extended-experiment results.json or app-evidence.json")
        output = Path(args.output or args.figures_only.parent).resolve()
        if results.get("synthetic") and not output.is_relative_to((ROOT / "work").resolve()):
            parser.error("Synthetic SVG redraws are restricted to temporary work/ paths")
        output.mkdir(parents=True, exist_ok=True)
        figures = build_figures(output, results)
        write_json(output / "figure-manifest.json", {"batch_id": results["batch_id"],
                   "synthetic": results["synthetic"], "figures": figures})
        print(json.dumps({"mode": "aggregate-only SVG redraw", "figures": len(figures), "output": str(output)}, ensure_ascii=False))
        return
    analyze(args.config, args.run_dir, args.output, args.partial)


if __name__ == "__main__":
    main()
