import argparse
import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import importlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
from types import SimpleNamespace
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.validation.project_summary_support import (
    assert_checkpoint_not_dispatched, checked_connection, child_environment, owned_data_root, owned_work_root, stop_owned_fixture,
    probe_base_imports, verify_base_source, verify_installed_sdk, worker_matches_process, write_json,
)


def configure_catalog(directory):
    django = importlib.import_module('django')
    settings = importlib.import_module('django.conf').settings
    if settings.configured:
        raise ValueError('The joint driver requires a fresh settings context.')
    settings.configure(
        SECRET_KEY='synthetic-joint-validation-only',
        INSTALLED_APPS=['project_management', 'bug_metrics', 'jira_history', 'jira_sync', 'provider_sync'],
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(directory / 'catalog.sqlite3'),
                               'OPTIONS': {'timeout': 5}}},
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField', USE_TZ=True, TIME_ZONE='UTC',
    )
    django.setup()
    importlib.import_module('django.core.management').call_command('migrate', interactive=False, verbosity=0)


def create_source(directory, *, reuse=False):
    configure_catalog(directory)
    api_module = importlib.import_module('project_management.app.api')
    archive_module = importlib.import_module('project_management.app.api.capture_archive')
    factory = importlib.import_module('project_management.out.capture_archive').LocalArchiveRepositoryFactory()
    catalog = importlib.import_module('project_management.tests.fakes').FixedCatalog()
    catalog.descriptor = replace(catalog.descriptor, endpoint='https://tracker.example.test/jira')
    api = api_module.ApiForProjectManagement(catalog)
    actor = api_module.ProjectActor('archive-owner')
    if reuse:
        saved = json.loads((directory / 'vector.json').read_text(encoding='utf-8'))
        detail = api.get_project(actor, saved['input']['binding']['project_id'])
        project = detail.project
        stage = next(row for row in detail.stages if row.id == saved['input']['binding']['stage_id'])
    else:
        project = api.create_project(actor, key='alpha', name='Alpha reporting')
        stage = api.add_stage(actor, project.id, key='release-1', name='Release 1',
                              selection=api_module.ScopeSelection('alpha-jira', 1))
    data = directory / 'data'
    if reuse and not data.is_dir():
        raise ValueError('Source checkpoint archive is missing.')
    data.mkdir(exist_ok=reuse)
    config = archive_module.ArchiveStorageConfig(
        data, 'Synthetic Validation', 'validation@example.test',
        archive_module.ArchiveLimits(128 * 1024**2, 20000, 64 * 1024**2, 10000,
                                     16 * 1024**2, 2000, 1024**2, 2 * 1024**2),
    )
    archive = archive_module.CaptureArchiveService(api, factory, config)
    if reuse:
        captures = archive.list_captures(actor, project.id, stage.id, limit=2)
        if captures.next_cursor or len(captures.items) != 1:
            raise ValueError('The source checkpoint must contain exactly one capture.')
        receipt = captures.items[0]
        if receipt.capture_id != saved['input']['target_capture_id']:
            raise ValueError('Source checkpoint capture mismatch.')
        archive_path = data / 'projects' / project.id / 'stages' / stage.id / 'archive'
        assert_checkpoint_not_dispatched(archive_path)
    else:
        provider_module = importlib.import_module('provider_sync.tests.capture_gateway_fixtures')
        scenario = SimpleNamespace(actor=actor, project=project, stage=stage)
        provider = provider_module.JiraFixture(scenario, archive=archive)
        provider.project_api = api
        provider.service.project_api = api
        provider.rows = [provider_module.issue(
            status='Fixed', summary='Intermittent validation failure',
            assignee={'key': 'dev-a', 'displayName': 'Alice'}, reporter={'key': 'qa-b', 'displayName': 'Bob'},
        )]
        provider.comments = [
            provider_module.comment(201, 'Failure observed.'),
            provider_module.comment(202, 'Logs attached. Failure reproduced on build r7. '
                                   + '\u539f\u6587 preserved. ' + 'x' * 13000),
            provider_module.comment(203, 'Bob (qa-b), please rerun validation on build r8.'),
        ]
        context = provider.context()
        capture_type = importlib.import_module('project_management.services.capture').ProjectCaptureService
        receipt = capture_type(api, provider.service, archive).capture(context)
    if not receipt.complete or len(receipt.snapshots) != 1:
        raise ValueError('The application capture is not complete.')
    manifest = archive.read_capture(actor, project.id, stage.id, receipt.capture_id)
    reference = receipt.snapshots[0]
    key = archive_module.SourceChainKey(reference.identity.provider_id, reference.identity.endpoint_id,
                                       reference.identity.stable_id, manifest.intent.source.principal_id,
                                       manifest.intent.source.rule_hash)
    snapshot = archive.read_snapshot(actor, project.id, stage.id, receipt.capture_id, key)
    prepared = importlib.import_module('project_management.app.domain.summary_input').build_initial_input(
        project.id, stage, key, reference, snapshot, 'project-reporting.summary@review-1',
    )
    return SimpleNamespace(actor=actor, project=project, stage=stage, api=api, factory=factory,
                           config=config, archive=archive, key=key, prepared=prepared, capture=receipt)


def expected_output(prepared):
    value = json.loads(prepared.input_content)
    return {
        'kind': 'summary', 'binding': value['binding'], 'profile_revision': value['profile_revision'],
        'base_summary_id': None, 'target_capture_id': prepared.target_capture_id, 'output_language': 'en',
        'what': 'Intermittent failure during validation.',
        'current_position': 'The item is marked Fixed. A validation rerun on build r8 is requested.',
        'verification': 'The supplied evidence does not confirm that the rerun passed.',
        'next_actions': [{'action': 'Rerun validation on build r8.', 'owner_id': 'qa-b', 'owner_basis': 'explicit',
                          'owner_quote': 'Bob (qa-b), please rerun validation on build r8.',
                          'owner_confirmed': False, 'state': 'open', 'evidence': ['comment:203']}],
        'blockers': [], 'limitations': [], 'evidence': ['fields', 'comment:201', 'comment:202', 'comment:203'],
    }


def wait_connection(process, directory, scope):
    until = time.monotonic() + 20
    while time.monotonic() < until:
        path = directory / 'connection.json'
        if path.exists():
            return checked_connection(json.loads(path.read_text(encoding='utf-8')), directory, process.pid, scope,
                                      worker_matches=lambda child: worker_matches_process(child, process))
        if process.poll() is not None:
            raise RuntimeError('The synthetic Base fixture exited before readiness.')
        time.sleep(0.05)
    raise TimeoutError('Synthetic fixture readiness timed out.')


async def advance_to_acceptance(service, source, attempt, backend, end):
    for _ in range(8):
        if time.monotonic() >= end:
            raise TimeoutError('The joint validation window expired.')
        step = await service.advance(source.actor, source.project.id, source.stage.id, attempt.attempt_id,
                                     backend=backend)
        if step.state == 'accepted':
            return step.accepted
        if step.state not in {'queued', 'running'}:
            raise RuntimeError(f'Analysis did not progress: {step.state}.')
        await asyncio.sleep(0.1)
    raise RuntimeError('The joint observation limit was reached.')


def run_join(args, work, directory, data_directory, provenance):
    started = time.monotonic()
    sdk = importlib.import_module('ai_base_application_sdk')
    wheel_sha = verify_installed_sdk(work, sdk)
    httpx = importlib.import_module('httpx')
    contract_module = importlib.import_module('project_management.out.ai_task_contract')
    contract = contract_module.AiTaskContract.load(args.pack_root)
    source = create_source(data_directory, reuse=args.resume_source is not None)
    value = json.loads(source.prepared.input_content)
    contract.validate_input(value)
    scope = f'projects.{source.project.id}.stages.{source.stage.id}'
    vector = {'schema_version': 1, 'scope_key': scope, 'input': value,
              'input_sha256': source.prepared.input_hash, 'output': expected_output(source.prepared)}
    vector_path = data_directory / 'vector.json'
    if vector_path.exists():
        if json.loads(vector_path.read_text(encoding='utf-8')) != vector:
            raise ValueError('The preserved source vector differs from the current application input.')
    else:
        write_json(vector_path, vector)
    base_directory = data_directory / f'base-{directory.name}'
    environment_root = data_directory / f'environment-{directory.name}'
    environment_root.mkdir()
    process, connection, accepted, preparation = None, None, None, None
    clients = []
    cleanup = None
    try:
        with (directory / 'fixture.log').open('xb') as log:
            process = subprocess.Popen(
                [str(args.base_python), '-I', '-X', f'pycache_prefix={environment_root / "pycache"}',
                 str(ROOT / 'scripts/validation/project_summary_base_fixture.py'),
                 '--data-dir', str(base_directory), '--source-root', str(args.base_source),
                 '--pack-root', str(args.pack_root), '--fixture', str(data_directory / 'vector.json')],
                cwd=data_directory, env=child_environment(environment_root), stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            connection = wait_connection(process, base_directory, scope)
            analysis = importlib.import_module('project_management.app.api.summary_analysis')
            backend = analysis.AiBackendTarget(
                connection['baseUrl'], connection['sourceAppId'], connection['runStoreId'], scope,
                connection['grantRevision'], connection['limitPolicyRevision'],
            )

            def client(target):
                clients.append(target.run_store_id)
                return sdk.TaskRunClient(
                    base_url=target.base_url, source_app_id=target.source_app_id,
                    credential_ref=connection['credentialRef'], token=connection['token'],
                    run_store_id=target.run_store_id, transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
                )

            service = analysis.SummaryAnalysisService(source.archive, contract, client)
            deadline = datetime.now(UTC) + timedelta(seconds=min(300, max(1, 570 - (time.monotonic() - started))))
            preparation = service.prepare(source.actor, source.project.id, source.stage.id, source.key,
                                          backend=backend, deadline_at=deadline)
            if preparation.kind != 'ready' or preparation.attempt.prepared != source.prepared:
                raise ValueError('Persisted application input differs from the registered vector.')
            accepted = asyncio.run(advance_to_acceptance(service, source, preparation.attempt, backend, started + 600))
            before = len(clients)
            archive_type = importlib.import_module('project_management.app.api.capture_archive').CaptureArchiveService
            reloaded = archive_type(source.api, source.factory, source.config)
            resumed = analysis.SummaryAnalysisService(reloaded, contract, client)
            reused = resumed.prepare(source.actor, source.project.id, source.stage.id, source.key,
                                     backend=backend, deadline_at=datetime.now(UTC) + timedelta(minutes=5))
            if (reused.kind != 'no_work' or reused.accepted.summary_id != accepted.summary_id or len(clients) != before):
                raise ValueError('Recreated application did not reuse its durable accepted summary.')
    finally:
        cleanup = stop_owned_fixture(process, connection, base_directory)
        write_json(directory / 'cleanup.json', cleanup)
    if not cleanup['normal']:
        raise RuntimeError('The owned Base fixture required abnormal cleanup.')
    observations = [json.loads(line) for line in (base_directory / 'executor-observations.jsonl').read_text().splitlines()]
    if len(observations) != 1:
        raise ValueError('Expected exactly one synthetic execution.')
    return {
        'status': 'passed', 'qualification': 'synthetic_business_join_only', 'task': 'W5.JOIN',
        'source': provenance, 'sdkVersion': '0.1.0a2', 'sdkWheelSha256': wheel_sha,
        'dataDirectory': str(data_directory),
        'fixtureDataDirectory': str(base_directory), 'reusedSourceCheckpoint': args.resume_source is not None,
        'contractManifestSha256': contract_module.MANIFEST_SHA, 'projectId': source.project.id,
        'stageId': source.stage.id, 'scopeKey': scope, 'captureId': source.capture.capture_id,
        'sourceHash': source.prepared.source_hash, 'inputSha256': source.prepared.input_hash,
        'attemptId': preparation.attempt.attempt_id, 'runStoreId': connection['runStoreId'],
        'runId': accepted.run_result['runId'], 'resultSha256': accepted.run_result['sha256'],
        'acceptedSummaryId': accepted.summary_id, 'acceptedRevision': accepted.revision,
        'syntheticExecutions': len(observations), 'sdkClientContexts': len(clients),
        'recreatedServiceNoWork': True, 'ownedProcessStopped': cleanup['normal'],
        'elapsedSeconds': round(time.monotonic() - started, 3),
        'notQualified': ['live_provider', 'live_model', 'report_publication', 'full_delta', 'native_crash_recovery'],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--resume-source', type=Path)
    parser.add_argument('--base-python', type=Path, required=True)
    parser.add_argument('--base-source', type=Path, required=True)
    parser.add_argument('--pack-root', type=Path, required=True)
    args = parser.parse_args()
    directory, data_directory = None, None
    try:
        work = owned_work_root(args.work_root, ROOT)
        args.base_source = args.base_source.resolve(strict=True)
        args.base_python = args.base_python.resolve(strict=True)
        args.pack_root = args.pack_root.resolve(strict=True)
        if args.pack_root != work / 'artifacts/contract-pack' or not args.base_python.is_file():
            raise ValueError('Use the prepared integration inputs.')
        provenance = verify_base_source(work, args.base_source)
        data_root = owned_data_root(args.data_root, ROOT)
        run_id = str(uuid.uuid4())
        directory = work / 'runs' / run_id
        directory.mkdir(parents=True)
        if args.resume_source is not None:
            data_directory = args.resume_source.resolve(strict=True)
            if data_directory.parent != data_root or str(uuid.UUID(data_directory.name)) != data_directory.name:
                raise ValueError('Source checkpoint is outside the owned validation root.')
        else:
            data_directory = data_root / run_id
            data_directory.mkdir()
        probe_base_imports(args.base_python, args.base_source, data_directory, directory)
        receipt = run_join(args, work, directory, data_directory, provenance)
        write_json(directory / 'receipt.json', receipt)
        print(json.dumps({'status': 'passed', 'receipt': str(directory / 'receipt.json')}, ensure_ascii=True))
        return 0
    except Exception as error:
        failure = {'status': 'failed', 'errorType': type(error).__name__,
                   'errorCode': getattr(error, 'code', 'INTEGRATION_FAILED'),
                   'frames': [{'file': Path(frame.filename).name, 'line': frame.lineno, 'function': frame.name}
                              for frame in traceback.extract_tb(error.__traceback__)]}
        if directory is not None:
            failure['dataDirectory'] = str(data_directory) if data_directory else None
            write_json(directory / 'failure.json', failure)
            failure['evidenceDirectory'] = str(directory)
        print(json.dumps(failure), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
