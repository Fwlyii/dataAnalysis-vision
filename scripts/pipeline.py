"""Offline coursework pipeline. Collection is deliberately outside this command."""
from pathlib import Path
import argparse,subprocess,sys,shlex
ROOT=Path(__file__).resolve().parents[1]
STAGES={
 'clean':['scripts/cleaning/verify_source_inputs.py','scripts/cleaning/clean_baseline_data.py','scripts/cleaning/clean_experiment_records.py','scripts/cleaning/build_unified_features.py'],
 'analyze':['scripts/analysis/analyze_baselines.py','scripts/system/export_baseline_features.py','scripts/analysis/export_question_clusters.py','scripts/cleaning/classify_and_audit.py','scripts/cleaning/import_code_generation.py','scripts/analysis/analyze_prompt_variants.py','scripts/analysis/analyze_code_diagnostics.py','experiments/document_qa/src/analyze_document_positions.py','experiments/code_repair/src/analyze.py','scripts/analysis/build_story_evidence.py'],
 'figures':['scripts/figures/plot_baseline_figures.py','scripts/figures/plot_code_generation.py','scripts/figures/plot_story_figures.py','scripts/figures/plot_story_figures.py --mobile','scripts/figures/plot_narrative_figures.py'],
 'web':['scripts/system/build_web_app.py'],
 'documents':['scripts/delivery/build_course_documents.py'],
}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['snapshot','clean','analyze','figures','web','documents','all']);p.add_argument('--plan',action='store_true');a=p.parse_args()
 selected=['web'] if a.stage=='snapshot' else list(STAGES) if a.stage=='all' else [a.stage]
 for stage in selected:
  for script in STAGES[stage]:
   print(f'[{stage}] {script}',flush=True)
   if not a.plan:
    parts=shlex.split(script)
    subprocess.run([sys.executable,str(ROOT/parts[0]),*parts[1:]],cwd=ROOT,check=True)
 print('Model API requests: 0. Generated-code execution: 0.',flush=True)
if __name__=='__main__':main()
