#!/usr/bin/env python3
"""Package a completed local run without changing its append-only evidence."""
import argparse
from collections import Counter
import csv
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(2**20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    progress = json.loads((source / 'progress.json').read_text())
    assert progress['state'] == 'completed' and progress['completed'] == 74800
    scenarios = {}
    with (source / 'scenarios.jsonl').open() as f:
        for line in f:
            r = json.loads(line)
            assert r['scenario_id'] not in scenarios
            assert hashlib.sha256(r['prompt_text'].encode()).hexdigest() == r['prompt_sha256']
            scenarios[r['scenario_id']] = (r['prompt_sha256'], r['answers'])
    assert len(scenarios) == 37400
    seen, counts, coverage, statuses = set(), Counter(), Counter(), Counter()
    examples = []
    secret = re.compile(rb'(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{25,})')
    with (source / 'raw_responses.jsonl').open('rb') as f:
        for line in f:
            assert not secret.search(line), 'Credential-like content in raw response'
            r = json.loads(line)
            key = (r['model'], r['scenario_id'])
            assert key not in seen
            seen.add(key)
            assert (r['prompt_sha256'], r['answers']) == scenarios[r['scenario_id']]
            prompt = r['request']['messages'][0]['content']
            assert hashlib.sha256(prompt.encode()).hexdigest() == r['prompt_sha256']
            assert r['response']['model'] == r['model']
            counts[r['model']] += 1
            statuses[r['status']] += 1
            coverage[(r['task_type'], r['model'], r['prompt_id'], r['document_count'], r['position_label'])] += 1
            if (r['question_id'] in ['nq-001', 'nq-002', 'nq-003'] and
                r['document_count'] == 20 and r['position_label'] == 'middle' and
                r['prompt_id'] in ['NoCoT', 'DefaultCoT', 'WordLimit(25)']):
                examples.append(r)
    assert len(seen) == 74800 and set(counts.values()) == {37400}
    assert statuses == {'ok': 74800}
    assert len(coverage) == 374 and set(coverage.values()) == {200}
    assert len(examples) == 18
    checksums = {}
    for name, dest in [('raw_responses.jsonl', 'data/raw_responses.jsonl.gz'),
                       ('scenarios.jsonl', 'data/scenarios.jsonl.gz'),
                       ('attempt_log.jsonl', 'data/attempt_log.jsonl.gz'),
                       ('results.csv', 'derived/collector_results.csv.gz'),
                       ('review_queue.jsonl', 'derived/review_queue.jsonl.gz')]:
        original, packed = source / name, ROOT / dest
        with original.open('rb') as src, packed.open('wb') as target:
            with gzip.GzipFile(filename='', fileobj=target, mode='wb', mtime=0) as gz:
                shutil.copyfileobj(src, gz, length=2**20)
        checksums[dest] = {'sha256': sha(packed), 'bytes': packed.stat().st_size,
                           'uncompressed_sha256': sha(original), 'uncompressed_bytes': original.stat().st_size}
    for name, dest in [('progress.json', 'derived/collection_progress.json'),
                       ('summary.json', 'derived/collector_summary.json'),
                       ('manifest.json', 'data/manifest.json'),
                       ('cache/pricing-confirmation.json', 'data/pricing_at_collection.json')]:
        shutil.copyfile(source / name, ROOT / dest)
    (ROOT / 'data' / 'CHECKSUMS.json').write_text(json.dumps(checksums, indent=2) + '\n')
    verification = {'verified_at': dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds'),
                    'finished_at': progress['updated_at'], 'state': 'completed', 'records': len(seen),
                    'models': dict(counts), 'statuses': dict(statuses), 'scenario_definitions': len(scenarios),
                    'groups': len(coverage), 'records_per_group': 200,
                    'checks': ['unique model/scenario keys', 'full planned coverage', 'request/scenario SHA-256 agreement',
                               'response model IDs', 'official answer labels unchanged', 'credential pattern scan']}
    (ROOT / 'derived' / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
    with (ROOT / 'derived' / 'coverage.csv').open('w', newline='') as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(['task_type', 'model', 'prompt_id', 'document_count', 'position_label', 'records'])
        writer.writerows([*key, n] for key, n in sorted(coverage.items()))
    text = ['# 三道示例题 × 三种策略 × 两个模型的完整原始输出', '',
            '固定条件：20 篇资料，gold 在第 10 篇。下列 18 条按预先固定的题目和策略选择，包含错误回答；没有按正确率筛选。', '']
    for r in sorted(examples, key=lambda x: (x['question_id'], x['model'], x['prompt_id'])):
        content = r['response']['choices'][0]['message'].get('content') or ''
        text += [f"## {r['question_id']} | {r['model']} | {r['prompt_id']}", '',
                 '问题：' + r['question'], '', '官方答案：' + json.dumps(r['answers'], ensure_ascii=False), '',
                 '场景：`' + r['scenario_id'] + '`；prompt SHA-256：`' + r['prompt_sha256'] + '`。', '',
                 '```text', content, '```', '']
    (ROOT / 'docs' / '05-output-examples.md').write_text('\n'.join(text), encoding='utf-8')
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
