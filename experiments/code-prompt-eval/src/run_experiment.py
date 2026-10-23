#!/usr/bin/env python3
"""Run CodePromptEval prompts through an OpenAI-compatible chat API.

The runner is deliberately independent from the original cluster-specific
scripts. It reads the published CSV verbatim, writes one JSON object per model
call, resumes completed calls, and defaults to a single call to prevent an
accidental full-dataset bill.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gzip
import json
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CODE_PROMPT_VERSION = "code-v1"
DEFAULT_INPUT = ROOT / "data" / "benchmark_194_tasks.csv.gz"
DEFAULT_MODELS = ROOT / "data" / "model_profiles.json"
DEFAULT_COT_PROMPTS = ROOT / "data" / "prompts.json"
DEFAULT_ENV = ROOT / ".env"
INCONVENIENT_PROMPT_IDS = {
    "OnlyNumbers",
    "NoSpaces",
    "NoProperGrammar",
    "AbbreviateWords",
}


def load_env_file(path: Path) -> None:
    """Load a small .env file without making python-dotenv a dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Model config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict) or not data:
        raise SystemExit(f"No model profiles found in {path}")
    return data


def load_cot_prompts(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"CoT prompt config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict) or len(data) != 31:
        raise SystemExit(f"Expected exactly 31 CoT prompts in {path}, found {len(data)}")
    normalized: dict[str, dict[str, str]] = {}
    for prompt_id, value in data.items():
        if not isinstance(prompt_id, str):
            raise SystemExit(f"Every CoT prompt ID in {path} must be text")
        if isinstance(value, str):
            normalized[prompt_id] = {"original": value, "code": value}
        elif (
            isinstance(value, dict)
            and isinstance(value.get("original"), str)
            and isinstance(value.get("code"), str)
        ):
            normalized[prompt_id] = {"original": value["original"], "code": value["code"]}
        else:
            raise SystemExit(
                f"Prompt '{prompt_id}' must be text or contain text fields 'original' and 'code'"
            )
    return normalized


def select_cot_prompts(
    prompts: dict[str, dict[str, str]],
    policy: str,
    prompt_ids: list[str] | None,
) -> dict[str, dict[str, str]]:
    """Select the prompts used by a run without changing the source catalog."""
    if prompt_ids:
        requested = list(dict.fromkeys(prompt_ids))
        missing = [prompt_id for prompt_id in requested if prompt_id not in prompts]
        if missing:
            raise SystemExit(f"Unknown prompt ID(s): {', '.join(missing)}")
        return {prompt_id: prompts[prompt_id] for prompt_id in requested}
    if policy == "recommended27":
        return {
            prompt_id: value
            for prompt_id, value in prompts.items()
            if prompt_id not in INCONVENIENT_PROMPT_IDS
        }
    return prompts


def read_dataset(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Dataset not found: {path}")
    csv.field_size_limit(sys.maxsize)
    handle = (
        gzip.open(path, "rt", encoding="utf-8", newline="")
        if path.suffix.lower() == ".gz"
        else path.open("r", encoding="utf-8", newline="")
    )
    with handle:
        rows = list(csv.DictReader(handle))
    required = {"task_id", "combination_id", "prompt"}
    missing = required.difference(rows[0] if rows else {})
    if missing:
        raise SystemExit(f"Dataset is missing columns: {', '.join(sorted(missing))}")
    return rows


def csv_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def build_cot_compression_rows(
    rows: list[dict[str, str]],
    prompts: dict[str, dict[str, str]],
    base_context: str,
    prompt_set_name: str = "cot-compression31",
) -> list[dict[str, str]]:
    """Adapt the paper's 31 reasoning-compression prompts to code generation.

    The compression instruction controls only prose reasoning. The final code is
    exempt so limits such as OnlyNumbers and WordLimit(1) do not make a valid
    Python function impossible.
    """
    context_flags = {
        "zero-shot": (False, False),
        "signature": (False, True),
        "signature-packages": (True, True),
    }
    packages_required, signature_required = context_flags[base_context]
    task_order = list(dict.fromkeys(row["task_id"] for row in rows))
    base_by_task: dict[str, dict[str, str]] = {}
    for row in rows:
        is_base = (
            csv_bool(row.get("is_zero_shot", "False"))
            and not csv_bool(row.get("is_few_shot", "False"))
            and not csv_bool(row.get("is_chain_of_thought", "False"))
            and not csv_bool(row.get("is_persona", "False"))
            and csv_bool(row.get("is_packages", "False")) == packages_required
            and csv_bool(row.get("is_signature", "False")) == signature_required
        )
        if is_base:
            base_by_task[row["task_id"]] = row

    missing = [task_id for task_id in task_order if task_id not in base_by_task]
    if missing:
        raise SystemExit(
            f"Could not find the '{base_context}' base prompt for {len(missing)} task(s)"
        )

    prefix = "Respond with a Python function in one code block."
    expanded: list[dict[str, str]] = []
    for task_id in task_order:
        base = base_by_task[task_id]
        task_text = base["prompt"].strip()
        if task_text.startswith(prefix):
            task_text = task_text[len(prefix):].strip()
        for prompt_id, instructions in prompts.items():
            original_instruction = instructions["original"]
            code_instruction = instructions["code"]
            row = dict(base)
            row["prompt_set"] = prompt_set_name
            row["prompt_version"] = CODE_PROMPT_VERSION
            row["compression_prompt_id"] = prompt_id
            row["compression_instruction_original"] = original_instruction
            row["compression_instruction"] = code_instruction
            row["compression_scope"] = "reasoning_only"
            row["compression_adaptation"] = "code-generation reasoning-only"
            row["base_context"] = base_context
            row["combination_id"] = f"{prompt_set_name}-{CODE_PROMPT_VERSION}::{prompt_id}"
            row["prompt"] = (
                "Answer the following programming task.\n"
                "Reasoning instruction (applies only to optional text before the code):\n"
                f"{code_instruction}\n"
                f"Question: {task_text}\n"
                "Code requirement: End the response with exactly one Python code block containing "
                "the complete function. Never apply the reasoning instruction's language, length, "
                "spacing, or format restrictions to the code."
            )
            expanded.append(row)
    return expanded


def choose_rows(
    rows: list[dict[str, str]],
    task_ids: list[str] | None,
    task_limit: int | None,
    offset: int,
    row_limit: int | None,
) -> list[dict[str, str]]:
    if task_ids:
        requested = list(dict.fromkeys(task_ids))
        available = {row["task_id"] for row in rows}
        missing = [task_id for task_id in requested if task_id not in available]
        if missing:
            raise SystemExit(f"Unknown task ID(s): {', '.join(missing)}")
        order = {task_id: index for index, task_id in enumerate(requested)}
        rows = sorted(
            (row for row in rows if row["task_id"] in order),
            key=lambda row: order[row["task_id"]],
        )
    if task_limit is not None:
        selected_ids: list[str] = []
        seen: set[str] = set()
        for row in rows:
            task_id = row["task_id"]
            if task_id not in seen:
                seen.add(task_id)
                selected_ids.append(task_id)
                if len(selected_ids) == task_limit:
                    break
        allowed = set(selected_ids)
        rows = [row for row in rows if row["task_id"] in allowed]
    rows = rows[offset:]
    if row_limit is not None:
        rows = rows[:row_limit]
    return rows


def extract_code(response: str) -> str | None:
    python_block = re.search(r"```python\s*(.*?)```", response, re.DOTALL | re.IGNORECASE)
    if python_block:
        return python_block.group(1).strip()
    generic_block = re.search(r"```\s*(.*?)```", response, re.DOTALL)
    if generic_block:
        return generic_block.group(1).strip()
    return None


def extract_visible_reasoning(response: str) -> str:
    """Return visible response text outside fenced code blocks."""
    return re.sub(r"```(?:python)?\s*.*?```", "", response, flags=re.DOTALL | re.IGNORECASE).strip()


def call_key(task_id: str, combination_id: str, turn_id: int) -> tuple[str, str, int]:
    return task_id, combination_id, turn_id


def load_completed(path: Path) -> set[tuple[str, str, int]]:
    completed: set[tuple[str, str, int]] = set()
    if not path.exists():
        return completed
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: ignoring invalid JSON at {path}:{line_number}", file=sys.stderr)
                continue
            if item.get("status") == "success":
                turn_id = item.get("turn_id", item.get("repeat_id"))
                if turn_id is None:
                    continue
                completed.add(
                    call_key(
                        str(item["task_id"]),
                        str(item["combination_id"]),
                        int(turn_id),
                    )
                )
    return completed


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "model"


def response_usage(response: Any) -> dict[str, int | None]:
    usage = getattr(response, "usage", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    return {
        "input_tokens": getattr(usage, "prompt_tokens", None),
        "output_tokens": getattr(usage, "completion_tokens", None),
        "reasoning_tokens": getattr(completion_details, "reasoning_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the published CodePromptEval prompts through an OpenAI-compatible API."
    )
    parser.add_argument("--profile", help="Profile name in config/models.json; defaults to its first entry")
    parser.add_argument("--models-config", type=Path, default=DEFAULT_MODELS)
    parser.add_argument("--cot-prompts-config", type=Path, default=DEFAULT_COT_PROMPTS)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, help="JSONL output path")
    parser.add_argument(
        "--prompt-set",
        choices=("cot-compression31", "original32"),
        default="cot-compression31",
        help="Use the compression paper's 31 prompts or the original CodePromptEval 32 combinations",
    )
    parser.add_argument(
        "--prompt-policy",
        choices=("recommended27", "all31"),
        default="recommended27",
        help="For cot-compression31, exclude four inconvenient prompts by default or keep all 31",
    )
    parser.add_argument(
        "--prompt-ids",
        nargs="+",
        help="Run only these exact compression prompt IDs",
    )
    parser.add_argument(
        "--base-context",
        choices=("zero-shot", "signature", "signature-packages"),
        default="signature-packages",
        help="Fixed code context used with cot-compression31",
    )
    parser.add_argument(
        "--turns",
        type=int,
        default=1,
        help="Backward-compatible name for independent samples per model/task/prompt",
    )
    parser.add_argument(
        "--samples",
        type=int,
        help="Clearer alias for --turns when computing Pass@k",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        help="Deprecated alias for --turns",
    )
    parser.add_argument("--task-limit", type=int, help="Select the first N tasks and all their prompt combinations")
    parser.add_argument(
        "--task-ids",
        nargs="+",
        help="Select these exact task IDs and all their prompt combinations",
    )
    parser.add_argument("--offset", type=int, default=0, help="Skip this many selected rows")
    parser.add_argument("--limit", type=int, help="Maximum number of prompt rows")
    parser.add_argument("--all", action="store_true", help="Run every selected prompt row")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration without calling the API")
    parser.add_argument("--force", action="store_true", help="Run calls again even if output already contains them")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--request-timeout", type=float, default=180.0)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of simultaneous API requests; keep 1 for local Ollama",
    )
    parser.add_argument(
        "--shuffle-seed",
        type=int,
        default=20261021,
        help="Deterministically shuffle calls to reduce ordering/time bias",
    )
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--list-prompts", action="store_true")
    args = parser.parse_args()
    if args.samples is not None:
        if args.turns != 1 or args.repeats is not None:
            parser.error("Use only one of --samples, --turns, or --repeats")
        args.turns = args.samples
    if args.repeats is not None:
        if args.turns != 1:
            parser.error("Use either --turns or --repeats, not both")
        args.turns = args.repeats
    if args.turns < 1 or args.max_retries < 1 or args.concurrency < 1:
        parser.error("--turns, --max-retries, and --concurrency must be positive")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.task_limit is not None and args.task_limit < 1:
        parser.error("--task-limit must be positive")
    if args.task_ids and args.task_limit is not None:
        parser.error("Use either --task-ids or --task-limit, not both")
    if args.offset < 0:
        parser.error("--offset cannot be negative")
    if args.all and args.limit is not None:
        parser.error("Use either --all or --limit, not both")
    if args.prompt_set == "original32" and args.prompt_ids:
        parser.error("--prompt-ids is only available with cot-compression31")
    return args


def main() -> int:
    args = parse_args()
    load_env_file(args.env_file)
    profiles = load_profiles(args.models_config)

    if args.list_models:
        for name, item in profiles.items():
            print(f"{name}: {item.get('model', '<missing model>')} @ {item.get('base_url', '<default URL>')}")
        return 0
    if args.list_prompts:
        for prompt_id, instructions in load_cot_prompts(args.cot_prompts_config).items():
            print(f"{prompt_id}: {instructions['code']}")
        return 0

    profile_name = args.profile or next(iter(profiles))
    if profile_name not in profiles:
        available = ", ".join(sorted(profiles))
        raise SystemExit(f"Unknown profile '{profile_name}'. Available profiles: {available}")

    profile = profiles[profile_name]
    required_profile_keys = {"model", "api_key_env"}
    missing = required_profile_keys.difference(profile)
    if missing:
        raise SystemExit(f"Profile '{profile_name}' is missing: {', '.join(sorted(missing))}")
    extra_body = profile.get("extra_body") or {}
    thinking_config = extra_body.get("thinking") or {}
    thinking_type = thinking_config.get("type")
    reasoning_effort = profile.get("reasoning_effort")
    declared_thinking_mode = profile.get("thinking_mode")
    non_thinking = (
        declared_thinking_mode in {"disabled", "not-supported"}
        or
        thinking_type == "disabled"
        or reasoning_effort == "none"
        or extra_body.get("think") is False
        or extra_body.get("enable_thinking") is False
    )
    if profile.get("require_non_thinking") and not non_thinking:
        raise SystemExit(
            f"Profile '{profile_name}' requires non-thinking mode, but neither "
            "thinking.type=disabled nor reasoning_effort=none is configured"
        )

    rows = read_dataset(args.input)
    effective_prompt_set = args.prompt_set
    selected_prompt_count = 32
    if args.prompt_set == "cot-compression31":
        selected_prompts = select_cot_prompts(
            load_cot_prompts(args.cot_prompts_config),
            args.prompt_policy,
            args.prompt_ids,
        )
        selected_prompt_count = len(selected_prompts)
        effective_prompt_set = (
            f"cot-compression{selected_prompt_count}"
            if not args.prompt_ids
            else f"cot-custom{selected_prompt_count}"
        )
        rows = build_cot_compression_rows(
            rows,
            selected_prompts,
            args.base_context,
            effective_prompt_set,
        )
    else:
        rows = [dict(row, prompt_set="original32") for row in rows]
    # Safe default: one prompt row unless the user explicitly selects a scope.
    row_limit = None if args.all or args.task_limit is not None or args.task_ids else (args.limit or 1)
    if args.limit is not None:
        row_limit = args.limit
    selected = choose_rows(rows, args.task_ids, args.task_limit, args.offset, row_limit)
    if not selected:
        raise SystemExit("No dataset rows matched the requested scope")

    output_prompt_set = (
        f"{effective_prompt_set}-{CODE_PROMPT_VERSION}"
        if args.prompt_set == "cot-compression31"
        else args.prompt_set
    )
    output = args.output or (
        ROOT
        / "outputs"
        / safe_name(profile_name)
        / f"responses_{safe_name(output_prompt_set)}_{args.turns}samples.jsonl"
    )
    completed = set() if args.force else load_completed(output)
    planned = [
        (row, turn_id)
        for row in selected
        for turn_id in range(1, args.turns + 1)
        if args.force
        or call_key(row["task_id"], row["combination_id"], turn_id) not in completed
    ]
    random.Random(args.shuffle_seed).shuffle(planned)

    api_key_env = str(profile["api_key_env"])
    api_key_present = bool(os.environ.get(api_key_env))
    print(f"Profile: {profile_name}")
    print(f"Model: {profile['model']}")
    print(f"Base URL: {profile.get('base_url') or '<OpenAI default>'}")
    print(
        "Thinking mode: "
        + (
            str(declared_thinking_mode)
            if declared_thinking_mode
            else "disabled" if non_thinking else thinking_type or "provider default"
        )
        + f" (reasoning_effort={reasoning_effort or 'not set'})"
    )
    print(f"Prompt set: {args.prompt_set}")
    if args.prompt_set == "cot-compression31":
        print(f"Prompt policy: {args.prompt_policy} ({selected_prompt_count} prompt(s))")
        print(f"Prompt version: {CODE_PROMPT_VERSION}")
        print(f"Base context: {args.base_context}")
    print(f"Dataset rows selected: {len(selected)} of {len(rows)}")
    print(f"Model calls planned: {len(planned)} ({args.turns} independent sample(s))")
    print(f"Concurrency: {args.concurrency}")
    print(f"Shuffle seed: {args.shuffle_seed}")
    print(f"Output: {output}")
    print(f"API key variable: {api_key_env} ({'set' if api_key_present else 'not set'})")
    print(f"First task: {selected[0]['task_id']}")
    print(f"First prompt preview: {selected[0]['prompt'][:180].replace(chr(10), ' ')}...")

    if args.dry_run:
        print("Dry run successful; no API request was sent.")
        return 0
    if not api_key_present:
        raise SystemExit(f"Add {api_key_env}=... to {args.env_file} before running")
    if not planned:
        print("Nothing to do; all selected calls already succeeded.")
        return 0

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency. Run: python -m pip install -r requirements-runner.txt"
        ) from exc

    client_kwargs: dict[str, Any] = {
        "api_key": os.environ[api_key_env],
        "timeout": args.request_timeout,
    }
    if profile.get("base_url"):
        client_kwargs["base_url"] = profile["base_url"]
    client = OpenAI(**client_kwargs)

    def perform_call(row: dict[str, str], turn_id: int) -> dict[str, Any]:
        started = time.time()
        request: dict[str, Any] = {
            "model": profile["model"],
            "messages": [{"role": "user", "content": row["prompt"]}],
        }
        if profile.get("temperature") is not None:
            request["temperature"] = profile["temperature"]
        if profile.get("top_p") is not None:
            request["top_p"] = profile["top_p"]
        if reasoning_effort is not None:
            request["reasoning_effort"] = reasoning_effort
        max_tokens_key = profile.get("max_tokens_parameter", "max_tokens")
        if profile.get("max_tokens") is not None:
            request[max_tokens_key] = profile["max_tokens"]
        if profile.get("extra_body") is not None:
            request["extra_body"] = profile["extra_body"]

        last_error: Exception | None = None
        for attempt in range(1, args.max_retries + 1):
            try:
                response = client.chat.completions.create(**request)
                message = response.choices[0].message
                content = message.content or ""
                visible_reasoning = extract_visible_reasoning(content)
                provider_reasoning = getattr(message, "reasoning_content", None)
                usage = response_usage(response)
                if profile.get("require_non_thinking") and (
                    provider_reasoning or (usage.get("reasoning_tokens") or 0) > 0
                ):
                    raise RuntimeError(
                        "The provider returned reasoning content/tokens although non-thinking mode "
                        "was required."
                    )
                result: dict[str, Any] = dict(row)
                result.update(
                    {
                        "status": "success",
                        "profile": profile_name,
                        "model": profile["model"],
                        "base_url": profile.get("base_url"),
                        "turn_id": turn_id,
                        "repeat_id": turn_id,
                        "sample_id": turn_id,
                        "sampling_mode": "independent",
                        "prompt_id": row.get("compression_prompt_id", row["combination_id"]),
                        "temperature": profile.get("temperature"),
                        "top_p": profile.get("top_p"),
                        "thinking_mode": declared_thinking_mode or ("disabled" if non_thinking else thinking_type),
                        "reasoning_effort": reasoning_effort,
                        "max_tokens": profile.get("max_tokens"),
                        "complete_response": content,
                        "generated_code": extract_code(content),
                        "visible_reasoning": visible_reasoning,
                        "visible_reasoning_chars": len(visible_reasoning),
                        "provider_reasoning_content": provider_reasoning,
                        "finish_reason": response.choices[0].finish_reason,
                        "latency_seconds": round(time.time() - started, 3),
                        "attempts": attempt,
                        **usage,
                    }
                )
                return result
            except Exception as exc:  # Provider SDK exceptions vary.
                last_error = exc
                if attempt < args.max_retries:
                    delay = min(2 ** attempt, 30) + random.random()
                    print(
                        f"Request failed ({type(exc).__name__}); retrying in {delay:.1f}s",
                        file=sys.stderr,
                    )
                    time.sleep(delay)

        assert last_error is not None
        return {
            "status": "error",
            "task_id": row["task_id"],
            "combination_id": row["combination_id"],
            "profile": profile_name,
            "model": profile["model"],
            "turn_id": turn_id,
            "repeat_id": turn_id,
            "sample_id": turn_id,
            "sampling_mode": "independent",
            "prompt_id": row.get("compression_prompt_id", row["combination_id"]),
            "error_type": type(last_error).__name__,
            "error_message": str(last_error),
            "latency_seconds": round(time.time() - started, 3),
            "attempts": args.max_retries,
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8", buffering=1) as handle:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            future_to_call = {
                executor.submit(perform_call, row, turn_id): (row, turn_id)
                for row, turn_id in planned
            }
            for number, future in enumerate(concurrent.futures.as_completed(future_to_call), start=1):
                row, turn_id = future_to_call[future]
                result = future.result()
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                print(
                    f"[{number}/{len(planned)}] {result['status']} task={row['task_id']} "
                    f"combination={row['combination_id']} sample={turn_id}"
                )
                if result["status"] == "error":
                    print(f"Call failed permanently: {result['error_message']}", file=sys.stderr)

    print(f"Finished. Results were appended to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
