#!/usr/bin/env python3
"""Render the interim Lost-in-the-Middle result tables as publication-ready PNGs.

The input is the frozen JSON produced by the analysis script.  The figures are
descriptive only: the collection was still running when this snapshot was
made, so the script labels every output as interim.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


MODEL_LABELS = {
    "Qwen/Qwen2.5-7B-Instruct": "Qwen2.5-7B",
    "Qwen/Qwen3-8B": "Qwen3-8B",
}
COLORS = {"Qwen/Qwen2.5-7B-Instruct": "#3465A4", "Qwen/Qwen3-8B": "#E07A3F"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def style(ax, title: str, ylabel: str = "") -> None:
    ax.set_title(title, loc="left", fontweight="bold")
    if ylabel:
        ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#D9DEE7", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)


def position_figure(data: dict, out: Path) -> None:
    rows = [r for r in data["position_rates"] if r["scope"] == "english19"]
    positions = ["front", "middle", "back"]
    fig, ax = plt.subplots(figsize=(8.2, 4.8), dpi=180)
    x = np.arange(len(positions))
    width = 0.34
    for i, model in enumerate(MODEL_LABELS):
        vals = []
        for pos in positions:
            subset = [r for r in rows if r["model"] == model and r["position"] == pos]
            n = sum(r["n"] for r in subset)
            vals.append(100 * sum(r["n"] * r["paper_firstline"] for r in subset) / n)
        bars = ax.bar(x + (i - 0.5) * width, vals, width, label=MODEL_LABELS[model], color=COLORS[model])
        ax.bar_label(bars, fmt="%.1f", padding=2, fontsize=8)
    ax.set_xticks(x, ["Front", "Middle", "Back"])
    ax.set_ylim(0, 85)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    style(ax, "Interim answer accuracy by evidence position", "Official first-line accuracy (%)")
    fig.text(0.01, 0.01, "English19 strategies; 10 and 20 documents pooled. Snapshot is partial.", fontsize=8, color="#555B66")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def strategy_figure(data: dict, out: Path) -> None:
    rows = [r for r in data["strategies"] if r["scope"] == "main_comparison"]
    names = list(dict.fromkeys(r["strategy"] for r in rows))
    # Sort by the mean score across the two models, with the best at the top.
    means = {name: np.mean([r["paper_firstline"] for r in rows if r["strategy"] == name]) for name in names}
    names = sorted(names, key=means.get)
    fig, ax = plt.subplots(figsize=(9.2, max(5.2, len(names) * 0.28)), dpi=180)
    y = np.arange(len(names))
    for model in MODEL_LABELS:
        vals = [100 * next((r["paper_firstline"] for r in rows if r["model"] == model and r["strategy"] == name), np.nan) for name in names]
        ax.plot(vals, y, "o-", label=MODEL_LABELS[model], color=COLORS[model], markersize=4, linewidth=1.4)
    ax.set_yticks(y, names, fontsize=8)
    ax.set_xlim(0, 85)
    ax.set_xlabel("Official first-line accuracy (%)")
    ax.invert_yaxis()
    ax.legend(frameon=False, ncol=2, loc="lower right")
    style(ax, "Interim accuracy across prompt strategies")
    fig.text(0.01, 0.01, "Only strategies classified as main_comparison; incomplete combinations remain visible by their available records.", fontsize=8, color="#555B66")
    fig.tight_layout(rect=(0.22, 0.04, 1, 1))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def token_figure(data: dict, out: Path) -> None:
    rows = [r for r in data["strategies"] if r["scope"] == "main_comparison"]
    fig, ax = plt.subplots(figsize=(7.6, 5.2), dpi=180)
    for model in MODEL_LABELS:
        subset = [r for r in rows if r["model"] == model]
        x = [r["mean_output_tokens"] for r in subset]
        y = [100 * r["paper_firstline"] for r in subset]
        ax.scatter(x, y, s=38, alpha=0.8, label=MODEL_LABELS[model], color=COLORS[model], edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Mean output tokens")
    ax.set_ylabel("Official first-line accuracy (%)")
    ax.legend(frameon=False)
    style(ax, "Output length and answer accuracy", "Official first-line accuracy (%)")
    fig.text(0.01, 0.01, "Descriptive scatter; it does not establish that longer output causes higher accuracy.", fontsize=8, color="#555B66")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("../derived/interim_analysis_20261021T231742.json"))
    parser.add_argument("--out", type=Path, default=Path("../figures"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data = load(args.input)
    position_figure(data, args.out / "position_accuracy_interim.png")
    strategy_figure(data, args.out / "strategy_accuracy_interim.png")
    token_figure(data, args.out / "output_tokens_accuracy_interim.png")
    print(f"wrote figures to {args.out}")


if __name__ == "__main__":
    main()
