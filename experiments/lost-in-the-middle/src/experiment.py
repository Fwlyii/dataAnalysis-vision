#!/usr/bin/env python3
"""Reproducible, resumable course pilot. Raw API records are append-only."""
import argparse
import collections
import concurrent.futures
import csv
import datetime as dt
import fcntl
import gzip
import hashlib
import io
import json
import os
import queue
import signal
from pathlib import Path
import random
import re
import statistics
import string
import subprocess
import sys
import threading
import time
import traceback
import zipfile

import requests

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
TZ = dt.timezone(dt.timedelta(hours=8))
MODELS = ['Qwen/Qwen2.5-7B-Instruct', 'Qwen/Qwen3-8B']
STRATEGIES = ['NoCoT', 'DefaultCoT', 'BeConcise', 'BulletPoints',
              'WordLimit(25)', 'WordLimit(100)', 'TokenLimit(100)', 'StepLimit(2)']
SUFFIX = '\nEnd your response with FINAL ANSWER: <short answer in English>.'
TPM = 40000
LOCK = threading.RLock()


def now():
    return dt.datetime.now(TZ).isoformat(timespec='seconds')


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def document_id(document):
    return str(document.get('id') or ('sha256:' + sha(
        (document['title'] + '\n' + document['text']).encode('utf-8'))))


def prepare():
    previous = read_json(ROOT / 'cache' / 'pilot-manifest.json')
    branch = git('branch', '--show-current').decode().strip()
    assert branch == 'fwl', branch
    zzy_commit = git('rev-parse', 'origin/ZZY').decode().strip()
    main_commit = git('rev-parse', 'origin/main').decode().strip()
    blob = git('show', zzy_commit + ':data/compressed-cot-20261020/四模型回答数据_20261020.zip')
    archive = zipfile.ZipFile(io.BytesIO(blob))
    prompt_file = next(n for n in archive.namelist() if n.endswith('共用提示词.json'))
    all_prompts = json.loads(archive.read(prompt_file))
    write_json(ROOT / 'cache' / 'zzy-prompts.json', all_prompts)
    ds = {}
    for n in [10, 20]:
        with gzip.open(ROOT / 'cache' / f'nq-open-{n}_total_documents_gold_at_0.jsonl.gz',
                       'rt', encoding='utf-8') as handle:
            ds[n] = {x['question']: dict(x, source_line=i + 1)
                     for i, x in enumerate(map(json.loads, handle))}
    common = sorted(set(ds[10]) & set(ds[20]))
    previous_questions = read_json(ROOT / 'questions.json')
    selected = [q['question'] for q in previous_questions]
    assert len(selected) == 10
    selected += random.Random(91).sample([q for q in common if q not in selected], 190)
    strategies = list(all_prompts)
    assert len(strategies) == 31
    template = (ROOT / 'cache' / 'qa.prompt').read_text(encoding='utf-8').rstrip('\n')
    examples, jobs = [], []
    for qi, question in enumerate(selected):
        qid = f'nq-{qi + 1:03d}'
        examples.append({'question_id': qid, 'question': question,
                         'answers': ds[20][question]['answers'],
                         'source_lines': {str(n): ds[n][question]['source_line'] for n in [10, 20]},
                         'gold_document': next(c for c in ds[20][question]['ctxs'] if c['isgold'])})
        for n in [10, 20]:
            row = ds[n][question]
            assert row['answers'] == ds[20][question]['answers']
            gold = [c for c in row['ctxs'] if c.get('isgold')]
            distractors = [c for c in row['ctxs'] if not c.get('isgold')]
            assert len(gold) == 1 and len(distractors) == n - 1
            assert not any(c.get('hasanswer') for c in distractors)
            assert gold[0]['text'] == examples[-1]['gold_document']['text']
            for label, index in [('front', 0), ('middle', (n - 1) // 2), ('back', n - 1)]:
                docs = list(distractors)
                docs.insert(index, gold[0])
                # No gold/hasanswer flags, answer labels, or retrieval scores enter the prompt.
                search_results = '\n'.join(f'Document [{i + 1}](Title: {c["title"]}) {c["text"]}'
                                           for i, c in enumerate(docs))
                for strategy in strategies:
                    task_prompt = (all_prompts[strategy] + SUFFIX + '\n\n' +
                                   template.format(question=question, search_results=search_results))
                    jobs.append({'scenario_id': f'{qid}-d{n}-{label}-{strategy}',
                                 'question_id': qid, 'question': question, 'answers': row['answers'],
                                 'task_type': 'document_qa', 'document_count': n,
                                 'gold_position': index + 1, 'position_label': label,
                                 'gold_document_id': document_id(gold[0]),
                                 'document_ids': [document_id(c) for c in docs],
                                 'prompt_id': strategy, 'strategy_text': all_prompts[strategy],
                                 'prompt_text': task_prompt, 'prompt_sha256': sha(task_prompt.encode())})
        prompt = ('Answer this question from your own knowledge, without provided documents.\n' +
                  all_prompts['NoCoT'] + SUFFIX + '\n\nQuestion: ' + question + '\nAnswer:')
        jobs.append({'scenario_id': f'{qid}-closedbook-NoCoT', 'question_id': qid,
                     'question': question, 'answers': ds[20][question]['answers'],
                     'task_type': 'closedbook_control', 'document_count': 0,
                     'gold_position': None, 'position_label': 'none', 'document_ids': [],
                     'prompt_id': 'NoCoT', 'strategy_text': all_prompts['NoCoT'],
                     'prompt_text': prompt, 'prompt_sha256': sha(prompt.encode())})
    random.Random(91).shuffle(jobs)
    # First produce all eight strategies on the first real question, with 20 docs and middle evidence.
    early = [j for j in jobs if j['question_id'] == 'nq-001' and
             j['document_count'] == 20 and j['position_label'] == 'middle']
    early.sort(key=lambda j: strategies.index(j['prompt_id']))
    jobs = early + [j for j in jobs if j not in early]
    prior = {(r['model'], r['scenario_id']): r for r in load_records()}
    job_map = {j['scenario_id']: j for j in jobs}
    for (_, sid), r in prior.items():
        assert sid in job_map and job_map[sid]['prompt_sha256'] == r['prompt_sha256'], sid
    with (ROOT / 'scenarios.jsonl.tmp').open('w', encoding='utf-8') as f:
        for j in jobs:
            f.write(json.dumps(j, ensure_ascii=False) + '\n')
    (ROOT / 'scenarios.jsonl.tmp').replace(ROOT / 'scenarios.jsonl')
    write_json(ROOT / 'questions.json', examples)
    manifest = {'created_at': now(), 'branch': branch, 'base_main_commit': main_commit,
                'reference_zzy_commit': zzy_commit, 'zzy_archive_sha256': sha(blob),
                'benchmark': 'Lost in the Middle / NQ-Open multi-document QA',
                'upstream_commit': '29b8a6d042ce29abccee3db1a73171a107d7e6af',
                'dataset_sources': read_json(ROOT / 'cache' / 'dataset-sources.json'),
                'sample_seed': 91, 'sampling': 'preserve first 10 random pilot questions; seed-91 sample 190 from remaining sorted common questions',
                'source_questions_per_setting': len(common), 'independent_questions': 200,
                'models': MODELS, 'strategies': {s: all_prompts[s] for s in strategies},
                'unified_output_suffix': SUFFIX.strip(), 'document_counts': [10, 20],
                'positions_1based': {'10': [1, 5, 10], '20': [1, 10, 20]},
                'scenarios_per_model': len(jobs), 'main_calls': 74400, 'control_calls': 400,
                'total_calls': len(jobs) * len(MODELS), 'temperature': 0, 'max_tokens': 800,
                'qwen3_extra_body': {'enable_thinking': False},
                'qwen25_extra_body': {}, 'input_system_message': None,
                'per_model_token_budget_per_minute': TPM, 'max_attempts': 6, 'workers_per_model': 3,
                'primary_strategy_ids': STRATEGIES,
                'inherited_pilot_records': len(prior),
                'previous_manifest': 'cache/pilot-manifest.json',
                'operation_note': 'Inherited pilot used 1 worker/model; extension uses 3 workers/model. Latencies are operational, not controlled model-speed evidence.',
                'grading': ['normalized exact match of extracted final answer (primary)',
                            'official-style normalized answer substring in entire response (secondary)'],
                'adaptations': ['200-question course experiment; not a full paper reproduction',
                                'reposition gold while retaining distractor order within each length',
                                'all 31 original ZZY instructions plus one shared final-answer suffix; stress and translation strategies need separate scoring',
                                'closed-book controls use NoCoT and no supplied documents'],
                'credential_source': 'SILICONFLOW_API_KEY env, else in-memory extraction from main PDF; never exported',
                'python_version': sys.version, 'requests_version': requests.__version__,
                'scenarios_sha256': sha((ROOT / 'scenarios.jsonl').read_bytes()),
                'script_sha256_at_prepare': sha(Path(__file__).read_bytes())}
    write_json(ROOT / 'manifest.json', manifest)
    print(json.dumps({'prepared': len(jobs), 'total_calls': manifest['total_calls'],
                      'question_examples': [{'question': x['question'], 'answers': x['answers']}
                                            for x in examples[:3]]}, ensure_ascii=False, indent=2))


def credential():
    if os.environ.get('SILICONFLOW_API_KEY'):
        return os.environ['SILICONFLOW_API_KEY']
    from pypdf import PdfReader
    commit = read_json(ROOT / 'manifest.json')['base_main_commit']
    raw = git('show', commit + ':guide/可视化实践过程记录.pdf')
    text = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(raw)).pages)
    keys = list(dict.fromkeys(re.findall(r'sk-[a-zA-Z0-9]{25,}', text)))
    if not keys:
        raise RuntimeError('No project credential available. Set SILICONFLOW_API_KEY.')
    return keys[0]


def sanitize(text):
    return re.sub(r'sk-[A-Za-z0-9]{20,}', '[REDACTED]', str(text))


def normalize(text):
    text = str(text).lower().translate(str.maketrans('', '', string.punctuation))
    return ' '.join(re.sub(r'\b(a|an|the)\b', ' ', text).split())


def grade(record):
    choices = (record.get('response') or {}).get('choices') or []
    message = choices[0].get('message', {}) if choices else {}
    text = message.get('content') or ''
    matches = list(re.finditer(r'FINAL\s+ANSWER\s*:\s*', text, re.I))
    if matches:
        answer = text[matches[-1].end():].strip().split('\n')[0].strip(' *`"')
    else:
        answer = text.strip() if '\n' not in text.strip() and len(text.split()) <= 30 else None
    aliases = record['answers']
    exact = any(normalize(answer) == normalize(a) for a in aliases) if answer is not None else False
    contains = any(normalize(a) in normalize(text) for a in aliases)
    finish = choices[0].get('finish_reason') if choices else None
    return {'text': text, 'reasoning_text': message.get('reasoning_content'),
            'extracted_answer': answer, 'final_marker_present': bool(matches),
            'exact_match': exact if record['status'] == 'ok' else None,
            'answer_substring': contains if record['status'] == 'ok' else None,
            'finish_reason': finish, 'truncated': finish == 'length',
            'needs_review': record['status'] == 'ok' and (answer is None or contains != exact or finish == 'length'),
            'output_words': len(text.split()), 'output_characters': len(text)}


def load_records():
    path = ROOT / 'raw_responses.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def append(path, obj):
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def analyze(records=None):
    agg = Aggregates()
    source = records if records is not None else load_records()
    with (ROOT / 'results.csv').open('w', encoding='utf-8-sig', newline='') as f, (ROOT / 'review_queue.jsonl').open('w', encoding='utf-8') as review:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for record in source:
            row = derived_row(record)
            writer.writerow(row)
            if row['needs_review']:
                review.write(json.dumps(row, ensure_ascii=False) + '\n')
            agg.add(row)
    summary = agg.snapshot()
    write_json(ROOT / 'summary.json', summary)
    return None, summary


class Pacer:
    """One shared per-model rolling token budget across all its workers."""
    def __init__(self):
        self.recent = collections.deque()
        self.ratio = 1.5
        self.condition = threading.Condition()

    def wait(self, prompt, stop):
        with self.condition:
            while not stop.is_set():
                estimate = min(TPM, max(100, int(len(prompt.split()) * self.ratio) + 800))
                t = time.monotonic()
                while self.recent and t - self.recent[0][0] >= 61:
                    self.recent.popleft()
                if sum(entry[1] for entry in self.recent) + estimate <= TPM:
                    entry = [t, estimate]
                    self.recent.append(entry)
                    return entry
                self.condition.wait(timeout=1)
        return None

    def observe(self, entry, prompt, usage):
        with self.condition:
            if usage.get('total_tokens') is not None:
                entry[1] = usage['total_tokens']
            if usage.get('prompt_tokens'):
                self.ratio = max(self.ratio, usage['prompt_tokens'] / max(1, len(prompt.split())) * 1.05)
            self.condition.notify_all()


def strategy_scope(prompt_id):
    if prompt_id.startswith('ChineseCoT'):
        return 'translation_needs_review'
    if prompt_id in ['OnlyNumbers', 'WordLimit(1)', 'CharLimit(10)', 'TokenLimit(10)']:
        return 'answer_budget_stress'
    if prompt_id in ['NoSpaces', 'NoProperGrammar', 'AbbreviateWords']:
        return 'format_stress'
    return 'main_comparison'


CSV_FIELDS = ['run_id', 'scenario_id', 'question_id', 'question', 'answers', 'model',
              'task_type', 'document_count', 'gold_position', 'position_label', 'prompt_id',
              'strategy_scope', 'timestamp', 'status', 'http_status', 'latency_s',
              'attempt_count', 'text', 'reasoning_text', 'extracted_answer',
              'final_marker_present', 'exact_match', 'answer_substring', 'needs_review',
              'finish_reason', 'truncated', 'input_tokens', 'output_tokens', 'total_tokens',
              'output_words', 'output_characters', 'prompt_sha256', 'collector_version',
              'workers_per_model']


def derived_row(record):
    row = {k: record.get(k) for k in CSV_FIELDS}
    row.update(grade(record))
    row['answers'] = json.dumps(record['answers'], ensure_ascii=False)
    row['strategy_scope'] = strategy_scope(record['prompt_id'])
    if row['strategy_scope'] != 'main_comparison':
        row['needs_review'] = record['status'] == 'ok'
    usage = (record.get('response') or {}).get('usage') or {}
    row.update(input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'),
               total_tokens=usage.get('total_tokens'))
    return row


class Aggregates:
    def __init__(self):
        self.groups = {}
        self.counts = collections.Counter()
        self.ok_counts = collections.Counter()
        self.input_tokens = collections.Counter()
        self.total = 0

    def add(self, row):
        self.total += 1
        self.counts[row['model']] += 1
        self.input_tokens[row['model']] += row['input_tokens'] or 0
        if row['status'] == 'ok':
            self.ok_counts[row['model']] += 1
        keys = [(row['task_type'], row['model'], row['prompt_id'], 'all', 'all'),
                (row['task_type'], row['model'], row['prompt_id'], row['document_count'], row['position_label'])]
        for key in keys:
            g = self.groups.setdefault(key, {'task_type': key[0], 'model': key[1], 'prompt_id': key[2],
                'document_count': key[3], 'position_label': key[4], 'strategy_scope': row['strategy_scope'],
                'saved': 0, 'api_ok': 0, 'exact_correct': 0, 'substring_correct': 0,
                'needs_review': 0, 'truncated': 0, 'output_token_sum': 0, 'token_samples': 0,
                'latency_sum': 0, 'input_token_sum': 0})
            g['saved'] += 1
            if row['status'] != 'ok':
                continue
            g['api_ok'] += 1
            g['exact_correct'] += bool(row['exact_match'])
            g['substring_correct'] += bool(row['answer_substring'])
            g['needs_review'] += bool(row['needs_review'])
            g['truncated'] += bool(row['truncated'])
            g['latency_sum'] += row['latency_s']
            g['input_token_sum'] += row['input_tokens'] or 0
            if row['output_tokens'] is not None:
                g['output_token_sum'] += row['output_tokens']
                g['token_samples'] += 1

    def snapshot(self):
        groups = []
        for original in self.groups.values():
            g = dict(original)
            g['strict_exact_rate_on_api_ok'] = g['exact_correct'] / g['api_ok'] if g['api_ok'] else None
            g['substring_rate_on_api_ok'] = g['substring_correct'] / g['api_ok'] if g['api_ok'] else None
            g['mean_output_tokens'] = g['output_token_sum'] / g['token_samples'] if g['token_samples'] else None
            g['mean_latency_s'] = g['latency_sum'] / g['api_ok'] if g['api_ok'] else None
            groups.append(g)
        return {'updated_at': now(), 'completed': self.total,
                'main_expected': 74400, 'control_expected': 400,
                'note': 'Automatic preliminary scores; translation/format/budget stress require separate review.',
                'groups': groups}


def write_messages(handle, record):
    base = {k: record.get(k) for k in ['run_id', 'question_id', 'model', 'prompt_id', 'task_type',
                                      'document_count', 'position_label', 'gold_position', 'status']}
    base.update(task_id='data-reading', turn_id=1, tool_call=None, tool_input=None, tool_output=None)
    user = dict(base, timestamp=record['attempts'][0]['started_at'], role='user',
                content=record['request']['messages'][0]['content'])
    handle.write(json.dumps(user, ensure_ascii=False) + '\n')
    if record['status'] == 'ok':
        assistant = dict(base, timestamp=record['timestamp'], role='assistant',
                         content=record['response']['choices'][0]['message']['content'],
                         response_time=record['latency_s'], token_usage=record['response'].get('usage'))
        handle.write(json.dumps(assistant, ensure_ascii=False) + '\n')
    handle.flush()


def run():
    lock_handle = (ROOT / '.run.lock').open('w')
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Another experiment process holds the run lock.')
    manifest = read_json(ROOT / 'manifest.json')
    capacity = read_json(ROOT / 'capacity-estimate.json')
    total = manifest['total_calls']
    expected_per_model = manifest['scenarios_per_model']
    assert sha((ROOT / 'scenarios.jsonl').read_bytes()) == manifest['scenarios_sha256']
    for model in MODELS:
        price = read_json(ROOT / 'cache' / 'pricing-confirmation.json')['models'][model]
        assert price['inputPrice'] == '0' and price['price'] == '0'
    api_key = credential()
    jobs = [json.loads(line) for line in (ROOT / 'scenarios.jsonl').read_text(encoding='utf-8').splitlines()]
    agg = Aggregates()
    done = set()
    previews = []
    csv_handle = (ROOT / 'results.csv').open('w', encoding='utf-8-sig', newline='')
    csv_writer = csv.DictWriter(csv_handle, fieldnames=CSV_FIELDS)
    csv_writer.writeheader()
    review_handle = (ROOT / 'review_queue.jsonl').open('w', encoding='utf-8')
    messages_handle = (ROOT / 'messages.jsonl').open('w', encoding='utf-8')

    def save_derived(record):
        row = derived_row(record)
        csv_writer.writerow(row)
        csv_handle.flush()
        if row['needs_review']:
            review_handle.write(json.dumps(row, ensure_ascii=False) + '\n')
            review_handle.flush()
        write_messages(messages_handle, record)
        agg.add(row)
        if record['question_id'] == 'nq-001' and record['document_count'] == 20 and record['position_label'] == 'middle':
            previews.append(record)
        return row

    if (ROOT / 'raw_responses.jsonl').exists():
        with (ROOT / 'raw_responses.jsonl').open(encoding='utf-8') as handle:
            for line in handle:
                record = json.loads(line)
                identity = (record['model'], record['scenario_id'])
                assert identity not in done, 'Duplicate saved run: ' + str(identity)
                done.add(identity)
                save_derived(record)
    base_counts = dict(agg.counts)
    start_clock = time.monotonic()
    started = now()
    stop = threading.Event()
    reason = ['']
    pacers = {m: Pacer() for m in MODELS}
    queues = {m: queue.Queue() for m in MODELS}
    for model in MODELS:
        for j in jobs:
            if (model, j['scenario_id']) not in done:
                queues[model].put(j)
    latest = {}
    last_times = {m: start_clock for m in MODELS}
    rates = {m: collections.deque() for m in MODELS}
    failure_streak = collections.Counter()
    last_summary_time = [0.0]
    last_preview_count = [-1]

    def emit(state='running'):
        t = time.monotonic()
        elapsed = t - start_clock
        by_model = {}
        remaining_times = []
        for model in MODELS:
            count = agg.counts[model]
            added = count - base_counts.get(model, 0)
            pending = expected_per_model - count
            observed_elapsed = max(.1, last_times[model] - start_clock)
            model_rate = added / observed_elapsed if added else None
            window = rates[model]
            while window and t - window[0][0] > 900:
                window.popleft()
            recent_rate = ((len(window) - 1) / (window[-1][0] - window[0][0])
                           if len(window) >= 10 and window[-1][0] > window[0][0] else model_rate)
            per_s = recent_rate or model_rate
            remaining_s = pending / per_s if pending and per_s else (0 if not pending else None)
            estimated_input_left = max(0, capacity[model]['estimated_input_tokens'] - agg.input_tokens[model])
            token_time_floor = estimated_input_left / TPM * 60 if pending else 0
            if remaining_s is not None:
                remaining_s = max(remaining_s, token_time_floor)
            by_model[model] = {'completed': count, 'expected': expected_per_model,
                'api_ok': agg.ok_counts[model], 'new_this_session': added,
                'calls_per_minute': round(per_s * 60, 2) if per_s else None,
                'estimated_remaining_input_tokens': round(estimated_input_left),
                'input_budget_time_floor_s': round(token_time_floor),
                'estimated_remaining_s': round(remaining_s) if remaining_s is not None else None,
                'estimated_finish': (dt.datetime.now(TZ) + dt.timedelta(seconds=remaining_s)).isoformat(timespec='seconds') if remaining_s is not None else None}
            if remaining_s is not None:
                remaining_times.append(remaining_s)
        remaining = max(remaining_times) if len(remaining_times) == len(MODELS) else None
        progress = {'state': state, 'pid': os.getpid(), 'started_at': started,
            'updated_at': now(), 'total': total, 'completed': agg.total,
            'api_ok': sum(agg.ok_counts.values()), 'by_model': by_model,
            'workers_per_model': manifest['workers_per_model'], 'token_budget_per_model_per_minute': TPM,
            'elapsed_s': round(elapsed, 1), 'stop_reason': reason[0],
            'estimated_remaining_s': round(remaining) if remaining is not None else None,
            'estimated_finish': (dt.datetime.now(TZ) + dt.timedelta(seconds=remaining)).isoformat(timespec='seconds') if remaining is not None else None,
            'estimate_note': 'Per-model recent 15-minute throughput; unstable during first 5 minutes and after rate-limit events.',
            'latest': latest}
        write_json(ROOT / 'progress.json', progress)
        if state != 'running' or t - last_summary_time[0] >= 30:
            write_json(ROOT / 'summary.json', agg.snapshot())
            last_summary_time[0] = t
        if len(previews) != last_preview_count[0]:
            write_json(ROOT / 'preview-records.json', previews)
            last_preview_count[0] = len(previews)

    def request_stop(signum, frame):
        reason[0] = 'Signal ' + str(signum)
        stop.set()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    emit()
    print(f'{now()} resumed {agg.total}/{total}; 3 workers per model; 40k TPM per model', flush=True)

    def worker(model, worker_index):
        session = requests.Session()
        session.headers['Authorization'] = 'Bearer ' + api_key
        pacer = pacers[model]
        while not stop.is_set():
            try:
                scenario = queues[model].get_nowait()
            except queue.Empty:
                return
            request = {'model': model, 'messages': [{'role': 'user', 'content': scenario['prompt_text']}],
                       'temperature': 0, 'max_tokens': 800}
            if model.endswith('Qwen3-8B'):
                request['enable_thinking'] = False
            attempts, response, status, latency, http_status = [], None, 'api_error', None, None
            for attempt in range(1, manifest['max_attempts'] + 1):
                if stop.is_set():
                    break
                entry = pacer.wait(scenario['prompt_text'], stop)
                if entry is None:
                    break
                call_start = now()
                t = time.monotonic()
                try:
                    r = session.post('https://api.siliconflow.cn/v1/chat/completions', json=request, timeout=(15, 120))
                    latency = round(time.monotonic() - t, 4)
                    http_status = r.status_code
                    try:
                        body = r.json()
                    except ValueError:
                        body = {'non_json_error': sanitize(r.text[:1500])}
                    event = {'model': model, 'scenario_id': scenario['scenario_id'], 'attempt': attempt,
                             'worker_index': worker_index, 'started_at': call_start, 'ended_at': now(),
                             'latency_s': latency, 'http_status': http_status, 'retry_after': r.headers.get('Retry-After')}
                    if not r.ok:
                        event['error'] = sanitize(json.dumps(body, ensure_ascii=False))[:2000]
                    attempts.append(event)
                    with LOCK:
                        append(ROOT / 'attempt_log.jsonl', event)
                    if r.ok and body.get('choices'):
                        response, status = body, 'ok'
                        pacer.observe(entry, scenario['prompt_text'], body.get('usage') or {})
                        break
                    if http_status in [401, 402, 403, 404]:
                        reason[0] = 'Non-retryable HTTP ' + str(http_status)
                        stop.set()
                        break
                    if http_status not in [408, 429, 500, 502, 503, 504]:
                        break
                    if attempt < manifest['max_attempts']:
                        delay = (65 if http_status == 429 else min(60, 5 * 2 ** (attempt - 1)))
                        try:
                            delay = max(delay, float(r.headers.get('Retry-After', 0)))
                        except ValueError:
                            pass
                        if stop.wait(delay):
                            break
                except requests.RequestException as exc:
                    latency = round(time.monotonic() - t, 4)
                    event = {'model': model, 'scenario_id': scenario['scenario_id'], 'attempt': attempt,
                             'worker_index': worker_index, 'started_at': call_start, 'ended_at': now(),
                             'latency_s': latency, 'http_status': None, 'error': sanitize(exc)}
                    attempts.append(event)
                    with LOCK:
                        append(ROOT / 'attempt_log.jsonl', event)
                    if attempt < manifest['max_attempts'] and stop.wait(min(60, 5 * 2 ** (attempt - 1))):
                        break
            if not attempts:
                return
            if status != 'ok' and stop.is_set() and reason[0].startswith('Signal'):
                # The attempt log retains interrupted attempts; no terminal failed sample is invented.
                return
            record = {k: v for k, v in scenario.items() if k not in ['prompt_text', 'strategy_text', 'document_ids']}
            record.update(model=model, run_id=model.rsplit('/', 1)[-1] + ':' + scenario['scenario_id'],
                          timestamp=now(), status=status, http_status=http_status, latency_s=latency,
                          attempt_count=len(attempts), attempts=attempts, request=request, response=response,
                          collector_version='scale200-v1', workers_per_model=manifest['workers_per_model'])
            with LOCK:
                identity = (model, scenario['scenario_id'])
                assert identity not in done
                append(ROOT / 'raw_responses.jsonl', record)
                done.add(identity)
                save_derived(record)
                failure_streak[model] = 0 if status == 'ok' else failure_streak[model] + 1
                last_times[model] = time.monotonic()
                rates[model].append((last_times[model], agg.counts[model]))
                latest.update(model=model, scenario_id=scenario['scenario_id'], status=status, latency_s=latency)
                if failure_streak[model] >= 3:
                    reason[0] = 'Three consecutive failed scenarios for ' + model
                    stop.set()
                emit('stopping' if stop.is_set() else 'running')
                print(f'{now()} {agg.total}/{total} {model} {scenario["scenario_id"]} {status}', flush=True)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2 * manifest['workers_per_model']) as pool:
            futures = [pool.submit(worker, model, i) for model in MODELS for i in range(manifest['workers_per_model'])]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except BaseException:
                    reason[0] = 'Worker exception'
                    stop.set()
                    raise
        emit('completed' if agg.total == total else 'stopped_with_errors')
    except BaseException as exc:
        reason[0] = sanitize(exc)
        emit('crashed')
        raise
    finally:
        csv_handle.close()
        review_handle.close()
        messages_handle.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['prepare', 'run', 'analyze', 'status'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'run':
        run()
    elif args.command == 'analyze':
        _, summary = analyze()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print((ROOT / 'progress.json').read_text(encoding='utf-8'))
