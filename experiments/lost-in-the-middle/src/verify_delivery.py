#!/usr/bin/env python3
"""Read-only integrity checks on the delivered data; no API requests."""
import csv
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    checks = json.loads((ROOT/'data/CHECKSUMS.json').read_text())
    for name, expected in checks.items():
        path = ROOT/name
        for compressed in [True, False]:
            h, size = hashlib.sha256(), 0
            opener = open if compressed else gzip.open
            with opener(path, 'rb') as f:
                for block in iter(lambda: f.read(2**20), b''):
                    h.update(block)
                    size += len(block)
            prefix = '' if compressed else 'uncompressed_'
            assert h.hexdigest() == expected[prefix+'sha256'], name
            assert size == expected[prefix+'bytes'], name
    scenarios = {}
    with gzip.open(ROOT/'data/scenarios.jsonl.gz', 'rt') as f:
        for line in f:
            r=json.loads(line)
            assert hashlib.sha256(r['prompt_text'].encode()).hexdigest()==r['prompt_sha256']
            assert r['scenario_id'] not in scenarios
            scenarios[r['scenario_id']] = (r['prompt_sha256'], r['answers'])
    assert len(scenarios)==37400
    seen, groups = set(), Counter()
    with gzip.open(ROOT/'data/raw_responses.jsonl.gz', 'rt') as f:
        for line in f:
            r=json.loads(line)
            key=(r['model'],r['scenario_id'])
            assert key not in seen
            seen.add(key)
            assert r['status']=='ok' and r['response']['model']==r['model']
            assert (r['prompt_sha256'],r['answers'])==scenarios[r['scenario_id']]
            assert hashlib.sha256(r['request']['messages'][0]['content'].encode()).hexdigest()==r['prompt_sha256']
            groups[(r['task_type'],r['model'],r['prompt_id'],r['document_count'],r['position_label'])]+=1
    assert len(seen)==74800 and len(groups)==374 and set(groups.values())=={200}
    with (ROOT/'derived/scores.csv').open(encoding='utf-8-sig',newline='') as f:
        scores=list(csv.DictReader(f))
    assert len(scores)==74800 and {(r['model'],r['scenario_id']) for r in scores}==seen
    print('PASS: compressed/uncompressed SHA-256, complete JSON, prompt hashes, labels, model IDs, unique keys, 374 balanced groups, 74,800 score rows.')


if __name__=='__main__':
    main()
