import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import time
import uuid

from ai_base_application_sdk import TaskRunClient
import httpx

from project_management.app.api import ProjectActor
from project_management.app.api.capture_archive import SourceChainKey
from project_management.app.api.report_factories import build_report_service
from project_management.app.api.summary_analysis import SummaryAnalysisService
from project_management.app.domain.summary_contracts import AiBackendTarget, AnalysisError
from project_management.out.ai_task_contract import AiTaskContract
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.services.capture import ProjectCaptureService
from project_management.services.capture_archive import CaptureArchiveService
from scripts.validation.project_full_stack_fixture import (
    archive_config, build_runtime_environment, create_provider_fixture, expected_output,
    install_profile_registry_override,
)
from scripts.validation.project_full_stack_support import read_json, write_json
from scripts.validation.project_sdk_join_faults import HttpFaults


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def dispatches(run_dir):
    path = run_dir / 'base/store/executor-observations.jsonl'
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()] if path.exists() else []


def summary_files(archive, project_id, stage_id):
    root = archive.config.root / 'projects' / project_id / 'stages' / stage_id / 'archive'
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / 'accepted_summaries').glob('*/*.json')}


@dataclass(slots=True)
class JoinedContext:
    run_dir: Path
    manifest: dict
    connection: dict
    service: object
    actor: ProjectActor
    project_id: str
    stage_id: str
    contract: AiTaskContract
    backend: AiBackendTarget


def context(run_dir):
    manifest = read_json(run_dir / 'runtime-manifest.json')
    connection = read_json(run_dir / 'base/connection.json')
    install_profile_registry_override()
    service = build_runtime_environment(connection).run_service
    project_id, stage_id = manifest['catalog']['project_id'], manifest['catalog']['stage_id']
    backend = AiBackendTarget(
        connection['baseUrl'], connection['sourceAppId'], connection['runStoreId'],
        manifest['catalog']['scope_key'], connection['grantRevision'], connection['limitPolicyRevision'],
    )
    return JoinedContext(run_dir, manifest, connection, service,
                         ProjectActor(manifest['catalog']['actor']), project_id, stage_id,
                         AiTaskContract.load(connection['packRoot']), backend)


def sdk_client(ctx, faults=None):
    return TaskRunClient(
        base_url=ctx.backend.base_url, source_app_id=ctx.backend.source_app_id,
        credential_ref=ctx.connection['credentialRef'], token=ctx.connection['token'],
        run_store_id=ctx.backend.run_store_id,
        transport=faults.wrap() if faults else httpx.AsyncHTTPTransport(retries=0, trust_env=False),
    )


def web_run(ctx, case_dir):
    auth = ctx.manifest['auth']['alice']
    base_url = f'http://127.0.0.1:{ctx.manifest["app_port"]}'
    stage_url = ctx.manifest['routes']['project_stage_reports']
    with httpx.Client(base_url=base_url, auth=(auth['username'], auth['password']),
                      trust_env=False, timeout=20, follow_redirects=False) as client:
        page = client.get(stage_url)
        require(page.status_code == 200, f'Dashboard page refused: {page.status_code}')
        data = {
            'command_id': str(uuid.uuid4()), 'expected_stage_hash': ctx.manifest['catalog']['stage_hash'],
            'template_id': 'daily-standup', 'template_version': '1', 'timezone': 'Asia/Shanghai',
        }
        response = client.post(stage_url + 'runs/', data=data, headers={
            'X-CSRFToken': client.cookies[ctx.manifest['cookies']['csrf']], 'Referer': base_url + stage_url,
        })
        require(response.status_code == 302, f'Dashboard submit refused: {response.status_code}')
        location = response.headers['location']
        operation_id = str(uuid.UUID(location.rstrip('/').rsplit('/', 1)[-1]))
        deadline = time.monotonic() + 240
        while True:
            operation = ctx.service.get(ctx.actor, ctx.project_id, ctx.stage_id, operation_id)
            if operation.state in {'draft_ready', 'partial', 'failed', 'canceled'}:
                break
            require(time.monotonic() < deadline, 'Dashboard operation exceeded its bounded observation window.')
            time.sleep(0.5)
        write_json(case_dir / 'operation.json', operation)
        require(operation.state == 'draft_ready', f'Dashboard operation did not produce a draft: {operation}')
        status_page = client.get(location)
        require(status_page.status_code == 200 and operation.draft_id in status_page.text,
                'Dashboard status did not expose the produced draft.')
        (case_dir / 'status.html').write_bytes(status_page.content)
        draft = ctx.service.draft_service.get(ctx.actor, ctx.project_id, ctx.stage_id, operation.draft_id)
        render_url = stage_url + f'drafts/{operation.draft_id}/render/?revision={draft.revision}'
        rendered = client.get(render_url)
        require(rendered.status_code == 200 and b'ALPHA-101' in rendered.content,
                'Produced draft was not renderable through Dashboard HTTP.')
        (case_dir / 'draft.html').write_bytes(rendered.content)
    return operation, draft


def first_and_unchanged(ctx, evidence):
    first_dir = evidence / 'J020-01'
    first_dir.mkdir()
    before = len(dispatches(ctx.run_dir))
    operation, draft = web_run(ctx, first_dir)
    require(len(operation.item_results) == 1 and operation.item_results[0].state == 'accepted',
            'First run must accept exactly one ticket.')
    require(len(dispatches(ctx.run_dir)) == before + 1, 'First run did not use exactly one Base dispatch.')
    attempt = ctx.service.archive.read_analysis_attempt(
        ctx.actor, ctx.project_id, ctx.stage_id, operation.item_results[0].attempt_id,
    )
    accepted = ctx.service.analysis_service.prepare(
        ctx.actor, ctx.project_id, ctx.stage_id, attempt.source_key,
        backend=ctx.backend, deadline_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    require(accepted.kind == 'no_work', 'Accepted source unexpectedly needs another inference.')
    ctx.contract.validate_result(attempt, ctx.service.archive.read_analysis_observations(
        ctx.actor, ctx.project_id, ctx.stage_id, attempt.attempt_id,
    )[-1]['snapshot'], accepted.accepted.run_result)
    initial_files = summary_files(ctx.service.archive, ctx.project_id, ctx.stage_id)
    require(len(initial_files) == 1, 'First acceptance has the wrong durable summary count.')
    write_json(first_dir / 'accepted.json', accepted.accepted)
    write_json(first_dir / 'attempt.json', attempt)
    second_dir = evidence / 'J020-04'
    second_dir.mkdir()
    second, _ = web_run(ctx, second_dir)
    require(second.capture_id != operation.capture_id, 'Unchanged check must perform a new capture.')
    require(second.item_results[0].state == 'no_work' and second.item_results[0].attempt_id is None,
            'Unchanged capture created a new analysis attempt.')
    require(second.item_results[0].accepted_summary_id == accepted.accepted.summary_id,
            'Unchanged capture did not reuse the original accepted summary.')
    require(summary_files(ctx.service.archive, ctx.project_id, ctx.stage_id) == initial_files,
            'Unchanged capture modified accepted bytes.')
    require(len(dispatches(ctx.run_dir)) == before + 1, 'Unchanged capture dispatched inference.')
    return {
        'J020-01': {'status': 'passed', 'operation_id': operation.operation_id,
                    'draft_id': draft.draft_id, 'attempt_id': attempt.attempt_id,
                    'run_id': accepted.accepted.run_result['runId'], 'summary_id': accepted.accepted.summary_id,
                    'source_hash': attempt.prepared.source_hash, 'input_hash': attempt.prepared.input_hash},
        'J020-04': {'status': 'passed', 'operation_id': second.operation_id,
                    'new_dispatches': 0, 'accepted_files': initial_files},
    }


def prepare_fault_source(ctx, name):
    root = ctx.run_dir / 'case-data' / name
    root.mkdir(parents=True)
    archive = CaptureArchiveService(ctx.service.project_api, LocalArchiveRepositoryFactory(), archive_config(root))
    provider = create_provider_fixture(ctx.service.project_api, archive)
    capture = ProjectCaptureService(ctx.service.project_api, provider.service, archive,
                                    required_parts=('facts', 'comments', 'history')).capture(provider.context())
    require(capture.complete and len(capture.snapshots) == 1, 'Fault source capture is incomplete.')
    manifest = archive.read_capture(ctx.actor, ctx.project_id, ctx.stage_id, capture.capture_id)
    identity = capture.snapshots[0].identity
    key = SourceChainKey(identity.provider_id, identity.endpoint_id, identity.stable_id,
                         manifest.intent.source.principal_id, manifest.intent.source.rule_hash)
    return archive, key


def analysis_service(ctx, archive, faults):
    return SummaryAnalysisService(archive, ctx.contract, lambda target: sdk_client(ctx, faults))


def preparation(ctx, service, key):
    value = service.prepare(ctx.actor, ctx.project_id, ctx.stage_id, key, backend=ctx.backend,
                            deadline_at=datetime.now(UTC) + timedelta(minutes=5))
    require(value.kind == 'ready', 'Fresh fault source did not create an analysis intent.')
    return value.attempt


async def advance_until(ctx, service, attempt_id):
    for _ in range(12):
        step = await service.advance(ctx.actor, ctx.project_id, ctx.stage_id, attempt_id, backend=ctx.backend)
        if step.state not in {'queued', 'running'}:
            return step
        await asyncio.sleep(0.1)
    raise AssertionError('Joined analysis exceeded its bounded observation count.')


def lost_submit(ctx, evidence):
    directory = evidence / 'J020-02'
    directory.mkdir()
    archive, key = prepare_fault_source(ctx, 'lost-submit')
    faults = HttpFaults(mode='drop_submit')
    service = analysis_service(ctx, archive, faults)
    attempt = preparation(ctx, service, key)
    before = len(dispatches(ctx.run_dir))
    first = asyncio.run(service.advance(ctx.actor, ctx.project_id, ctx.stage_id, attempt.attempt_id, backend=ctx.backend))
    require(first.state == 'unknown' and faults.triggered, 'Submit loss did not retain an unknown outcome.')
    reloaded = CaptureArchiveService(ctx.service.project_api, LocalArchiveRepositoryFactory(), archive.config)
    resumed = analysis_service(ctx, reloaded, faults)
    recovered = asyncio.run(advance_until(ctx, resumed, attempt.attempt_id))
    require(recovered.state == 'accepted', 'Original-key recovery did not accept the retained result.')
    retained = reloaded.read_analysis_attempt(ctx.actor, ctx.project_id, ctx.stage_id, attempt.attempt_id)
    require(retained.request == attempt.request and retained.backend == attempt.backend,
            'Recovery replaced the key, deadline, store or immutable input.')
    require(sum(row['method'] == 'POST' for row in faults.events) == 1, 'Recovery sent a second POST.')
    require(any(row['client_run_key'] == attempt.attempt_id for row in faults.events),
            'Recovery did not query the original client key.')
    require(len(dispatches(ctx.run_dir)) == before + 1, 'Recovery repeated Base execution.')
    require(len(summary_files(reloaded, ctx.project_id, ctx.stage_id)) == 1, 'Recovery duplicated acceptance.')
    write_json(directory / 'http.json', faults.events)
    write_json(directory / 'accepted.json', recovered.accepted)
    write_json(directory / 'attempt.json', retained)
    return {'status': 'passed', 'attempt_id': attempt.attempt_id, 'run_id': recovered.accepted.run_result['runId'],
            'summary_id': recovered.accepted.summary_id, 'post_count': 1, 'dispatch_count': 1,
            'original_deadline': retained.request['deadlineAt'], 'archive_root': str(archive.config.root)}


def refuse_results(ctx, evidence):
    results = {}
    for mode in ('wrong_store', 'wrong_digest', 'wrong_evidence'):
        directory = evidence / 'J020-03' / mode
        directory.mkdir(parents=True)
        archive, key = prepare_fault_source(ctx, mode)
        faults = HttpFaults(mode=mode)
        service = analysis_service(ctx, archive, faults)
        attempt = preparation(ctx, service, key)
        invalid = expected_output(json.loads(attempt.prepared.input_content))
        invalid['target_capture_id'] = attempt.prepared.target_capture_id
        invalid['evidence'] = ['comment:999']
        faults.replacement_content = json.dumps(invalid, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        try:
            step = asyncio.run(advance_until(ctx, service, attempt.attempt_id))
            error = step.error_code
            require(step.state != 'accepted', 'Wrong result was accepted.')
        except AnalysisError as refused:
            error = refused.code
        require(faults.triggered, 'Wrong-result case never reached its HTTP boundary.')
        require(error in {'run_store_mismatch', 'invalid_response', 'ANALYSIS_RESULT_INVALID',
                          'ANALYSIS_EVIDENCE_INVALID'}, f'Unexpected refusal: {error}')
        if mode == 'wrong_evidence':
            require(error == 'ANALYSIS_EVIDENCE_INVALID', 'Evidence case did not reach business validation.')
        require(not summary_files(archive, ctx.project_id, ctx.stage_id), 'Refused result advanced acceptance.')
        reports = build_report_service(project_api=ctx.service.project_api, archive=archive, contract=ctx.contract)
        require(not reports.list_publications(ctx.actor, ctx.project_id, ctx.stage_id).items,
                'Refused result produced a publication.')
        write_json(directory / 'http.json', faults.events)
        write_json(directory / 'attempt.json', attempt)
        results[mode] = {'status': 'passed', 'error_code': error, 'accepted_count': 0,
                         'archive_root': str(archive.config.root), 'attempt_id': attempt.attempt_id}
    return results


def cancel_late_result(ctx, evidence):
    directory = evidence / 'J020-05'
    directory.mkdir()
    archive, key = prepare_fault_source(ctx, 'cancel-late-result')
    faults = HttpFaults(mode='cancel_before_result')
    service = analysis_service(ctx, archive, faults)
    attempt = preparation(ctx, service, key)

    async def persist_cancel():
        await asyncio.to_thread(archive.request_analysis_cancel, ctx.actor, ctx.project_id, ctx.stage_id,
                                attempt.attempt_id)

    faults.on_result = persist_cancel
    step = asyncio.run(advance_until(ctx, service, attempt.attempt_id))
    require(step.state == 'canceled' and faults.triggered, 'Late result crossed the durable cancel fence.')
    require(not summary_files(archive, ctx.project_id, ctx.stage_id), 'Canceled result advanced acceptance.')
    canceled = asyncio.run(service.cancel(ctx.actor, ctx.project_id, ctx.stage_id, attempt.attempt_id,
                                         backend=ctx.backend))
    before = len(faults.events)
    replay = asyncio.run(service.advance(ctx.actor, ctx.project_id, ctx.stage_id, attempt.attempt_id,
                                         backend=ctx.backend))
    require(replay.state == 'canceled' and len(faults.events) == before, 'Cancel replay performed new I/O.')
    write_json(directory / 'http.json', faults.events)
    write_json(directory / 'cancellation.json', canceled)
    return {'status': 'passed', 'attempt_id': attempt.attempt_id, 'remote_stop': canceled.remote_stop,
            'accepted_count': 0, 'archive_root': str(archive.config.root),
            'usage_not_inferred_from_business_cancel': True}
