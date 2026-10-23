#!/usr/bin/env python3
"""Analyze independent turns, cumulative success, and code-error categories.

Generation JSONL files may be supplied alone; API, extraction, and syntax errors
can then be classified immediately. Functional success and runtime error causes
require evaluation records containing `passed`/`test_result` and optionally
`error_message`/`error_category`.
"""

from __future__ import annotations

import argparse
import ast
import csv
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "derived"
DEFAULT_INPUTS = [
    ROOT / "data" / "raw_deepseek-flash.jsonl.gz",
    ROOT / "data" / "raw_qwen2.5-7b-instruct-cloud.jsonl.gz",
    ROOT / "data" / "raw_qwen3-8b-cloud.jsonl.gz",
]
DEFAULT_EVALUATIONS = [
    ROOT / "derived" / "evaluation_deepseek-flash.jsonl.gz",
    ROOT / "derived" / "evaluation_qwen2.5-7b-instruct-cloud.jsonl.gz",
    ROOT / "derived" / "evaluation_qwen3-8b-cloud.jsonl.gz",
]


def read_records(paths: Iterable[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            raise SystemExit(f"Input not found: {path}")
        if path.name.lower().endswith((".csv", ".csv.gz")):
            handle = (
                gzip.open(path, "rt", encoding="utf-8-sig", newline="")
                if path.suffix.lower() == ".gz"
                else path.open("r", encoding="utf-8-sig", newline="")
            )
            with handle:
                records.extend(dict(row) for row in csv.DictReader(handle))
        else:
            handle = (
                gzip.open(path, "rt", encoding="utf-8")
                if path.suffix.lower() == ".gz"
                else path.open("r", encoding="utf-8")
            )
            with handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as exc:
                        raise SystemExit(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
    return records


def turn_id(record: dict[str, Any]) -> int:
    return int(record.get("turn_id", record.get("repeat_id", 1)))


def model_id(record: dict[str, Any]) -> str:
    return str(record.get("profile") or record.get("model") or "unknown-model")


def prompt_id(record: dict[str, Any]) -> str:
    return str(record.get("compression_prompt_id") or record.get("prompt_id") or record.get("combination_id") or "unknown-prompt")


def identity(record: dict[str, Any]) -> tuple[str, str, str, int]:
    return model_id(record), str(record.get("task_id")), str(record.get("combination_id") or prompt_id(record)), turn_id(record)


def parse_passed(record: dict[str, Any]) -> bool | None:
    for key in ("passed", "test_passed", "test_result"):
        if key not in record or record[key] in (None, ""):
            continue
        value = record[key]
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"passed", "pass", "true", "1", "success", "successful"}:
            return True
        if normalized in {"failed", "fail", "false", "0", "error"}:
            return False
    return None


def static_python_error(code: Any) -> str | None:
    if code in (None, "", "null"):
        return "extraction_error"
    try:
        ast.parse(str(code))
    except (SyntaxError, ValueError, TypeError):
        return "syntax_error"
    return None


ERROR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("timeout", re.compile(r"timeout|timed out", re.I)),
    ("syntax_error", re.compile(r"syntaxerror|indentationerror|taberror", re.I)),
    ("dependency_error", re.compile(r"modulenotfounderror|importerror|no module named", re.I)),
    ("name_error", re.compile(r"nameerror|unboundlocalerror|is not defined", re.I)),
    ("attribute_error", re.compile(r"attributeerror|has no attribute", re.I)),
    ("type_error", re.compile(r"typeerror", re.I)),
    ("value_error", re.compile(r"valueerror", re.I)),
    ("key_error", re.compile(r"keyerror", re.I)),
    ("index_error", re.compile(r"indexerror", re.I)),
    ("assertion_failure", re.compile(r"assertionerror|assert failed|test failed|result not true|ist is not true", re.I)),
    ("resource_error", re.compile(r"memoryerror|out of memory|recursionerror", re.I)),
    ("file_error", re.compile(r"filenotfounderror|permissionerror|isadirectoryerror|notadirectoryerror", re.I)),
]


def classify(record: dict[str, Any]) -> tuple[bool | None, str]:
    if record.get("status") == "error":
        return False, "api_error"
    passed = parse_passed(record)
    if passed is True:
        return True, "success"
    explicit = record.get("error_category")
    if explicit:
        explicit = str(explicit)
        if explicit == "environment_error":
            return None, explicit
        if explicit not in {"runtime_error", "evaluation_error"}:
            return False, explicit
    if "generated_code" in record:
        static_error = static_python_error(record.get("generated_code"))
        if static_error:
            return False, static_error
    error_text = "\n".join(
        str(record.get(key) or "")
        for key in ("error_type", "error_message", "stderr", "test_output")
    )
    if passed is False:
        for category, pattern in ERROR_PATTERNS:
            if pattern.search(error_text):
                return False, category
        return False, explicit or "runtime_error"
    return None, "not_evaluated"


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def pass_at_k(total_samples: int, correct_samples: int, k: int) -> float | None:
    """Unbiased Pass@k estimator: 1 - C(n-c, k) / C(n, k)."""
    if k < 1 or total_samples < k or correct_samples < 0 or correct_samples > total_samples:
        return None
    if total_samples - correct_samples < k:
        return 1.0
    failure_probability = 1.0
    for index in range(k):
        failure_probability *= (total_samples - correct_samples - index) / (total_samples - index)
    return 1.0 - failure_probability


def exact_mcnemar_p(fail_to_success: int, success_to_fail: int) -> float:
    """Two-sided exact McNemar p-value using a stable binomial tail."""
    discordant = fail_to_success + success_to_fail
    if discordant == 0:
        return 1.0
    tail = min(fail_to_success, success_to_fail)
    log_probabilities = [
        math.lgamma(discordant + 1)
        - math.lgamma(k + 1)
        - math.lgamma(discordant - k + 1)
        - discordant * math.log(2)
        for k in range(tail + 1)
    ]
    maximum = max(log_probabilities)
    one_sided = math.exp(maximum) * sum(
        math.exp(value - maximum) for value in log_probabilities
    )
    return min(1.0, 2 * one_sided)


def add_holm_adjustment(rows: list[dict[str, Any]], p_key: str, output_key: str) -> None:
    """Add Holm family-wise-error adjusted p-values in place."""
    ordered = sorted(enumerate(rows), key=lambda item: float(item[1][p_key]))
    running_max = 0.0
    count = len(ordered)
    adjusted: dict[int, float] = {}
    for rank, (original_index, row) in enumerate(ordered):
        candidate = min(1.0, (count - rank) * float(row[p_key]))
        running_max = max(running_max, candidate)
        adjusted[original_index] = running_max
    for index, row in enumerate(rows):
        row[output_key] = round(adjusted[index], 8)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, default=DEFAULT_INPUTS, help="Generation JSONL files")
    parser.add_argument("--evaluations", nargs="*", type=Path, default=DEFAULT_EVALUATIONS, help="Optional evaluation JSONL/CSV files")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-models", type=int, default=3)
    parser.add_argument("--expected-tasks", type=int, default=194)
    parser.add_argument("--expected-prompts", type=int, default=31)
    parser.add_argument("--expected-turns", type=int, default=5)
    parser.add_argument(
        "--pass-k",
        nargs="+",
        type=int,
        help="Pass@k values to report; defaults to every k from 1 through expected-turns",
    )
    parser.add_argument(
        "--marginal-gain-threshold",
        type=float,
        default=0.01,
        help="Candidate saturation threshold; 0.01 means one percentage point",
    )
    parser.add_argument(
        "--minimum-coverage",
        type=float,
        default=0.95,
        help="Minimum cumulative evaluation coverage for saturation decisions",
    )
    args = parser.parse_args()
    if not 0 <= args.marginal_gain_threshold <= 1:
        parser.error("--marginal-gain-threshold must be between 0 and 1")
    if not 0 < args.minimum_coverage <= 1:
        parser.error("--minimum-coverage must be greater than 0 and at most 1")
    pass_k_values = sorted(set(args.pass_k or range(1, args.expected_turns + 1)))
    if any(k < 1 or k > args.expected_turns for k in pass_k_values):
        parser.error("Every --pass-k value must be between 1 and --expected-turns")

    generated = read_records(args.inputs)
    latest: dict[tuple[str, str, str, int], dict[str, Any]] = {identity(row): row for row in generated}
    if args.evaluations:
        for evaluation in read_records(args.evaluations):
            key = identity(evaluation)
            if key in latest:
                latest[key].update(evaluation)
            else:
                latest[key] = evaluation

    normalized: list[dict[str, Any]] = []
    for row in latest.values():
        passed, category = classify(row)
        normalized.append(
            {
                **row,
                "analysis_model": model_id(row),
                "analysis_prompt_id": prompt_id(row),
                "analysis_turn_id": turn_id(row),
                "analysis_passed": passed,
                "analysis_error_category": category,
            }
        )
    normalized.sort(key=lambda row: (row["analysis_model"], str(row.get("task_id")), row["analysis_prompt_id"], row["analysis_turn_id"]))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    score_fields = [
        "analysis_model", "task_id", "analysis_prompt_id", "analysis_turn_id",
        "analysis_passed", "analysis_error_category", "project", "level",
        "finish_reason", "input_tokens", "output_tokens", "total_tokens",
        "latency_seconds", "evaluation_seconds", "sandboxed", "normalization",
    ]
    with gzip.open(args.output_dir / "scores.csv.gz", "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=score_fields)
        writer.writeheader()
        for row in normalized:
            writer.writerow({field: row.get(field, "") for field in score_fields})

    units: dict[tuple[str, str, str], dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in normalized:
        units[(row["analysis_model"], str(row.get("task_id")), row["analysis_prompt_id"])][row["analysis_turn_id"]] = row

    turn_rows: list[dict[str, Any]] = []
    groups = {(model, prompt) for model, _, prompt in units}
    groups |= {(model, "ALL") for model, _, _ in units}

    pass_k_rows: list[dict[str, Any]] = []
    for model, prompt in sorted(groups):
        matching = {
            key: turns
            for key, turns in units.items()
            if key[0] == model and (prompt == "ALL" or key[2] == prompt)
        }
        for k in pass_k_values:
            estimates: list[float] = []
            projected_tokens: list[float] = []
            sample_counts: list[int] = []
            correct_counts: list[int] = []
            for turns in matching.values():
                evaluated_rows = [
                    row for row in turns.values() if row["analysis_passed"] is not None
                ]
                n = len(evaluated_rows)
                c = sum(row["analysis_passed"] is True for row in evaluated_rows)
                estimate = pass_at_k(n, c, k)
                if estimate is None:
                    continue
                estimates.append(estimate)
                sample_counts.append(n)
                correct_counts.append(c)
                token_values = [
                    float(row.get("total_tokens"))
                    for row in evaluated_rows
                    if row.get("total_tokens") not in (None, "")
                ]
                if token_values:
                    projected_tokens.append(k * sum(token_values) / len(token_values))
            mean_estimate = sum(estimates) / len(estimates) if estimates else None
            if len(estimates) > 1:
                variance = sum((value - mean_estimate) ** 2 for value in estimates) / (len(estimates) - 1)
                margin = 1.96 * math.sqrt(variance / len(estimates))
                ci_low = max(0.0, mean_estimate - margin)
                ci_high = min(1.0, mean_estimate + margin)
            elif estimates:
                ci_low = ci_high = mean_estimate
            else:
                ci_low = ci_high = None
            pass_k_rows.append(
                {
                    "model": model,
                    "prompt_id": prompt,
                    "k": k,
                    "eligible_task_prompt_units": len(estimates),
                    "insufficient_or_unevaluated_units": len(matching) - len(estimates),
                    "mean_samples_available": round(sum(sample_counts) / len(sample_counts), 6) if sample_counts else "",
                    "total_correct_samples": sum(correct_counts),
                    "pass_at_k": round(mean_estimate, 6) if mean_estimate is not None else "",
                    "pass_at_k_ci95_low": round(ci_low, 6) if ci_low is not None else "",
                    "pass_at_k_ci95_high": round(ci_high, 6) if ci_high is not None else "",
                    "mean_projected_total_tokens_at_k": round(sum(projected_tokens) / len(projected_tokens), 3) if projected_tokens else "",
                    "estimator": "1-C(n-c,k)/C(n,k)",
                }
            )
    write_csv(
        args.output_dir / "pass_at_k.csv",
        pass_k_rows,
        list(pass_k_rows[0]) if pass_k_rows else ["model", "prompt_id", "k", "pass_at_k"],
    )

    for model, prompt in sorted(groups):
        matching = {
            key: turns
            for key, turns in units.items()
            if key[0] == model and (prompt == "ALL" or key[2] == prompt)
        }
        for current_turn in range(1, args.expected_turns + 1):
            available = [turns[current_turn] for turns in matching.values() if current_turn in turns]
            environment_excluded = sum(
                row["analysis_error_category"] == "environment_error" for row in available
            )
            direct = [row for row in available if row["analysis_passed"] is not None]
            direct_successes = sum(row["analysis_passed"] is True for row in direct)
            cumulative_environment_excluded = sum(
                any(
                    t in turns
                    and turns[t]["analysis_error_category"] == "environment_error"
                    for t in range(1, current_turn + 1)
                )
                for turns in matching.values()
            )
            cumulative_eligible = [
                turns
                for turns in matching.values()
                if all(t in turns and turns[t]["analysis_passed"] is not None for t in range(1, current_turn + 1))
            ]
            cumulative_successes = sum(
                any(turns[t]["analysis_passed"] is True for t in range(1, current_turn + 1))
                for turns in cumulative_eligible
            )
            low, high = wilson(direct_successes, len(direct))
            cum_low, cum_high = wilson(cumulative_successes, len(cumulative_eligible))
            cumulative_rate = (
                cumulative_successes / len(cumulative_eligible) if cumulative_eligible else None
            )
            previously_unsolved = []
            newly_solved = None
            retry_recovery_rate = None
            marginal_gain = None
            marginal_low = marginal_high = 0.0
            recovery_low = recovery_high = 0.0
            if current_turn > 1:
                previously_unsolved = [
                    turns
                    for turns in cumulative_eligible
                    if not any(turns[t]["analysis_passed"] is True for t in range(1, current_turn))
                ]
                newly_solved = sum(
                    turns[current_turn]["analysis_passed"] is True
                    for turns in previously_unsolved
                )
                marginal_gain = (
                    newly_solved / len(cumulative_eligible) if cumulative_eligible else None
                )
                retry_recovery_rate = (
                    newly_solved / len(previously_unsolved) if previously_unsolved else None
                )
                marginal_low, marginal_high = wilson(newly_solved, len(cumulative_eligible))
                recovery_low, recovery_high = wilson(newly_solved, len(previously_unsolved))
            turn_rows.append(
                {
                    "model": model,
                    "prompt_id": prompt,
                    "turn_id": current_turn,
                    "records_at_turn": len(available),
                    "environment_excluded": environment_excluded,
                    "evaluated_at_turn": len(direct),
                    "not_evaluated_at_turn": len(available) - environment_excluded - len(direct),
                    "evaluation_coverage": round(
                        len(direct) / (len(available) - environment_excluded), 6
                    ) if len(available) > environment_excluded else "",
                    "successes_at_turn": direct_successes,
                    "success_rate_at_turn": round(direct_successes / len(direct), 6) if direct else "",
                    "success_ci95_low": round(low, 6) if direct else "",
                    "success_ci95_high": round(high, 6) if direct else "",
                    "cumulative_evaluated": len(cumulative_eligible),
                    "cumulative_environment_excluded": cumulative_environment_excluded,
                    "cumulative_coverage": round(
                        len(cumulative_eligible) / (len(matching) - cumulative_environment_excluded), 6
                    ) if len(matching) > cumulative_environment_excluded else "",
                    "cumulative_successes": cumulative_successes,
                    "cumulative_success_rate": round(cumulative_rate, 6) if cumulative_rate is not None else "",
                    "cumulative_marginal_gain": round(marginal_gain, 6) if marginal_gain is not None else "",
                    "marginal_ci95_low": round(marginal_low, 6) if marginal_gain is not None else "",
                    "marginal_ci95_high": round(marginal_high, 6) if marginal_gain is not None else "",
                    "previously_unsolved": len(previously_unsolved) if current_turn > 1 else "",
                    "newly_solved_this_turn": newly_solved if newly_solved is not None else "",
                    "retry_recovery_rate": round(retry_recovery_rate, 6) if retry_recovery_rate is not None else "",
                    "recovery_ci95_low": round(recovery_low, 6) if retry_recovery_rate is not None else "",
                    "recovery_ci95_high": round(recovery_high, 6) if retry_recovery_rate is not None else "",
                    "newly_solved_per_1000_additional_calls": round(1000 * marginal_gain, 3) if marginal_gain is not None else "",
                    "remaining_unsolved": len(cumulative_eligible) - cumulative_successes,
                    "cumulative_ci95_low": round(cum_low, 6) if cumulative_eligible else "",
                    "cumulative_ci95_high": round(cum_high, 6) if cumulative_eligible else "",
                }
            )
    write_csv(
        args.output_dir / "turn_success.csv",
        turn_rows,
        list(turn_rows[0]) if turn_rows else ["model", "prompt_id", "turn_id"],
    )

    stability_rows: list[dict[str, Any]] = []
    for model, prompt in sorted(groups):
        matching = {
            key: turns
            for key, turns in units.items()
            if key[0] == model and (prompt == "ALL" or key[2] == prompt)
        }
        for current_turn in range(2, args.expected_turns + 1):
            previous_turn = current_turn - 1
            available_pairs = [
                turns for turns in matching.values()
                if previous_turn in turns and current_turn in turns
            ]
            paired = [
                turns for turns in available_pairs
                if turns[previous_turn]["analysis_passed"] is not None
                and turns[current_turn]["analysis_passed"] is not None
            ]
            fail_to_success = sum(
                turns[previous_turn]["analysis_passed"] is False
                and turns[current_turn]["analysis_passed"] is True
                for turns in paired
            )
            success_to_fail = sum(
                turns[previous_turn]["analysis_passed"] is True
                and turns[current_turn]["analysis_passed"] is False
                for turns in paired
            )
            delta = (
                sum(
                    int(turns[current_turn]["analysis_passed"])
                    - int(turns[previous_turn]["analysis_passed"])
                    for turns in paired
                ) / len(paired)
                if paired else 0.0
            )
            stability_rows.append(
                {
                    "model": model,
                    "prompt_id": prompt,
                    "from_turn": previous_turn,
                    "to_turn": current_turn,
                    "available_pairs": len(available_pairs),
                    "paired_evaluated": len(paired),
                    "paired_coverage": round(len(paired) / len(available_pairs), 6) if available_pairs else "",
                    "fail_to_success": fail_to_success,
                    "success_to_fail": success_to_fail,
                    "single_turn_rate_change": round(delta, 6) if paired else "",
                    "mcnemar_exact_p": round(exact_mcnemar_p(fail_to_success, success_to_fail), 8),
                }
            )
    if stability_rows:
        prompt_level_rows = [row for row in stability_rows if row["prompt_id"] != "ALL"]
        add_holm_adjustment(prompt_level_rows, "mcnemar_exact_p", "mcnemar_holm_p")
        for row in stability_rows:
            if row["prompt_id"] == "ALL":
                row["mcnemar_holm_p"] = row["mcnemar_exact_p"]
        for row in stability_rows:
            row["significant_turn_drift_0_05"] = row["mcnemar_holm_p"] < 0.05
    write_csv(
        args.output_dir / "turn_stability.csv",
        stability_rows,
        list(stability_rows[0]) if stability_rows else ["model", "prompt_id", "from_turn", "to_turn"],
    )

    reliability_rows: list[dict[str, Any]] = []
    for model, prompt in sorted(groups):
        matching = {
            key: turns
            for key, turns in units.items()
            if key[0] == model and (prompt == "ALL" or key[2] == prompt)
        }
        complete = [
            turns for turns in matching.values()
            if all(
                t in turns and turns[t]["analysis_passed"] is not None
                for t in range(1, args.expected_turns + 1)
            )
        ]
        environment_units = sum(
            any(
                t in turns and turns[t]["analysis_error_category"] == "environment_error"
                for t in range(1, args.expected_turns + 1)
            )
            for turns in matching.values()
        )
        always_success = sum(
            all(turns[t]["analysis_passed"] is True for t in range(1, args.expected_turns + 1))
            for turns in complete
        )
        always_fail = sum(
            all(turns[t]["analysis_passed"] is False for t in range(1, args.expected_turns + 1))
            for turns in complete
        )
        flaky = len(complete) - always_success - always_fail
        reliability_rows.append(
            {
                "model": model,
                "prompt_id": prompt,
                "complete_units": len(complete),
                "environment_units_excluded": environment_units,
                "complete_coverage": round(
                    len(complete) / (len(matching) - environment_units), 6
                ) if len(matching) > environment_units else "",
                "always_success_count": always_success,
                "always_success_rate": round(always_success / len(complete), 6) if complete else "",
                "flaky_count": flaky,
                "flaky_rate": round(flaky / len(complete), 6) if complete else "",
                "always_fail_count": always_fail,
                "always_fail_rate": round(always_fail / len(complete), 6) if complete else "",
            }
        )
    write_csv(
        args.output_dir / "prompt_reliability.csv",
        reliability_rows,
        list(reliability_rows[0]) if reliability_rows else ["model", "prompt_id", "complete_units"],
    )

    saturation_rows: list[dict[str, Any]] = []
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in turn_rows:
        by_group[(row["model"], row["prompt_id"])].append(row)
    for (model, prompt), rows in sorted(by_group.items()):
        retries = [
            row for row in rows
            if row["turn_id"] > 1
            and row["cumulative_coverage"] != ""
            and float(row["cumulative_coverage"]) >= args.minimum_coverage
        ]
        point_candidates = [
            row for row in retries
            if row["cumulative_marginal_gain"] != ""
            and float(row["cumulative_marginal_gain"]) < args.marginal_gain_threshold
        ]
        strong_candidates = [
            row for row in retries
            if row["marginal_ci95_high"] != ""
            and float(row["marginal_ci95_high"]) < args.marginal_gain_threshold
        ]
        saturation_rows.append(
            {
                "model": model,
                "prompt_id": prompt,
                "marginal_gain_threshold": args.marginal_gain_threshold,
                "minimum_coverage": args.minimum_coverage,
                "first_point_estimate_below_threshold_turn": point_candidates[0]["turn_id"] if point_candidates else "",
                "first_ci95_below_threshold_turn": strong_candidates[0]["turn_id"] if strong_candidates else "",
                "interpretation": (
                    "strong_saturation_evidence" if strong_candidates
                    else "candidate_saturation" if point_candidates
                    else "no_saturation_observed" if retries
                    else "insufficient_coverage"
                ),
            }
        )
    write_csv(
        args.output_dir / "saturation_summary.csv",
        saturation_rows,
        list(saturation_rows[0]) if saturation_rows else ["model", "prompt_id", "interpretation"],
    )

    error_counts: Counter[tuple[str, str, int, str]] = Counter()
    record_counts: Counter[tuple[str, str, int]] = Counter()
    environment_counts: Counter[tuple[str, str, int]] = Counter()
    evaluated_counts: Counter[tuple[str, str, int]] = Counter()
    failed_counts: Counter[tuple[str, str, int]] = Counter()
    for row in normalized:
        passed = row["analysis_passed"]
        key = (row["analysis_model"], row["analysis_prompt_id"], row["analysis_turn_id"])
        record_counts[key] += 1
        if row["analysis_error_category"] == "environment_error":
            environment_counts[key] += 1
            error_counts[(*key, "environment_error")] += 1
        if passed is not None:
            evaluated_counts[key] += 1
        if passed is False:
            failed_counts[key] += 1
            error_counts[(*key, row["analysis_error_category"])] += 1
    error_rows: list[dict[str, Any]] = []
    for (model, prompt, turn, category), count in sorted(error_counts.items()):
        evaluated = evaluated_counts[(model, prompt, turn)]
        failed = failed_counts[(model, prompt, turn)]
        records = record_counts[(model, prompt, turn)]
        environment = environment_counts[(model, prompt, turn)]
        eligible_records = records - environment
        is_environment = category == "environment_error"
        error_rows.append(
            {
                "model": model,
                "prompt_id": prompt,
                "turn_id": turn,
                "error_category": category,
                "error_count": count,
                "record_count": records,
                "environment_excluded": environment,
                "evaluated_count": evaluated,
                "failed_count": failed,
                "error_rate_of_records": "" if is_environment else round(count / eligible_records, 6) if eligible_records else "",
                "share_of_failures": "" if is_environment else round(count / failed, 6) if failed else "",
                "excluded_from_model_metrics": is_environment,
            }
        )
    write_csv(
        args.output_dir / "prompt_error_rates.csv",
        error_rows,
        list(error_rows[0]) if error_rows else ["model", "prompt_id", "turn_id", "error_category"],
    )

    first_success_rows: list[dict[str, Any]] = []
    transitions: Counter[tuple[str, str, int, str, str]] = Counter()
    for (model, task, prompt), turns in sorted(units.items()):
        successful_turns = sorted(t for t, row in turns.items() if row["analysis_passed"] is True)
        first_success_rows.append(
            {
                "model": model,
                "task_id": task,
                "prompt_id": prompt,
                "first_success_turn": successful_turns[0] if successful_turns else "",
                "ever_succeeded": bool(successful_turns),
            }
        )
        for t in range(2, args.expected_turns + 1):
            if t - 1 in turns and t in turns:
                previous = turns[t - 1]["analysis_error_category"]
                current = turns[t]["analysis_error_category"]
                if previous not in {"not_evaluated", "environment_error"} and current not in {"not_evaluated", "environment_error"}:
                    transitions[(model, prompt, t, previous, current)] += 1
    write_csv(
        args.output_dir / "first_success_turn.csv",
        first_success_rows,
        ["model", "task_id", "prompt_id", "first_success_turn", "ever_succeeded"],
    )
    transition_totals: Counter[tuple[str, str, int, str]] = Counter()
    for (model, prompt, turn, previous, _), count in transitions.items():
        transition_totals[(model, prompt, turn, previous)] += count
    transition_rows = []
    for (model, prompt, turn, previous, current), count in sorted(transitions.items()):
        total = transition_totals[(model, prompt, turn, previous)]
        transition_rows.append(
            {
                "model": model,
                "prompt_id": prompt,
                "to_turn": turn,
                "from_category": previous,
                "to_category": current,
                "from_category_count": total,
                "transition_count": count,
                "transition_rate": round(count / total, 6) if total else "",
                "recovered_to_success": current == "success",
            }
        )
    write_csv(
        args.output_dir / "error_transitions.csv",
        transition_rows,
        list(transition_rows[0]) if transition_rows else ["model", "prompt_id", "to_turn", "from_category", "to_category", "transition_count"],
    )

    models = {row["analysis_model"] for row in normalized}
    tasks = {str(row.get("task_id")) for row in normalized}
    prompts = {row["analysis_prompt_id"] for row in normalized}
    turns = {row["analysis_turn_id"] for row in normalized}
    evaluated = sum(row["analysis_passed"] is not None for row in normalized)
    environment_excluded = sum(row["analysis_error_category"] == "environment_error" for row in normalized)
    not_evaluated = sum(row["analysis_error_category"] == "not_evaluated" for row in normalized)
    evaluable_records = len(normalized) - environment_excluded
    expected_records = args.expected_models * args.expected_tasks * args.expected_prompts * args.expected_turns
    summary = {
        "records": len(normalized),
        "expected_records": expected_records,
        "record_coverage": len(normalized) / expected_records if expected_records else None,
        "evaluated_records": evaluated,
        "environment_records_excluded": environment_excluded,
        "not_evaluated_records": not_evaluated,
        "functional_evaluation_coverage": evaluated / evaluable_records if evaluable_records else 0,
        "models_found": sorted(models),
        "task_count": len(tasks),
        "prompt_count": len(prompts),
        "turns_found": sorted(turns),
        "sampling_mode": "independent",
        "pass_k_values": pass_k_values,
        "marginal_gain_threshold": args.marginal_gain_threshold,
        "minimum_coverage": args.minimum_coverage,
        "notes": "pass_at_k.csv uses the unbiased estimator 1-C(n-c,k)/C(n,k). turn_success.csv additionally reports order-specific cumulative success across samples 1..t.",
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not_evaluated:
        print("Warning: valid generated code without test results is marked not_evaluated.")
    print(f"Analysis written to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
