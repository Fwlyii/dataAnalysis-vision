"""Finalize the real full feedback batch locally, without model calls.

--once checks readiness without writing anything. --watch waits at 30-second
intervals, then runs the offline delivery pipeline exactly once. --output is a
staging parent: a unique new child is created only after all checks pass.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid


ROOT = Path(__file__).resolve().parents[2]
EXPECTED = 24600
REQUIRED_FIGURES = {'strong-endpoints', 'public-trajectories', 'repair-regression',
                    'cost-quality', 'initial-error-support', 'strong-trajectories'}
RUN_INPUTS = ('plan.json', 'reference-preflight.json', 'responses.jsonl', 'evaluations.jsonl',
              'holdout-evaluations.jsonl', 'attempts.jsonl', 'operational-amendment-1.json',
              'resource-audit.jsonl')
REQUIRED_INPUTS = set(RUN_INPUTS[:5])
STOP = threading.Event()


class FinalizationError(RuntimeError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def resolve(value):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


def read_json(path):
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise FinalizationError(f'Cannot read valid JSON: {path.name}: {type(error).__name__}') from error
    if not isinstance(value, dict):
        raise FinalizationError('JSON object required: ' + path.name)
    return value


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def atomic_json(path, value):
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def context(config_path):
    path = resolve(config_path)
    config = read_json(path)
    if config.get('synthetic', False) is not False:
        raise FinalizationError('Synthetic batches cannot be finalized')
    batch = config.get('batch_id', '')
    if not isinstance(batch, str) or not re.fullmatch(r'[\w.-]+', batch):
        raise FinalizationError('Invalid batch identifier')
    repeats = config.get('replicates')
    repeats = repeats if isinstance(repeats, list) else list(range(repeats)) if isinstance(repeats, int) and not isinstance(repeats, bool) and repeats > 0 else []
    expected = config.get('expected_tasks', 0) * len(config.get('models', [])) * len(repeats) * (1 + len(config.get('arms', [])) * (config.get('rounds', 0) - 1))
    if expected != EXPECTED or config.get('maximum_physical_responses') != EXPECTED or config.get('expected_tasks') != 164:
        raise FinalizationError('This finalizer requires the precommitted 164-task, 24,600-response full batch')
    run = resolve(config['run_dir'])
    if not run.is_dir():
        raise FinalizationError('Existing collection run directory required')
    # Preserve the venv executable spelling; resolving its symlink loses venv identity.
    python = Path(config['python_executable']).expanduser()
    python = python if python.is_absolute() else ROOT / python
    if not python.is_file() or not os.access(python, os.X_OK):
        raise FinalizationError('Configured Python executable is unavailable')
    return {'config': config, 'config_path': path, 'config_sha256': digest(path), 'batch_id': batch,
            'run': run, 'python': str(python), 'report': ROOT / 'reports/code_repair_extension' / batch,
            'legacy': ROOT / 'reports/code_repair_extension/legacy-full-recheck'}


def readiness(ctx):
    waiting, fatal = [], []
    statuses = {}
    for name in ('plan.json', 'reference-preflight.json', 'collection-status.json', 'holdout-status.json'):
        path = ctx['run'] / name
        if not path.is_file():
            waiting.append('Missing ' + name)
            statuses[name] = {}
        else:
            statuses[name] = read_json(path)
    plan, preflight, collection, holdout = [statuses[name] for name in statuses]
    sha = ctx['config_sha256']
    if digest(ctx['config_path']) != sha:
        fatal.append('Configuration changed while finalization was waiting')
    if plan:
        if plan.get('config_sha256') != sha or plan.get('batch_id') != ctx['batch_id'] or plan.get('expected_requests') != EXPECTED:
            fatal.append('Frozen plan identity/configuration/count mismatch')
        if len(plan.get('task_ids', [])) != 164:
            fatal.append('Frozen plan does not contain all164 tasks')
    if preflight and (preflight.get('config_sha256') != sha or preflight.get('batch_id') != ctx['batch_id']):
        fatal.append('Reference preflight identity/configuration mismatch')
    if preflight.get('complete') is not True:
        waiting.append('Reference preflight is incomplete')
    # The frozen collector predates an explicit complete/config field. Its final
    # full counts plus the plan SHA are the documented compatibility rule.
    collection_sha = collection.get('config_sha256') if 'config_sha256' in collection else plan.get('config_sha256')
    if collection and collection_sha != sha:
        fatal.append('Collection status configuration mismatch')
    if collection.get('batch_id', ctx['batch_id']) != ctx['batch_id']:
        fatal.append('Collection status batch mismatch')
    if collection.get('stopped') is True or collection.get('failed_blocks', 0):
        fatal.append('Collector stopped or reported failed blocks; resume/inspect collection before finalizing')
    collection_complete = (collection.get('scope') == 'full' and collection.get('expected') == EXPECTED
                           and collection.get('responses') == EXPECTED and collection.get('evaluated') == EXPECTED
                           and collection.get('failed_blocks') == 0 and collection.get('stopped') is False
                           and collection.get('complete', True) is True)
    if not collection_complete:
        waiting.append('Full collection/public counts have not completed')
    if holdout and (holdout.get('config_sha256') != sha or holdout.get('batch_id') != ctx['batch_id']):
        fatal.append('Holdout status identity/configuration mismatch')
    if holdout.get('fatal'):
        fatal.append('Holdout runner reports a fatal error; inspect holdout-status.json')
    if holdout.get('stopped') is True:
        fatal.append('Holdout runner was stopped; inspect/resume its status before finalizing')
    holdout_complete = (holdout.get('complete') is True and holdout.get('measurement_scope') == 'all_rounds'
                        and all(holdout.get(name) == EXPECTED for name in ('source_responses', 'expected_responses', 'candidates_available', 'expected_holdouts', 'measured'))
                        and all(holdout.get(name) == 0 for name in ('active', 'pending_available', 'unknown_unresolved'))
                        and holdout.get('stopped') is False and holdout.get('incomplete_response_tail') is False
                        and holdout.get('passed', -1) + holdout.get('failed', -1) == EXPECTED)
    if not holdout_complete:
        waiting.append('Full-round strong measurements have not completed')
    return {'ready': not waiting and not fatal, 'batch_id': ctx['batch_id'], 'config_sha256': sha,
            'collection_complete': collection_complete, 'collection_complete_derived': 'complete' not in collection,
            'collection_config_source': 'status' if 'config_sha256' in collection else 'frozen_plan',
            'collection_responses': collection.get('responses'), 'public_evaluated': collection.get('evaluated'),
            'strong_complete': holdout_complete, 'strong_measured': holdout.get('measured'),
            'strong_unknown_unresolved': holdout.get('unknown_unresolved'), 'expected': EXPECTED,
            'waiting': waiting, 'fatal': fatal}


def known(split):
    return isinstance(split, dict) and split.get('complete') is True and split.get('outcome_known', True) is not False and isinstance(split.get('passed'), bool)


def public_known(split):
    if not known(split):
        return False
    return not split['passed'] or (split.get('scan_complete') is True and isinstance(split.get('total_cases'), int)
                                   and not isinstance(split['total_cases'], bool) and split['total_cases'] >= 0
                                   and split.get('cases_checked') == split['total_cases'])


def strong_known(row):
    if not isinstance(row.get('full_pass'), bool):
        return False
    public, hidden = row.get('public'), row.get('hidden')
    if row['full_pass'] is False:
        return any(known(split) and split['passed'] is False for split in (public, hidden))
    return all(public_known(split) and split['passed'] is True for split in (public, hidden))


def saved_ids(path, ctx, verdict=None):
    ids = set()
    with path.open('rb') as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            if not line.endswith(b'\n'):
                raise FinalizationError(f'Incomplete JSONL tail: {path.name}:{line_number}')
            try:
                row = json.loads(line)
            except ValueError as error:
                raise FinalizationError(f'Invalid JSONL: {path.name}:{line_number}') from error
            identity = row.get('record_id')
            if not isinstance(identity, str) or identity in ids or row.get('config_sha256') != ctx['config_sha256']:
                raise FinalizationError('Duplicate/missing identity or configuration mismatch: ' + path.name)
            if verdict is not None and (row.get('sandboxed') is not True or not verdict(row)):
                raise FinalizationError('Unresolved or non-sandboxed outcome: ' + path.name)
            ids.add(identity)
    if len(ids) != EXPECTED:
        raise FinalizationError(f'{path.name} does not contain exactly{EXPECTED} physical records')
    return ids


def verify_saved_outcomes(ctx):
    raw = saved_ids(ctx['run'] / 'responses.jsonl', ctx)
    public = saved_ids(ctx['run'] / 'evaluations.jsonl', ctx, lambda row: public_known(row.get('public')))
    strong = saved_ids(ctx['run'] / 'holdout-evaluations.jsonl', ctx, strong_known)
    if raw != public or raw != strong:
        raise FinalizationError('Response/public/strong identity sets differ')
    return {'physical_responses': len(raw), 'known_public_outcomes': len(public), 'known_strong_outcomes': len(strong),
            'unknown_outcomes': 0, 'unexecuted_cases': 'preserved as unmeasured; a demonstrated failing split settles joint FAIL'}


def input_hashes(ctx):
    result = {}
    for name in RUN_INPUTS:
        path = ctx['run'] / name
        if name in REQUIRED_INPUTS and not path.is_file():
            raise FinalizationError('Missing frozen input: ' + name)
        result[name] = digest(path) if path.is_file() else None
    return result


def tooling_hashes():
    paths = {Path(__file__), ROOT / 'project.json', ROOT / 'app/index.html', ROOT / 'tests/browser/defense.mjs',
             ROOT / 'scripts/cleaning/build_unified_features.py'}
    for directory, pattern in [('experiments/code_repair_v2/src', '*.py'), ('experiments/code_repair_v2/analysis', '*.py'), ('scripts/system', '*.py'),
                               ('scripts/figures', '*.py'), ('tests', 'test_repair_v2_*.py'),
                               ('app/src', '*.js'), ('app', '*.css')]:
        paths.update((ROOT / directory).glob(pattern))
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def verify_report(ctx, hashes):
    directory = ctx['report']
    evidence = read_json(directory / 'app-evidence.json')
    integrity = read_json(directory / 'integrity.json')
    coverage = evidence.get('coverage') or {}
    if (evidence.get('synthetic') is not False or evidence.get('status') != 'complete'
            or evidence.get('batch_id') != ctx['batch_id'] or coverage.get('complete') is not True
            or coverage.get('missing_count') != 0 or evidence.get('strong_trajectory_complete') is not True
            or evidence.get('saved_physical_responses') != EXPECTED
            or evidence.get('strong_trajectory_task_clusters') != 164 or integrity.get('complete') is not True
            or integrity.get('config_sha256') != ctx['config_sha256']):
        raise FinalizationError('Existing report is not a complete matching real full-round report; preserve and inspect it')
    for name, value in (integrity.get('source_sha256') or {}).items():
        if name in hashes and value != hashes[name]:
            raise FinalizationError('Report was built from different frozen inputs: ' + name)
    if not {'responses.jsonl', 'evaluations.jsonl', 'holdout-evaluations.jsonl', 'plan.json'}.issubset(integrity.get('source_sha256', {})):
        raise FinalizationError('Report lacks required frozen input hashes')
    manifest = read_json(directory / 'figure-manifest.json')
    figures = manifest.get('figures') or []
    if (manifest.get('synthetic') is not False or manifest.get('batch_id') != ctx['batch_id']
            or len(figures) != 6 or {row.get('id') for row in figures} != REQUIRED_FIGURES):
        raise FinalizationError('Complete real six-figure manifest required')
    for row in figures:
        for field in ('file', 'data_file'):
            name = row.get(field, '')
            if Path(name).name != name or not (directory / name).is_file():
                raise FinalizationError('Missing or nonlocal figure source')
    return evidence


def verify_normalized(ctx, hashes):
    directory = ctx['report'] / 'unified-format'
    meta = read_json(directory / 'metadata.json')
    if (meta.get('complete') is not True or meta.get('synthetic') is not False or meta.get('batch_id') != ctx['batch_id']
            or meta.get('records') != EXPECTED or meta.get('config_sha256') != ctx['config_sha256']
            or meta.get('metric_counts', {}).get('unknown') != 0
            or meta.get('normalizer_source_sha256') != digest(ROOT / 'experiments/code_repair_v2/src/normalize.py')):
        raise FinalizationError('Existing unified export is not a complete matching export; preserve and inspect it')
    sources = meta.get('source_sha256') or {}
    if not REQUIRED_INPUTS.issubset(sources) or any(sources.get(name) != hashes[name] for name in REQUIRED_INPUTS):
        raise FinalizationError('Unified export belongs to different frozen inputs')
    assets = meta.get('assets_sha256') or {}
    if set(assets) != {'unified-records.csv.gz', 'lineage.csv', 'field-statistics.csv'}:
        raise FinalizationError('Unified export asset manifest is incomplete')
    if any(digest(directory / name) != sha for name, sha in assets.items()):
        raise FinalizationError('Unified export asset hash mismatch')


def verify_publication(ctx):
    publication = read_json(ROOT / 'app/data/code-feedback-extension.json')
    if publication.get('evidence') != read_json(ctx['report'] / 'app-evidence.json'):
        raise FinalizationError('Existing publication belongs to different evidence; preserve and inspect it')
    if publication.get('figures') != read_json(ctx['report'] / 'figure-manifest.json').get('figures'):
        raise FinalizationError('Existing publication has a different figure manifest')
    provenance = publication.get('provenance') or {}
    if provenance.get('evidence_sha256') != digest(ctx['report'] / 'app-evidence.json'):
        raise FinalizationError('Existing publication evidence hash mismatch')
    assets = provenance.get('assets') or {}
    if not assets or any(Path(name).is_absolute() or '..' in Path(name).parts for name in assets):
        raise FinalizationError('Invalid publication asset manifest')
    if any(digest(ROOT / 'app/assets/research-extension' / name) != sha for name, sha in assets.items()):
        raise FinalizationError('Existing publication asset hash mismatch')
    public_checks = publication.get('legacyEvidence', {}).get('checks', {})
    legacy_checks = read_json(ctx['legacy'] / 'strong-checks.json')
    if public_checks.get('complete') is not True or any(legacy_checks.get(key) != value for key, value in public_checks.items()):
        raise FinalizationError('Legacy publication is incomplete')


def child_environment(ctx, extra=None):
    # Forward only ordinary runtime/browser settings. No credential environment
    # variable, credential file or provider client is read by this finalizer.
    names = ('PATH', 'HOME', 'USER', 'LOGNAME', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE',
             'SYSTEMROOT', 'CHROMIUM_PATH', 'PLAYWRIGHT_BROWSERS_PATH')
    environment = {name: os.environ[name] for name in names if name in os.environ}
    environment.update({'PATH': str(Path(ctx['python']).parent) + os.pathsep + environment.get('PATH', os.defpath),
                        'PYTHONPATH': str(ROOT), 'PYTHONUNBUFFERED': '1', 'NO_PROXY': '127.0.0.1,localhost'})
    environment.update(extra or {})
    return environment


@contextmanager
def local_site(directory):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, *_):
            pass
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name='feedback-finalization-http', daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class Runner:
    def __init__(self, ctx, status, output_parent):
        self.ctx, self.status, self.output_parent = ctx, status, output_parent
        self.status_path = ctx['run'] / 'finalization-status.json'
        self.log_dir = ctx['run'] / 'finalization-logs' / status['attempt_id']
        self.log_dir.mkdir(parents=True, exist_ok=False)

    def save(self):
        self.status['updated_at_utc'] = utc()
        atomic_json(self.status_path, self.status)

    def unchanged(self):
        if digest(self.ctx['config_path']) != self.ctx['config_sha256']:
            raise FinalizationError('Configuration changed during finalization')
        for name, signature in self.status['input_stat'].items():
            path = self.ctx['run'] / name
            stat = path.stat() if path.is_file() else None
            current = [stat.st_size, stat.st_mtime_ns] if stat else None
            if current != signature:
                raise FinalizationError('Frozen input changed during finalization: ' + name)
        if STOP.is_set():
            raise InterruptedError('Finalization interrupted')

    def reuse(self, name, validate):
        self.unchanged()
        entry = {'name': name, 'state': 'verifying_existing', 'started_at_utc': utc()}
        self.status['steps'].append(entry)
        self.status['current_step'] = name
        self.save()
        try:
            validate()
        except BaseException:
            entry.update(state='existing_artifact_invalid', ended_at_utc=utc())
            self.save()
            raise
        entry.update(state='reused_verified', returncode=0, ended_at_utc=utc())
        self.save()

    def step(self, name, command, validate=None, extra_env=None):
        self.unchanged()
        log_path = self.log_dir / f'{len(self.status["steps"]) + 1:02d}-{name}.log'
        entry = {'name': name, 'state': 'running', 'command': command, 'log': str(log_path), 'started_at_utc': utc()}
        self.status['steps'].append(entry)
        self.status['current_step'] = name
        self.save()
        print(json.dumps({'step': name, 'state': 'running', 'log': str(log_path)}, ensure_ascii=False), flush=True)
        with log_path.open('w', encoding='utf-8') as log:
            try:
                process = subprocess.Popen(command, cwd=ROOT, env=child_environment(self.ctx, extra_env),
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            except OSError:
                entry.update(state='launch_failed', returncode=None, ended_at_utc=utc())
                self.save()
                raise
            while process.poll() is None:
                if STOP.wait(1):
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                    break
            code = process.wait()
        entry.update(returncode=code, ended_at_utc=utc(), state='passed' if code == 0 else 'failed')
        self.save()
        if code != 0:
            raise FinalizationError(f'{name} failed with return code {code}; see {log_path}')
        self.unchanged()
        if validate:
            try:
                validate()
            except BaseException:
                entry['state'] = 'validation_failed'
                self.save()
                raise
        return entry

    def execute(self):
        ctx, python = self.ctx, self.ctx['python']
        hashes = self.status['input_sha256']
        legacy = read_json(ctx['legacy'] / 'strong-checks.json')
        if legacy.get('complete') is not True or legacy.get('known_results') != legacy.get('source_records'):
            raise FinalizationError('Complete independent legacy recheck required before finalization')
        report = ctx['report']
        if report.exists() and any(report.iterdir()):
            self.reuse('analyze', lambda: verify_report(ctx, hashes))
        else:
            self.step('analyze', [python, '-m', 'experiments.code_repair_v2.src.analyze', '--config', str(ctx['config_path']), '--output', str(report)], lambda: verify_report(ctx, hashes))
        normalized = report / 'unified-format'
        if normalized.exists() and any(normalized.iterdir()):
            self.reuse('normalize', lambda: verify_normalized(ctx, hashes))
        else:
            self.step('normalize', [python, '-m', 'experiments.code_repair_v2.src.normalize', '--config', str(ctx['config_path']), '--output', str(normalized)], lambda: verify_normalized(ctx, hashes))
        if (ROOT / 'app/data/code-feedback-extension.json').exists():
            self.reuse('publish', lambda: verify_publication(ctx))
        else:
            self.step('publish', [python, '-m', 'experiments.code_repair_v2.src.publish', '--source', str(report), '--legacy-source', str(ctx['legacy'])], lambda: verify_publication(ctx))
        self.step('build-web-app', [python, 'scripts/system/build_web_app.py'])
        self.step('unittest-all-repair-v2', [python, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_repair_v2_*.py', '-v'])
        self.step('scientific-check', [python, 'scripts/system/check_reconstruction.py'])
        node = shutil.which('node')
        if not node:
            raise FinalizationError('Local node executable required; dependencies are never installed automatically')
        with local_site(ROOT / 'app/dist') as base:
            self.status['browser_base_url'] = base
            self.save()
            self.step('browser-defense', [str(Path(node).absolute()), 'tests/browser/defense.mjs'], self.verify_browser,
                      {'BASE_URL': base, 'DEFENSE_PREVIEW_DIR': str(self.log_dir / 'screenshots')})
        self.output_parent.mkdir(parents=True, exist_ok=True)
        staging = self.output_parent / f'{ctx["batch_id"]}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid.uuid4().hex[:8]}'
        staging.mkdir(exist_ok=False)
        self.status['staging_output'] = str(staging)
        self.save()
        self.step('package', [python, 'scripts/system/package_reconstruction.py', '--output', str(staging), '--extension-report', str(report)])
        self.verify_delivery(staging)
        if input_hashes(ctx) != hashes or tooling_hashes() != self.status['tooling_sha256']:
            raise FinalizationError('Frozen inputs or tooling changed; staged files retained, not approved as complete')
        artifacts = [path for path in report.rglob('*') if path.is_file()]
        artifacts += [ROOT / 'app/data/code-feedback-extension.json', ROOT / 'app/assets/research-feedback-svg.zip',
                      ROOT / 'app/dist/index.html', ROOT / 'app/dist/data/code-feedback-extension.json',
                      ROOT / 'app/dist/assets/research-feedback-svg.zip', ROOT / 'artifacts/qa/defense/report.json']
        artifacts += [path for path in staging.rglob('*') if path.is_file()]
        self.status['artifacts_sha256'] = {str(path): digest(path) for path in sorted(set(artifacts))}
        self.status.update(state='complete', current_step=None, completed_at_utc=utc(), returncode=0,
                           report=str(report), unified_format=str(normalized), live_outputs_modified=False,
                           model_api_calls=0)
        self.save()
        print(json.dumps({'state': 'complete', 'staging_output': str(staging), 'live_outputs_modified': False}, ensure_ascii=False), flush=True)

    def verify_browser(self):
        path = ROOT / 'artifacts/qa/defense/report.json'
        report = read_json(path)
        shutil.copy2(path, self.log_dir / 'browser-defense-report.json')
        if (report.get('baseURL') != self.status['browser_base_url'] or report.get('failed')
                or report.get('checks', 0) == 0 or report.get('passed') != report.get('checks')
                or report.get('errors') or report.get('missing')):
            raise FinalizationError('Browser defense report did not fully pass against this script-owned server')

    @staticmethod
    def verify_delivery(staging):
        required = ['知微展示系统_重构版.zip', '知微科研SVG图包.zip', '知微代码反馈SVG图包.zip',
                    '知微展示系统/网站/index.html', '知微展示系统/重建代码反馈图.py',
                    '知微展示系统/代码反馈源图/reports/current/app-evidence.json']
        if any(not (staging / name).is_file() for name in required):
            raise FinalizationError('Packaging command returned without all expected staged artifacts')


def staging_parent(value):
    parent = resolve(value) if value else (ROOT / 'outputs/staging').resolve()
    live = (ROOT / 'outputs/知微展示系统').resolve()
    if parent == live or parent.is_relative_to(live) or (parent.exists() and not parent.is_dir()):
        raise FinalizationError('Use a separate staging parent outside the live delivery directory')
    return parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--watch', action='store_true', help='poll statuses every30s, then finalize once')
    mode.add_argument('--once', action='store_true', help='read-only readiness check; never starts the pipeline or writes status')
    parser.add_argument('--output', type=Path, help='staging parent; a new unique child is always created')
    args = parser.parse_args(argv)
    ctx = context(args.config)
    state = readiness(ctx)
    if args.once:
        if state['ready']:
            state['outcome_audit'] = verify_saved_outcomes(ctx)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0 if state['ready'] else 2
    if state['fatal']:
        raise FinalizationError('; '.join(state['fatal']))
    if not state['ready'] and not args.watch:
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 2
    output_parent = staging_parent(args.output)
    if output_parent.is_relative_to(ctx['run']) or output_parent.is_relative_to(ROOT / 'data'):
        raise FinalizationError('Staging output must stay outside frozen data and the collection run')
    for name in (signal.SIGINT, signal.SIGTERM):
        signal.signal(name, lambda *_: STOP.set())
    status_path = ctx['run'] / 'finalization-status.json'
    with (ctx['run'] / '.finalization.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise FinalizationError('Another finalizer owns this run') from error
        previous = read_json(status_path) if status_path.is_file() else None
        attempt = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        status = {'schema': 'code-feedback-finalization-v1', 'batch_id': ctx['batch_id'],
                  'config_sha256': ctx['config_sha256'], 'attempt_id': attempt, 'state': 'waiting',
                  'started_at_utc': utc(), 'steps': [], 'readiness': state, 'model_api_calls': 0,
                  'live_outputs_modified': False, 'staging_parent': str(output_parent),
                  'planned_artifacts': {'report': str(ctx['report']), 'unified_format': str(ctx['report'] / 'unified-format'),
                                        'publication': str(ROOT / 'app/data/code-feedback-extension.json'),
                                        'built_site': str(ROOT / 'app/dist')}}
        runner = Runner(ctx, status, output_parent)
        if previous:
            atomic_json(runner.log_dir / 'previous-status.json', previous)
        try:
            while not state['ready']:
                status['readiness'] = state
                runner.save()
                print(json.dumps(state, ensure_ascii=False), flush=True)
                if state['fatal']:
                    raise FinalizationError('; '.join(state['fatal']))
                if STOP.wait(30):
                    raise InterruptedError('Stopped while waiting; no pipeline was started')
                state = readiness(ctx)
            status['readiness'] = state
            status['outcome_audit'] = verify_saved_outcomes(ctx)
            hashes, tools = input_hashes(ctx), tooling_hashes()
            if previous and previous.get('state') == 'complete':
                if (previous.get('config_sha256') != ctx['config_sha256'] or previous.get('input_sha256') != hashes
                        or previous.get('tooling_sha256') != tools or not previous.get('artifacts_sha256')
                        or any(not Path(path).is_file() or digest(Path(path)) != sha for path, sha in previous['artifacts_sha256'].items())):
                    raise FinalizationError('Existing completed finalization no longer verifies; all old artifacts preserved')
                print(json.dumps({'state': 'reused_verified_complete', 'staging_output': previous.get('staging_output')}, ensure_ascii=False))
                return 0
            if previous and previous.get('config_sha256') != ctx['config_sha256']:
                raise FinalizationError('Previous finalization belongs to another configuration; preserved for inspection')
            status.update(state='running', input_sha256=hashes, tooling_sha256=tools,
                          input_stat={name: [path.stat().st_size, path.stat().st_mtime_ns] if path.is_file() else None
                                      for name in RUN_INPUTS for path in [ctx['run'] / name]})
            runner.save()
            runner.execute()
            return 0
        except BaseException as error:
            message = f'{type(error).__name__}: {error}'
            failure_log = runner.log_dir / 'finalization-failure.log'
            failure_log.write_text(message + '\n', encoding='utf-8')
            status.update(state='interrupted' if isinstance(error, (KeyboardInterrupt, InterruptedError)) else 'failed',
                          error=message, failure_log=str(failure_log), returncode=130 if STOP.is_set() else 1)
            runner.save()
            print(json.dumps({'state': status['state'], 'error': message, 'failure_log': str(failure_log)}, ensure_ascii=False), file=sys.stderr)
            return status['returncode']


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (FinalizationError, OSError, ValueError, KeyError) as error:
        print(json.dumps({'state': 'not_started', 'error': f'{type(error).__name__}: {error}'}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
