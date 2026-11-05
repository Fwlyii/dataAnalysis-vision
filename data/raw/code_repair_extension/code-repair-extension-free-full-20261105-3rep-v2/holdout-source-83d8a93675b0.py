"""Score saved programs on sealed full tests; no model API calls.

Default/--once scores the complete response lines present at startup.  --watch
tails the append-only collection every 15 seconds and exits only when the full
precommitted response and holdout counts are complete.  Unknown infrastructure
outcomes are logged separately and retried, never written as measured FAIL.
--all-rounds additionally measures intermediate versions for secondary curves;
it never changes the precommitted seed/final primary metric or model feedback.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pickle
import signal
import threading
import time

from .dataset import ROOT, load_benchmark
from .resource_policy import evaluate_resolved
from .prepare import atomic_json, canonical_sha256, replicate_ids, runtime_identity, source_hashes, valid_oracle


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def resolve(value):
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


class IntegrityError(ValueError):
    """A frozen input changed; this must stop rather than become a model FAIL."""


class ResponseTail:
    """Consume complete UTF-8 JSON lines while leaving an unfinished tail alone."""
    def __init__(self, path):
        self.path = Path(path)
        self.offset = 0
        self.buffer = b""
        self.inode = None

    def poll(self, limit=None):
        if not self.path.exists():
            if self.inode is not None:
                raise IntegrityError("The append-only response file disappeared")
            return
        stat = self.path.stat()
        if self.inode is not None and (self.inode != stat.st_ino or stat.st_size < self.offset):
            raise IntegrityError("The append-only response file was replaced or truncated")
        self.inode = stat.st_ino
        end = min(stat.st_size, limit) if limit is not None else stat.st_size
        if end < self.offset:
            return
        with self.path.open("rb") as handle:
            handle.seek(self.offset)
            while self.offset < end:
                chunk = handle.read(min(1024 * 1024, end - self.offset))
                if not chunk:
                    break
                self.offset += len(chunk)
                parts = (self.buffer + chunk).split(b"\n")
                self.buffer = parts.pop()
                for line in parts:
                    if not line.strip():
                        continue
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError) as error:
                        raise IntegrityError("A committed response JSON line is invalid") from error
                    yield value, digest(line)


def read_journal(path):
    if not path.exists():
        return []
    blob = path.read_bytes()
    if blob and not blob.endswith(b"\n"):
        raise IntegrityError(f"Interrupted {path.name} tail; preserve and repair it before resuming")
    try:
        return [json.loads(line) for line in blob.splitlines() if line.strip()]
    except (ValueError, UnicodeError) as error:
        raise IntegrityError(f"Invalid committed JSON in {path.name}") from error


def known_strong(result, task):
    public, hidden = result.get("public", {}), result.get("hidden", {})
    if result.get("sandboxed") is not True:
        raise IntegrityError("A holdout result was not sandboxed")
    if public.get("total_cases") != len(task["base_input"]) or (hidden and hidden.get("total_cases") != len(task["plus_input"])):
        raise IntegrityError("Evaluation test counts differ from frozen inputs")
    if not isinstance(result.get("full_pass"), bool):
        return False
    known_failure = lambda split: split.get("passed") is False and (split.get("complete") is True or split.get("outcome_known") is True)
    if result["full_pass"] is False:
        # A proven public failure settles task FAIL even if no hidden test ran.
        return known_failure(public) or known_failure(hidden)
    if public.get("complete") is not True or hidden.get("complete") is not True:
        return False
    if not isinstance(public.get("passed"), bool) or not isinstance(hidden.get("passed"), bool):
        raise IntegrityError("Known holdout result has invalid pass flags")
    if result["full_pass"] != (public["passed"] and hidden["passed"]):
        raise IntegrityError("Full pass contradicts its public/hidden results")
    for name, split, inputs in [("public", public, task["base_input"]), ("hidden", hidden, task["plus_input"])]:
        if split["passed"] and (split.get("scan_complete") is not True or split.get("cases_checked") != len(inputs)):
            raise IntegrityError("A passing " + name + " evaluation did not scan every case")
    return True


class HoldoutRunner:
    def __init__(self, config_path, *, poll_seconds=15, stop=None, all_rounds=False, concurrency=None):
        self.config_path = resolve(config_path)
        self.config_blob = self.config_path.read_bytes()
        self.config_sha = digest(self.config_blob)
        self.config = json.loads(self.config_blob)
        self.out = resolve(self.config["run_dir"])
        self.out.mkdir(parents=True, exist_ok=True)
        self.lock = (self.out / ".holdout.lock").open("w")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self.lock.close()
            raise RuntimeError("Another holdout evaluator owns this batch") from error
        self.stop = stop or threading.Event()
        self.poll_seconds = max(.01, poll_seconds)
        self.started = time.monotonic()
        self.runner_sha = digest(Path(__file__).read_bytes())
        self.resource_policy_sha = digest(Path(__file__).with_name("resource_policy.py").read_bytes())
        amendment_path = self.out / "operational-amendment-1.json"
        if amendment_path.is_file() and json.loads(amendment_path.read_text()).get("resource_policy_sha256") != self.resource_policy_sha:
            raise IntegrityError("Resource policy differs from the declared operational amendment")
        self.plan = json.loads((self.out / "plan.json").read_text())
        if self.plan.get("config_sha256") != self.config_sha or self.plan.get("batch_id") != self.config["batch_id"]:
            raise IntegrityError("Holdout configuration differs from its frozen plan")
        self.assert_frozen()
        if canonical_sha256(runtime_identity(self.config)) != self.plan["runtime_sha256"]:
            raise IntegrityError("Evaluation runtime differs from the frozen reference runtime")
        preflight = json.loads((self.out / "reference-preflight.json").read_text())
        if preflight.get("complete") is not True or preflight.get("config_sha256") != self.config_sha:
            raise IntegrityError("All canonical references must pass before held-out evaluation")
        task_list, manifest = load_benchmark(self.config)
        self.tasks = {task["task_id"]: task for task in task_list}
        if self.plan["task_ids"] != list(self.tasks) or self.plan.get("dataset_sha256") != manifest["dataset_sha256"]:
            raise IntegrityError("The frozen benchmark identities changed")
        if self.plan.get("manifest", {}).get("split_manifest_sha256") != manifest["split_manifest_sha256"]:
            raise IntegrityError("The sealed test split changed")
        self.splits = {row["task_id"]: row for row in manifest["task_splits"]}
        self.repeats = replicate_ids(self.config)
        self.final_round = self.config["rounds"] - 1
        self.all_rounds = bool(all_rounds)
        self.allowed_rounds = set(range(self.config["rounds"])) if self.all_rounds else {0, self.final_round}
        self.measurement_scope = "all_rounds" if self.all_rounds else "seed_and_final"
        self.expected_responses = len(self.tasks) * len(self.config["models"]) * len(self.repeats) * (1 + len(self.config["arms"]) * self.final_round)
        self.expected_primary_holdouts = len(self.tasks) * len(self.config["models"]) * len(self.repeats) * (1 + len(self.config["arms"]))
        self.expected_holdouts = self.expected_responses if self.all_rounds else self.expected_primary_holdouts
        if self.expected_responses != self.plan["expected_requests"] or self.expected_responses != self.config.get("maximum_physical_responses", self.expected_responses):
            raise IntegrityError("Response count does not match the precommitted design")
        if self.expected_primary_holdouts != self.config.get("maximum_measured_holdouts", self.expected_primary_holdouts):
            raise IntegrityError("Holdout count does not match the precommitted design")
        self.workers = int(self.config.get("holdout_concurrency", 8) if concurrency is None else concurrency)
        if not 1 <= self.workers <= 32:
            raise ValueError("holdout_concurrency must be between 1 and 32")
        timeout = float(self.config.get("holdout_timeout_s", 300))
        self.evaluation_config = {**self.config, "evaluation_timeout_s": timeout,
                                  "cpu_limit_s": max(1, int(timeout - 5)),
                                  "split_time_budget_s": max(.01, timeout - 5),
                                  "holdout_stop_on_failure": True}
        self.reader = ResponseTail(self.out / "responses.jsonl")
        self.seen = set()
        self.candidates = {}
        self.all_measured = {}
        self.measured = {}
        for row in read_journal(self.out / "holdout-evaluations.jsonl"):
            self.validate_identity(row)
            rid = row["record_id"]
            if rid in self.all_measured:
                raise IntegrityError("Duplicate measured holdout record_id")
            if row.get("config_sha256") != self.config_sha or row.get("reference_code_sha256") != self.plan["reference_code_sha256"]:
                raise IntegrityError("Saved holdout protocol differs from the frozen experiment")
            if not known_strong(row, self.tasks[row["task_id"]]):
                raise IntegrityError("An unknown holdout was written into the measured journal")
            self.all_measured[rid] = row
            if row["round"] in self.allowed_rounds:
                self.measured[rid] = row
        self.attempts = Counter()
        self.unknown_attempts = 0
        self.unknown_ids = set()
        for event in read_journal(self.out / "holdout-events.jsonl"):
            if event.get("event_type") == "holdout_started":
                self.attempts[event["record_id"]] = max(self.attempts[event["record_id"]], event.get("attempt", 0))
            self.unknown_attempts += event.get("event_type") == "holdout_unknown"
            if event.get("event_type") == "holdout_unknown":
                self.unknown_ids.add(event["record_id"])
        self.retry_at = {}
        self.oracle_cache = {}
        self.oracle_lock = threading.Lock()
        self.handles = {name: (self.out / name).open("a", encoding="utf-8") for name in ["holdout-evaluations.jsonl", "holdout-events.jsonl"]}
        self.io_lock = threading.RLock()
        (self.out / ("holdout-source-" + self.runner_sha[:12] + ".py")).write_bytes(Path(__file__).read_bytes())
        scope_path = self.out / "holdout-scope.json"
        scope = json.loads(scope_path.read_text()) if scope_path.exists() else {}
        if scope and scope.get("config_sha256") != self.config_sha:
            raise IntegrityError("Saved measurement scope belongs to a different experiment")
        expanded = scope.get("all_rounds_requested", False) or self.all_rounds
        atomic_json(scope_path, {"schema": "code-repair-holdout-scope-v1", "timestamp": timestamp(),
                    "batch_id": self.config["batch_id"], "config_sha256": self.config_sha,
                    "active_scope": self.measurement_scope, "all_rounds_requested": expanded,
                    "expected_active_measurements": self.expected_holdouts,
                    "expected_primary_measurements": self.expected_primary_holdouts,
                    "expected_all_round_measurements": self.expected_responses,
                    "primary_metric": "Precommitted shared-seed and final-round strong-test results remain unchanged.",
                    "additional_measurement": "All intermediate versions are measured for secondary five-version curves and evaluation of versions selected using public feedback only.",
                    "used_for_model_feedback": False, "used_for_candidate_selection": False,
                    "scheduler_concurrency": self.workers, "holdout_runner_sha256": self.runner_sha})

    def assert_frozen(self):
        if digest(self.config_path.read_bytes()) != self.config_sha:
            raise IntegrityError("The experiment configuration changed during held-out evaluation")
        if source_hashes() != self.plan["reference_source_hashes"]:
            raise IntegrityError("Frozen evaluation/protocol source changed")
        if digest(Path(__file__).with_name("resource_policy.py").read_bytes()) != self.resource_policy_sha:
            raise IntegrityError("Resource resolution policy changed while scoring")

    def validate_identity(self, row):
        try:
            model, tid, repeat, arm, round_ = [row[key] for key in ("model", "task_id", "replicate", "arm", "round")]
        except KeyError as error:
            raise IntegrityError("Missing saved program identity") from error
        if model not in self.config["models"] or tid not in self.plan["task_ids"] or repeat not in replicate_ids(self.config):
            raise IntegrityError("Saved program identity is outside the frozen design")
        if not isinstance(round_, int) or isinstance(round_, bool) or not 0 <= round_ < self.config["rounds"]:
            raise IntegrityError("Saved program round is invalid")
        if (round_ == 0 and arm != "seed") or (round_ > 0 and arm not in self.config["arms"]):
            raise IntegrityError("Saved program arm/round is invalid")
        if row.get("record_id") != f"{model}|{tid}|rep{repeat}|{arm}|{round_}":
            raise IntegrityError("Saved program record_id contradicts its fields")

    def ingest(self, limit=None):
        for row, line_sha in self.reader.poll(limit):
            self.validate_identity(row)
            rid = row["record_id"]
            if rid in self.seen:
                raise IntegrityError("Duplicate source response record_id")
            if row.get("config_sha256") != self.config_sha or row.get("batch_id") != self.config["batch_id"]:
                raise IntegrityError("Source response protocol changed")
            if not isinstance(row.get("code"), str) or row.get("code_sha256") != digest(row["code"].encode()):
                raise IntegrityError("Source response code checksum mismatch")
            if row.get("response", {}).get("model") != row["model"]:
                raise IntegrityError("Provider/model identity differs from the saved response")
            self.seen.add(rid)
            previous = self.all_measured.get(rid)
            if previous and previous.get("source_response_sha256") != line_sha:
                raise IntegrityError("A previously scored source response changed")
            if row["round"] not in self.allowed_rounds:
                continue
            self.candidates[rid] = {key: row[key] for key in ("record_id", "model", "task_id", "replicate", "arm", "round", "code", "code_sha256")}
            self.candidates[rid]["source_response_sha256"] = line_sha
        if len(self.seen) > self.expected_responses or len(self.candidates) > self.expected_holdouts:
            raise IntegrityError("Saved collection exceeds its precommitted size")
        if set(self.all_measured) - self.seen:
            raise IntegrityError("A measured holdout no longer has its matching source response")

    def append(self, filename, value):
        with self.io_lock:
            handle = self.handles[filename]
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
            handle.flush()
            if filename == "holdout-evaluations.jsonl":
                os.fsync(handle.fileno())

    def event(self, kind, rid=None, **fields):
        self.append("holdout-events.jsonl", {"timestamp": timestamp(), "event_type": kind,
                    "record_id": rid, "config_sha256": self.config_sha, **fields})

    def oracle(self, tid):
        with self.oracle_lock:
            if tid in self.oracle_cache:
                return self.oracle_cache[tid]
            task = self.tasks[tid]
            split = self.splits[tid]
            path = self.out / "oracles" / (tid.replace("/", "_") + ".pkl")
            meta = json.loads(path.with_suffix(".json").read_text())
            expected = {"task_id": tid, "config_sha256": self.config_sha,
                "dataset_sha256": self.plan["dataset_sha256"],
                "reference_code_sha256": self.plan["reference_code_sha256"],
                "runtime_sha256": self.plan["runtime_sha256"],
                "reference_spec_sha256": split["reference_spec_sha256"],
                "public_inputs_sha256": split["public_inputs_sha256"],
                "holdout_inputs_sha256": split["holdout_inputs_sha256"],
                "canonical_code_sha256": digest((task["prompt"] + task["canonical_solution"]).encode()),
                "public_cases": len(task["base_input"]), "holdout_cases": len(task["plus_input"]),
                "reference_pass": True, "sandboxed": True}
            if any(meta.get(key) != value for key, value in expected.items()):
                raise IntegrityError("Reference oracle metadata mismatch: " + tid)
            blob = path.read_bytes()
            if digest(blob) != meta.get("oracle_sha256"):
                raise IntegrityError("Reference oracle payload checksum mismatch: " + tid)
            value = pickle.loads(blob)
            if not valid_oracle(value, task):
                raise IntegrityError("Reference oracle counts do not match the frozen tests: " + tid)
            self.oracle_cache[tid] = (value, meta)
            return value, meta

    def score(self, row):
        self.assert_frozen()
        oracle, metadata = self.oracle(row["task_id"])
        try:
            result = evaluate_resolved(self.evaluation_config, self.tasks[row["task_id"]], row["code"], oracle,
                                       include_holdout=True, run_dir=self.out, record_id=row["record_id"])
        except (RuntimeError, OSError) as error:
            self.assert_frozen()
            return {"known": False, "reason": type(error).__name__ + ": " + str(error)[:1500]}
        self.assert_frozen()
        if not known_strong(result, self.tasks[row["task_id"]]):
            return {"known": False, "reason": result.get("infrastructure_status") or result.get("public", {}).get("infrastructure_status") or result.get("hidden", {}).get("infrastructure_status") or "incomplete_strong_evaluation",
                    "checked": {name: {key: result.get(name, {}).get(key) for key in ("complete", "cases_checked", "total_cases")} for name in ("public", "hidden")}}
        identity = {key: row[key] for key in ("record_id", "model", "task_id", "replicate", "arm", "round")}
        measured = {**identity, **result, "timestamp": timestamp(), "batch_id": self.config["batch_id"],
                    "config_sha256": self.config_sha, "source_response_sha256": row["source_response_sha256"],
                    "code_sha256": row["code_sha256"], "oracle_sha256": metadata["oracle_sha256"],
                    "reference_code_sha256": self.plan["reference_code_sha256"],
                    "holdout_runner_sha256": self.runner_sha, "holdout_inputs_sha256": metadata["holdout_inputs_sha256"],
                    "resource_policy_sha256": self.resource_policy_sha,
                    "holdout_policy": {key: self.evaluation_config[key] for key in ("evaluation_timeout_s", "cpu_limit_s", "split_time_budget_s", "holdout_stop_on_failure")}}
        return {"known": True, "row": measured}

    def status(self, active=0, stopped=False, fatal=None):
        by_model = {}
        for model in self.config["models"]:
            rows = [row for row in self.measured.values() if row["model"] == model]
            by_model[model] = {"measured": len(rows), "passed": sum(row["full_pass"] for row in rows),
                               "failed": sum(not row["full_pass"] for row in rows)}
        unresolved = set(self.candidates) - set(self.measured)
        complete = (len(self.seen) == self.expected_responses and len(self.measured) == self.expected_holdouts
                    and not self.reader.buffer and not unresolved and not fatal)
        result = {"timestamp": timestamp(), "batch_id": self.config["batch_id"], "config_sha256": self.config_sha,
                  "schema": "code-repair-holdout-status-v2", "complete": complete,
                  "source_responses": len(self.seen), "expected_responses": self.expected_responses,
                  "candidates_available": len(self.candidates), "expected_holdouts": self.expected_holdouts,
                  "measurement_scope": self.measurement_scope, "scheduler_concurrency": self.workers,
                  "expected_primary_holdouts": self.expected_primary_holdouts,
                  "measured_primary_holdouts": sum(row["round"] in (0, self.final_round) for row in self.all_measured.values()),
                  "measured": len(self.measured), "passed": sum(row["full_pass"] for row in self.measured.values()),
                  "failed": sum(not row["full_pass"] for row in self.measured.values()), "by_model": by_model,
                  "active": active, "pending_available": len(unresolved),
                  "unknown_unresolved": len(unresolved & self.unknown_ids),
                  "unknown_attempts": self.unknown_attempts, "incomplete_response_tail": bool(self.reader.buffer),
                  "stopped": stopped, "fatal": fatal, "api_calls": 0,
                  "seconds": round(time.monotonic() - self.started, 3)}
        atomic_json(self.out / "holdout-status.json", result)
        return result

    def run(self, watch=False):
        pending = {}
        active_ids = set()
        attempted_this_pass = set()
        snapshot_size = self.reader.path.stat().st_size if self.reader.path.exists() else 0
        next_poll = 0
        next_status = 0
        pool = ThreadPoolExecutor(max_workers=self.workers)
        try:
            while True:
                now = time.monotonic()
                if now >= next_poll and (watch or not self.seen):
                    self.assert_frozen()
                    self.ingest(None if watch else snapshot_size)
                    next_poll = now + self.poll_seconds
                for future in [future for future in pending if future.done()]:
                    rid = pending.pop(future)
                    active_ids.remove(rid)
                    scored = future.result()
                    if scored["known"]:
                        if rid in self.measured:
                            raise IntegrityError("Attempted to append a duplicate measured holdout")
                        self.append("holdout-evaluations.jsonl", scored["row"])
                        self.measured[rid] = scored["row"]
                        self.all_measured[rid] = scored["row"]
                        self.event("holdout_measured", rid, full_pass=scored["row"]["full_pass"])
                    else:
                        self.unknown_attempts += 1
                        self.unknown_ids.add(rid)
                        self.event("holdout_unknown", rid, attempt=self.attempts[rid], **{key: value for key, value in scored.items() if key != "known"})
                        self.retry_at[rid] = time.monotonic() + min(300, self.poll_seconds * 2 ** min(self.attempts[rid] - 1, 5))
                if not self.stop.is_set():
                    for rid, row in self.candidates.items():
                        if len(pending) >= self.workers:
                            break
                        if rid in self.measured or rid in active_ids or (not watch and rid in attempted_this_pass) or time.monotonic() < self.retry_at.get(rid, 0):
                            continue
                        self.attempts[rid] += 1
                        attempted_this_pass.add(rid)
                        self.event("holdout_started", rid, attempt=self.attempts[rid])
                        future = pool.submit(self.score, row)
                        pending[future] = rid
                        active_ids.add(rid)
                state = self.status(len(pending), self.stop.is_set()) if now >= next_status else None
                if state is not None:
                    print(json.dumps(state, ensure_ascii=False), flush=True)
                    next_status = now + self.poll_seconds
                if not pending:
                    if self.stop.is_set() or (not watch and all(rid in self.measured or rid in attempted_this_pass for rid in self.candidates)):
                        break
                    if watch and self.status()["complete"]:
                        break
                if pending:
                    wait(pending, timeout=.5, return_when=FIRST_COMPLETED)
                else:
                    self.stop.wait(min(self.poll_seconds, max(.01, next_poll - time.monotonic())))
            state = self.status(stopped=self.stop.is_set())
            print(json.dumps(state, ensure_ascii=False), flush=True)
            return state
        except BaseException as error:
            self.stop.set()
            for future in pending:
                future.cancel()
            self.status(len(pending), stopped=True, fatal=type(error).__name__ + ": " + str(error)[:1500])
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
            self.close()

    def close(self):
        for handle in getattr(self, "handles", {}).values():
            handle.close()
        if not self.lock.closed:
            self.lock.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--all-rounds", action="store_true", help="Also measure intermediate versions; primary metric and public feedback are unchanged")
    parser.add_argument("--concurrency", type=int, help="Scheduling-only worker override (1 to 32); does not modify the frozen configuration")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--watch", action="store_true")
    mode.add_argument("--once", action="store_true", help="Default: score the currently saved complete lines")
    args = parser.parse_args(argv)
    stop = threading.Event()
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_: stop.set())
    runner = HoldoutRunner(args.config, stop=stop, all_rounds=args.all_rounds, concurrency=args.concurrency)
    state = runner.run(watch=args.watch)
    return 130 if state["stopped"] else 2 if state["pending_available"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
