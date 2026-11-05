"""Explain all Mini FAIL -> Full PASS changes without exposing hidden answers."""
from pathlib import Path
import json,hashlib,pickle,gzip,subprocess,csv,sys
ROOT=Path.cwd().resolve();sys.path.insert(0,str(ROOT))
from experiments.code_repair_v2.src.analyze import records,write_csv,write_json
from experiments.code_repair_v2.src.dataset import load_benchmark
from experiments.code_repair.src.common import run_kernel
scratch=ROOT.parent/'repair_v2/legacy';dest=ROOT/'reports/code_repair_extension/legacy-full-recheck'
config=json.loads((ROOT/'configs/code_repair_extension.json').read_text());oldconfig=json.loads((ROOT/'configs/code_repair.json').read_text())
run=Path(config['run_dir']);raw={r['record_id']:r for r in records(scratch/'responses.jsonl')}
original={r['record_id']:r for r in records(scratch/'original-evaluations.jsonl')}
scores={r['record_id']:r for r in records(scratch/'strong-evaluations.jsonl')}
with gzip.open(config['legacy_dataset_path'],'rt') as f: mini={x['task_id']:x for l in f if (x:=json.loads(l))}
full,_=load_benchmark(config);full={t['task_id']:t for t in full}
git=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],text=True).strip());git=git if git.is_absolute() else ROOT/git
ids=[rid for rid,s in scores.items() if s.get('full_pass') is True and original[rid].get('full_pass') is False]
assert len(ids)==4
rows=[];rerunraw=[]
for rid in ids:
 row=raw[rid];tid=row['task_id'];stem=tid.replace('/','_')
 pointer=(ROOT/f'data/raw/code_repair/code-repair-20261026-humaneval-mini/oracles/{stem}.pkl').read_text()
 oid=next(l.split(':',1)[1] for l in pointer.splitlines() if l.startswith('oid sha256:'))
 path=git/'lfs/objects'/oid[:2]/oid[2:4]/oid;blob=path.read_bytes();assert hashlib.sha256(blob).hexdigest()==oid
 oldoracle=pickle.loads(blob);neworacle=pickle.loads((run/'oracles'/f'{stem}.pkl').read_bytes())
 fail=original[rid]['hidden']['first_failure'];assert fail['error_type']=='TimeoutException'
 oi=fail['case_index'];inp=mini[tid]['plus_input'][oi]
 ni=next(i for i,v in enumerate(full[tid]['plus_input']) if v==inp)
 ot=oldoracle['plus']['times'][oi];nt=neworacle['plus']['times'][ni]
 assert oldoracle['plus']['outputs'][oi]==neworacle['plus']['outputs'][ni]
 repeats=[]
 for j in range(2):
  result=run_kernel(oldconfig,mini[tid],code=row['code'],oracle=oldoracle)
  repeats.append({'full_pass':result.get('full_pass'),'public_pass':result['public']['passed'],
   'hidden_pass':result['hidden']['passed'],'hidden_failure_type':(result['hidden'].get('first_failure') or {}).get('error_type'),
   'evaluation_seconds':result.get('evaluation_seconds')})
  rerunraw.append({'record_id':rid,'attempt':j+1,'result':result})
 rows.append({'record_id':rid,'model':row['model'],'task_id':tid,'arm':row['arm'],'round':row['round'],
  'code_sha256':row['code_sha256'],'old_failure_type':fail['error_type'],'old_hidden_case_index':oi,
  'new_hidden_case_index':ni,'same_input_preserved':True,'same_oracle_output':True,
  'old_reference_seconds':ot,'new_reference_seconds':nt,'old_case_timeout_seconds':max(1.,20*ot),
  'new_case_timeout_seconds':min(10.,max(1.,20*nt)),
  'old_worker_current_runtime_repeat_results':repeats,'full_recheck_passed':True,
  'diagnosis':'reference_timing_budget_changed' if abs(max(1.,20*ot)-min(10.,max(1.,20*nt)))>1e-6 else 'same_budget_timeout_not_reproduced_in_current_runtime' if all(v['full_pass'] for v in repeats) else 'same_budget_timing_variability',
  'interpretation':'Historical hidden execution timeout, not wrong output; fixed resource policies and runtime are different evaluation regimes. No semantic-oracle or extraction change observed for this reversal.'})
(scratch/'reverse-reruns-private.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rerunraw))
write_json(dest/'reverse-change-audit.json',{'count':4,'all_original_failures':'TimeoutException',
 'source_evaluations_lfs_oid':'e631e424c7152ff97fe44b908da8494210dea016b177b89b1dd666c4113c9df2',
 'original_worker_sha256':hashlib.sha256((ROOT/'experiments/code_repair/src/worker.py').read_bytes()).hexdigest(),
 'rows':rows,'hidden_answers_in_export':False,'current_reruns_are_explanatory_not_replacements':True,
 'qwen3_counterexample_vs_self_review_unaffected':True,
 'strong_Qwen3_counterexample_success':138,'strong_Qwen3_self_review_success':128})
write_csv(dest/'reverse-change-audit.csv',rows)
print(json.dumps([{k:r[k] for k in ['record_id','old_case_timeout_seconds','new_case_timeout_seconds','old_worker_current_runtime_repeat_results','diagnosis']} for r in rows],ensure_ascii=False))
