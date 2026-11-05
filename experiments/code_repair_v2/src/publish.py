"""Publish a fully measured real batch as a static, anonymous website supplement."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from .dataset import ROOT
from .prepare import atomic_json
from scripts.cleaning.build_unified_features import FIELDS


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def check_anonymous(value):
    prohibited = {'task_id', 'task_ids', 'record_id', 'record_ids', 'request', 'response',
                  'headers', 'authorization', 'api_key', 'credential', 'credentials',
                  'access_token', 'api_token', 'secret_key'}
    if isinstance(value, dict):
        if any(str(key).lower() in prohibited for key in value):
            raise ValueError('Anonymous evidence contains a raw identifier or credential field')
        for item in value.values():
            check_anonymous(item)
    elif isinstance(value, list):
        for item in value:
            check_anonymous(item)
    elif isinstance(value, str) and re.search(r'sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}', value):
        raise ValueError('Anonymous evidence contains a credential-like string')


def publish(source: Path, legacy: Path, app: Path = ROOT / 'app'):
    source = Path(source).resolve()
    evidence = read_json(source / 'app-evidence.json')
    manifest = read_json(source / 'figure-manifest.json')
    if (evidence.get('synthetic') is not False or evidence.get('status') != 'complete'
            or evidence.get('coverage', {}).get('complete') is not True):
        raise ValueError('Only a complete real experiment may be published')
    if evidence.get('strong_trajectory_complete') is not True:
        raise ValueError('All-round strong measurements must finish before publication')
    check_anonymous(evidence)
    coverage = evidence['coverage']
    tasks = evidence.get('planned_tasks')
    repeats = evidence.get('repeats_per_task')
    rounds = evidence.get('rounds')
    models = evidence.get('models') or []
    arms = evidence.get('arms') or []
    if (any(not isinstance(n, int) or isinstance(n, bool) or n <= 0 for n in (tasks, repeats, rounds))
            or rounds < 2 or not models or not arms):
        raise ValueError('A nonempty planned experiment is required')
    expected = tasks * len(models) * repeats * (1 + len(arms) * (rounds - 1))
    if (coverage.get('expected_physical_responses') != expected
            or coverage.get('planned_tasks') != tasks or coverage.get('public_task_clusters') != tasks
            or coverage.get('task_clusters') != tasks or coverage.get('strong_trajectory_task_clusters') != tasks
            or evidence.get('public_task_clusters') != tasks or coverage.get('saved_physical_responses') != expected
            or evidence.get('planned_tasks') != evidence.get('task_clusters')
            or evidence.get('planned_tasks') != evidence.get('strong_trajectory_task_clusters')
            or coverage.get('expected_physical_responses') != evidence.get('saved_physical_responses')
            or coverage.get('missing_count') != 0):
        raise ValueError('Published batch does not cover every planned paired task')
    if manifest.get('synthetic') is not False or manifest.get('batch_id') != evidence.get('batch_id'):
        raise ValueError('Figure provenance does not match the real batch')
    figures = manifest.get('figures') or []
    required = {'strong-endpoints', 'public-trajectories', 'repair-regression',
                'cost-quality', 'initial-error-support', 'strong-trajectories'}
    if {item['id'] for item in figures} != required or len(figures) != len(required):
        raise ValueError('The six measured scientific figures are required')
    files = {}
    for figure in figures:
        for key in ('file', 'data_file'):
            name = figure[key]
            if Path(name).name != name:
                raise ValueError('Figure asset path must be a local basename')
            path = source / name
            if not path.is_file():
                raise ValueError('Missing measured figure asset: ' + name)
            files[name] = path
        svg = ET.parse(source / figure['file']).getroot()
        if svg.tag != '{http://www.w3.org/2000/svg}svg':
            raise ValueError('Scientific figures must be SVG')
    checks = read_json(legacy / 'strong-checks.json')
    if checks.get('complete') is not True or checks.get('known_results') != checks.get('source_records'):
        raise ValueError('Legacy recheck must be complete and reported separately')
    with (legacy / 'legacy-vs-strong-summary.csv').open(encoding='utf-8-sig', newline='') as handle:
        legacy_rows = list(csv.DictReader(handle))
    with (legacy / 'legacy-vs-strong-curves.csv').open(encoding='utf-8-sig', newline='') as handle:
        legacy_curves = list(csv.DictReader(handle))
    legacy_manifest = read_json(legacy / 'figure-manifest.json')
    if legacy_manifest.get('synthetic') is not False or legacy_manifest.get('complete') is not True:
        raise ValueError('Legacy figure must describe the completed real recheck')
    for figure in legacy_manifest['figures']:
        for key in ('file', 'data_file'):
            name = figure[key]
            if Path(name).name != name or not (legacy / name).is_file():
                raise ValueError('Invalid or missing legacy figure asset')
            files['legacy/' + name] = legacy / name
    public_checks = {key: checks.get(key) for key in (
        'schema', 'complete', 'source_records', 'source_initial_programs', 'known_results',
        'full_holdout_inputs', 'model_api_calls', 'feedback_changed', 'source_sha256',
        'dataset_sha256', 'changed_program_verdicts', 'public_verdict_changes',
        'strong_pass_old_mini_fail', 'interpretation')}
    bundle = {'schema': 'course-code-feedback-publication-v1', 'evidence': evidence,
              'figures': figures,
              'legacyEvidence': {'checks': public_checks, 'summary': legacy_rows, 'curves': legacy_curves,
                                 'figures': legacy_manifest['figures']},
              'provenance': {'evidence_sha256': hashlib.sha256((source / 'app-evidence.json').read_bytes()).hexdigest(),
                             'assets': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}}}
    normalized = source / 'unified-format/metadata.json'
    if normalized.exists():
        metadata = read_json(normalized)
        if (metadata.get('schema') != 'code-repair-unified-supplement-v1'
                or metadata.get('synthetic') is not False or metadata.get('complete') is not True
                or metadata.get('batch_id') != evidence['batch_id'] or metadata.get('records') != expected
                or metadata.get('fields') != list(FIELDS)
                or set(metadata.get('assets_sha256', {})) != {'unified-records.csv.gz', 'lineage.csv', 'field-statistics.csv'}):
            raise ValueError('Unified-format provenance does not match the complete batch')
        for name, sha in metadata.get('assets_sha256', {}).items():
            if Path(name).name != name or hashlib.sha256((normalized.parent / name).read_bytes()).hexdigest() != sha:
                raise ValueError('Unified-format asset checksum mismatch')
        bundle['unifiedFormat'] = {key: metadata.get(key) for key in (
            'schema', 'batch_id', 'complete', 'records', 'physical_seeds', 'planned_tasks',
            'replicates_per_task_model', 'fields', 'metric_name', 'assets_sha256', 'null_policy', 'replicate_policy')}
        bundle['provenance']['unified_metadata_sha256'] = hashlib.sha256(normalized.read_bytes()).hexdigest()
    check_anonymous(bundle)
    target = app / 'assets/research-extension'
    target.mkdir(parents=True, exist_ok=True)
    for name, path in files.items():
        (target / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target / name)
    (app / 'data').mkdir(parents=True, exist_ok=True)
    atomic_json(app / 'data/code-feedback-extension.json', bundle)
    return {'batch_id': evidence['batch_id'], 'task_clusters': evidence['task_clusters'],
            'responses': evidence['saved_physical_responses'], 'figures': len(figures),
            'destination': str(app / 'data/code-feedback-extension.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--legacy-source', type=Path, default=ROOT / 'reports/code_repair_extension/legacy-full-recheck')
    args = parser.parse_args()
    print(json.dumps(publish(args.source, args.legacy_source), ensure_ascii=False))


if __name__ == '__main__':
    main()
