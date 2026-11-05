"""Re-evaluate saved v1 programs on the pinned stronger v2 held-out tests.

No model API requests. The legacy Git/LFS files and reports stay read-only.
Outputs identify this as retrospective evaluation, never feedback available to
the models during the old collection. Candidate execution uses only the frozen
macOS evaluator and verified canonical-reference caches.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import csv
import fcntl
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import pickle
import re
import signal
import sys
import threading
import time

from .analyze import ClusterBootstrap, records, strong_observed, split_observed, write_csv
from .dataset import ROOT, load_benchmark
from .evaluator import evaluate
from .prepare import atomic_json, source_hashes, valid_oracle

LEGACY_SHA = "c3642543bf926adc566f6d1ca28dc062d36ecf76dbd3e69f56e320e1ba9b0008"
LEGACY_SIZE = 41281976
ARMS = ("resample", "self_review", "pass_fail", "counterexample")
LABELS = {"resample":"独立重采样", "self_review":"自行检查", "pass_fail":"仅通过状态", "counterexample":"单个失败反例"}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def safe_error(error):
    return re.sub(r"(?:sk-[A-Za-z0-9_-]{20,}|Bearer\s+[^\s]+)", "[REDACTED]", type(error).__name__ + ": " + str(error))[:1200]


def frozen_features():
    """The logical v1 CSV repeats seeds; collapse only identical physical IDs."""
    path = ROOT / "data/processed/code_repair/full/features.csv"
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = row["physical_record_id"]
            value = {"full_pass":row["full_pass"] == "true", "diagnostic_pass":row["diagnostic_pass"] == "true",
                     "hidden_pass":row["hidden_pass"] == "true", "public_error_type":row["public_error_type"]}
            if key in rows and rows[key] != value:
                raise ValueError("Conflicting legacy shared-seed features")
            rows[key] = value
    return rows, sha(path.read_bytes())


def without_hidden_answers(result):
    """Persist verdict/count evidence without exposing sealed case payloads."""
    result = dict(result)
    if result.get("hidden") is not None:
        hidden = dict(result["hidden"])
        case_payload = {key:hidden.pop(key) for key in ("failures", "first_failure") if key in hidden}
        hidden["failure_payload_sha256"] = sha(json.dumps(case_payload, sort_keys=True, ensure_ascii=False).encode())
        result["hidden"] = hidden
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=ROOT.parent / "repair_v2/legacy/responses.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT.parent / "repair_v2/legacy")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=2, help="bounded retry for incomplete infrastructure outcomes")
    parser.add_argument("--deduplicate-identical-code", action="store_true",
                        help="evaluate each exact task/code once and explicitly link reused results; counts remain physical candidates")
    args = parser.parse_args(argv)
    if not 1 <= args.concurrency <= 8 or not 1 <= args.attempts <= 3:
        raise ValueError("Concurrency must be1..8; attempts must be1..3")
    config_path = args.config.resolve()
    config_blob = config_path.read_bytes()
    config = json.loads(config_blob)
    source, out = args.source.resolve(), args.output.resolve()
    protected = ROOT / "data/raw/code_repair"
    if out == protected or protected in out.parents or (ROOT / "reports/code_repair") in out.parents:
        raise ValueError("Retrospective results must not overwrite legacy data/reports")
    blob = source.read_bytes()
    if len(blob) != LEGACY_SIZE or sha(blob) != LEGACY_SHA:
        raise ValueError("Legacy response payload differs from its protected Git LFS OID/size")
    rows = [json.loads(line) for line in blob.decode("utf-8").splitlines() if line.strip()]
    indexed = {row["record_id"]:row for row in rows}
    if len(rows) != len(indexed) or len(rows) != 5576 or sum(int(row["round"]) == 0 for row in rows) != 328:
        raise ValueError("Legacy response/seed count differs from the frozen experiment")
    old, old_features_sha = frozen_features()
    if set(old) != set(indexed):
        raise ValueError("Legacy physical feature IDs do not exactly match the response payload")
    tasks_list, manifest = load_benchmark(config)
    tasks = {task["task_id"]:task for task in tasks_list}
    run_dir = Path(config["run_dir"])
    run_dir = run_dir if run_dir.is_absolute() else ROOT / run_dir
    plan = json.loads((run_dir / "plan.json").read_text())
    preflight = json.loads((run_dir / "reference-preflight.json").read_text())
    config_sha = sha(config_blob)
    if (plan.get("config_sha256") != config_sha or not preflight.get("complete")
            or preflight.get("config_sha256") != config_sha or preflight.get("reference_complete") != 164):
        raise ValueError("A complete matching strong-reference preflight is required")
    sources = source_hashes()
    if sources != plan["reference_source_hashes"]:
        raise ValueError("Frozen evaluator/reference source files changed")
    if manifest["split_manifest_sha256"] != plan["manifest"]["split_manifest_sha256"]:
        raise ValueError("Strong benchmark split differs from frozen plan")
    settings = dict(config)
    settings["evaluation_timeout_s"] = config.get("holdout_timeout_s", 300)
    settings["cpu_limit_s"] = max(int(settings["evaluation_timeout_s"]) - 5, 1)
    settings["split_time_budget_s"] = max(float(settings["evaluation_timeout_s"]) - 5, 1)
    settings["holdout_stop_on_failure"] = True
    out.mkdir(parents=True, exist_ok=True)
    lock = (out / ".reevaluation.lock").open("w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    frozen = {"schema":"legacy-code-repair-strong-reevaluation-v1", "source_sha256":LEGACY_SHA,
              "source_bytes":LEGACY_SIZE, "source_records":5576, "source_initial_programs":328,
              "source_features_sha256":old_features_sha, "new_config_sha256":config_sha,
              "benchmark_split_sha256":manifest["split_manifest_sha256"],
              "dataset_sha256":manifest["dataset_sha256"], "reference_source_hashes":sources,
              "runtime_sha256":plan["runtime_sha256"],
              "evaluation_settings":{key:settings[key] for key in ("python_executable","evaluation_timeout_s","cpu_limit_s","split_time_budget_s","holdout_stop_on_failure")},
              "feedback_changed":False, "model_api_calls":0,
              "evaluation_policy":"All5576 saved physical candidates, initial programs once; no new generations and no source outcome selection",
              "exact_code_reuse":args.deduplicate_identical_code,
              "interpretation":"Retrospective full-test re-evaluation, not feedback available during original collection"}
    plan_path = out / "reevaluation-plan.json"
    if plan_path.is_file():
        previous = json.loads(plan_path.read_text())
        if any(previous.get(key) != value for key,value in frozen.items()):
            raise ValueError("Existing retrospective batch uses another frozen protocol")
    else:
        atomic_json(plan_path, {**frozen,"created_at_utc":now()})
    path = out / "strong-evaluations.jsonl"
    existing = records(path)
    result_rows = {}
    for row in existing:
        rid = row["record_id"]
        if rid in result_rows or rid not in indexed:
            raise ValueError("Unexpected or duplicate retrospective record ID")
        if row.get("code_sha256") != indexed[rid]["code_sha256"]:
            raise ValueError("Saved retrospective evaluation belongs to another program")
        result_rows[rid] = row
    # Unknown outcomes stay in attempts and are re-evaluated on resume. They
    # never become model failures and are never duplicated in the final JSONL.
    retry_unknown = {rid:row for rid,row in result_rows.items() if not strong_observed(row)}
    known = {rid:row for rid,row in result_rows.items() if strong_observed(row)}
    if retry_unknown:
        with (out / "strong-attempts.jsonl").open("a", encoding="utf-8") as stream:
            for row in retry_unknown.values():
                stream.write(json.dumps({"event":"resume_unknown",**row},ensure_ascii=False)+"\n")
        temp = path.with_suffix(".tmp")
        temp.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in known.values()))
        temp.replace(path)
    result_rows = known
    started = time.monotonic()
    stop = threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):
        signal.signal(sig,lambda *_:stop.set())
    (out / "reevaluation.pid").write_text(str(os.getpid()) + "\n")
    io_lock = threading.RLock()
    output_handle = path.open("a",encoding="utf-8")
    attempt_handle = (out / "strong-attempts.jsonl").open("a",encoding="utf-8")
    actual_executions = 0
    job_errors = []

    @lru_cache(maxsize=8)
    def oracle(tid):
        stem=tid.replace("/","_")
        cache=run_dir/"oracles"/(stem+".pkl")
        metadata=json.loads(cache.with_suffix(".json").read_text())
        data=cache.read_bytes()
        if (metadata.get("oracle_sha256")!=sha(data) or metadata.get("config_sha256")!=config_sha
                or metadata.get("reference_pass") is not True or metadata.get("runtime_sha256")!=plan["runtime_sha256"]):
            raise ValueError("Unverified canonical oracle: "+tid)
        value=pickle.loads(data)
        if not valid_oracle(value,tasks[tid]):
            raise ValueError("Canonical oracle shape mismatch: "+tid)
        return value

    def persist(row):
        with io_lock:
            output_handle.write(json.dumps(row,ensure_ascii=False)+"\n");output_handle.flush()
            result_rows[row["record_id"]]=row

    def score_one(group):
        nonlocal actual_executions
        if stop.is_set():
            return
        representative=group[0]
        tid=representative["task_id"]
        original_code=representative["code"]
        code_hash=sha(original_code.encode())
        if code_hash!=representative["code_sha256"]:
            raise ValueError("Legacy saved-code hash differs")
        known_reuse=next((result_rows[row["record_id"]] for row in group if row["record_id"] in result_rows),None)
        last=None
        if known_reuse is not None and args.deduplicate_identical_code:
            last=known_reuse
        else:
            for attempt in range(1,args.attempts+1):
                if stop.is_set():
                    return
                try:
                    if source_hashes()!=sources:
                        stop.set()
                        raise RuntimeError("Frozen evaluation source changed during retrospective execution")
                    result=evaluate(settings,tasks[tid],original_code,oracle(tid),include_holdout=True)
                    with io_lock:
                        actual_executions+=1
                    last=without_hidden_answers(result)
                    with io_lock:
                        attempt_handle.write(json.dumps({"record_id":representative["record_id"],"attempt":attempt,
                            "updated_at_utc":now(),"strong_known":strong_observed(last),
                            "evaluation_seconds":last.get("evaluation_seconds"),
                            "infrastructure_status":last.get("infrastructure_status")},ensure_ascii=False)+"\n")
                        attempt_handle.flush()
                    if strong_observed(last):
                        break
                except Exception as error:
                    last={"sandboxed":False,"public":{"passed":False,"complete":False},
                          "infrastructure_status":safe_error(error)}
                    with io_lock:
                        attempt_handle.write(json.dumps({"record_id":representative["record_id"],"attempt":attempt,
                            "updated_at_utc":now(),"strong_known":False,"error":safe_error(error)},ensure_ascii=False)+"\n")
                        attempt_handle.flush()
            if last is None:
                return
        for source_row in group:
            if source_row["record_id"] in result_rows:
                continue
            result={**last,"record_id":source_row["record_id"],"model":source_row["model"],
                "task_id":tid,"arm":source_row["arm"],"round":int(source_row["round"]),
                "code_sha256":source_row["code_sha256"],"source_batch_id":source_row["batch_id"],
                "evaluation_scope":"retrospective_strong_holdout","reference_split_sha256":manifest["split_manifest_sha256"],
                "legacy_mini_full_pass":old[source_row["record_id"]]["full_pass"],
                "legacy_public_pass":old[source_row["record_id"]]["diagnostic_pass"],
                "reused_exact_code_result":args.deduplicate_identical_code and source_row["record_id"]!=representative["record_id"],
                "evaluated_representative_record_id":representative["record_id"] if args.deduplicate_identical_code else source_row["record_id"],
                "updated_at_utc":now()}
            persist(result)

    grouped=defaultdict(list)
    for row in rows:
        key=(row["task_id"],row["code_sha256"]) if args.deduplicate_identical_code else (row["record_id"],)
        grouped[key].append(row)
    jobs=[group for group in grouped.values() if any(row["record_id"] not in result_rows for row in group)]
    jobs.sort(key=lambda group:(int(group[0]["task_id"].split("/")[-1]),group[0]["model"],int(group[0]["round"])))

    def progress():
        with io_lock:
            known_count=sum(strong_observed(row) for row in result_rows.values())
            state={"updated_at_utc":now(),"source_physical_candidates":5576,"saved_records":len(result_rows),
                "known_strong_results":known_count,"unknown_results":len(result_rows)-known_count,
                "missing_records":5576-len(result_rows),"source_seeds":328,
                "exact_code_groups":len(grouped),"actual_new_sandbox_executions":actual_executions,
                "exact_code_reuse_enabled":args.deduplicate_identical_code,"concurrency":args.concurrency,
                "complete":known_count==5576,"seconds_this_process":round(time.monotonic()-started,2),
                "stopped":stop.is_set(),"job_errors":job_errors[-10:],"api_calls":0}
        atomic_json(out/"strong-status.json",state)
        print(json.dumps(state,ensure_ascii=False),flush=True)
        return state

    progress()
    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            pending={pool.submit(score_one,group):group[0]["record_id"] for group in jobs}
            last_progress=time.monotonic()
            while pending:
                finished,_=wait(pending,timeout=10,return_when=FIRST_COMPLETED)
                for future in finished:
                    rid=pending.pop(future)
                    try:
                        future.result()
                    except Exception as error:
                        job_errors.append({"record_id":rid,"error":safe_error(error)})
                if time.monotonic()-last_progress>=15:
                    progress();last_progress=time.monotonic()
                if stop.is_set():
                    for future in pending:
                        future.cancel()
        state=progress()
    finally:
        output_handle.close();attempt_handle.close()
    summarize(rows,old,result_rows,out,manifest,frozen)
    return 0 if state["complete"] and not job_errors else 2


def summarize(raw,old,scores,out,manifest,protocol):
    by_key={(row["model"],row["task_id"],row["arm"],int(row["round"])):row for row in raw}
    models=sorted({row["model"] for row in raw})
    tasks=sorted({row["task_id"] for row in raw},key=lambda task:int(task.split("/")[-1]))
    bootstrap=ClusterBootstrap(tasks,5000,20261105)
    curves,summary,changes,features=[],[],[],[]
    for source in raw:
        rid=source["record_id"];new=scores.get(rid);known=strong_observed(new)
        features.append({"record_id":rid,"model":source["model"],"task_id":source["task_id"],
            "arm":source["arm"],"round":source["round"],"legacy_mini_full_pass":old[rid]["full_pass"],
            "legacy_public_pass":old[rid]["diagnostic_pass"],"strong_known":known,
            "reevaluated_public_pass":new["public"]["passed"] if known else None,
            "strong_full_pass":new["full_pass"] if known else None,
            "hidden_pass":new["hidden"]["passed"] if known and split_observed(new.get("hidden")) else None,
            "hidden_cases_checked":(new.get("hidden") or {}).get("cases_checked") if new else None,
            "resource_resolution_overlay":bool((new or {}).get("resolution_overlay"))})
        if known and (old[rid]["full_pass"]!=new["full_pass"] or old[rid]["diagnostic_pass"]!=new["public"]["passed"]):
            changes.append({**features[-1],"public_verdict_changed":old[rid]["diagnostic_pass"]!=new["public"]["passed"],
                            "strong_pass_but_old_mini_fail":new["full_pass"] and not old[rid]["full_pass"]})
    for model in models:
        for arm in ARMS:
            trajectories=[]
            for task in tasks:
                seq=[by_key[model,task,"seed" if round_==0 else arm,round_] for round_ in range(5)]
                if all(strong_observed(scores.get(row["record_id"])) for row in seq):
                    trajectories.append(seq)
            cohort=[seq[0]["task_id"] for seq in trajectories]
            boot=ClusterBootstrap(cohort,5000,20261105)
            for round_ in range(5):
                old_values={seq[0]["task_id"]:float(old[seq[round_]["record_id"]]["full_pass"]) for seq in trajectories}
                new_values={seq[0]["task_id"]:float(scores[seq[round_]["record_id"]]["full_pass"]) for seq in trajectories}
                differences={task:new_values[task]-old_values[task] for task in cohort}
                interval=boot.mean(new_values);delta_ci=boot.mean(differences)
                curves.append({"model":model,"arm":arm,"round":round_,"task_clusters":len(cohort),
                    "planned_tasks":164,"legacy_mini_passed":sum(old_values.values()),"strong_passed":sum(new_values.values()),
                    "legacy_mini_rate":sum(old_values.values())/len(cohort) if cohort else None,
                    "strong_rate":sum(new_values.values())/len(cohort) if cohort else None,
                    "strong_ci":interval,"delta_pp":sum(differences.values())/len(cohort)*100 if cohort else None,
                    "delta_ci_pp":[v*100 for v in delta_ci] if delta_ci else None,
                    "scope":"retrospective_strong_test_not_original_feedback"})
            public_changed=0;old_mini_pass_new_fail=0;reverse=0;stop_pass=0;initial_pass=0;final_pass=0
            stable_public=[]
            for seq in trajectories:
                seed,final=seq[0]["record_id"],seq[-1]["record_id"]
                new=scores[final];initial_pass+=scores[seed]["full_pass"];final_pass+=new["full_pass"]
                public_changed+=old[final]["diagnostic_pass"]!=new["public"]["passed"]
                old_mini_pass_new_fail+=old[final]["full_pass"] and not new["full_pass"]
                reverse+=new["full_pass"] and not old[final]["full_pass"]
                if old[final]["diagnostic_pass"]==new["public"]["passed"]:
                    stable_public.append(final)
                # The delivery choice uses only the OLD diagnostic record.
                index=next((index for index,row in enumerate(seq) if old[row["record_id"]]["diagnostic_pass"]),4)
                stop_pass+=scores[seq[index]["record_id"]]["full_pass"]
            summary.append({"model":model,"arm":arm,"tasks":len(cohort),"planned_tasks":164,
                "legacy_final_pass":sum(old[seq[-1]["record_id"]]["full_pass"] for seq in trajectories),
                "strong_initial_pass":initial_pass,"strong_final_pass":final_pass,
                "old_mini_pass_strong_fail":old_mini_pass_new_fail,"strong_pass_old_mini_fail":reverse,
                "public_verdict_changed":public_changed,"final_public_stable_programs":len(stable_public),
                "stable_public_old_mini_pass":sum(old[rid]["full_pass"] for rid in stable_public),
                "stable_public_strong_pass":sum(scores[rid]["full_pass"] for rid in stable_public),
                "old_first_diagnostic_pass_policy_strong_success":stop_pass,
                "stopping_policy_source":"Original diagnostic scores only; strong re-evaluation never selects a version"})
    write_csv(out/"legacy-vs-strong-curves.csv",curves)
    write_csv(out/"legacy-vs-strong-summary.csv",summary)
    write_csv(out/"strong-verdict-changes.csv",changes)
    write_csv(out/"strong-features.csv",features)
    checks={**protocol,"complete":len(scores)==5576 and all(strong_observed(row) for row in scores.values()),
        "saved_results":len(scores),"known_results":sum(strong_observed(row) for row in scores.values()),
        "changed_program_verdicts":sum(row["legacy_mini_full_pass"]!=row["strong_full_pass"] for row in changes),
        "public_verdict_changes":sum(row["public_verdict_changed"] for row in changes),
        "strong_pass_old_mini_fail":sum(row["strong_pass_but_old_mini_fail"] for row in changes),
        "reference_compatibility":manifest["legacy_reference_spec"],"full_holdout_inputs":manifest["totals"]["holdout_count"],
        "source_worktree_pointer_unchanged":(ROOT/"data/raw/code_repair/code-repair-20261026-humaneval-mini/responses.jsonl").read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"),
        "hidden_case_answers_in_export":False}
    atomic_json(out/"strong-checks.json",checks)
    lines=['# 旧代码的完整保留测试复核','',
        '这是一轮事后评测；没有重新调用模型，没有把新测试反馈给旧模型，也没有覆盖旧报告。',
        f'5576份原始物理候选，目前{checks["known_results"]}份强测试结果已知。完整保留输入{checks["full_holdout_inputs"]}个，与公开诊断去重。',
        '', '| 模型 | 原处理 | 完整轨迹题数 | 原Mini终稿 | 强测终稿 | Mini过／强测失败 | 公开结果变动 |',
        '|---|---|---:|---:|---:|---:|---:|']
    for row in summary:
        lines.append(f'| {row["model"].split("/")[-1]} | {LABELS[row["arm"]]} | {row["tasks"]}/164 | {row["legacy_final_pass"]} | {row["strong_final_pass"]} | {row["old_mini_pass_strong_fail"]} | {row["public_verdict_changed"]} |')
    lines += ['', '统计与解释：', '',
        '- 只有五个版本强测齐全的同题轨迹进入该组曲线；缺失与基础设施未知不计模型失败。',
        '- 区间按题目配对bootstrap；初稿在四组逻辑视图复用，不增加物理响应或独立题数。',
        '- 新旧评测执行环境与资源策略已经固定记录。公开诊断结果变化的程序单独标记，不能把全部差异都归因于新增测试。',
        '- Strong通过但原Mini失败属于需要核对的反向变化，完整列表保留，不默默删去。',
        '- 首次诊断通过的停止策略只用原始诊断分数选版本，再查看此次强测，不能借保留结果挑选。',
        '- exact-code复用若启用，实际沙箱执行数与关联候选数分开报告；不是5576次独立执行。',
        '- 隐藏失败的输入／期望／实际值未写入本导出；保留结果永不进入反馈。','']
    (out/"findings.md").write_text('\n'.join(lines),encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
