#!/usr/bin/env python3
"""Read a frozen prefix of the append-only log; never modify collection outputs."""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cache' / 'analysis-deps'))
TZ = dt.timezone(dt.timedelta(hours=8))
CORE = ['NoCoT', 'DefaultCoT', 'BeConcise', 'BulletPoints', 'WordLimit(25)',
        'WordLimit(100)', 'TokenLimit(100)', 'StepLimit(2)']
STRESS = ['OnlyNumbers', 'NoSpaces', 'NoProperGrammar', 'AbbreviateWords',
          'WordLimit(1)', 'CharLimit(10)', 'TokenLimit(10)']


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def jsonable(value):
    return json.loads(json.dumps(value, default=lambda x: x.item() if isinstance(x, np.generic) else str(x)))


def paired_stat(frame, first, second, metric):
    """Difference first - second, resampling independent question IDs as clusters."""
    pivot = frame.pivot(index=['question_id', 'prompt_id', 'document_count'],
                        columns='position_label', values=metric)
    if first not in pivot or second not in pivot:
        return {'pairs': 0}
    pairs = pivot[[first, second]].dropna().reset_index()
    if pairs.empty:
        return {'pairs': 0}
    pairs['difference'] = pairs[first].astype(float) - pairs[second].astype(float)
    return clustered_difference(pairs, first, second)


def clustered_difference(pairs, first, second):
    grouped = pairs.groupby('question_id')['difference'].agg(['sum', 'count'])
    sums = grouped['sum'].to_numpy(dtype=float)
    counts = grouped['count'].to_numpy(dtype=float)
    rng = np.random.default_rng(91)
    samples = rng.integers(0, len(sums), size=(5000, len(sums)))
    bootstrap = sums[samples].sum(axis=1) / counts[samples].sum(axis=1)
    low, high = np.quantile(bootstrap, [.025, .975])
    return {'pairs': len(pairs), 'independent_questions': len(grouped),
            'first_rate': float(pairs[first].mean()), 'second_rate': float(pairs[second].mean()),
            'difference_pp': float(pairs['difference'].mean() * 100),
            'cluster_bootstrap_95ci_pp': [float(low * 100), float(high * 100)]}


def analyze(snapshot_bytes=None):
    path = ROOT / 'raw_responses.jsonl'
    size = snapshot_bytes or path.stat().st_size
    with path.open('rb') as handle:
        raw = handle.read(size)
    if not raw.endswith(b'\n'):
        raw = raw[:raw.rfind(b'\n') + 1]
    official = load_module('official_metrics', ROOT / 'cache' / 'official-metrics.py')
    collector = load_module('collector_helpers', ROOT / 'source' / 'experiment.py')
    rows = []
    for line in raw.splitlines():
        record = json.loads(line)
        if record['status'] != 'ok':
            continue
        assert record['response']['model'] == record['model']
        grade = collector.grade(record)
        text = grade['text']
        extracted = grade['extracted_answer']
        repaired_empty_marker = False
        if extracted == '':
            marker = list(re.finditer(r'FINAL\s+ANSWER\s*:\s*', text, re.I))[-1]
            before = text[:marker.start()].strip()
            if '\n' not in before and len(before.split()) <= 30:
                extracted = before
                repaired_empty_marker = True
        aliases = record['answers']
        row = {k: record[k] for k in ['question_id', 'scenario_id', 'model', 'prompt_id',
                                      'document_count', 'position_label', 'task_type', 'timestamp', 'latency_s']}
        row.update(paper_firstline=official.best_subspan_em(text.split('\n')[0].strip(), aliases),
                   full_response_contains=official.best_subspan_em(text, aliases),
                   strict_final_em=int(any(official.normalize_answer(extracted) == official.normalize_answer(a)
                                           for a in aliases)) if extracted is not None else 0,
                   final_contains=official.best_subspan_em(extracted or '', aliases),
                   repaired_empty_marker=repaired_empty_marker,
                   extracted_answer=extracted, text=text, answers=json.dumps(aliases, ensure_ascii=False),
                   truncated=grade['truncated'], needs_review=grade['needs_review'],
                   input_tokens=record['response']['usage'].get('prompt_tokens'),
                   output_tokens=record['response']['usage'].get('completion_tokens'),
                   scope=collector.strategy_scope(record['prompt_id']))
        rows.append(row)
    data = pd.DataFrame(rows)
    assert not data.duplicated(['model', 'scenario_id']).any()
    main = data[data.task_type == 'document_qa']
    scopes = {'NoCoT': main[main.prompt_id == 'NoCoT'],
              'core8': main[main.prompt_id.isin(CORE)],
              'english19': main[main.scope == 'main_comparison']}
    result = {'snapshot_at': dt.datetime.now(TZ).isoformat(timespec='seconds'),
              'last_record_at': str(data.timestamp.max()),
              'analysis_dependencies': {'numpy': np.__version__, 'pandas': pd.__version__},
              'snapshot_raw_prefix_bytes': len(raw), 'snapshot_raw_prefix_sha256': hashlib.sha256(raw).hexdigest(),
              'source': 'raw_responses.jsonl', 'records': len(data),
              'by_model': data.groupby('model').size().to_dict(),
              'distinct_questions_by_model': data.groupby('model').question_id.nunique().to_dict(),
              'main_records': len(main), 'controls': len(data) - len(main),
              'repaired_empty_final_marker': int(data.repaired_empty_marker.sum()),
              'truncated': int(data.truncated.sum()),
              'paper_scoring': 'official pinned metrics.best_subspan_em on first response line, matching evaluate_qa_responses.py',
              'other_scores': 'strict_final_em repairs a short answer before an empty trailing marker; final_contains uses extracted final span',
              'position_rates': [], 'paired_positions': [], 'complete_triples': [],
              'length_pairs': [], 'prompt_pairs': [], 'model_pairs': [], 'strategies': []}
    for scope_name, subset in scopes.items():
        for (model, n, position), group in subset.groupby(['model', 'document_count', 'position_label']):
            result['position_rates'].append({'scope': scope_name, 'model': model, 'documents': int(n),
                'position': position, 'n': len(group), 'questions': int(group.question_id.nunique()),
                'paper_firstline': float(group.paper_firstline.mean()),
                'strict_final_em': float(group.strict_final_em.mean()),
                'final_contains': float(group.final_contains.mean())})
        for model, model_frame in subset.groupby('model'):
            for n in ['pooled', 10, 20]:
                frame = model_frame if n == 'pooled' else model_frame[model_frame.document_count == n]
                for metric in ['paper_firstline', 'strict_final_em', 'final_contains']:
                    for edge in ['front', 'back']:
                        result['paired_positions'].append({'scope': scope_name, 'model': model,
                            'documents': n, 'metric': metric, 'comparison': edge + '-middle',
                            **paired_stat(frame, edge, 'middle', metric)})
                pivot = frame.pivot(index=['question_id', 'prompt_id', 'document_count'],
                                    columns='position_label', values='paper_firstline')
                if all(pos in pivot for pos in ['front', 'middle', 'back']):
                    complete = pivot[['front', 'middle', 'back']].dropna()
                    result['complete_triples'].append({'scope': scope_name, 'model': model, 'documents': n,
                        'triples': len(complete), 'questions': int(complete.reset_index().question_id.nunique()),
                        'rates': complete.mean().to_dict()})
                lp = frame.pivot(index=['question_id', 'prompt_id', 'position_label'],
                                 columns='document_count', values='paper_firstline')
                if n == 'pooled' and 10 in lp and 20 in lp:
                    pairs = lp[[10, 20]].dropna().reset_index()
                    if len(pairs):
                        pairs['difference'] = pairs[10] - pairs[20]
                        result['length_pairs'].append({'scope': scope_name, 'model': model,
                            'comparison': '10docs-20docs', **clustered_difference(pairs, 10, 20)})
    for model, group in main[main.scope == 'main_comparison'].groupby('model'):
        for metric in ['strict_final_em', 'final_contains']:
            pivot = group.pivot(index=['question_id', 'document_count', 'position_label'],
                                columns='prompt_id', values=metric)
            if 'NoCoT' in pivot and 'DefaultCoT' in pivot:
                pairs = pivot[['DefaultCoT', 'NoCoT']].dropna().reset_index()
                pairs['difference'] = pairs.DefaultCoT - pairs.NoCoT
                result['prompt_pairs'].append({'model': model, 'metric': metric,
                    'comparison': 'DefaultCoT-NoCoT', **clustered_difference(pairs, 'DefaultCoT', 'NoCoT')})
    for scope_name, subset in scopes.items():
        for metric in ['paper_firstline', 'strict_final_em', 'final_contains']:
            pivot = subset.pivot(index=['question_id', 'prompt_id', 'document_count', 'position_label'],
                                 columns='model', values=metric)
            first, second = 'Qwen/Qwen3-8B', 'Qwen/Qwen2.5-7B-Instruct'
            pairs = pivot[[first, second]].dropna().reset_index()
            pairs['difference'] = pairs[first] - pairs[second]
            result['model_pairs'].append({'scope': scope_name, 'metric': metric,
                'comparison': 'Qwen3-Qwen2.5', **clustered_difference(pairs, first, second)})
    result['truncation_by_strategy'] = [{'model': model, 'strategy': prompt,
        'truncated': int(g.truncated.sum()), 'n': len(g)}
        for (model, prompt), g in main.groupby(['model', 'prompt_id']) if g.truncated.sum()]
    for (model, strategy), group in main.groupby(['model', 'prompt_id']):
        result['strategies'].append({'model': model, 'strategy': strategy, 'scope': group.scope.iloc[0],
            'n': len(group), 'paper_firstline': float(group.paper_firstline.mean()),
            'strict_final_em': float(group.strict_final_em.mean()), 'final_contains': float(group.final_contains.mean()),
            'mean_output_tokens': float(group.output_tokens.mean()), 'truncated': int(group.truncated.sum())})
    control = data[data.task_type == 'closedbook_control']
    result['control_rates'] = [{'model': model, 'n': len(g), 'paper_firstline': float(g.paper_firstline.mean())}
                               for model, g in control.groupby('model')]
    result['scoring_disagreement'] = [{'model': model, 'n': len(g),
        'full_positive_firstline_negative': int(((g.full_response_contains == 1) & (g.paper_firstline == 0)).sum()),
        'full_positive_strict_final_negative': int(((g.full_response_contains == 1) & (g.strict_final_em == 0)).sum())}
        for model, g in main[main.scope == 'main_comparison'].groupby('model')]
    result = jsonable(result)
    (ROOT / 'interim-analysis.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    data.drop(columns=['text']).to_csv(ROOT / 'interim-analysis-records.csv', index=False, encoding='utf-8-sig')
    show = {k: result[k] for k in ['snapshot_at', 'records', 'by_model', 'distinct_questions_by_model',
                                  'controls', 'truncated', 'repaired_empty_final_marker', 'control_rates', 'prompt_pairs', 'length_pairs']}
    show['NoCoT_position_rates'] = [r for r in result['position_rates'] if r['scope'] == 'NoCoT']
    show['pooled_english19_pairs'] = [r for r in result['paired_positions'] if r['scope'] == 'english19'
                                     and r['documents'] == 'pooled' and r['metric'] == 'paper_firstline']
    show['english19_triples'] = [r for r in result['complete_triples'] if r['scope'] == 'english19' and r['documents'] == 'pooled']
    print(json.dumps(show, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot-bytes', type=int)
    args = parser.parse_args()
    analyze(args.snapshot_bytes)
