import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import reverse

from project_management.app.api.project_runs import (
    ProjectRunRuntime,
    ProjectRunService,
    ProjectRunWorker,
    build_project_runtime,
    clear_project_runtime,
    install_project_runtime,
)
from project_management.app.api.capture_archive import (
    CaptureCoverage,
    CaptureIntent,
    CaptureSourceIdentity,
    MembershipInput,
    PartCoverage,
    RawPageInput,
    SnapshotInput,
    WorkItemIdentity,
)
from project_management.tests.history_persistence_fixtures import history_fixture
from project_management.app.api.reports import UserTemplateSelection
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_daily_reprepare_backend import refresh_manual_service
from project_management.tests.test_report_preparation_read import runtime_files
from ui_web.facades import project_reports as facade_module
from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header


def choice(selection):
    return f'user|{selection.template_id}|{selection.revision}|{selection.revision_hash}'


def preview_url(fixture):
    return reverse('ui_web:report_baseline_preview', kwargs={
        'project_id': fixture.project.id,
        'stage_id': fixture.stage.id,
    })


def prepare_url(fixture):
    return reverse('ui_web:report_preparation_create', kwargs={
        'project_id': fixture.project.id,
        'stage_id': fixture.stage.id,
    })


def preparation_payload(fixture, *, command=9400, day='2026-11-02', capture_id=None):
    preview = fixture.continuity.preview(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        series_id=fixture.series.series_id,
        meeting_date=day,
        template_selection=fixture.template_selection,
    )
    return {
        'command_id': draft_command(command),
        'series_id': fixture.series.series_id,
        'meeting_date': day,
        'template_choice': choice(fixture.template_selection),
        'expected_series_policy_hash': preview.series_policy_hash,
        'baseline_publication_id': '' if preview.baseline_ref is None else preview.baseline_ref.publication_id,
        'baseline_manifest_hash': '' if preview.baseline_ref is None else preview.baseline_ref.manifest_hash,
        'baseline_commit': '' if preview.baseline_ref is None else preview.baseline_ref.commit,
        'source_mode': 'saved_capture',
        'capture_id': fixture.retained_capture_id if capture_id is None else capture_id,
        'analysis_mode': 'manual_only',
    }


def auth():
    return {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}


@pytest.fixture
def daily_fixture(tmp_path):
    fixture = history_fixture(tmp_path, actor_subject='basic:alice')
    fixture.retained_capture_id = seed_retained_capture(fixture)
    return fixture


def seed_retained_capture(fixture):
    capture_id = str(uuid4())
    item = WorkItemIdentity('jira', 'alpha-endpoint', 'ALPHA-1', 'ALPHA-1')
    intent = CaptureIntent(
        project_id=fixture.project.id,
        stage_id=fixture.stage.id,
        capture_id=capture_id,
        request_id=str(uuid4()),
        source=CaptureSourceIdentity(
            'jira',
            'alpha-endpoint',
            fixture.stage.descriptor.endpoint,
            'principal:archive-owner',
            'credential-revision-1',
            fixture.stage.definition_hash,
        ),
        original_input_hash='a' * 64,
        required_parts=('facts', 'comments'),
        deadline_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    fixture.archive.prepare(fixture.actor, intent)
    page = fixture.archive.append_page(
        fixture.actor,
        intent,
        RawPageInput(
            'facts-page-1',
            item,
            'application/json; charset=utf-8',
            b'{"summary":"retained daily source"}',
            'request-page-1',
        ),
    )
    complete = PartCoverage('complete', 'source-version-1', 1, 1, None)
    fixture.archive.append_snapshot(
        fixture.actor,
        intent,
        SnapshotInput(
            item,
            {'summary': 'Retained daily source', 'status': 'Fixed'},
            {'c1': {'id': 'c1', 'body': 'ready for manual report'}},
            {},
            {},
            {},
            CaptureCoverage(
                complete,
                complete,
                PartCoverage('not_requested', None, None, None, None),
                PartCoverage('not_requested', None, None, None, None),
                PartCoverage('not_requested', None, None, None, None),
            ),
            (page.page_id,),
            True,
        ),
    )
    fixture.archive.finalize(fixture.actor, intent, MembershipInput((item,), complete, (page.page_id,)), complete=True)
    fixture.source_reader.source_commit = fixture.archive._read_repository(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
    ).head()
    return capture_id


@contextmanager
def patch_default_facade(monkeypatch, fixture, runtime=None):
    monkeypatch.setattr(facade_module, 'build_project_api', lambda: fixture.archive.project_api)
    monkeypatch.setattr(facade_module, 'build_capture_archive_service', lambda project_api=None: fixture.archive)
    monkeypatch.setattr(facade_module, 'build_report_template_service', lambda: fixture.template_service)
    monkeypatch.setattr(facade_module, 'build_report_service', lambda **kwargs: fixture.draft_service)
    monkeypatch.setattr(facade_module, 'build_report_continuity_service', lambda **kwargs: fixture.continuity)
    if runtime is not None:
        install_project_runtime(runtime)
        try:
            yield
        finally:
            clear_project_runtime(runtime)
    else:
        yield


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_should_preview_daily_baseline_without_creating_preparation(daily_fixture, monkeypatch):
    with patch_default_facade(monkeypatch, daily_fixture):
        response = Client().get(preview_url(daily_fixture), {
            'series_id': daily_fixture.series.series_id,
            'meeting_date': '2026-11-02',
            'template_choice': choice(daily_fixture.template_selection),
        }, **auth())

    runtime = (
        daily_fixture.archive_root / 'projects' / daily_fixture.project.id
        / 'stages' / daily_fixture.stage.id / 'runtime'
    )
    body = response.content.decode('utf-8')

    assert response.status_code == 200, body
    assert 'data-report-daily-baseline' in body
    assert 'initial' in body
    assert not (runtime / 'report-preparations').exists()


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_should_make_previewed_selection_submittable_without_reentering_hidden_fields(daily_fixture, monkeypatch):
    with patch_default_facade(monkeypatch, daily_fixture):
        response = Client().get(preview_url(daily_fixture), {
            'series_id': daily_fixture.series.series_id,
            'meeting_date': '2026-11-02',
            'template_choice': choice(daily_fixture.template_selection),
        }, **auth())

    form = response.context['daily_prepare_form']
    assert form['expected_series_policy_hash'].value() == daily_fixture.series.revision_hash
    assert form['command_id'].value()
    assert form['meeting_date'].value() == '2026-11-02'
    assert form['source_mode'].value() == 'saved_capture'
    assert form['analysis_mode'].value() == 'manual_only'


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_should_prepare_saved_capture_manual_without_runtime_and_reject_refresh(daily_fixture, monkeypatch):
    client = Client()
    with patch_default_facade(monkeypatch, daily_fixture):
        saved = client.post(prepare_url(daily_fixture), preparation_payload(daily_fixture), **auth())
        refresh = client.post(prepare_url(daily_fixture), {
            **preparation_payload(daily_fixture, command=9401, capture_id=''),
            'source_mode': 'refresh',
        }, **auth())
        before_unavailable = runtime_files(daily_fixture)
        unavailable = client.post(prepare_url(daily_fixture), {
            **preparation_payload(daily_fixture, command=9402, day='2026-11-03', capture_id=''),
            'source_mode': 'refresh',
        }, **auth())

    assert saved.status_code == 302, saved.content.decode('utf-8')
    draft_id = saved['Location'].rstrip('/').rsplit('/', 1)[-1]
    draft = daily_fixture.draft_service.get(
        daily_fixture.actor,
        daily_fixture.project.id,
        daily_fixture.stage.id,
        draft_id,
    )

    assert saved.status_code == 302
    assert draft.authoring_context['meeting']['local_date'] == '2026-11-02'
    assert refresh.status_code == 409
    assert refresh.context['daily_result']['draft_id'] == draft_id
    assert refresh.context['daily_result']['selection_conflicts'] == ('source',)
    assert unavailable.status_code == 503
    assert runtime_files(daily_fixture) == before_unavailable


@pytest.mark.django_db(transaction=True)
def test_should_wire_registered_runtime_into_daily_preparation_service(tmp_path, monkeypatch):
    daily_fixture = history_fixture(tmp_path, actor_subject='basic:alice')
    run_service = ProjectRunService(
        daily_fixture.archive.project_api,
        daily_fixture.archive,
        None,
        None,
        daily_fixture.draft_service,
        lambda *args: None,
        notifier=lambda *args: None,
    )
    runtime = ProjectRunRuntime(run_service, ProjectRunWorker(run_service))

    with override_settings(METRICS_PROJECT_RUNTIME_FACTORY=lambda: runtime):
        built = build_project_runtime()
    preparation = built.worker.daily_preparation_service
    assert preparation is not None
    with patch_default_facade(monkeypatch, daily_fixture, runtime):
        facade = facade_module.default_report_facade()
        reopened = facade_module.default_report_facade()

    assert facade.preparation_service.run_service is run_service
    assert preparation is facade.preparation_service is reopened.preparation_service


@pytest.mark.django_db(transaction=True)
def test_project_run_prepare_cli_uses_daily_preparation_service(tmp_path):
    daily_fixture = history_fixture(tmp_path, actor_subject='local_operator')
    retained_capture_id = seed_retained_capture(daily_fixture)
    run_service = ProjectRunService(
        daily_fixture.archive.project_api,
        daily_fixture.archive,
        None,
        None,
        daily_fixture.draft_service,
        lambda *args: None,
        notifier=lambda *args: None,
    )
    with patch('project_management.app.api.report_factories.build_project_api',
               return_value=daily_fixture.archive.project_api), \
            patch('project_management.app.api.report_factories.build_capture_archive_service',
                  return_value=daily_fixture.archive), \
            patch('project_management.app.api.report_factories.build_report_template_service',
                  return_value=daily_fixture.template_service), \
            patch('project_management.app.api.report_factories.build_report_service',
                  return_value=daily_fixture.draft_service), \
            patch('project_management.app.api.report_factories.build_report_continuity_service',
                  return_value=daily_fixture.continuity), \
            patch('project_management.management.commands.project_run.build_run_read_service',
                  return_value=run_service):
        preview_out = StringIO()
        call_command(
            'project_run', 'preview', daily_fixture.project.id, daily_fixture.stage.id,
            '--series-id', daily_fixture.series.series_id,
            '--meeting-date', '2026-11-02',
            '--template-id', daily_fixture.template_selection.template_id,
            '--template-revision', str(daily_fixture.template_selection.revision),
            '--template-revision-hash', daily_fixture.template_selection.revision_hash,
            stdout=preview_out,
        )
        preview = json.loads(preview_out.getvalue())['result']
        assert preview['baseline_ref'] is None
        assert preview['series_policy_hash'] == daily_fixture.series.revision_hash
        out = StringIO()
        call_command(
            'project_run', 'prepare', daily_fixture.project.id, daily_fixture.stage.id,
            '--command-id', draft_command(9410),
            '--series-id', daily_fixture.series.series_id,
            '--meeting-date', '2026-11-02',
            '--expected-series-policy-hash', preview['series_policy_hash'],
            '--template-id', daily_fixture.template_selection.template_id,
            '--template-revision', str(daily_fixture.template_selection.revision),
            '--template-revision-hash', daily_fixture.template_selection.revision_hash,
            '--source-mode', 'saved_capture',
            '--capture-id', retained_capture_id,
            '--analysis-mode', 'manual_only',
            stdout=out,
        )

    payload = json.loads(out.getvalue())

    assert payload['error'] is None
    assert payload['result']['operation_id'] is None
    assert payload['result']['draft_id'] is not None


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldKeepPendingDraftAndPostedSelectionUntilExactGapAcknowledgment(daily_fixture, monkeypatch):
    fixture = daily_fixture
    client = Client()
    with patch_default_facade(monkeypatch, fixture):
        monday = client.post(prepare_url(fixture), preparation_payload(fixture), **auth())
        draft_id = monday['Location'].rstrip('/').rsplit('/', 1)[-1]
        tuesday = preparation_payload(fixture, command=9430, day='2026-11-03')
        refused = client.post(prepare_url(fixture), tuesday, **auth())

        assert refused.status_code == 409
        assert 'data-report-daily-prepare-form' in refused.content.decode('utf-8')
        assert refused.context['daily_prepare_form']['meeting_date'].value() == '2026-11-03'
        preview = client.get(preview_url(fixture), {
            'series_id': fixture.series.series_id,
            'meeting_date': '2026-11-03',
            'template_choice': choice(fixture.template_selection),
        }, **auth())
        gap_choices = preview.context['daily_prepare_form'].fields['acknowledge_gap_draft_ids'].choices
        assert draft_id in {value for value, _ in gap_choices}
        accepted = client.post(prepare_url(fixture), {
            **tuesday, 'acknowledge_gap_draft_ids': [draft_id],
        }, **auth())

    assert accepted.status_code == 302, accepted.content.decode('utf-8')
    assert fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, draft_id).state == 'draft'


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldExposeReadOnlyPreparationDetailsAndRejectMismatchedRepreparePath(daily_fixture, monkeypatch):
    fixture = daily_fixture
    with patch_default_facade(monkeypatch, fixture):
        facade = facade_module.default_report_facade()
        client = Client()
        client.post(prepare_url(fixture), preparation_payload(fixture), **auth())
        details = facade.preparation_service.for_meeting(
            fixture.actor, fixture.project.id, fixture.stage.id,
            series_id=fixture.series.series_id, meeting_date='2026-11-02',
        )
        route = reverse('ui_web:report_preparation_detail', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
            'preparation_id': details.result.preparation_id,
        })
        response = client.get(route, **auth())
        assert response.status_code == 200
        assert 'data-report-reprepare-form' in response.content.decode('utf-8')
        reprepare_url = reverse('ui_web:report_preparation_reprepare', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
            'preparation_id': details.result.preparation_id,
        })
        refused = client.post(reprepare_url, {
            'command_id': draft_command(9432),
            'preparation_id': draft_command(9433),
            'expected_draft_revision': details.result.draft_revision,
            'expected_draft_revision_hash': details.draft_revision_hash,
            'template_choice': choice(fixture.template_selection),
            'source_mode': 'saved_capture',
            'capture_id': fixture.retained_capture_id,
            'analysis_mode': 'manual_only',
        }, **auth())

    assert refused.status_code == 400


@pytest.mark.django_db(transaction=True)
def test_shouldExecuteManualRefreshFromCliThroughConfiguredDailyWorker(tmp_path):
    fixture = history_fixture(tmp_path, actor_subject='local_operator')
    _, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1', 'summary': 'Manual refresh source', 'status': 'Fixed',
    },))
    runtime = ProjectRunRuntime(run_service, ProjectRunWorker(run_service))
    output = StringIO()
    with override_settings(METRICS_PROJECT_RUNTIME_FACTORY=lambda: runtime):
        call_command(
            'project_run', 'prepare', fixture.project.id, fixture.stage.id,
            '--command-id', draft_command(9440),
            '--series-id', fixture.series.series_id,
            '--meeting-date', '2026-11-02',
            '--expected-series-policy-hash', fixture.series.revision_hash,
            '--template-id', fixture.template_selection.template_id,
            '--template-revision', str(fixture.template_selection.revision),
            '--template-revision-hash', fixture.template_selection.revision_hash,
            '--source-mode', 'refresh', '--analysis-mode', 'manual_only', '--execute-local',
            stdout=output,
        )

    result = json.loads(output.getvalue())['result']
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, result['draft_id'])
    assert draft.authoring_context['meeting']['local_date'] == '2026-11-02'
    assert draft.authoring_context['current_observations'][0]['source_status']['value'] == 'Fixed'


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldReturnExistingMeetingBeforeValidatingDifferentTemplateSelection(daily_fixture, monkeypatch):
    fixture = daily_fixture
    original = fixture.template_service.get(
        fixture.actor, fixture.project.id, fixture.template_selection.template_id,
        revision=fixture.template_selection.revision,
    )
    another = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(9470),
        name='Another daily template', document=original.document, fill_policy=original.fill_policy,
    )
    another_selection = UserTemplateSelection(str(another.template_id), another.revision, another.revision_hash)
    with patch_default_facade(monkeypatch, fixture):
        client = Client()
        first = client.post(prepare_url(fixture), preparation_payload(fixture), **auth())
        repeated = client.post(prepare_url(fixture), {
            **preparation_payload(fixture, command=9471),
            'template_choice': choice(another_selection),
        }, **auth())

    assert repeated.status_code == 409
    assert repeated.context['daily_result']['draft_id'] in first['Location']
    assert repeated.context['daily_result']['selection_conflicts'] == ('template',)


@pytest.mark.django_db(transaction=True)
def test_shouldIncludeVerifiedCaptureCutoffInPreparationChoices(daily_fixture, monkeypatch):
    fixture = daily_fixture
    manifest = fixture.archive.read_capture(
        fixture.actor, fixture.project.id, fixture.stage.id, fixture.retained_capture_id,
    )
    with patch_default_facade(monkeypatch, fixture):
        context = facade_module.default_report_facade().stage_context(
            fixture.actor, fixture.project.id, fixture.stage.id,
        )

    selected = next(item for item in context['captures'] if item.capture_id == fixture.retained_capture_id)
    assert selected.source_as_of == manifest.finalized_at
    assert datetime.fromisoformat(manifest.finalized_at).strftime('%Y-%m-%d') in selected.label
