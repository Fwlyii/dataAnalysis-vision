#!/usr/bin/env python3
"""Export a fixed, auditable set of complete model-output examples."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = [
    "deepseek-flash",
    "qwen2.5-7b-instruct-cloud",
    "qwen3-8b-cloud",
]
PROMPTS = ["NoCoT", "DefaultCoT"]


def load_jsonl(path: Path) -> dict[tuple[str, str, int], dict]:
    rows: dict[tuple[str, str, int], dict] = {}
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            key = (str(row["task_id"]), str(row["prompt_id"]), int(row["turn_id"]))
            rows[key] = row
    return rows


def main() -> None:
    tasks = json.loads((ROOT / "data" / "task_examples.json").read_text(encoding="utf-8"))
    raw = {model: load_jsonl(ROOT / "data" / f"raw_{model}.jsonl.gz") for model in MODELS}
    evaluations = {
        model: load_jsonl(ROOT / "derived" / f"evaluation_{model}.jsonl.gz")
        for model in MODELS
    }
    lines = [
        "# 18条完整输出示例",
        "",
        "以下固定展示3道题、2种Prompt（`NoCoT`、`DefaultCoT`）、3个模型的第1次独立采样，共18条。",
        "原始回答保持原样；通过状态来自最终的 `target-function-ast-v2` 沙箱评分。示例用于理解输出形态，不能代替总体统计。",
        "",
    ]
    index = 0
    for task in tasks:
        lines.extend([
            f"## 题目：`{task['function_name']}`",
            "",
            f"- task_id：`{task['task_id']}`",
            f"- 任务说明：{task['zero_shot_prompt']}",
            f"- 函数签名：`{task['prompt'].split('The function signature is: ', 1)[-1].split('. The function', 1)[0]}`",
            "",
        ])
        for prompt_id in PROMPTS:
            lines.extend([f"### Prompt：`{prompt_id}`", ""])
            for model in MODELS:
                index += 1
                key = (task["task_id"], prompt_id, 1)
                response = raw[model][key].get("complete_response", "")
                result = evaluations[model][key]
                status = "通过" if result.get("passed") else f"未通过（{result.get('error_category', 'unknown')}）"
                lines.extend([
                    f"#### {index}. `{model}` — {status}",
                    "",
                    "~~~text",
                    response.rstrip(),
                    "~~~",
                    "",
                ])
    destination = ROOT / "docs" / "05-output-examples.md"
    destination.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {destination} with {index} complete examples.")


if __name__ == "__main__":
    main()
