#!/usr/bin/env python3
"""Read-only integrity checks for the complete code-generation delivery."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["deepseek-flash", "qwen2.5-7b-instruct-cloud", "qwen3-8b-cloud"]


def digest(path: Path, compressed: bool) -> tuple[str, int]:
    hasher, size = hashlib.sha256(), 0
    opener = path.open if compressed else lambda mode: gzip.open(path, mode)
    with opener("rb") as handle:
        for block in iter(lambda: handle.read(2**20), b""):
            hasher.update(block)
            size += len(block)
    return hasher.hexdigest(), size


def jsonl_keys(path: Path) -> tuple[set[tuple[str, str, int]], int]:
    keys: set[tuple[str, str, int]] = set()
    rows = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            key = (
                str(record["task_id"]),
                str(record.get("combination_id") or record.get("prompt_id")),
                int(record.get("turn_id", record.get("repeat_id", 1))),
            )
            assert key not in keys, (path, key)
            keys.add(key)
            rows += 1
    return keys, rows


def main() -> None:
    checks = json.loads((ROOT / "data" / "CHECKSUMS.json").read_text())
    for relative, expected in checks.items():
        path = ROOT / relative
        compressed_hash, compressed_size = digest(path, True)
        raw_hash, raw_size = digest(path, False)
        assert compressed_hash == expected["sha256"], relative
        assert compressed_size == expected["bytes"], relative
        assert raw_hash == expected["uncompressed_sha256"], relative
        assert raw_size == expected["uncompressed_bytes"], relative

    prompt_count = len(json.loads((ROOT / "data" / "prompts.json").read_text()))
    with gzip.open(ROOT / "data" / "benchmark_194_tasks.csv.gz", "rt", encoding="utf-8", newline="") as handle:
        benchmark = list(csv.DictReader(handle))
    assert prompt_count == 31
    assert len(benchmark) == 6208
    assert len({row["task_id"] for row in benchmark}) == 194

    total = 0
    for model in MODELS:
        raw_path = ROOT / "data" / f"raw_{model}.jsonl.gz"
        evaluation_path = ROOT / "derived" / f"evaluation_{model}.jsonl.gz"
        raw_keys, raw_rows = jsonl_keys(raw_path)
        eval_keys, eval_rows = jsonl_keys(evaluation_path)
        assert raw_rows == eval_rows == 30070
        assert raw_keys == eval_keys
        with gzip.open(raw_path, "rt", encoding="utf-8") as handle:
            assert all(json.loads(line).get("status") == "success" for line in handle)
        with gzip.open(evaluation_path, "rt", encoding="utf-8") as handle:
            for line in handle:
                record = json.loads(line)
                assert record.get("sandboxed") is True
                assert record.get("normalization") == "target-function-ast-v2"
        total += raw_rows
    assert total == 90210

    with gzip.open(ROOT / "derived" / "scores.csv.gz", "rt", encoding="utf-8", newline="") as handle:
        scores = list(csv.DictReader(handle))
    assert len(scores) == 90210
    assert len({row["task_id"] for row in scores}) == 194
    assert len({row["analysis_prompt_id"] for row in scores}) == 31
    assert {int(row["analysis_turn_id"]) for row in scores} == {1, 2, 3, 4, 5}
    print("PASS: checksums, 90,210 unique raw/evaluation pairs, sandbox provenance, 194 tasks, 31 prompts, five samples, and 90,210 score rows.")


if __name__ == "__main__":
    main()
