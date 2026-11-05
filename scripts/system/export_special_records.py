"""Export anonymous numeric rows for the nine-position and repair studies.

Only the unified, saved numeric table is read. No source responses, model calls,
code execution or original record/question keys are included in the web snapshot.
If Git LFS has not hydrated the full table, the committed snapshot is reused.
"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
from collections import Counter

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'project.json').is_file())
SOURCE = ROOT / 'data/processed/all_records.csv.gz'
TARGET = ROOT / 'app/data/special-records.json.gz'
FIELDS = ['id', 'question', 'topic', 'model', 'documents', 'position', 'feedback',
          'round', 'metric', 'score', 'input_tokens', 'output_tokens',
          'latency_seconds', 'finish_reason', 'truncated', 'excluded']
TOPICS = {'document_positions': 'position', 'code_repair': 'feedback'}
EXPECTED = {'position': 3600, 'feedback': 5576}


def numeric(value):
    if value in ['', None]:
        return None
    value = float(value)
    return int(value) if value.is_integer() else value


def boolean(value):
    if value in ['', None]:
        return None
    if str(value).lower() in ['true', '1']:
        return True
    if str(value).lower() in ['false', '0']:
        return False
    raise ValueError('Unexpected boolean in saved numeric table')


def question_alias(topic, saved_key):
    prefix = 'D' if topic == 'position' else 'C'
    return prefix + hashlib.sha256(('lens-special-v1|' + topic + '|' + saved_key).encode()).hexdigest()[:10]


def chosen_example():
    path = ROOT / 'reports/code_repair/full/examples.json'
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    example = next((r for r in data if r.get('model') == 'Qwen3-8B'
                    and r.get('category') == 'feedback_repair'
                    and 'choose_num' in r.get('before_code', '')), None)
    if not example:
        return []
    def changed_block(code):
        lines = code.splitlines()
        for index, line in enumerate(lines):
            if line.strip() == 'if x > y:':
                return '\n'.join(lines[index:index + 2]).strip()
        return ''
    before, after = changed_block(example['before_code']), changed_block(example['after_code'])
    if not before or not after:
        return []
    failure = example['before_score']['public'].get('first_failure') or {}
    saved_key = hashlib.sha256(('code_repair|' + example['task_id']).encode()).hexdigest()[:24]
    return [{
        'id': 'repair-interval-boundary', 'title': '逆序区间：反例指出多余的交换操作',
        'question': question_alias('feedback', saved_key), 'model': 'qwen3',
        'feedback': 'counterexample', 'round': example['round'],
        'before': before, 'after': after,
        'input': failure.get('input'), 'expected': failure.get('expected'),
        'actual': failure.get('actual'),
        'passed_after': bool(example['after_score']['full_pass']),
        'note': '摘自项目已有的精选修复案例，只展示关键改行与失败用例，不含原始对话全文或源记录键。',
    }]


def build():
    hydrated = SOURCE.is_file() and SOURCE.open('rb').read(2) == b'\x1f\x8b'
    if not hydrated:
        if not TARGET.is_file():
            raise FileNotFoundError('Full numeric table is not hydrated and anonymous snapshot is missing.')
        existing = json.loads(gzip.decompress(TARGET.read_bytes()))
        if existing.get('schema') != 'lens-special-records-v1' or existing.get('counts') != EXPECTED:
            raise ValueError('Unexpected committed special-record snapshot.')
        return {'snapshot_reused': True, 'counts': existing['counts'], 'rows': len(existing['rows'])}
    counts = Counter()
    rows = []
    with gzip.open(SOURCE, 'rt', encoding='utf-8', newline='') as stream:
        for source in csv.DictReader(stream):
            topic = TOPICS.get(source['experiment_id'])
            if not topic:
                continue
            counts[topic] += 1
            record = {
                'id': ('P' if topic == 'position' else 'R') + f'{counts[topic]:06d}',
                'question': question_alias(topic, source['question_key']),
                'topic': topic, 'model': source['model_id'],
                'documents': numeric(source['document_count']),
                'position': numeric(source['evidence_position']),
                'feedback': source['feedback_type'] or None,
                'round': numeric(source['revision_round']),
                'metric': source['metric_name'], 'score': numeric(source['metric_value']),
                'input_tokens': numeric(source['input_tokens']),
                'output_tokens': numeric(source['output_tokens']),
                'latency_seconds': numeric(source['latency_seconds']),
                'finish_reason': source['finish_reason'] or None,
                'truncated': boolean(source['is_truncated']),
                'excluded': boolean(source['environment_excluded']),
            }
            rows.append([record[key] for key in FIELDS])
    if dict(counts) != EXPECTED:
        raise ValueError('Saved experiment counts changed: ' + str(dict(counts)))
    payload = {
        'schema': 'lens-special-records-v1', 'fields': FIELDS, 'rows': rows,
        'counts': dict(counts),
        'metrics': {'position': 'final_answer_contains', 'feedback': 'base_and_heldout_pass'},
        'examples': chosen_example(),
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'privacy': 'Sequential anonymous record IDs and rehashed question IDs; no original keys, full texts, API identifiers, timestamps or credentials.',
        'shared_seed_policy': '328 physical initial drafts occur once with feedback=seed; no duplication across repair arms.',
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    TARGET.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    return {'snapshot_reused': False, 'counts': dict(counts), 'rows': len(rows),
            'bytes': TARGET.stat().st_size, 'examples': len(payload['examples'])}


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False))
