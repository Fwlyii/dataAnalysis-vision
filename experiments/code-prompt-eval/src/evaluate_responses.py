#!/usr/bin/env python3
"""Functionally evaluate generated code with CoderEval test templates.

This script never installs packages. Non-Standalone projects must already be
downloaded and have a usable virtual environment. Generated code is untrusted;
execution requires the explicit --allow-code-execution flag.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import copy
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "CodePromptEval" / "CodePromptEval.csv"
DEFAULT_TASKS = ROOT / "benchmarks" / "CoderEval" / "CoderEval4Python.json"
DEFAULT_TESTS = ROOT / "benchmarks" / "CoderEval" / "tests" / "record_testcases_map_python.json"
DEFAULT_PROJECTS = ROOT / "benchmarks" / "CoderEval" / "CoderEval" / "home" / "travis" / "builds" / "repos"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON at {path}:{line_number}: {exc}") from exc
    return rows


def record_key(row: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(row.get("task_id")),
        str(row.get("combination_id") or row.get("prompt_id")),
        int(row.get("turn_id", row.get("repeat_id", 1))),
    )


def completed_keys(path: Path) -> set[tuple[str, str, int]]:
    if not path.exists():
        return set()
    return {record_key(row) for row in read_jsonl(path)}


def first_function_name(source: str) -> str | None:
    tree = ast.parse(textwrap.dedent(source))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return None


def normalized_generated_function(
    source: str,
    original_name: str,
    reference: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    """Return one target function with harmless top-level helpers moved inside it.

    Models often include imports before a function. Inserting those lines at a
    class-method indentation turns the imports into class attributes and makes
    otherwise valid code fail. Function-level evaluation only needs the target
    function, so imports, assignments, helper functions, and helper classes are
    moved into its body before insertion into the original test template.
    """
    source = textwrap.dedent(source)
    tree = ast.parse(source)
    functions = [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if not functions:
        raise ValueError("Could not find a function definition")
    target_original = next((node for node in functions if node.name == original_name), functions[0])
    target = copy.deepcopy(target_original)
    target.name = original_name
    movable = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign, ast.FunctionDef,
               ast.AsyncFunctionDef, ast.ClassDef)
    helpers = [
        copy.deepcopy(node) for node in tree.body
        if isinstance(node, movable) and node is not target_original
    ]
    helpers = [node for node in helpers if not (
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target.name
    )]
    if helpers:
        insertion = 1 if (
            target.body
            and isinstance(target.body[0], ast.Expr)
            and isinstance(target.body[0].value, ast.Constant)
            and isinstance(target.body[0].value.value, str)
        ) else 0
        target.body[insertion:insertion] = helpers
    reference_annotations = {
        argument.arg: argument.annotation
        for argument in [
            *reference.args.posonlyargs,
            *reference.args.args,
            *reference.args.kwonlyargs,
        ]
    }
    for argument in [*target.args.posonlyargs, *target.args.args, *target.args.kwonlyargs]:
        argument.annotation = copy.deepcopy(reference_annotations.get(argument.arg))
    if target.args.vararg is not None:
        target.args.vararg.annotation = copy.deepcopy(
            reference.args.vararg.annotation
            if reference.args.vararg is not None and reference.args.vararg.arg == target.args.vararg.arg
            else None
        )
    if target.args.kwarg is not None:
        target.args.kwarg.annotation = copy.deepcopy(
            reference.args.kwarg.annotation
            if reference.args.kwarg is not None and reference.args.kwarg.arg == target.args.kwarg.arg
            else None
        )
    target.returns = copy.deepcopy(reference.returns)
    target.type_comment = reference.type_comment
    target.decorator_list = copy.deepcopy(reference.decorator_list)
    ast.fix_missing_locations(target)
    return ast.unparse(target)


def replace_function(
    template: str,
    original: str,
    generated: str,
    original_lineno: int | None = None,
) -> str:
    original_name = first_function_name(original)
    if not original_name:
        raise ValueError("Could not find a function definition")
    original_tree = ast.parse(textwrap.dedent(original))
    original_nodes = [
        node for node in ast.walk(original_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == original_name
    ]
    original_node = original_nodes[0] if original_nodes else None
    template_tree = ast.parse(template)
    targets = [
        node
        for node in ast.walk(template_tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == original_name
    ]
    if not targets:
        raise ValueError("Ground-truth function was not found in the test template")
    structural_matches = (
        [node for node in targets if ast.dump(node) == ast.dump(original_node)]
        if original_node is not None
        else []
    )
    if structural_matches:
        target = min(structural_matches, key=lambda node: node.lineno)
    elif original_lineno is not None:
        target = min(targets, key=lambda node: abs(node.lineno - original_lineno))
    else:
        target = min(targets, key=lambda node: node.lineno)
    generated = normalized_generated_function(generated, original_name, target)
    start_line = min(
        [target.lineno, *(decorator.lineno for decorator in target.decorator_list)]
    )
    end_line = target.end_lineno
    if end_line is None:
        raise ValueError("Could not determine the end of the ground-truth function")
    indentation = target.col_offset
    replacement = textwrap.indent(generated, " " * indentation) + "\n"
    template_lines = template.splitlines(keepends=True)
    return "".join(template_lines[: start_line - 1]) + replacement + "".join(template_lines[end_line:])


def generated_code_safety_error(source: str) -> str | None:
    """Reject capabilities that these small function tasks do not need."""
    tree = ast.parse(source)
    blocked_calls = {
        "__import__", "breakpoint", "compile", "eval", "exec", "globals", "input",
        "locals", "open", "os.popen", "os.remove", "os.rmdir", "os.system",
        "os.unlink", "subprocess.call", "subprocess.Popen", "subprocess.run",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = {alias.name.split(".", 1)[0] for alias in node.names}
            disallowed = modules - {"os"}
            if disallowed:
                return f"Disallowed import(s): {', '.join(sorted(disallowed))}"
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module != "os":
                return f"Disallowed import: {node.module}"
        elif isinstance(node, ast.Call):
            try:
                name = ast.unparse(node.func)
            except Exception:
                name = ""
            if name in blocked_calls:
                return f"Disallowed call: {name}"
    return None


def project_python(project: Path, project_name: str, fallback: Path | None) -> Path | None:
    candidates = [
        project / f"{project_name}_env" / "bin" / "python",
        project / ".venv" / "bin" / "python",
        project / "venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return fallback


def overlay_project(original: Path, destination: Path, relative_parent: Path) -> Path:
    """Create a symlink overlay with a writable target source directory."""
    if relative_parent.is_absolute() or ".." in relative_parent.parts:
        raise ValueError(f"Unsafe source path: {relative_parent}")
    source_dir = original
    target_dir = destination
    target_dir.mkdir(parents=True, exist_ok=True)
    parts = list(relative_parent.parts)
    for depth in range(len(parts) + 1):
        next_name = parts[depth] if depth < len(parts) else None
        for child in source_dir.iterdir():
            target = target_dir / child.name
            if child.name == next_name and child.is_dir():
                target.mkdir(exist_ok=True)
            elif not target.exists() and not target.is_symlink():
                target.symlink_to(child, target_is_directory=child.is_dir())
        if next_name is None:
            break
        source_dir = source_dir / next_name
        target_dir = target_dir / next_name
    return target_dir


def prepare_test_project(
    original: Path, project_name: str, task_id: str, relative_parent: Path,
) -> tuple[Path, Path]:
    project = (
        Path(tempfile.gettempdir()) / "codeprompteval-evaluation" / "projects"
        / task_id / project_name
    )
    test_dir = overlay_project(original, project, relative_parent)
    compatibility_repos = project / "repos"
    compatibility_repos.mkdir(exist_ok=True)
    compatibility_project = compatibility_repos / project_name
    if not compatibility_project.exists() and not compatibility_project.is_symlink():
        compatibility_project.symlink_to(project, target_is_directory=True)
    if relative_parent.parts:
        outer_package = project / relative_parent.parts[0]
        inner_package = outer_package / relative_parent.parts[0]
        if inner_package.is_dir():
            for child in inner_package.iterdir():
                compatibility_child = outer_package / child.name
                if not compatibility_child.exists() and not compatibility_child.is_symlink():
                    compatibility_child.symlink_to(child, target_is_directory=child.is_dir())
    return project, test_dir


def relocate_template_paths(template: str, project: Path) -> str:
    relocated = template.replace("/home/travis/builds/repos", str(project.parent))
    pattern = re.compile(
        r"^sys\.path\.remove\((os\.path\.join\(os\.getcwd\(\),[^\n]+\))\)$",
        re.MULTILINE,
    )
    return pattern.sub(
        "_candidate_path = \\1\n"
        "for _candidate_entry in list(sys.path):\n"
        "    if os.path.realpath(_candidate_entry) == os.path.realpath(_candidate_path):\n"
        "        sys.path.remove(_candidate_entry)",
        relocated,
    )


def error_record(row: dict[str, Any], category: str, message: str, elapsed: float = 0.0) -> dict[str, Any]:
    return {
        "profile": row.get("profile"),
        "model": row.get("model"),
        "task_id": row.get("task_id"),
        "combination_id": row.get("combination_id"),
        "prompt_id": row.get("prompt_id"),
        "turn_id": int(row.get("turn_id", row.get("repeat_id", 1))),
        "passed": None if category == "environment_error" else False,
        "error_category": category,
        "error_message": message,
        "evaluation_seconds": round(elapsed, 3),
    }


def run_test_source(
    source: str,
    task: dict[str, Any],
    python: Path,
    project: Path,
    test_dir: Path,
    task_id: str,
    timeout: float,
    sandboxed: bool = False,
) -> subprocess.CompletedProcess[str]:
    test_dir.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=f"_{task_id}.py",
            prefix="codex_eval_",
            dir=test_dir,
            encoding="utf-8",
            delete=False,
        ) as temp_file:
            temp_file.write(source)
            temp_path = Path(temp_file.name)
        if str(task.get("test_name") or "") and task.get("level") != "self_contained":
            command = [str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", str(temp_path)]
        else:
            command = [str(python), str(temp_path)]
        if sandboxed:
            sandbox_exec = shutil.which("sandbox-exec")
            if sandbox_exec is None:
                raise RuntimeError("sandbox-exec is required for sandboxed evaluation")
            writable_root = Path(tempfile.gettempdir()).resolve()
            profile = (
                "(version 1)\n"
                "(deny default)\n"
                '(import "system.sb")\n'
                "(allow process*)\n"
                "(allow file-read*)\n"
                f'(allow file-write* (subpath "{writable_root}"))\n'
                "(deny network*)\n"
            )
            command = [sandbox_exec, "-p", profile, *command]
        python_paths = [project / "src", project / "lib", project]
        return subprocess.run(
            command,
            cwd=project,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={
                "HOME": tempfile.gettempdir(),
                "PATH": f"{python.parent}:/usr/bin:/bin",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": os.pathsep.join(str(path) for path in python_paths),
            },
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def load_evaluation_assets(
    dataset_path: Path = DEFAULT_DATASET,
    tasks_path: Path = DEFAULT_TASKS,
    tests_path: Path = DEFAULT_TESTS,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    """Load metadata needed by both batch and feedback-driven evaluation."""
    with dataset_path.open("r", encoding="utf-8", newline="") as handle:
        dataset = {row["task_id"]: row for row in csv.DictReader(handle)}
    task_rows = json.loads(tasks_path.read_text(encoding="utf-8"))["RECORDS"]
    tasks = {str(row["_id"]): row for row in task_rows}
    test_templates = json.loads(tests_path.read_text(encoding="utf-8"))
    return dataset, tasks, test_templates


def evaluate_generation(
    row: dict[str, Any],
    dataset: dict[str, dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    test_templates: dict[str, str],
    projects_root: Path = DEFAULT_PROJECTS,
    fallback_python: Path | None = None,
    timeout: float = 60.0,
    preflight_errors: dict[tuple[str, str], str | None] | None = None,
    evaluation_lock: threading.Lock | None = None,
    sandbox_generated: bool = False,
) -> dict[str, Any]:
    """Evaluate one generation and return a compact result record."""
    if preflight_errors is None:
        preflight_errors = {}
    started = time.monotonic()
    task_id = str(row.get("task_id"))
    if row.get("status") == "error":
        return error_record(row, "api_error", str(row.get("error_message") or "API call failed"))
    generated = row.get("generated_code")
    if not generated:
        return error_record(row, "extraction_error", "No generated Python code")
    try:
        ast.parse(str(generated))
    except (SyntaxError, ValueError, TypeError) as exc:
        return error_record(row, "syntax_error", f"{type(exc).__name__}: {exc}")
    if not sandbox_generated:
        safety_error = generated_code_safety_error(str(generated))
        if safety_error:
            result = error_record(row, "safety_error", safety_error)
            result["passed"] = None
            return result

    metadata = dataset.get(task_id)
    task = tasks.get(task_id)
    template = test_templates.get(task_id)
    if not metadata or not task or not template:
        return error_record(row, "environment_error", "Task metadata or test template is missing")

    project_name = str(metadata["project"]).replace("/", "---")
    project_candidate = projects_root / project_name
    prepared_python = (
        project_python(project_candidate, project_name, None)
        if project_candidate.is_dir()
        else None
    )
    if metadata["project"] == "Standalone":
        project = Path(tempfile.gettempdir()) / "codeprompteval-self-contained"
        project.mkdir(parents=True, exist_ok=True)
        python = fallback_python or Path(sys.executable)
        test_dir = project
    elif project_candidate.is_dir():
        project = project_candidate
        python = prepared_python
        if python is None and metadata.get("level") == "self_contained":
            python = fallback_python or Path(sys.executable)
        if python is None:
            return error_record(row, "environment_error", f"No prepared Python environment found for {project_name}")
        relative_parent = Path(str(metadata.get("file_path") or ".")).parent
        if relative_parent.is_absolute() or ".." in relative_parent.parts:
            return error_record(row, "environment_error", f"Unsafe source path: {relative_parent}")
        if evaluation_lock is None:
            project, test_dir = prepare_test_project(
                project_candidate, project_name, task_id, relative_parent
            )
        else:
            with evaluation_lock:
                project, test_dir = prepare_test_project(
                    project_candidate, project_name, task_id, relative_parent
                )
    else:
        return error_record(row, "environment_error", f"Project environment missing: {project_candidate}")

    python = python.absolute()
    template = relocate_template_paths(str(template), project)
    preflight_key = (task_id, str(python))
    def run_preflight() -> None:
        if preflight_key in preflight_errors:
            return
        try:
            preflight = run_test_source(
                template, task, python, project, test_dir, task_id, timeout,
                sandboxed=sandbox_generated,
            )
            preflight_errors[preflight_key] = (
                None if preflight.returncode == 0 else "Reference implementation failed: "
                + (preflight.stderr or preflight.stdout)[-10000:]
            )
        except subprocess.TimeoutExpired as exc:
            preflight_errors[preflight_key] = f"Reference implementation timed out after {timeout:g}s: {exc}"
        except Exception as exc:
            preflight_errors[preflight_key] = f"Reference implementation could not run: {type(exc).__name__}: {exc}"

    if evaluation_lock is None:
        run_preflight()
    else:
        with evaluation_lock:
            run_preflight()
    if preflight_errors[preflight_key] is not None:
        return error_record(
            row,
            "environment_error",
            str(preflight_errors[preflight_key]),
            time.monotonic() - started,
        )

    try:
        test_source = replace_function(
            str(template),
            str(task["code"]),
            str(generated),
            int(task["lineno"]) if task.get("lineno") is not None else None,
        )
        completed = run_test_source(
            test_source, task, python, project, test_dir, task_id, timeout,
            sandboxed=sandbox_generated,
        )
        elapsed = time.monotonic() - started
        return {
            **error_record(row, "runtime_error", completed.stderr or completed.stdout, elapsed),
            "passed": completed.returncode == 0,
            "error_category": "success" if completed.returncode == 0 else "runtime_error",
            "returncode": completed.returncode,
            "stdout": completed.stdout[-10000:],
            "stderr": completed.stderr[-10000:],
        }
    except subprocess.TimeoutExpired as exc:
        return error_record(
            row,
            "timeout",
            f"Timed out after {timeout:g}s: {exc}",
            time.monotonic() - started,
        )
    except ValueError as exc:
        if str(exc) == "Could not find a function definition":
            return error_record(
                row,
                "extraction_error",
                str(exc),
                time.monotonic() - started,
            )
        return error_record(
            row,
            "evaluation_error",
            f"{type(exc).__name__}: {exc}",
            time.monotonic() - started,
        )
    except Exception as exc:
        return error_record(
            row,
            "evaluation_error",
            f"{type(exc).__name__}: {exc}",
            time.monotonic() - started,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Generation JSONL from run_experiment.py")
    parser.add_argument("--output", type=Path, required=True, help="Evaluation JSONL")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--tests", type=Path, default=DEFAULT_TESTS)
    parser.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument(
        "--sandbox-generated",
        action="store_true",
        help="Run candidate tests in macOS sandbox-exec; network is denied and writes are limited to the temp directory",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--python", type=Path, help="Fallback Python interpreter; use only with a prepared environment")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--allow-code-execution", action="store_true")
    args = parser.parse_args()

    if not args.allow_code_execution:
        raise SystemExit(
            "Generated code is untrusted. Re-run with --allow-code-execution only inside an isolated environment."
        )
    if args.timeout <= 0 or args.concurrency <= 0 or (args.limit is not None and args.limit <= 0):
        parser.error("--timeout, --concurrency, and --limit must be positive")
    if args.input.resolve() == args.output.resolve():
        parser.error("--input and --output must be different files")

    dataset, tasks, test_templates = load_evaluation_assets(
        args.dataset, args.tasks, args.tests
    )

    generations = read_jsonl(args.input)
    done = set() if args.force else completed_keys(args.output)
    pending = [row for row in generations if record_key(row) not in done]
    if args.limit is not None:
        pending = pending[: args.limit]
    print(f"Records pending: {len(pending)}")
    print(f"Timeout per record: {args.timeout:g}s")
    print(f"Concurrency: {args.concurrency}")
    print(f"Sandbox generated code: {args.sandbox_generated}")

    preflight_errors: dict[tuple[str, str], str | None] = {}
    evaluation_lock = threading.Lock()
    def evaluate(row: dict[str, Any]) -> dict[str, Any]:
        return evaluate_generation(
            row, dataset, tasks, test_templates, args.projects_root,
            args.python, args.timeout, preflight_errors, evaluation_lock,
            args.sandbox_generated,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8", buffering=1) as handle:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            future_to_row = {executor.submit(evaluate, row): row for row in pending}
            for index, future in enumerate(concurrent.futures.as_completed(future_to_row), start=1):
                row = future_to_row[future]
                task_id = str(row.get("task_id"))
                result = future.result()
                result["sandboxed"] = args.sandbox_generated
                result["normalization"] = "target-function-ast-v2"
                handle.write(json.dumps(result, ensure_ascii=False) + "\n")
                print(f"[{index}/{len(pending)}] task={task_id} turn={row.get('turn_id', row.get('repeat_id', 1))}")

    print(f"Evaluation written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
