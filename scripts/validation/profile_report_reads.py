from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack, contextmanager
from datetime import datetime, UTC
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
from time import perf_counter
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validation.project_full_stack_support import require_owned_run_dir, write_json
from scripts.validation.report_read_identity import (
    baseline_query,
    environment_identity,
    first_draft_id,
    fixture_identity,
    preflight_run_manifest,
    source_identity,
)


AUTH = {
    'HTTP_AUTHORIZATION': 'Basic ' + base64.b64encode(
        b'SYNTHETIC_ALICE:SYNTHETIC_ALICE_PASSWORD',
    ).decode('ascii'),
}


def nearest_rank_p95(values):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = max(1, (95 * len(ordered) + 99) // 100) - 1
    return ordered[index]


def summarize_samples(first_process, serial_samples):
    all_samples = [first_process, *serial_samples]
    failures = [sample for sample in all_samples if sample.get('error') or sample.get('status_code', 0) >= 400]
    redirects = [sample for sample in all_samples if sample.get('redirect_only')]
    first_over_10 = first_process['seconds'] > 10
    invalid = bool(failures or redirects or first_over_10)
    return {
        'first_process_seconds': first_process['seconds'],
        'first_process_status_code': first_process['status_code'],
        'first_process_over_10_seconds': first_over_10,
        'serial_count': len(serial_samples),
        'serial_nearest_rank_p95_seconds': nearest_rank_p95(sample['seconds'] for sample in serial_samples),
        'serial_status_codes': [sample['status_code'] for sample in serial_samples],
        'redirect_only_serial_samples': sum(1 for sample in serial_samples if sample.get('redirect_only')),
        'failure_count': len(failures),
        'invalid_for_slo': invalid,
        'gate_results': {
            'collector_completed': True,
            'slo_eligible': not invalid,
            'all_http_200': all(sample.get('status_code') == 200 for sample in all_samples),
            'no_redirect_only': not redirects,
            'first_process_under_10_seconds': not first_over_10,
        },
    }


def validate_output_dir(run_dir: Path, output_dir: Path) -> Path:
    run_dir = Path(run_dir).resolve(strict=False)
    evidence = run_dir / 'evidence'
    resolved = Path(output_dir).resolve(strict=False)
    if not (resolved == evidence or resolved.is_relative_to(evidence)):
        raise ValueError('Output directory must be inside the owned evidence directory.')
    return resolved


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Profile synthetic report read requests with Django Client.')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--scenario', choices=('workbench', 'baseline', 'preparation', 'editor'), required=True)
    parser.add_argument('--samples', type=_positive_int, default=20)
    parser.add_argument('--dataset', choices=('s0', 's1'), default='s0')
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    started = datetime.now(UTC).isoformat()
    run_dir = require_owned_run_dir(args.run_dir)
    manifest = preflight_run_manifest(run_dir)
    output_dir = validate_output_dir(run_dir, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_started = perf_counter()
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run_dir)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'scripts.validation.project_week_settings'
    import django
    django.setup()
    target = resolve_scenario(run_dir, args.scenario, manifest)
    source_before = source_identity()
    fixture_before = fixture_identity(run_dir, target, manifest)
    setup_seconds = perf_counter() - setup_started
    samples = run_samples(target, args.samples)
    source_after = source_identity()
    fixture_after = fixture_identity(run_dir, target, manifest)
    stable = (source_before['runtime_source_digest'] == source_after['runtime_source_digest']
              and all(fixture_before[key] == fixture_after[key] for key in
                      ('archive_head', 'catalog_sha256', 'runtime_mutable_digest')))
    summary = summarize_samples(samples[0], samples[1:])
    p95 = summary['serial_nearest_rank_p95_seconds']
    scale = args.dataset == 's1'
    enough = len(samples) >= 21
    latency_limit = 5 if scale and args.scenario == 'workbench' else 3
    gates = {
        'stable_inputs': stable,
        'sample_size': enough,
        'successful_requests': not summary['invalid_for_slo'],
        'first_request': samples[0]['seconds'] <= (5 if args.scenario == 'workbench' and not scale else 10),
        'steady_p95': p95 is not None and p95 <= latency_limit,
        'git_processes': max(row['git_calls'] for row in samples) <= (24 if scale else 16),
    }
    summary['performance_gates'] = gates
    summary['performance_passed'] = all(gates.values())
    receipt = {
        'schema_version': 1,
        'started_at': started,
        'scenario': args.scenario,
        'dataset': args.dataset,
        'run_dir': str(run_dir),
        'target': target.receipt(),
        'setup_seconds_not_counted': setup_seconds,
        'first_process': samples[0],
        'serial_samples': samples[1:],
        'summary': summary,
        'source_identity': source_after,
        'source_identity_before': source_before,
        'fixture_identity': fixture_after,
        'fixture_identity_before': fixture_before,
        'environment_identity': environment_identity(output_dir, manifest),
    }
    write_json(output_dir / f'report-read-{args.scenario}-{_stamp()}.json', receipt)
    print(json.dumps(summary, sort_keys=True), flush=True)
    if summary['invalid_for_slo'] or not stable or (args.samples >= 20 and not summary['performance_passed']):
        return 1
    return 0


def run_samples(target, serial_count: int):
    from django.test import Client
    from project_management.storage.git import GitRunner

    samples = []
    with denied_network() as network_attempts:
        for index in range(serial_count + 1):
            meter = GitMeter()
            timer = SqlTimer()
            original = GitRunner.run

            def measured(runner, arguments, **kwargs):
                return meter.run(original, runner, arguments, kwargs)

            client = Client()
            network_before = len(network_attempts)
            before = perf_counter()
            try:
                with patch.object(GitRunner, 'run', measured), sql_wrapper(timer):
                    response = client.get(target.path, data=target.query, **AUTH)
                sample = sample_result(index, perf_counter() - before, response, meter, timer,
                                       len(network_attempts) - network_before)
            except Exception as error:
                sample = failed_sample(index, perf_counter() - before, error, meter, timer,
                                       len(network_attempts) - network_before)
            samples.append(sample)
            if index == 0 and (sample['seconds'] > 10 or sample.get('error') or sample['status_code'] >= 400
                               or sample.get('redirect_only')):
                break
    return samples


def sample_result(index, elapsed, response, meter, timer, network_attempts):
    status = int(response.status_code)
    body = bytes(response.content)
    redirect_only = 300 <= status < 400
    return {
        'index': index,
        'phase': 'first_process' if index == 0 else 'serial',
        'seconds': elapsed,
        'status_code': status,
        'redirect_only': redirect_only,
        'error': None,
        'body_sha256': hashlib.sha256(body).hexdigest(),
        'body_bytes': len(body),
        'git_calls': meter.calls,
        'git_seconds': meter.seconds,
        'git_bytes': meter.bytes,
        'git_operations': meter.operations,
        'sql_calls': timer.calls,
        'sql_seconds': timer.seconds,
        'network_attempts': network_attempts,
    }


def failed_sample(index, elapsed, error, meter, timer, network_attempts):
    return {
        'index': index,
        'phase': 'first_process' if index == 0 else 'serial',
        'seconds': elapsed,
        'status_code': 0,
        'redirect_only': False,
        'error': {'type': type(error).__name__, 'code': getattr(error, 'code', None)},
        'body_sha256': None,
        'body_bytes': 0,
        'git_calls': meter.calls,
        'git_seconds': meter.seconds,
        'git_bytes': meter.bytes,
        'git_operations': meter.operations,
        'sql_calls': timer.calls,
        'sql_seconds': timer.seconds,
        'network_attempts': network_attempts,
    }


class GitMeter:
    def __init__(self):
        self.calls = 0
        self.seconds = 0.0
        self.bytes = 0
        self.operations = {}

    def run(self, original, runner, arguments, kwargs):
        started = perf_counter()
        self.calls += 1
        self.bytes += len(kwargs.get('input_data') or b'')
        self.operations[arguments[0]] = self.operations.get(arguments[0], 0) + 1
        try:
            result = original(runner, arguments, **kwargs)
            self.bytes += len(result.stdout) + len(result.stderr)
            return result
        finally:
            self.seconds += perf_counter() - started


class SqlTimer:
    def __init__(self):
        self.calls = 0
        self.seconds = 0.0

    def __call__(self, execute, sql, params, many, context):
        started = perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            self.calls += 1
            self.seconds += perf_counter() - started


@contextmanager
def sql_wrapper(timer):
    from django.db import connection
    with connection.execute_wrapper(timer):
        yield


@contextmanager
def denied_network():
    attempts = []

    def denied(*args, **kwargs):
        attempts.append({'args': repr(args[:1])})
        raise AssertionError('External network is forbidden for report read profiling.')

    with ExitStack() as stack:
        stack.enter_context(patch.object(socket.socket, 'connect', denied))
        stack.enter_context(patch.object(socket.socket, 'connect_ex', denied))
        stack.enter_context(patch.object(socket, 'create_connection', denied))
        stack.enter_context(patch.object(socket, 'getaddrinfo', denied))
        yield attempts


class ScenarioTarget:
    def __init__(self, path: str, query: dict, project_id: str, stage_id: str, extra: dict | None = None):
        self.path = path
        self.query = query
        self.project_id = project_id
        self.stage_id = stage_id
        self.extra = extra or {}

    def receipt(self):
        return {
            'path': self.path,
            'query_keys': sorted(self.query),
            'project_id': self.project_id,
            'stage_id': self.stage_id,
            **self.extra,
        }


def resolve_scenario(run_dir: Path, scenario: str, manifest: dict) -> ScenarioTarget:
    from project_management.models import Project

    catalog = manifest['catalog']
    project = Project.objects.filter(id=catalog['project_id'], owner_subject=catalog['actor']).first()
    if project is None:
        raise ValueError('Synthetic Alice project was not found in the run database.')
    stage = project.stages.filter(id=catalog['stage_id']).first()
    if stage is None:
        raise ValueError('Synthetic Alice stage was not found in the run database.')
    base = manifest.get('routes', {}).get('project_stage_reports', '')
    if (not base.startswith('/') or base.startswith('//') or not base.endswith('/reports/')
            or f'/projects/{project.id}/stages/{stage.id}/' not in base):
        raise ValueError('Manifest report route does not match its catalog.')
    if scenario == 'workbench':
        return ScenarioTarget(base, {}, str(project.id), str(stage.id))
    if scenario == 'baseline':
        query = baseline_query(run_dir, project, stage)
        return ScenarioTarget(base + 'baseline-preview/', query, str(project.id), str(stage.id))
    if scenario == 'preparation':
        from uuid import UUID

        root = run_dir / 'archive' / 'projects' / str(project.id) / 'stages' / str(stage.id) / 'runtime' / 'report-preparations'
        ids = sorted(path.parent.name for path in root.glob('*/intent.json'))
        if not ids:
            raise ValueError('Preparation scenario requires a saved preparation.')
        preparation_id = str(UUID(ids[0]))
        return ScenarioTarget(base + f'preparations/{preparation_id}/', {}, str(project.id), str(stage.id),
                              {'preparation_id': preparation_id})
    draft_id = first_draft_id(run_dir, str(project.id), str(stage.id))
    return ScenarioTarget(
        base + f'drafts/{draft_id}/',
        {},
        str(project.id),
        str(stage.id),
        {'draft_id': draft_id},
    )


def _stamp() -> str:
    return datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')


def _positive_int(value: str) -> int:
    parsed = int(value)
    if not 1 <= parsed <= 100:
        raise argparse.ArgumentTypeError('samples must be between 1 and 100')
    return parsed


if __name__ == '__main__':
    raise SystemExit(main())
