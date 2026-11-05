from pathlib import Path
import json,csv,sys,statistics
ROOT=Path.cwd().resolve();sys.path.insert(0,str(ROOT))
from experiments.code_repair_v2.src.analyze import records,ClusterBootstrap,Figure,write_csv,write_json,COLORS
from experiments.code_repair_v2.src.legacy_reevaluate import ARMS,LABELS
scratch=ROOT.parent/'repair_v2/legacy';dest=ROOT/'reports/code_repair_extension/legacy-full-recheck'
audit=json.loads((dest/'reverse-change-audit.json').read_text())
if audit.get('count') != 4 or not all(v.get('full_pass') is True for r in audit['rows'] for v in r['old_worker_current_runtime_repeat_results']):
 raise ValueError('Explanatory reruns differ from this finalized report: review timing evidence before generating its interpretation')
for r in audit['rows']:
 r['reference_budget_changed']=abs(r['old_case_timeout_seconds']-r['new_case_timeout_seconds'])>1e-6
 r['diagnosis']='historical_timeout_not_reproduced_with_original_worker_and_oracle'
 r['interpretation']='Both current-runtime reruns passed with the original worker, original Mini inputs, original oracle and original timeout formula. Historical timing failure is real but not reproduced; reference-budget differences alone are not established as its cause. No extraction, syntax or semantic-oracle change for this reversal.'
write_json(dest/'reverse-change-audit.json',audit);write_csv(dest/'reverse-change-audit.csv',audit['rows'])
scores={r['record_id']:r for r in records(scratch/'strong-evaluations.jsonl')}
scores.update({r['record_id']:r for r in records(scratch/'strong-resolution-overlays.jsonl')})
raw=records(scratch/'responses.jsonl');idx={(r['model'],r['task_id'],r['arm'],int(r['round'])):r['record_id'] for r in raw}
models=sorted({r['model'] for r in raw});tasks=sorted({r['task_id'] for r in raw},key=lambda x:int(x.split('/')[-1]));boot=ClusterBootstrap(tasks,5000,20261105)
contrasts=[]
for model in models+['__pooled__']:
 selected=models if model=='__pooled__' else [model]
 for ia,arm in enumerate(ARMS):
  for baseline in ARMS[:ia]:
   bytask={};wins=losses=ties=0
   for task in tasks:
    diffs=[]
    for m in selected:
     a=scores[idx[m,task,arm,4]]['full_pass'];b=scores[idx[m,task,baseline,4]]['full_pass'];d=int(a)-int(b)
     diffs.append(d);wins+=d>0;losses+=d<0;ties+=d==0
    bytask[task]=statistics.fmean(diffs)
   ci=boot.mean(bytask)
   contrasts.append({'model':model,'arm':arm,'baseline':baseline,'task_clusters':164,'paired_programs':164*len(selected),
    'arm_wins':wins,'baseline_wins':losses,'ties':ties,'delta_pp':statistics.fmean(bytask.values())*100,
    'ci_low_pp':ci[0]*100,'ci_high_pp':ci[1]*100,'interval_note':'95% paired task-cluster bootstrap; exploratory, no multiplicity adjustment'})
write_csv(dest/'strong-contrasts.csv',contrasts)
from redraw_legacy import redraw
redraw(dest)
lines=['','## 反向变化核查','',
'5,576 份候选中，40 份由 Mini PASS 变为完整强测 FAIL，另有 4 份由 Mini FAIL 变为 PASS；公开诊断分数变化为 0。四条反向均为原隐藏测试 `TimeoutException`，相同失败输入仍保留在新集合中，期望输出一致。使用原 worker、原 Mini 输入、原 oracle 和原逐例时间公式在当前运行时各复跑两次，8 次全部通过。历史超时未复现，不能把这些变化解释为新增测试提高了代码正确性。',
'','| 候选 | 原／新逐例限时（秒） | 原 worker 两次复跑总时长（秒） | 诊断 |','|---|---:|---:|---|']
for r in audit['rows']:
 durations=' / '.join(f'{v["evaluation_seconds"]:.4f}' for v in r['old_worker_current_runtime_repeat_results'])
 label=f'{r["model"].split("/")[-1]} · {r["task_id"]} · {LABELS[r["arm"]]} · 第{r["round"]}次修改'
 lines.append(f'| {label} | {r["old_case_timeout_seconds"]:.4f} / {r["new_case_timeout_seconds"]:.4f} | {durations} | 原超时未复现，两次均通过 |')
lines+=['','HumanEval/15 与 83 的 canonical 参考计时、相应逐例预算有变化；147 的预算同为 1 秒。因为四条在原预算下也均通过，这些预算差异不能被确认为反向变化的唯一原因。新旧评测属于不同运行时和资源环境下的复核，应将“新增测试暴露错误”与“时间测量变化”分别解释。',
'','四条反向均不属于 Qwen3 的“单反例 vs 自行检查”终稿对照；其强测 138/164 vs 128/164 的方向不依赖这四条。',
'','## 终稿强测的配对对照','', '| 模型 | 对照 | 赢／输／平 | 差值 pp | 95%区间 pp |','|---|---|---:|---:|---:|']
for r in contrasts:
 if r['arm']=='counterexample' and r['baseline']=='self_review' and r['model']!='__pooled__':
  lines.append(f'| {r["model"].split("/")[-1]} | 单反例 − 自行检查 | {r["arm_wins"]}/{r["baseline_wins"]}/{r["ties"]} | {r["delta_pp"]:+.2f} | [{r["ci_low_pp"]:+.2f}, {r["ci_high_pp"]:+.2f}] |')
lines+=['','区间按 164 道题配对 bootstrap；本轮仅复核旧实验每题每模型的一份初稿，不能替代正在采集的三份独立初稿，也不能由两个模型推断普适规律。',
'','资源中断修正单独见 `resource-resolution-audit.json`；原始未知记录保留，canonical 同预算全过后候选两次内存违规才确定任务失败，未检查用例仍为未测。',
'','复核源码与哈希见 `reverse-change-audit.json`；原始执行记录、隐藏答案保留在外部工作目录，未写入此导出。','']
base=(dest/'findings.md').read_text().split('\n## 反向变化核查')[0].rstrip()
(dest/'findings.md').write_text(base+'\n'+'\n'.join(lines))
print(json.dumps([r for r in contrasts if r['arm']=='counterexample' and r['baseline']=='self_review' and r['model']!='__pooled__'],ensure_ascii=False))
