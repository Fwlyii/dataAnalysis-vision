"""Load the pinned full HumanEval+ benchmark without executing reference/code.

The upstream HumanEval loader uses JSON values directly; no MBPP-style input
deserialization is needed. Public inputs keep their original order and content.
Full plus inputs are preserved in the downloaded source; the returned tasks
contain only distinct plus inputs that do not occur in the public base set.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "project.json").is_file())
DATA_DIR = ROOT.parent / "repair_v2/datasets"
FULL_NAME = "HumanEvalPlus-v0.1.10.jsonl.gz"
MINI_NAME = "HumanEvalPlus-Mini-v0.1.10.jsonl.gz"
FULL_SHA256 = "272720b90ac375502c8ed23cd791c2a93dfb22a911641a494da74a426c09f101"
MINI_SHA256 = "91486741f1627101021fbe50523df08eebb5b0bf5e804b633dcd5ca3c14dbd2f"
FULL_URL = "https://github.com/evalplus/humanevalplus_release/releases/download/v0.1.10/HumanEvalPlus.jsonl.gz"
MINI_URL = "https://github.com/evalplus/humanevalplus_release/releases/download/v0.1.10/HumanEvalPlus-Mini.jsonl.gz"
LOADER_URL = "https://github.com/evalplus/evalplus/blob/master/evalplus/data/humaneval.py"
SPEC_FIELDS = ("prompt", "canonical_solution", "entry_point", "atol", "contract", "base_input")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _object_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _resolve(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def _load(path: Path, expected_sha256: str) -> tuple[dict[str, dict], str]:
    if not path.is_file():
        raise FileNotFoundError(f"Pinned benchmark not found: {path}. Official source: {FULL_URL}")
    blob = path.read_bytes()
    if blob.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise ValueError(f"Benchmark is a Git LFS pointer, not a downloaded payload: {path}")
    digest = hashlib.sha256(blob).hexdigest()
    if digest != expected_sha256:
        raise ValueError(f"Benchmark SHA-256 mismatch for {path}: {digest}")
    payload = gzip.decompress(blob).decode("utf-8") if path.suffix == ".gz" else blob.decode("utf-8")
    tasks: dict[str, dict] = {}
    for line_number, line in enumerate(payload.splitlines(), 1):
        if not line.strip():
            continue
        task = json.loads(line)
        tid = task.get("task_id")
        if not isinstance(tid, str) or tid in tasks:
            raise ValueError(f"Invalid/duplicate task at {path}:{line_number}: {tid}")
        for field in ("task_id", "prompt", "canonical_solution", "entry_point", "contract"):
            if not isinstance(task.get(field), str):
                raise ValueError(f"Missing/string-invalid {field}: {tid}")
        for field in ("base_input", "plus_input"):
            if not isinstance(task.get(field), list) or not task[field]:
                raise ValueError(f"Missing/nonempty-list-invalid {field}: {tid}")
            if not all(isinstance(arguments, list) for arguments in task[field]):
                raise ValueError(f"Task inputs must be JSON argument arrays: {tid}/{field}")
        if not isinstance(task.get("atol"), (int, float)):
            raise ValueError(f"Invalid atol: {tid}")
        tasks[tid] = task
    return tasks, digest


def load_benchmark(config: dict) -> tuple[list[dict], dict]:
    """Return all 164 tasks and a reproducible public/holdout manifest.

    Supported config keys: dataset_path, dataset_sha256, benchmark_version,
    expected_tasks, legacy_dataset_path and legacy_dataset_sha256. The source
    files are read only. The returned ``plus_input`` is the sealed holdout,
    with public overlaps and duplicate plus inputs removed deterministically.
    """
    path = _resolve(config.get("dataset_path", DATA_DIR / FULL_NAME))
    expected_sha = config.get("dataset_sha256", FULL_SHA256)
    version = config.get("benchmark_version", "HumanEvalPlus-v0.1.10")
    if "v0.1.10" not in version:
        raise ValueError("This extension protocol is pinned to HumanEval+ v0.1.10")
    full, digest = _load(path, expected_sha)
    if len(full) != config.get("expected_tasks", 164) or set(full) != {f"HumanEval/{i}" for i in range(164)}:
        raise ValueError("Expected the complete, unchanged 164-task HumanEval+ set")

    mini_path = _resolve(config.get("legacy_dataset_path", path.parent / MINI_NAME))
    mini, mini_digest = _load(mini_path, config.get("legacy_dataset_sha256", MINI_SHA256))
    if set(mini) != set(full):
        raise ValueError("Full and legacy Mini task identities differ")
    mismatches = [
        {"task_id": tid, "field": field}
        for tid in full for field in SPEC_FIELDS
        if full[tid][field] != mini[tid][field]
    ]
    if mismatches:
        raise ValueError("Full/Mini reference protocol mismatch: " + json.dumps(mismatches[:10]))

    tasks, split_rows = [], []
    for tid in sorted(full, key=lambda key: int(key.split("/")[-1])):
        original = full[tid]
        public_fingerprints = {_canonical(arguments) for arguments in original["base_input"]}
        raw_plus_fingerprints = [_canonical(arguments) for arguments in original["plus_input"]]
        seen = set(public_fingerprints)
        holdout, base_overlap, novel_duplicates = [], 0, 0
        for arguments, fingerprint in zip(original["plus_input"], raw_plus_fingerprints):
            if fingerprint in public_fingerprints:
                base_overlap += 1
            elif fingerprint in seen:
                novel_duplicates += 1
            else:
                holdout.append(arguments)
                seen.add(fingerprint)
        if not holdout:
            raise ValueError(f"No disjoint holdout inputs remain: {tid}")
        mini_plus_fingerprints = {_canonical(arguments) for arguments in mini[tid]["plus_input"]}
        if not mini_plus_fingerprints.issubset(set(raw_plus_fingerprints)):
            raise ValueError(f"Legacy Mini plus tests are not a subset of pinned full plus tests: {tid}")
        task = dict(original)
        task["plus_input"] = holdout
        tasks.append(task)
        split_rows.append({
            "task_id": tid,
            "reference_spec_sha256": _object_sha256({field: original[field] for field in SPEC_FIELDS}),
            "public_count": len(original["base_input"]),
            "public_unique_count": len(public_fingerprints),
            "public_inputs_sha256": _object_sha256(original["base_input"]),
            "raw_plus_count": len(original["plus_input"]),
            "raw_plus_duplicate_count": len(raw_plus_fingerprints) - len(set(raw_plus_fingerprints)),
            "excluded_public_overlap_occurrences": base_overlap,
            "excluded_novel_duplicate_occurrences": novel_duplicates,
            "holdout_count": len(holdout),
            "holdout_inputs_sha256": _object_sha256(holdout),
            "legacy_mini_plus_count": len(mini[tid]["plus_input"]),
            "legacy_mini_novel_holdout_count": len(mini_plus_fingerprints - public_fingerprints),
            "additional_full_holdout_count": len({_canonical(v) for v in holdout} - mini_plus_fingerprints),
        })

    total_fields = (
        "public_count", "public_unique_count", "raw_plus_count", "raw_plus_duplicate_count",
        "excluded_public_overlap_occurrences", "excluded_novel_duplicate_occurrences",
        "holdout_count", "legacy_mini_plus_count", "legacy_mini_novel_holdout_count",
        "additional_full_holdout_count",
    )
    manifest = {
        "schema": "code-repair-benchmark-manifest-v2",
        "benchmark_version": version,
        "dataset_path": str(path),
        "dataset_sha256": digest,
        "dataset_size_bytes": path.stat().st_size,
        "official_url": FULL_URL,
        "legacy_dataset_path": str(mini_path),
        "legacy_dataset_sha256": mini_digest,
        "legacy_official_url": MINI_URL,
        "upstream_loader": LOADER_URL,
        "input_deserialization": "JSON values unchanged, matching official HumanEval+ loader",
        "legacy_reference_spec": "All task prompts, references, interfaces, tolerances, contracts and base inputs exactly match Mini v0.1.10",
        "tasks": len(tasks),
        "task_selection": "All 164 upstream tasks; no filtering by candidate outcomes",
        "split_policy": "Public=original base_input; holdout=distinct full plus_input excluding every public input; source gzip remains unchanged",
        "feedback_policy": "Only public diagnostics may be projected into model messages; no plus inputs, expectations or outcomes",
        "totals": {field: sum(row[field] for row in split_rows) for field in total_fields},
        "task_splits": split_rows,
    }
    manifest["split_manifest_sha256"] = _object_sha256(split_rows)
    return tasks, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config else {}
    tasks, manifest = load_benchmark(config)
    if args.manifest_out:
        args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"tasks": len(tasks), "dataset_path": manifest["dataset_path"],
                      "dataset_sha256": manifest["dataset_sha256"], "totals": manifest["totals"],
                      "split_manifest_sha256": manifest["split_manifest_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
