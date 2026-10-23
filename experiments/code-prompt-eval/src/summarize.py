#!/usr/bin/env python3
"""Create task-clustered model and prompt summaries from compact score rows."""
from __future__ import annotations

import argparse
import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEED = 91
BOOTSTRAP_DRAWS = 5000
K_VALUES = (1, 3, 5)


def pass_at_k(n: int, c: int, k: int) -> float:
    if n < k:
        return math.nan
    if n - c < k:
        return 1.0
    failure = 1.0
    for index in range(k):
        failure *= (n - c - index) / (n - index)
    return 1.0 - failure


def clustered_summary(frame: pd.DataFrame, value: str) -> dict[str, float | int]:
    per_task = frame.groupby("task_id", sort=False)[value].mean().dropna().to_numpy(float)
    if not len(per_task):
        return {"estimate": math.nan, "ci95_low": math.nan, "ci95_high": math.nan, "tasks": 0}
    rng = np.random.default_rng(SEED)
    draws = per_task[rng.integers(0, len(per_task), (BOOTSTRAP_DRAWS, len(per_task)))].mean(axis=1)
    low, high = np.quantile(draws, [0.025, 0.975])
    return {
        "estimate": float(per_task.mean()),
        "ci95_low": float(low),
        "ci95_high": float(high),
        "tasks": int(len(per_task)),
    }


def load_scores(path: Path) -> pd.DataFrame:
    scores = pd.read_csv(path)
    scores["passed_numeric"] = scores["analysis_passed"].map(
        {True: 1.0, False: 0.0, "True": 1.0, "False": 0.0, "true": 1.0, "false": 0.0}
    )
    for column in ["input_tokens", "output_tokens", "total_tokens", "latency_seconds", "evaluation_seconds"]:
        scores[column] = pd.to_numeric(scores[column], errors="coerce")
    return scores


def build_units(scores: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (model, task_id, prompt), group in scores.groupby(
        ["analysis_model", "task_id", "analysis_prompt_id"], sort=False
    ):
        evaluated = group.dropna(subset=["passed_numeric"])
        n = len(evaluated)
        c = int(evaluated["passed_numeric"].sum())
        row: dict[str, object] = {
            "model": model,
            "task_id": task_id,
            "prompt_id": prompt,
            "evaluated_samples": n,
            "correct_samples": c,
            "mean_total_tokens": evaluated["total_tokens"].mean(),
        }
        for k in K_VALUES:
            row[f"pass_at_{k}"] = pass_at_k(n, c, k)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, default=ROOT / "derived" / "scores.csv.gz")
    parser.add_argument("--out", type=Path, default=ROOT / "derived")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    scores = load_scores(args.scores)
    units = build_units(scores)
    units.to_csv(args.out / "task_prompt_units.csv.gz", index=False, compression="gzip")

    model_rows: list[dict[str, object]] = []
    for model, group in scores.groupby("analysis_model", sort=True):
        evaluated = group.dropna(subset=["passed_numeric"])
        row: dict[str, object] = {
            "model": model,
            "records": len(group),
            "evaluated_records": len(evaluated),
            "environment_excluded": int(group["passed_numeric"].isna().sum()),
            "successful_samples": int(evaluated["passed_numeric"].sum()),
            "single_sample_success_rate": float(evaluated["passed_numeric"].mean()),
            "total_input_tokens": int(group["input_tokens"].sum()),
            "total_output_tokens": int(group["output_tokens"].sum()),
            "total_tokens": int(group["total_tokens"].sum()),
            "mean_total_tokens": float(evaluated["total_tokens"].mean()),
            "mean_generation_latency_seconds": float(group["latency_seconds"].mean()),
            "mean_evaluation_seconds": float(group["evaluation_seconds"].mean()),
        }
        model_units = units[units.model == model]
        for k in K_VALUES:
            eligible = model_units.dropna(subset=[f"pass_at_{k}"])
            stats = clustered_summary(eligible, f"pass_at_{k}")
            row[f"pass_at_{k}"] = stats["estimate"]
            row[f"pass_at_{k}_ci95_low"] = stats["ci95_low"]
            row[f"pass_at_{k}_ci95_high"] = stats["ci95_high"]
            row[f"eligible_units_at_{k}"] = len(eligible)
            row[f"task_clusters_at_{k}"] = stats["tasks"]
        model_rows.append(row)
    model_summary = pd.DataFrame(model_rows)
    model_summary.to_csv(args.out / "model_summary.csv", index=False)

    prompt_rows: list[dict[str, object]] = []
    for (model, prompt), group in units.groupby(["model", "prompt_id"], sort=True):
        row: dict[str, object] = {
            "model": model,
            "prompt_id": prompt,
            "mean_total_tokens": float(group["mean_total_tokens"].mean()),
        }
        for k in K_VALUES:
            eligible = group.dropna(subset=[f"pass_at_{k}"])
            stats = clustered_summary(eligible, f"pass_at_{k}")
            row[f"pass_at_{k}"] = stats["estimate"]
            row[f"pass_at_{k}_ci95_low"] = stats["ci95_low"]
            row[f"pass_at_{k}_ci95_high"] = stats["ci95_high"]
            row[f"eligible_units_at_{k}"] = len(eligible)
        row["pass5_minus_pass1"] = row["pass_at_5"] - row["pass_at_1"]
        prompt_rows.append(row)
    prompt_summary = pd.DataFrame(prompt_rows)
    prompt_summary.to_csv(args.out / "prompt_summary.csv", index=False)

    pair_rows: list[dict[str, object]] = []
    models = sorted(units.model.unique())
    for left, right in combinations(models, 2):
        for k in K_VALUES:
            metric = f"pass_at_{k}"
            joined = units[units.model == left][["task_id", "prompt_id", metric]].merge(
                units[units.model == right][["task_id", "prompt_id", metric]],
                on=["task_id", "prompt_id"], suffixes=("_left", "_right"), how="inner"
            ).dropna()
            joined["difference"] = joined[f"{metric}_left"] - joined[f"{metric}_right"]
            stats = clustered_summary(joined, "difference")
            pair_rows.append({
                "left_model": left,
                "right_model": right,
                "k": k,
                "paired_units": len(joined),
                "task_clusters": stats["tasks"],
                "left_minus_right": stats["estimate"],
                "ci95_low": stats["ci95_low"],
                "ci95_high": stats["ci95_high"],
                "bootstrap_draws": BOOTSTRAP_DRAWS,
                "seed": SEED,
            })
    pd.DataFrame(pair_rows).to_csv(args.out / "model_pairs.csv", index=False)

    prompt_pair_rows: list[dict[str, object]] = []
    for model in models:
        model_units = units[units.model == model]
        baseline = model_units[model_units.prompt_id == "NoCoT"]
        for prompt in sorted(model_units.prompt_id.unique()):
            if prompt == "NoCoT":
                continue
            candidate = model_units[model_units.prompt_id == prompt]
            for k in K_VALUES:
                metric = f"pass_at_{k}"
                joined = candidate[["task_id", metric]].merge(
                    baseline[["task_id", metric]], on="task_id", suffixes=("_prompt", "_nocot")
                ).dropna()
                joined["difference"] = joined[f"{metric}_prompt"] - joined[f"{metric}_nocot"]
                stats = clustered_summary(joined, "difference")
                prompt_pair_rows.append({
                    "model": model,
                    "prompt_id": prompt,
                    "k": k,
                    "paired_tasks": len(joined),
                    "prompt_minus_nocot": stats["estimate"],
                    "ci95_low": stats["ci95_low"],
                    "ci95_high": stats["ci95_high"],
                    "bootstrap_draws": BOOTSTRAP_DRAWS,
                    "seed": SEED,
                })
    pd.DataFrame(prompt_pair_rows).to_csv(args.out / "prompt_vs_nocot.csv", index=False)

    error_rows: list[dict[str, object]] = []
    for model, group in scores.groupby("analysis_model", sort=True):
        evaluated = group.dropna(subset=["passed_numeric"])
        failures = evaluated[evaluated.passed_numeric == 0]
        for category, count in failures["analysis_error_category"].value_counts().items():
            error_rows.append({
                "model": model,
                "error_category": category,
                "error_count": int(count),
                "evaluated_records": len(evaluated),
                "failed_records": len(failures),
                "rate_of_evaluated": count / len(evaluated),
                "share_of_failures": count / len(failures) if len(failures) else 0,
            })
    pd.DataFrame(error_rows).to_csv(args.out / "error_summary.csv", index=False)

    summary = {
        "records": int(len(scores)),
        "models": models,
        "tasks": int(scores.task_id.nunique()),
        "prompts": int(scores.analysis_prompt_id.nunique()),
        "samples_per_condition": int(scores.analysis_turn_id.nunique()),
        "bootstrap": {"cluster": "task_id", "draws": BOOTSTRAP_DRAWS, "seed": SEED},
        "model_summary": json.loads(model_summary.to_json(orient="records")),
    }
    (args.out / "research_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Wrote model, prompt, paired, error, and compact unit summaries.")


if __name__ == "__main__":
    main()
