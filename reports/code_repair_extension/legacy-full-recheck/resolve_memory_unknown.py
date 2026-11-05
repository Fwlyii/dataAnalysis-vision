"""Audited retrospective-only overlay. No model calls; preserves raw scores."""
from pathlib import Path
import hashlib,json,pickle,shutil,sys
ROOT=Path.cwd().resolve();sys.path.insert(0,str(ROOT))
from experiments.code_repair_v2.src.analyze import records,strong_observed
from experiments.code_repair_v2.src.dataset import load_benchmark
from experiments.code_repair_v2.src.prepare import source_hashes,valid_oracle
from experiments.code_repair_v2.src.resource_policy import evaluate_resolved,POLICY_VERSION
from experiments.code_repair_v2.src.legacy_reevaluate import without_hidden_answers,sha
config_path=ROOT/'configs/code_repair_extension.json';config=json.loads(config_path.read_text())
run=Path(config['run_dir']);out=ROOT.parent/'repair_v2/legacy'
plan=json.loads((run/'plan.json').read_text())
assert sha(config_path.read_bytes())==plan['config_sha256']
assert source_hashes()==plan['reference_source_hashes']
raw={r['record_id']:r for r in records(out/'responses.jsonl')}
scores=records(out/'strong-evaluations.jsonl')
unknown=[r for r in scores if not strong_observed(r)]
assert len(scores)==5576 and len(unknown)==1
old=unknown[0];source=raw[old['record_id']]
assert source['task_id']=='HumanEval/108'
assert sha(source['code'].encode())==source['code_sha256']==old['code_sha256']
tasks,manifest=load_benchmark(config);task=next(t for t in tasks if t['task_id']==source['task_id'])
assert manifest['split_manifest_sha256']==plan['manifest']['split_manifest_sha256']
cache=run/'oracles/HumanEval_108.pkl';meta=json.loads(cache.with_suffix('.json').read_text())
assert sha(cache.read_bytes())==meta['oracle_sha256']
assert meta['reference_pass'] and meta['runtime_sha256']==plan['runtime_sha256']
oracle=pickle.loads(cache.read_bytes());assert valid_oracle(oracle,task)
(out/'oracles').mkdir(exist_ok=True)
shutil.copyfile(cache.with_suffix('.json'),out/'oracles/HumanEval_108.json')
settings=dict(config,evaluation_timeout_s=config.get('holdout_timeout_s',300),cpu_limit_s=295,split_time_budget_s=295,holdout_stop_on_failure=True)
result=evaluate_resolved(settings,task,source['code'],oracle,include_holdout=True,run_dir=out,record_id=source['record_id'])
overlay={**old,**without_hidden_answers(result),'record_id':source['record_id'],'resolution_overlay':True,
 'original_evaluation_sha256':sha(json.dumps(old,sort_keys=True,ensure_ascii=False).encode()),
 'resource_policy_sha256':sha((ROOT/'experiments/code_repair_v2/src/resource_policy.py').read_bytes()),
 'resource_policy_version':POLICY_VERSION,'feedback_changed':False}
path=out/'strong-resolution-overlays.jsonl'
assert not path.exists()
path.write_text(json.dumps(overlay,ensure_ascii=False)+'\n')
print(json.dumps({'strong_known':strong_observed(overlay),'full_pass':overlay.get('full_pass'),
 'decision':result.get('resource_resolution',{}).get('decision'),'overlay':str(path)},ensure_ascii=False))
