import argparse
from datetime import UTC, datetime
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import traceback
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validation import project_full_stack
from scripts.validation.project_full_stack_support import read_json, require_owned_run_dir, write_json
from scripts.validation.run_report_authoring_tests import (
    guarded_connect, guarded_create_connection, guarded_getaddrinfo,
)


def source_identity():
    paths = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], timeout=15,
    ).decode('utf-8').split('\0')
    prefixes = ('project_management/', 'provider_sync/', 'bug_metrics/', 'ui_web/', 'metrics/', 'scripts/')
    files = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
             for name in sorted(set(paths))
             if name.startswith(prefixes) and (ROOT / name).is_file()
             and Path(name).suffix in {'.py', '.json', '.js', '.css', '.html'}}
    return {'commit': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                                              text=True, timeout=15).strip(),
            'kind': 'working_tree_not_clean_commit', 'files': files}


def run_cases(run_dir, directory):
    from scripts.validation.project_sdk_join_cases import (
        cancel_late_result, context, dispatches, first_and_unchanged, lost_submit, refuse_results,
    )

    ctx = context(run_dir)
    results = first_and_unchanged(ctx, directory)
    write_json(directory / 'progress.json', results)
    results['J020-02'] = lost_submit(ctx, directory)
    write_json(directory / 'progress.json', results, replace=True)
    results['J020-03'] = refuse_results(ctx, directory)
    write_json(directory / 'progress.json', results, replace=True)
    results['J020-05'] = cancel_late_result(ctx, directory)
    count = len(dispatches(run_dir))
    if count != 6:
        raise AssertionError(f'Expected six synthetic executions across independent cases, observed {count}.')
    receipt = {'status': 'JOIN_BUSINESS_PASSED', 'run_store_id': ctx.backend.run_store_id,
               'base_url': ctx.backend.base_url, 'dispatch_count': count, 'cases': results,
               'evidence_directory': str(directory)}
    write_json(run_dir / 'evidence/sdk020-business.json', receipt)
    return receipt


def verify_reopen(run_dir, directory):
    import asyncio
    from scripts.validation.project_sdk_join_cases import (
        context, dispatches, require, sdk_client, summary_files,
    )

    previous = read_json(run_dir / 'evidence/sdk020-business.json')
    ctx = context(run_dir)
    require(ctx.backend.run_store_id == previous['run_store_id'], 'Reopen replaced the Base store.')
    require(ctx.backend.base_url == previous['base_url'], 'Reopen changed a retained Run endpoint.')
    require(len(dispatches(run_dir)) == previous['dispatch_count'], 'Reopen dispatched new inference.')
    case = previous['cases']['J020-01']
    original = ctx.service.get(ctx.actor, ctx.project_id, ctx.stage_id, case['operation_id'])
    require(original.draft_id == case['draft_id'] and original.state == 'draft_ready',
            'Reopen lost the original Dashboard operation or draft.')
    ctx.service.draft_service.get(ctx.actor, ctx.project_id, ctx.stage_id, case['draft_id'])
    require(summary_files(ctx.service.archive, ctx.project_id, ctx.stage_id)
            == previous['cases']['J020-04']['accepted_files'], 'Reopen altered accepted summary bytes.')

    async def read_original():
        async with sdk_client(ctx) as client:
            return await client.get_by_client_key(ctx.backend.scope_key, case['attempt_id'])

    snapshot = asyncio.run(read_original())
    require(snapshot['runId'] == case['run_id'], 'Reopen did not preserve the original Run reference.')
    require(len(dispatches(run_dir)) == previous['dispatch_count'], 'Read-only reopen check created new work.')
    result = {'case': 'J020-06', 'status': 'passed', 'run_store_id': ctx.backend.run_store_id,
              'run_id': snapshot['runId'], 'dispatch_count': previous['dispatch_count'],
              'prior_business_evidence': previous['evidence_directory']}
    write_json(directory / 'reopen.json', result)
    write_json(run_dir / 'evidence/sdk020-reopen.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run', 'reopen'))
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    run_dir = require_owned_run_dir(args.run_dir)
    manifest = project_full_stack.trusted_manifest(run_dir)
    if manifest.get('sdk_version') != '0.2.0a1':
        raise ValueError('This qualification requires the selected SDK 0.2.0a1 fixture.')
    if args.action == 'run' and (run_dir / 'evidence/sdk020-business.json').exists():
        raise ValueError('A completed business run cannot be relabeled or repeated.')
    directory = run_dir / 'evidence' / f'sdk020-{args.action}-{uuid.uuid4()}'
    directory.mkdir()
    started = time.monotonic()
    os.environ['DJANGO_SETTINGS_MODULE'] = 'scripts.validation.project_full_stack_settings'
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run_dir)
    os.environ.pop('METRICS_PROJECT_FULL_STACK_BOOTSTRAP', None)
    receipt = {'action': args.action, 'started_at': datetime.now(UTC).isoformat(),
               'sdk_version': metadata.version('ai-base-application-sdk'),
               'interpreter': sys.executable, 'base_provenance': manifest['base_source_provenance'],
               'sdk_wheel_sha256': manifest['sdk_wheel_sha256'],
               'pack_manifest_sha256': manifest['contract_pack_manifest_sha256'],
               'dependencies': {name: metadata.version(name) for name in ('django', 'httpx', 'jsonschema', 'pywin32')},
               'source': source_identity(), 'real_providers': False, 'real_models': False}
    code = 1
    try:
        with patch.object(socket.socket, 'connect', guarded_connect(socket.socket.connect)), \
                patch.object(socket.socket, 'connect_ex', guarded_connect(socket.socket.connect_ex)), \
                patch.object(socket, 'create_connection', guarded_create_connection(socket.create_connection)), \
                patch.object(socket, 'getaddrinfo', guarded_getaddrinfo(socket.getaddrinfo)):
            import django
            django.setup()
            receipt['result'] = run_cases(run_dir, directory) if args.action == 'run' else verify_reopen(run_dir, directory)
        receipt['status'] = 'passed'
        code = 0
    except Exception as error:
        receipt.update(status='failed', error_type=type(error).__name__,
                       error_code=getattr(error, 'code', None), traceback=traceback.format_exc())
    finally:
        receipt['elapsed_seconds'] = round(time.monotonic() - started, 3)
        write_json(directory / 'receipt.json', receipt)
    print(json.dumps({'status': receipt['status'], 'receipt': str(directory / 'receipt.json')}))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
