"""Build a new retrospective report from frozen base results plus an audited overlay."""
from pathlib import Path
import json,shutil,sys,hashlib
ROOT=Path.cwd().resolve();sys.path.insert(0,str(ROOT))
from experiments.code_repair_v2.src.analyze import records,strong_observed,write_json
from experiments.code_repair_v2.src.legacy_reevaluate import frozen_features,summarize,sha
scratch=ROOT.parent/'repair_v2/legacy';dest=ROOT/'reports/code_repair_extension/legacy-full-recheck'
config=json.loads((ROOT/'configs/code_repair_extension.json').read_text());run=Path(config['run_dir'])
plan=json.loads((run/'plan.json').read_text());protocol=json.loads((scratch/'reevaluation-plan.json').read_text())
raw=records(scratch/'responses.jsonl');old,_=frozen_features();base=records(scratch/'strong-evaluations.jsonl')
scores={r['record_id']:r for r in base};overlays=records(scratch/'strong-resolution-overlays.jsonl')
audit=records(scratch/'resource-audit.jsonl')
assert len(scores)==5576 and len(overlays)==1
for overlay in overlays:
 prior=scores[overlay['record_id']]
 assert overlay['original_evaluation_sha256']==sha(json.dumps(prior,sort_keys=True,ensure_ascii=False).encode())
 assert prior['code_sha256']==overlay['code_sha256'] and not strong_observed(prior)
 entry=next(e for e in audit if e['audit_id']==overlay['resource_resolution']['audit_id'])
 assert entry['decision']=='confirmed_candidate_resource_violation'
 assert entry['canonical_control']['passed_same_scope'] is True
 assert entry['candidate_code_sha256']==overlay['code_sha256']
 assert all(e['result'].get('infrastructure_status')=='memory_limit' for e in entry['evaluations'])
 for split in ['public','hidden']:
  retry=entry['evaluations'][-1]['result'].get(split,{})
  for key in ['cases_checked','passed_cases','failed_cases','blocked_cases','unchecked_cases']:
   assert overlay.get(split,{}).get(key)==retry.get(key)
 scores[overlay['record_id']]=overlay
assert all(strong_observed(r) for r in scores.values())
resolution={'schema':'legacy-retrospective-resource-resolution-v1','base_records':len(base),
 'base_known_results':sum(strong_observed(r) for r in base),'resolution_overlay_records':len(overlays),
 'resolved_known_results':len(scores),'complete':True,'model_api_calls':0,
 'original_scores_preserved':True,'frozen_evaluator_unchanged':True,
 'source_hashes_match_frozen_preflight':plan['reference_source_hashes'],
 'policy_version':overlays[0]['resource_policy_version'],'policy_sha256':overlays[0]['resource_policy_sha256'],
 'files_sha256':{p.name:sha(p.read_bytes()) for p in [scratch/'strong-evaluations.jsonl',scratch/'strong-resolution-overlays.jsonl',scratch/'resource-audit.jsonl',ROOT/'experiments/code_repair_v2/analysis/resolve_legacy_resource.py']},
 'resolutions':[{'record_id':o['record_id'],'task_id':o['task_id'],'candidate_code_sha256':o['code_sha256'],
   'original_evaluation_sha256':o['original_evaluation_sha256'],'audit_id':o['resource_resolution']['audit_id'],
   'decision':o['resource_resolution']['decision'],'canonical_control_passed':True,
   'candidate_memory_limit_reproduced':True,'public_cases_checked':o['public']['cases_checked'],
   'public_failed_cases':o['public']['failed_cases'],'hidden_outcome_known':o['hidden']['outcome_known'],
   'hidden_cases_checked':o['hidden']['cases_checked'],'joint_full_pass':o['full_pass']} for o in overlays],
 'interpretation':'A reproduced candidate memory violation settles task failure; unchecked cases remain unmeasured, with zero imputed failures. Canonical control passed under the exact same unchanged budget. No new feedback was sent to any model.'}
write_json(scratch/'resolved-status.json',resolution)
protocol={**protocol,'resource_resolution':{'policy_version':resolution['policy_version'],'overlay_records':len(overlays),
 'base_known_results':resolution['base_known_results'],'resolved_known_results':len(scores),'raw_scores_preserved':True}}
dest.mkdir(parents=True,exist_ok=True)
summarize(raw,old,scores,dest,plan['manifest'],protocol)
write_json(dest/'resource-resolution-audit.json',resolution)
shutil.copyfile(scratch/'reevaluation-plan.json',dest/'reevaluation-plan.json')
shutil.copyfile(ROOT/'experiments/code_repair_v2/src/resource_policy.py',dest/'resource_policy.py')
shutil.copyfile(ROOT/'experiments/code_repair_v2/analysis/resolve_legacy_resource.py',dest/'resolve_legacy_resource.py')
print(json.dumps({'report':str(dest),'complete':True,'known_results':len(scores)}))
