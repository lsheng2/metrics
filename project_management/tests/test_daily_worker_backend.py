from dataclasses import replace
from pathlib import Path
import uuid

import pytest

from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker, RunError
from project_management.app.domain.capture_values import canonical_bytes, content_hash, decode_json, sha256_bytes
from project_management.app.domain.run_admission_values import (
    original_operation_from_record,
    stored_request_payload,
    validate_stored_request,
)
from project_management.app.api import reports as report_api
from project_management.app.domain.run_contracts import DailyRunRequest, DailyRunTarget, RunRequest
from project_management.app.domain.run_values import (
    capture_id as run_capture_id,
    operation_id as run_operation_id,
    policy_hash,
    request_from_mapping,
    request_hash,
    request_payload,
)
from project_management.tests.project_run_fixtures import ManualRunEnvironment
from project_management.tests.project_run_fixtures import ProviderAccessDouble
from project_management.tests.history_persistence_fixtures import history_fixture
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.report_render_fixtures import daily_template
from project_management.services.capture import ProjectCaptureService
from project_management.services.report_sources import ReportSourceReader
from project_management.out.ai_task_contract import AiTaskContract
from project_management.tests.summary_fixtures import PACK_ROOT
from project_management.app.api.summary_analysis import AiBackendTarget, SummaryAnalysisService
from project_management.tests.project_run_fixtures import ProjectRunHttp


def daily_target(operation_id, draft_id='71000000-0000-4000-8000-000000000001',
                 preparation_id='71000000-0000-4000-8000-000000000002',
                 intent_hash='1' * 64, selection_hash='2' * 64,
                 analysis_mode='manual_only'):
    return DailyRunTarget(
        preparation_id=preparation_id,
        preparation_intent_hash=intent_hash,
        draft_id=draft_id,
        effective_selection_hash=selection_hash,
        source_mode='refresh',
        analysis_mode=analysis_mode,
    )


def daily_request(stage_hash, command_id, *, analysis_mode='manual_only'):
    operation_id = run_operation_id('70000000-0000-4000-8000-000000000002', command_id)
    return DailyRunRequest(
        command_id,
        stage_hash,
        report_api.UserTemplateSelection(
            '76000000-0000-4000-8000-000000000001',
            1,
            'a' * 64,
        ),
        'Asia/Shanghai',
        daily_target(operation_id, analysis_mode=analysis_mode),
    )


def operation_for(environment, request):
    op_id = run_operation_id(environment.stage.id, request.command_id)
    created_at = '2026-11-02T00:00:00.000Z'
    from project_management.app.domain.run_contracts import RunOperation

    return RunOperation(
        op_id,
        request.command_id,
        environment.project.id,
        environment.stage.id,
        environment.actor.subject,
        environment.stage.definition_hash,
        policy_hash(environment.run_service.policy),
        created_at,
        '2026-11-02T00:10:00.000Z',
        run_capture_id(op_id),
        'queued',
        1,
        False,
        (),
        None,
        None,
        None,
        None,
        None,
        None,
        'synthetic',
    )


def test_should_keep_legacy_run_request_payload_and_hash_exactly_four_fields():
    legacy = RunRequest('bbbbbbbb-bbbb-4bbb-8bbb-000000000001', 'b' * 64, daily_template(), 'Asia/Shanghai')

    payload = request_payload(legacy)

    assert set(payload) == {'command_id', 'expected_stage_hash', 'template', 'timezone'}
    assert request_from_mapping(payload) == legacy
    assert request_hash(legacy) == content_hash(payload)


def test_should_hash_daily_request_from_original_schema2_payload_without_effective_capture_id():
    command_id = 'bbbbbbbb-bbbb-4bbb-8bbb-000000000002'
    request = daily_request('b' * 64, command_id)

    payload = request_payload(request)
    replay = request_from_mapping(payload)

    assert payload['schema_version'] == 2
    assert 'capture_id' not in payload['target']
    assert payload['target']['analysis_mode'] == 'manual_only'
    assert request_hash(request) == content_hash(payload)
    assert replay == request


def test_should_reject_daily_request_with_legacy_builtin_template_selection():
    request = DailyRunRequest(
        'bbbbbbbb-bbbb-4bbb-8bbb-000000000099',
        'b' * 64,
        daily_template(),
        'Asia/Shanghai',
        daily_target('71000000-0000-4000-8000-000000000099'),
    )

    with pytest.raises(RunError) as error:
        request_payload(request)

    assert error.value.code == 'RUN_INVALID'


def test_should_store_daily_manual_request_with_null_backend_and_reject_changed_items_without_backend(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    request = daily_request(environment.stage.definition_hash, str(uuid.uuid4()))
    operation = operation_for(environment, request)

    record = stored_request_payload(
        operation,
        request,
        environment.run_service.policy,
        None,
        request_hash(request),
        environment.run_service.capture_limits,
    )
    restored_request, _, backend, stored_hash, _ = validate_stored_request(record)

    changed = replace(request, target=replace(request.target, analysis_mode='changed_items'))
    changed_record = stored_request_payload(
        operation,
        changed,
        environment.run_service.policy,
        None,
        request_hash(changed),
        environment.run_service.capture_limits,
    )

    assert record['schema_version'] == 2
    assert record['backend'] is None
    assert restored_request == request
    assert backend is None
    assert stored_hash == request_hash(request)
    assert original_operation_from_record(record) == operation
    with pytest.raises(RunError) as error:
        validate_stored_request(changed_record)
    assert error.value.code == 'RUN_STORAGE_INVALID'


def test_should_submit_daily_manual_request_without_constructing_backend(tmp_path):
    environment = ManualRunEnvironment(tmp_path / 'archive-root')
    request = daily_request(environment.stage.definition_hash, str(uuid.uuid4()))

    operation = environment.run_service.submit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        request,
    )
    operation_root = (
        tmp_path / 'archive-root' / 'projects' / environment.project.id / 'stages' / environment.stage.id
        / 'runtime' / 'operations' / operation.operation_id
    )
    stored = decode_json((operation_root / 'request.json').read_bytes())

    assert environment.backend_calls == 0
    assert operation.capture_id == run_capture_id(operation.operation_id)
    assert stored['schema_version'] == 2
    assert stored['backend'] is None


@pytest.mark.django_db(transaction=True)
def test_should_prepare_refresh_manual_operation_with_original_null_capture_request(tmp_path):
    fixture = history_fixture(tmp_path)
    backend_calls = []

    def backend(*args):
        backend_calls.append(args)
        raise AssertionError('manual refresh must not construct an analysis backend')

    from project_management.app.api.project_runs import ProjectRunService

    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        None,
        None,
        fixture.draft_service,
        backend,
        notifier=lambda *args: None,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    )
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader

    result = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9100),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    intent = decode_json((runtime / 'report-preparations' / result.preparation_id / 'intent.json').read_bytes())
    stored = decode_json((runtime / 'operations' / result.operation_id / 'request.json').read_bytes())

    assert result.disposition == 'created'
    assert result.operation_id == intent['derived_operation_id']
    assert result.draft_id == intent['draft_id']
    assert result.draft_revision is None
    assert backend_calls == []
    assert intent['original_request']['capture_id'] is None
    assert intent['effective_selection']['capture_id'] == run_capture_id(result.operation_id)
    assert intent['request_hash'] == content_hash(intent['original_request'])
    assert stored['schema_version'] == 2
    assert stored['request_hash'] == intent['run_request_hash']
    assert stored['request']['target']['preparation_intent_hash'] == intent['preparation_intent_hash']
    assert stored['request']['target']['draft_id'] == result.draft_id
    assert stored['request']['target']['analysis_mode'] == 'manual_only'
    assert stored['backend'] is None


@pytest.mark.django_db(transaction=True)
def test_should_execute_refresh_manual_worker_without_analysis_and_create_one_authored_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    provider = ProviderAccessDouble(fixture.stage, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
        'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
        'comments': {
            '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
            '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
            '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
        },
    },))
    capture_service = ProjectCaptureService(
        fixture.archive.project_api,
        provider,
        fixture.archive,
        required_parts=('facts', 'comments', 'history'),
    )
    analysis_calls = []

    class NoAnalysis:
        def prepare(self, *args, **kwargs):
            analysis_calls.append(('prepare', args, kwargs))
            raise AssertionError('manual refresh must not prepare analysis')

        def advance(self, *args, **kwargs):
            analysis_calls.append(('advance', args, kwargs))
            raise AssertionError('manual refresh must not advance analysis')

        def cancel(self, *args, **kwargs):
            analysis_calls.append(('cancel', args, kwargs))
            raise AssertionError('manual refresh must not cancel analysis')

    from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker

    backend_calls = []
    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        capture_service,
        NoAnalysis(),
        fixture.draft_service,
        lambda *args: backend_calls.append(args),
        notifier=lambda *args: None,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    )
    prepared = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9110),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )

    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'
    assert completed.draft_id is not None, completed.error_code
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    selection = decode_json((runtime / 'operations' / completed.operation_id / 'draft-selection.json').read_bytes())
    draft_dirs = tuple((runtime / 'report-drafts').iterdir())

    assert completed.state == 'partial'
    assert completed.draft_id == prepared.draft_id
    assert completed.draft_revision == 1
    assert provider.open_count == 1
    assert backend_calls == []
    assert analysis_calls == []
    assert len(draft_dirs) == 1
    assert draft.authoring_context['meeting']['local_date'] == '2026-11-02'
    assert selection['schema_version'] == 2
    assert selection['kind'] == 'daily_preparation'
    assert selection['preparation_id'] == prepared.preparation_id
    assert selection['context_hash'] == sha256_bytes(canonical_bytes(draft.authoring_context))


@pytest.mark.django_db(transaction=True)
def test_should_cancel_daily_manual_after_capture_before_compose_without_analysis_or_draft(tmp_path):
    fixture = history_fixture(tmp_path)
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    provider = ProviderAccessDouble(fixture.stage, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'comments': {'201': {'id': '201', 'body': 'Failure observed.'}},
    },))
    analysis_calls = []

    class NoAnalysis:
        def prepare(self, *args, **kwargs):
            analysis_calls.append('prepare')
            raise AssertionError('cancel before compose must not analyze')

        def advance(self, *args, **kwargs):
            analysis_calls.append('advance')
            raise AssertionError('cancel before compose must not advance')

        def cancel(self, *args, **kwargs):
            analysis_calls.append('cancel')
            raise AssertionError('manual operation has no analysis attempt to cancel')

    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        ProjectCaptureService(
            fixture.archive.project_api,
            provider,
            fixture.archive,
            required_parts=('facts', 'comments', 'history'),
        ),
        NoAnalysis(),
        fixture.draft_service,
        lambda *args: None,
        notifier=lambda *args: None,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    )
    prepared = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9115),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )

    class CancelAfterCaptureWorker(ProjectRunWorker):
        def _capture(self, actor, project_id, stage_id, operation):
            receipt = super()._capture(actor, project_id, stage_id, operation)
            current = self.run_service.get(actor, project_id, stage_id, operation.operation_id)
            self.run_service.cancel(actor, project_id, stage_id, operation.operation_id, expected_revision=current.revision)
            return receipt

    completed = CancelAfterCaptureWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    runtime = fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id / 'runtime'

    assert completed.state == 'canceled'
    assert completed.draft_id is None
    assert analysis_calls == []
    assert not (runtime / 'report-drafts').exists()
    assert not (runtime / 'operations' / completed.operation_id / 'draft-selection.json').exists()


@pytest.mark.django_db(transaction=True)
def test_should_execute_refresh_changed_items_through_existing_analysis_no_work_loop(tmp_path):
    fixture = history_fixture(tmp_path)
    source_reader = ReportSourceReader(fixture.archive, AiTaskContract.load(PACK_ROOT))
    fixture.continuity.source_reader = source_reader
    fixture.draft_service.source_reader = source_reader
    provider = ProviderAccessDouble(fixture.stage, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Intermittent validation failure',
        'status': 'Fixed',
        'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
        'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
        'comments': {
            '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
            '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
            '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
        },
    },))
    capture_service = ProjectCaptureService(
        fixture.archive.project_api,
        provider,
        fixture.archive,
        required_parts=('facts', 'comments', 'history'),
    )
    contract = AiTaskContract.load(PACK_ROOT)
    http = ProjectRunHttp(contract)
    analysis_service = SummaryAnalysisService(fixture.archive, contract, http.client_factory)

    from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker

    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        capture_service,
        analysis_service,
        fixture.draft_service,
        lambda actor, project_id, stage_id: AiBackendTarget(
            'http://127.0.0.1:18888',
            'metrics-dashboard',
            'store-fixture',
            f'projects.{project_id}.stages.{stage_id}',
            'dashboard-join-1',
            'base-b-cancel-synthetic-1',
        ),
        notifier=lambda *args: None,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    )
    worker = ProjectRunWorker(run_service, daily_preparation_service=service)
    day1 = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9120),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='changed_items',
        acknowledge_gap_draft_ids=(),
    )
    completed1 = worker.execute(fixture.actor, fixture.project.id, fixture.stage.id, day1.operation_id)
    day2 = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9121),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-03',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='changed_items',
        acknowledge_gap_draft_ids=(completed1.draft_id,),
    )
    completed2 = worker.execute(fixture.actor, fixture.project.id, fixture.stage.id, day2.operation_id)

    assert completed1.state == 'draft_ready'
    assert completed1.item_results[0].state == 'accepted'
    assert completed2.state == 'draft_ready'
    assert completed2.item_results[0].state == 'no_work'
    assert completed2.item_results[0].accepted_summary_id == completed1.item_results[0].accepted_summary_id
    assert [request for request in http.requests if request == ('POST', '/api/runs')] == [('POST', '/api/runs')]


@pytest.mark.django_db(transaction=True)
def test_should_refuse_reprepare_while_refresh_operation_is_active(tmp_path):
    fixture = history_fixture(tmp_path)
    run_service = ProjectRunService(
        fixture.archive.project_api,
        fixture.archive,
        None,
        None,
        fixture.draft_service,
        lambda *args: None,
        notifier=lambda *args: None,
    )
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
        run_service=run_service,
    )
    prepared = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9130),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )

    with pytest.raises(report_api.ReportError) as error:
        service.reprepare(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            command_id=draft_command(9131),
            preparation_id=prepared.preparation_id,
            expected_operation_revision=1,
            expected_draft_revision=None,
            expected_draft_revision_hash=None,
            expected_baseline_ref=None,
            template_selection=fixture.template_selection,
            source_mode='refresh',
            capture_id=None,
            analysis_mode='manual_only',
        )

    assert error.value.code == 'REPORT_REVISION_CONFLICT'
