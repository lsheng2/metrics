from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
from shutil import copy2
import sys
import traceback
import uuid


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.service_lifecycle_engine import PlatformOperationSet, ServiceLifecycleEngine, ServiceSpec
from scripts.validation.project_full_stack_support import (
    DEFAULT_DATA_ROOT,
    REPO_ROOT,
    available_port,
    create_run_dir,
    ensure_data_root,
    environment_digest,
    initialize_run_dir,
    json_lines,
    read_json,
    positive_int,
    require_owned_run_dir,
    sanitized_process_environment,
    write_json,
)
from scripts.validation.project_full_stack_identity import (
    classify_stop_evidence,
    create_launch,
    current_launch_for_service,
    normal_stop_evidence,
    relocated_manifest,
    resolve_qualification_work_root,
    status_url,
    stdout_offset,
    validate_connection,
    validate_before_stop,
    validate_manifest,
    validate_process_proof,
    wait_valid_connection,
)
from scripts.validation.project_summary_support import (
    probe_base_imports, sdk_selection, sdk_selection_digest, verify_base_source, verify_installed_sdk,
)
from scripts.validation.project_week_scenarios import fixture_for, settings_for


PROJECT_NAME = 'dashboard-full-stack'
INSTANCE = 'qualify'
APP_NAME = 'project-app'
BASE_NAME = 'ai-base'
SAFE_STOP_SECONDS = 620
APPROVED_CLEAN_WORK_ROOT = ROOT / '.tmp' / 'task-run-w5-clean-merged-20261103'
APPROVED_SDK020_WORK_ROOT = ROOT / '.tmp' / 'sdk-020-join-20261105'
APPROVED_WORK_ROOTS = (APPROVED_CLEAN_WORK_ROOT, APPROVED_SDK020_WORK_ROOT)


def default_base_python() -> Path:
    return ROOT.parent / 'Report_creater_agent' / '.venv' / 'Scripts' / 'python.exe'


def qualify_work_root(value: Path) -> Path:
    return resolve_qualification_work_root(value, ROOT, APPROVED_WORK_ROOTS)


def prepare(args) -> dict:
    scenario = getattr(args, 'scenario', 'single')
    settings_module = settings_for(scenario)
    work = qualify_work_root(args.work_root)
    base_source = (work / 'base-source').resolve(strict=True)
    pack_root = (work / 'artifacts' / 'contract-pack').resolve(strict=True)
    base_python = args.base_python.resolve(strict=True)
    if pack_root != work / 'artifacts' / 'contract-pack' or not base_python.is_file():
        raise ValueError('Use the prepared integration inputs.')
    provenance = verify_base_source(work, base_source)
    sdk = importlib.import_module('ai_base_application_sdk')
    wheel_sha = verify_installed_sdk(work, sdk)
    data_root = ensure_data_root(args.data_root)
    run_dir = create_run_dir(data_root)
    initialize_run_dir(run_dir, data_root)
    args.run_dir = run_dir
    sys.pycache_prefix = str(run_dir / 'environment' / 'pycache-prepare')
    os.environ['DJANGO_SETTINGS_MODULE'] = settings_module
    os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = str(run_dir)
    os.environ['METRICS_PROJECT_FULL_STACK_BOOTSTRAP'] = '1'
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.urls import reverse

    call_command('migrate', interactive=False, verbosity=0)
    fixture = importlib.import_module(fixture_for(scenario)).prepare_catalog(run_dir)
    routes = {'project_stage_reports': reverse('ui_web:project_stage_reports', kwargs={
        'project_id': fixture['project_id'],
        'stage_id': fixture['stage_id'],
    })}
    probe_base_imports(base_python, base_source, run_dir / 'environment', run_dir / 'evidence')
    manifest = {
        'schema_version': 1, 'execution_mode': 'synthetic', 'scenario': scenario,
        'run_dir': str(run_dir),
        'repository': str(REPO_ROOT.resolve()),
        'base_source': str(base_source),
        'base_python': str(base_python),
        'pack_root': str(pack_root),
        'app_python': sys.executable,
        'base_source_provenance': provenance,
        'sdk_version': sdk_selection(work)['sdk_version'],
        'sdk_wheel_sha256': wheel_sha,
        'sdk_selection_sha256': sdk_selection_digest(work),
        'contract_pack_manifest_sha256': hashlib.sha256((pack_root / 'manifest.json').read_bytes()).hexdigest(),
        'catalog': fixture,
        'auth': {
            'alice': {'username': 'SYNTHETIC_ALICE', 'password': 'SYNTHETIC_ALICE_PASSWORD'},
            'bob': {'username': 'SYNTHETIC_BOB', 'password': 'SYNTHETIC_BOB_PASSWORD'},
        },
        'cookies': {
            'session': settings.SESSION_COOKIE_NAME,
            'csrf': settings.CSRF_COOKIE_NAME,
            'language': settings.LANGUAGE_COOKIE_NAME,
        },
        'routes': routes,
        'lifetime_seconds': None,
    }
    write_json(run_dir / 'runtime-manifest.json', manifest)
    return {'status': 'prepared', 'run_dir': str(run_dir), 'execution_mode': 'synthetic',
            'fixture_vector_sha256': fixture['fixture_vector_sha256']}


def lifecycle(run_dir: Path, platform_ops: PlatformOperationSet | None = None) -> ServiceLifecycleEngine:
    return ServiceLifecycleEngine(PROJECT_NAME, run_dir, instance_name=INSTANCE,
                                  state_directory=run_dir / 'lifecycle',
                                  log_directory=run_dir / 'logs',
                                  platform_ops=platform_ops)


def trusted_manifest(run_dir: Path) -> dict:
    manifest = read_json(run_dir / 'runtime-manifest.json')
    validate_manifest(run_dir, manifest, root=ROOT, default_base_python=default_base_python(),
                      app_python=Path(sys.executable), allowed_work_roots=APPROVED_WORK_ROOTS)
    return manifest


def relocate_work_root(args) -> dict:
    run_dir = require_owned_run_dir(args.run_dir)
    work = qualify_work_root(args.work_root)
    manifest = read_json(run_dir / 'runtime-manifest.json')
    updated = relocated_manifest(run_dir, manifest, work, root=ROOT, default_base_python=default_base_python(),
                                 app_python=Path(sys.executable), allowed_work_roots=APPROVED_WORK_ROOTS)
    write_json(run_dir / 'runtime-manifest.json', updated, replace=True)
    return {'status': 'relocated', 'run_dir': str(run_dir), 'work_root': str(work), 'execution_mode': 'synthetic'}


def base_spec(run_dir: Path, lifetime_seconds: int, launch) -> ServiceSpec:
    manifest = trusted_manifest(run_dir)
    base_env = {'PYTHONPYCACHEPREFIX': str(run_dir / 'environment' / 'pycache-base')}
    return ServiceSpec.from_values(
        BASE_NAME, tuple(range(48600, 48621)),
        [manifest['base_python'], '-I', '-X', f'pycache_prefix={run_dir / "environment" / "pycache-base"}',
         str(ROOT / 'scripts' / 'validation' / 'project_full_stack_base.py'),
         '--data-dir', str(run_dir / 'base' / 'store'), '--source-root', manifest['base_source'],
         '--pack-root', manifest['pack_root'], '--fixture', str(run_dir / 'fixture-vector.json'),
         '--stop-file', str(launch.stop_file), '--connection-file', str(launch.connection_file),
         '--exit-file', str(launch.exit_file), '--launch-id', launch.launch_id,
         '--port', '{port}', '--lifetime-seconds', str(lifetime_seconds)],
        stop_command=[manifest['app_python'], '-I', '-c', f'from pathlib import Path; Path({str(launch.stop_file)!r}).touch()'],
        cwd=ROOT, env=base_env, startup_timeout_seconds=45, graceful_timeout_seconds=SAFE_STOP_SECONDS,
    )


def app_spec(run_dir: Path, lifetime_seconds: int, launch, app_port: int | None = None) -> ServiceSpec:
    manifest = trusted_manifest(run_dir)
    app_env = {
        'DJANGO_SETTINGS_MODULE': settings_for(manifest.get('scenario', 'single')),
        'METRICS_PROJECT_FULL_STACK_RUN_DIR': str(run_dir),
        'PYTHONPYCACHEPREFIX': str(run_dir / 'environment' / 'pycache-app'),
    }
    app_ports = (app_port,) if app_port else tuple(range(8127, 8148))
    return ServiceSpec.from_values(
        APP_NAME, app_ports,
        [manifest['app_python'], '-I', '-X', f'pycache_prefix={run_dir / "environment" / "pycache-app"}',
         str(ROOT / 'scripts' / 'validation' / 'project_full_stack_app_entry.py'),
         '--qualify-launch-id', launch.launch_id, '--qualify-exit-file', str(launch.exit_file),
         'project_serve', '--host', '127.0.0.1', '--port', '{port}',
         '--stop-file', str(launch.stop_file), '--lifetime-seconds', str(lifetime_seconds)],
        stop_command=[manifest['app_python'], '-I', '-c', f'from pathlib import Path; Path({str(launch.stop_file)!r}).touch()'],
        cwd=ROOT, env=app_env, startup_timeout_seconds=45, graceful_timeout_seconds=SAFE_STOP_SECONDS,
    )


def start(args) -> dict:
    run_dir = require_owned_run_dir(args.run_dir)
    manifest = trusted_manifest(run_dir)
    lifetime = args.lifetime_seconds
    engine = lifecycle(run_dir)
    state = engine.read_state()
    env_receipts = []
    started = []
    try:
        if not service_running(engine, state.get(BASE_NAME)):
            base_launch = create_launch(run_dir, BASE_NAME, connection=True)
            env_receipts.append(start_sanitized(engine, base_spec(run_dir, lifetime, base_launch), run_dir / 'environment' / 'base-env'))
            started.append(BASE_NAME)
            connection = wait_valid_connection(run_dir, base_launch, engine.read_state()[BASE_NAME], manifest,
                                               platform_ops=engine.platform_ops,
                                               expected_store=manifest.get('base_run_store_id'))
        else:
            base_state = state[BASE_NAME]
            base_launch = current_launch_for_service(run_dir, base_state, BASE_NAME)
            connection = read_json(run_dir / 'base' / 'connection.json')
            validate_connection(connection, base_launch, base_state, manifest, platform_ops=engine.platform_ops,
                                expected_store=manifest.get('base_run_store_id'))
        state = engine.read_state()
        if not service_running(engine, state.get(APP_NAME)):
            launch = create_launch(run_dir, APP_NAME)
            env_receipts.append(start_sanitized(engine, app_spec(run_dir, lifetime, launch, args.port), run_dir / 'environment' / 'app-env'))
            started.append(APP_NAME)
    except Exception:
        cleanup_started(engine, started)
        raise
    app_state = engine.read_state()[APP_NAME]
    manifest['lifetime_seconds'] = lifetime
    manifest['app_port'] = app_state['port']
    manifest['base_run_store_id'] = connection['runStoreId']
    write_json(run_dir / 'runtime-manifest.json', manifest, replace=True)
    write_json(run_dir / 'environment' / f'start-env-{uuid.uuid4()}.json', env_receipts)
    return status_result(run_dir, next_action='stop')


def service_running(engine: ServiceLifecycleEngine, service: dict | None) -> bool:
    return bool(service and engine._service_process_running(service))


def start_sanitized(engine: ServiceLifecycleEngine, spec: ServiceSpec, env_dir: Path):
    with sanitized_process_environment(env_dir) as inherited:
        state = engine.start_service(spec)
    allowed = sorted(inherited)
    return {'service': spec.name, 'allowed_inherited_keys': allowed,
            'environment_digest': environment_digest({key: inherited[key] for key in allowed}),
            'pid': state.pid, 'port': state.port}


def cleanup_started(engine: ServiceLifecycleEngine, started: list[str]) -> None:
    for name in reversed(started):
        try:
            engine.stop_service(name, graceful_timeout_seconds=SAFE_STOP_SECONDS)
        except Exception:
            continue


def status(args) -> dict:
    return status_result(require_owned_run_dir(args.run_dir), next_action='stop')


def status_result(run_dir: Path, *, next_action: str) -> dict:
    manifest = trusted_manifest(run_dir)
    engine = lifecycle(run_dir)
    state = engine.read_state()
    app = state.get(APP_NAME)
    port = int(app['port']) if app else manifest.get('app_port')
    result = {
        'status': 'running' if app and service_running(engine, app) else 'prepared',
        'run_dir': str(run_dir),
        'execution_mode': 'synthetic',
        'url': status_url(port, manifest) if port else None,
        'services': summarize_services(engine, state),
        'next_action': next_action,
        'stop_command': f'{manifest["app_python"]} scripts/validation/project_full_stack.py stop --run-dir "{run_dir}"',
    }
    observations = run_dir / 'base' / 'store' / 'executor-observations.jsonl'
    result['base_dispatch_count'] = len(json_lines(observations))
    return result


def restart_app(args) -> dict:
    run_dir = require_owned_run_dir(args.run_dir)
    manifest = trusted_manifest(run_dir)
    engine = lifecycle(run_dir)
    state = engine.read_state()
    if not service_running(engine, state.get(BASE_NAME)):
        raise ValueError('Owned Base is not running; refusing to replace it.')
    before_connection = read_json(run_dir / 'base' / 'connection.json')
    validate_connection(before_connection, current_launch_for_service(run_dir, state[BASE_NAME], BASE_NAME),
                        state[BASE_NAME], manifest, platform_ops=engine.platform_ops,
                        expected_store=manifest.get('base_run_store_id'))
    before_dispatch = len(json_lines(run_dir / 'base' / 'store' / 'executor-observations.jsonl'))
    app_state = state.get(APP_NAME)
    if not service_running(engine, app_state):
        raise ValueError('Owned app is not running.')
    launch = current_launch_for_service(run_dir, app_state, APP_NAME)
    validate_process_proof(launch, app_state, platform_ops=engine.platform_ops)
    offset = stdout_offset(app_state)
    restart_dir = run_dir / 'evidence' / 'restart' / str(uuid.uuid4())
    stop_result = engine.stop_service(APP_NAME, graceful_timeout_seconds=SAFE_STOP_SECONDS)
    preserve_logs(app_state, restart_dir)
    stop_evidence = normal_stop_evidence(launch, app_state, stop_result, stdout_start=offset, require_worker_event=True)
    write_json(restart_dir / 'app-stop-result.json', {'sle': stop_result, 'evidence': stop_evidence})
    new_launch = create_launch(run_dir, APP_NAME)
    env_receipt = start_sanitized(engine, app_spec(run_dir, int(manifest['lifetime_seconds'] or 1800), new_launch, int(app_state['port'])), run_dir / 'environment' / 'app-restart-env')
    after_connection = read_json(run_dir / 'base' / 'connection.json')
    after_dispatch = len(json_lines(run_dir / 'base' / 'store' / 'executor-observations.jsonl'))
    if (after_connection['runStoreId'], after_connection['grantRevision'], after_dispatch) != (
            before_connection['runStoreId'], before_connection['grantRevision'], before_dispatch):
        raise ValueError('App restart changed Base store, grant or dispatch count.')
    write_json(restart_dir / 'restart-receipt.json', {'environment': env_receipt, 'base_unchanged': True})
    return status_result(run_dir, next_action='stop')


def preserve_logs(app_state: dict, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for key, name in (('stdout_log', 'closed-app.out.log'), ('stderr_log', 'closed-app.err.log')):
        path = Path(app_state[key])
        if path.exists():
            copy2(path, target / name)


def stop(args) -> dict:
    run_dir = require_owned_run_dir(args.run_dir)
    engine = lifecycle(run_dir)
    state = engine.read_state()
    stop_dir = run_dir / 'evidence' / 'stop' / str(uuid.uuid4())
    app_state = state.get(APP_NAME)
    base_state = state.get(BASE_NAME)
    app_launch = current_launch_for_service(run_dir, app_state, APP_NAME) if app_state else None
    base_launch = current_launch_for_service(run_dir, base_state, BASE_NAME) if base_state else None
    validate_before_stop(app_launch, app_state, engine.platform_ops)
    validate_before_stop(base_launch, base_state, engine.platform_ops)
    app_offset = stdout_offset(app_state) if app_state else 0
    app_result = engine.stop_service(APP_NAME, graceful_timeout_seconds=SAFE_STOP_SECONDS)
    if app_state:
        preserve_logs(app_state, stop_dir / 'app')
    base_result = engine.stop_service(BASE_NAME, graceful_timeout_seconds=SAFE_STOP_SECONDS)
    if base_state:
        preserve_logs(base_state, stop_dir / 'base')
    receipt = {'app': app_result, 'base': base_result,
               'classification': classify_stop_evidence(app_launch, app_state, app_result, base_launch, base_state, base_result, app_offset)}
    write_json(stop_dir / 'stop-receipt.json', receipt)
    return {'status': 'stopped', 'run_dir': str(run_dir), 'execution_mode': 'synthetic',
            'normal': receipt['classification'] == 'normal', 'evidence': str(stop_dir / 'stop-receipt.json')}

def summarize_services(engine: ServiceLifecycleEngine, state: dict) -> dict:
    return {
        name: {'port': value.get('port'), 'pid': value.get('pid'),
               'lifecycle_state': value.get('lifecycle_state'),
               'process_running': service_running(engine, value)}
        for name, value in state.items()
    }


def build_parser():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    prepare_cmd = sub.add_parser('prepare')
    prepare_cmd.add_argument('--data-root', type=Path, default=DEFAULT_DATA_ROOT)
    prepare_cmd.add_argument('--base-python', type=Path, default=default_base_python())
    prepare_cmd.add_argument('--work-root', type=Path, default=ROOT / '.tmp' / 'task-run-w5')
    prepare_cmd.add_argument('--scenario', choices=('single', 'full-week'), default='single')
    prepare_cmd.set_defaults(func=prepare)
    start_cmd = sub.add_parser('start')
    start_cmd.add_argument('--run-dir', type=Path, required=True)
    start_cmd.add_argument('--port', type=available_port)
    start_cmd.add_argument('--lifetime-seconds', type=positive_int, default=1800)
    start_cmd.set_defaults(func=start)
    relocate_cmd = sub.add_parser('relocate-work-root')
    relocate_cmd.add_argument('--run-dir', type=Path, required=True)
    relocate_cmd.add_argument('--work-root', type=Path, required=True)
    relocate_cmd.set_defaults(func=relocate_work_root)
    for name, handler in (('status', status), ('restart-app', restart_app), ('stop', stop)):
        command = sub.add_parser(name)
        command.add_argument('--run-dir', type=Path, required=True)
        command.set_defaults(func=handler)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        print(json.dumps(args.func(args), ensure_ascii=True, sort_keys=True))
        return 0
    except Exception as error:
        failure = {'status': 'failed', 'category': type(error).__name__, 'message': 'qualification launcher failed'}
        run_dir = getattr(args, 'run_dir', None)
        if run_dir:
            evidence = Path(run_dir) / 'evidence' / f'failure-{uuid.uuid4()}.json'
            failure['evidence'] = str(evidence)
            write_json(evidence, {'error': type(error).__name__, 'frames': traceback.format_exception(error)})
        print(json.dumps(failure, ensure_ascii=True, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
