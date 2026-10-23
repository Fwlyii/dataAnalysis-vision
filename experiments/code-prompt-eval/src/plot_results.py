#!/usr/bin/env python3
"""Generate final static figures and auditable source tables."""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["deepseek-flash", "qwen2.5-7b-instruct-cloud", "qwen3-8b-cloud"]
LABELS = {
    "deepseek-flash": "DeepSeek Flash",
    "qwen2.5-7b-instruct-cloud": "Qwen2.5-7B",
    "qwen3-8b-cloud": "Qwen3-8B",
}
COLORS = {
    "deepseek-flash": "#0072B2",
    "qwen2.5-7b-instruct-cloud": "#E69F00",
    "qwen3-8b-cloud": "#009E73",
}
MARKERS = {"deepseek-flash": "o", "qwen2.5-7b-instruct-cloud": "s", "qwen3-8b-cloud": "^"}


def save(fig, out: Path, name: str, caption: str, frame: pd.DataFrame, layout: bool = True) -> None:
    fig.text(0.02, 0.012, caption, fontsize=8, va="bottom")
    if layout:
        fig.tight_layout(rect=(0, 0.07, 1, 0.98))
    fig.canvas.draw()
    for extension in ("png", "svg", "pdf"):
        fig.savefig(out / f"{name}.{extension}", dpi=300)
    frame.to_csv(out / "source_data" / f"{name}.csv", index=False, lineterminator="\n")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--derived", type=Path, default=ROOT / "derived")
    parser.add_argument("--out", type=Path, default=ROOT / "figures")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "source_data").mkdir(exist_ok=True)

    models = pd.read_csv(args.derived / "model_summary.csv")
    prompts = pd.read_csv(args.derived / "prompt_summary.csv")
    turns = pd.read_csv(args.derived / "turn_success.csv")
    errors = pd.read_csv(args.derived / "error_summary.csv")
    turns = turns[(turns.prompt_id == "ALL") & turns.model.isin(MODELS)].copy()
    prompts = prompts[prompts.model.isin(MODELS)].copy()

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "svg.fonttype": "none",
        "pdf.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False,
    })

    # 1. Model Pass@k with task-clustered intervals.
    frame_rows = []
    for _, row in models.iterrows():
        for k in (1, 3, 5):
            frame_rows.append({
                "model": row.model, "k": k, "pass_at_k": row[f"pass_at_{k}"],
                "ci95_low": row[f"pass_at_{k}_ci95_low"],
                "ci95_high": row[f"pass_at_{k}_ci95_high"],
                "eligible_units": row[f"eligible_units_at_{k}"],
            })
    frame = pd.DataFrame(frame_rows)
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for model in MODELS:
        group = frame[frame.model == model].sort_values("k")
        ax.errorbar(
            group.k, group.pass_at_k * 100,
            yerr=[(group.pass_at_k - group.ci95_low) * 100, (group.ci95_high - group.pass_at_k) * 100],
            color=COLORS[model], marker=MARKERS[model], linewidth=1.8, capsize=3,
            label=LABELS[model],
        )
    ax.set(xticks=[1, 3, 5], xlabel="k independent samples", ylabel="Pass@k (%)")
    ax.set_ylim(bottom=0)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False)
    save(fig, args.out, "01_model_pass_at_k",
         "194 tasks x 31 prompts. Mean unbiased Pass@k across task-prompt units; 95% bootstrap CI clustered by task (5,000 draws, seed 91).", frame)

    # 2. Order-specific cumulative success and marginal gain.
    frame = turns[["model", "turn_id", "cumulative_success_rate", "cumulative_ci95_low",
                   "cumulative_ci95_high", "cumulative_marginal_gain", "newly_solved_per_1000_additional_calls"]].copy()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for model in MODELS:
        group = frame[frame.model == model].sort_values("turn_id")
        axes[0].plot(group.turn_id, group.cumulative_success_rate * 100, color=COLORS[model],
                     marker=MARKERS[model], label=LABELS[model])
        axes[1].plot(group.turn_id.iloc[1:], group.cumulative_marginal_gain.iloc[1:] * 100,
                     color=COLORS[model], marker=MARKERS[model], label=LABELS[model])
    axes[0].set(xlabel="Samples observed", ylabel="Cumulative success (%)", xticks=range(1, 6))
    axes[1].set(xlabel="Additional sample", ylabel="Marginal gain (percentage points)", xticks=range(2, 6))
    for axis in axes:
        axis.set_ylim(bottom=0)
        axis.grid(alpha=0.2)
    axes[0].legend(frameon=False)
    save(fig, args.out, "02_sampling_saturation",
         "Order-specific cumulative success across the five independent samples. Later samples still add successes, but the marginal gain is expected to shrink.", frame)

    # 3. Prompt-level Pass@1.
    order = list(prompts.groupby("prompt_id").pass_at_1.mean().sort_values(ascending=False).index)
    frame = prompts[["model", "prompt_id", "pass_at_1", "pass_at_1_ci95_low", "pass_at_1_ci95_high",
                     "eligible_units_at_1"]].copy()
    fig, axes = plt.subplots(1, 3, figsize=(13, 10), sharex=True, sharey=True)
    for axis, model in zip(axes, MODELS):
        group = frame[frame.model == model].set_index("prompt_id").loc[order]
        y = np.arange(len(order))
        axis.errorbar(group.pass_at_1 * 100, y,
                      xerr=[(group.pass_at_1 - group.pass_at_1_ci95_low) * 100,
                            (group.pass_at_1_ci95_high - group.pass_at_1) * 100],
                      fmt=MARKERS[model], color=COLORS[model], capsize=2, markersize=4)
        axis.set(title=LABELS[model], xlabel="Pass@1 (%)", yticks=y, yticklabels=order)
        axis.grid(axis="x", alpha=0.2)
    axes[0].invert_yaxis()
    save(fig, args.out, "03_prompt_pass_at_1",
         "Each prompt-model point summarizes 194 task units with five samples per unit. Intervals are clustered by task; rankings are descriptive.", frame)

    # 4. Prompt-level gain from five samples.
    frame = prompts[["model", "prompt_id", "pass5_minus_pass1"]].copy()
    matrix = frame.pivot(index="prompt_id", columns="model", values="pass5_minus_pass1").loc[order, MODELS] * 100
    fig, ax = plt.subplots(figsize=(8, 10))
    mesh = ax.pcolormesh(matrix.to_numpy(), cmap="cividis", vmin=0,
                         vmax=max(1, float(np.nanmax(matrix.to_numpy()))), edgecolors="white", linewidth=0.5)
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            ax.text(column + 0.5, row + 0.5, f"{matrix.iloc[row, column]:.1f}",
                    ha="center", va="center", fontsize=7)
    ax.set(xticks=np.arange(3) + 0.5, xticklabels=[LABELS[m] for m in MODELS],
           yticks=np.arange(len(order)) + 0.5, yticklabels=order)
    ax.invert_yaxis()
    fig.colorbar(mesh, ax=ax, label="Pass@5 - Pass@1 (percentage points)")
    save(fig, args.out, "04_prompt_sampling_gain",
         "Additional success available from five independent samples. Values are descriptive percentage-point differences, not multi-turn repair effects.", frame)

    # 5. Error categories as a share of all evaluable records.
    categories = list(errors.groupby("error_category").error_count.sum().sort_values(ascending=False).head(8).index)
    frame = errors[errors.error_category.isin(categories)].copy()
    matrix = frame.pivot(index="error_category", columns="model", values="rate_of_evaluated").fillna(0).loc[categories, MODELS] * 100
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(len(categories)); width = 0.24
    for index, model in enumerate(MODELS):
        ax.bar(x + (index - 1) * width, matrix[model], width=width, color=COLORS[model], label=LABELS[model])
    ax.set(xticks=x, xticklabels=categories, ylabel="Share of evaluable answers (%)")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.2)
    ax.legend(frameon=False)
    save(fig, args.out, "05_error_categories",
         "Eight most frequent failure categories. Environment-excluded records are omitted from model-performance denominators.", frame)

    # 6. Token use and Pass@1 across prompts.
    frame = prompts[["model", "prompt_id", "mean_total_tokens", "pass_at_1"]].copy()
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for model in MODELS:
        group = frame[frame.model == model]
        ax.scatter(group.mean_total_tokens, group.pass_at_1 * 100, color=COLORS[model],
                   marker=MARKERS[model], label=LABELS[model], alpha=0.85)
        for _, row in group[group.prompt_id.isin(["NoCoT", "DefaultCoT"])].iterrows():
            ax.annotate(row.prompt_id, (row.mean_total_tokens, row.pass_at_1 * 100),
                        xytext=(5, 5), textcoords="offset points", fontsize=7)
    ax.set(xlabel="Mean total tokens per answer", ylabel="Pass@1 (%)")
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    save(fig, args.out, "06_tokens_and_pass_at_1",
         "Ninety-three prompt-model means. Association is descriptive; prompt wording and model both vary, so the plot does not establish a causal token effect.", frame)
    print("Exported six figures in PNG, SVG, and PDF with matching source CSV files.")


if __name__ == "__main__":
    main()
