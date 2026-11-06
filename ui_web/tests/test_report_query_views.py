from contextlib import contextmanager

import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse

from project_management.app.domain.captures import ArchiveError
from project_management.storage.git import GitRunner
from ui_web.tests.project_fixtures import ProjectRouteTestSupport
from ui_web.tests.test_report_daily_ui_views import (
    auth, choice, daily_fixture, patch_default_facade, preparation_payload, prepare_url, preview_url,
)


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_language_post_changes_cookie_without_opening_report_archive(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('language POST opened Git')

    monkeypatch.setattr(GitRunner, 'run', forbidden)
    target = '/projects/00000000-0000-4000-8000-000000000001/'
    response = Client().post(reverse('ui_web:project_language'),
                             {'language': 'zh-hans', 'next': target}, **auth())
    assert response.status_code == 302
    assert response['Location'] == target
    assert response.cookies[settings.LANGUAGE_COOKIE_NAME].value == 'zh-hans'


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_workbench_read_outage_is_retryable_not_invalid_input(daily_fixture, monkeypatch):
    @contextmanager
    def unavailable(*args, **kwargs):
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        yield

    fixture = daily_fixture
    monkeypatch.setattr(fixture.archive, '_report_read_view', unavailable)
    with patch_default_facade(monkeypatch, fixture):
        response = Client().get(reverse('ui_web:project_stage_reports', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
        }), **auth())
    assert response.status_code == 503
    assert response['Cache-Control'] == 'private, no-store'


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_workbench_shares_archive_identity_with_local_operation_list(daily_fixture, monkeypatch):
    from copy import copy
    from dataclasses import replace
    from project_management.app.api.project_runs import ProjectRunRuntime, ProjectRunService, ProjectRunWorker, RunRequest
    from project_management.app.api.report_queries import ReportOperationsRead
    from project_management.app.api.reports import ReportDraftService
    from project_management.app.api.summary_analysis import AiBackendTarget
    from project_management.services.capture_archive import CaptureArchiveService
    from project_management.tests.report_render_fixtures import daily_template
    from project_management.tests.report_draft_fixtures import draft_command
    from ui_web.facades.project_runs import ProjectRunFacade

    fixture = daily_fixture
    backend = AiBackendTarget('http://127.0.0.1:18888', 'metrics-dashboard', 'store-fixture',
                              f'projects.{fixture.project.id}.stages.{fixture.stage.id}',
                              'dashboard-join-1', 'base-b-cancel-synthetic-1')
    service = ProjectRunService(fixture.archive.project_api, fixture.archive, None, None,
                                fixture.draft_service, lambda *args: backend, notifier=lambda *args: None)
    runtime = ProjectRunRuntime(service, ProjectRunWorker(service))
    operation = service.submit(fixture.actor, fixture.project.id, fixture.stage.id, RunRequest(
        draft_command(17700), fixture.stage.definition_hash, daily_template(), 'Asia/Shanghai',
    ))

    def separate_read(*args, **kwargs):
        raise AssertionError('workbench reopened the same archive for operation history')

    original_list = service.list
    monkeypatch.setattr(service, 'list', separate_read)
    with patch_default_facade(monkeypatch, fixture, runtime):
        response = Client().get(reverse('ui_web:project_stage_reports', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
        }), **auth())
    assert response.status_code == 200
    assert response.context['run']['operations'] == (operation,)
    assert operation.operation_id.encode() in response.content
    monkeypatch.setattr(service, 'list', original_list)
    facade = ProjectRunFacade(fixture.archive.project_api, service, runtime_ready=True)
    observed = ReportOperationsRead(fixture.project.id, fixture.stage.id, fixture.actor.subject,
                                    fixture.stage.definition_hash, ())
    for mismatch in (
        {'actor_subject': 'basic:bob'}, {'stage_hash': 'f' * 64},
        {'stage_id': draft_command(17701)}, {'project_id': draft_command(17702)},
    ):
        context = facade.stage_context(fixture.actor, fixture.project.id, fixture.stage.id,
                                       operations_read=replace(observed, **mismatch))
        assert context['operations'] == (operation,)

    other = copy(fixture)
    other_root = fixture.archive_root.parent / 'other-report-archive'
    other_root.mkdir()
    other.archive = CaptureArchiveService(
        fixture.archive.project_api, fixture.archive.repository_factory,
        replace(fixture.archive.config, root=other_root),
    )
    other.archive.initialize_stage(fixture.actor, fixture.project.id, fixture.stage.id)
    other.draft_service = ReportDraftService(other.archive, fixture.source_reader, fixture.draft_service.renderer)
    with patch_default_facade(monkeypatch, other, runtime):
        separate = Client().get(reverse('ui_web:project_stage_reports', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
        }), **auth())
    assert separate.status_code == 200
    assert separate.context['captures'] == ()
    assert separate.context['run']['operations'] == (operation,)


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_daily_actions_do_not_build_history_and_errors_keep_bound_input(daily_fixture, monkeypatch):
    from project_management.tests.report_draft_fixtures import draft_command
    from ui_web.facades.project_reports import ProjectReportFacade

    fixture = daily_fixture
    payload = preparation_payload(fixture, command=17900)

    def history(*args, **kwargs):
        raise AssertionError('daily action rebuilt the workbench')

    monkeypatch.setattr(ProjectReportFacade, 'stage_context', history)
    with patch_default_facade(monkeypatch, fixture):
        client = Client()
        selection = {
            'series_id': fixture.series.series_id, 'meeting_date': '2026-11-02',
            'template_choice': choice(fixture.template_selection),
        }
        preview = client.get(preview_url(fixture), selection, HTTP_ACCEPT='application/json', **auth())
        assert preview.status_code == 200
        assert preview.json()['result']['preview']['state'] == 'initial'
        visible = client.get(preview_url(fixture), selection, **auth())
        assert visible.status_code == 200
        assert b'data-report-daily-baseline' in visible.content
        assert b'No saved drafts yet.' not in visible.content
        prepared = client.post(prepare_url(fixture), payload, HTTP_ACCEPT='application/json', **auth())
        assert prepared.status_code == 200
        result = prepared.json()['result']
        details_url = reverse('ui_web:report_preparation_detail', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
            'preparation_id': result['preparation_id'],
        })
        details = client.get(details_url, HTTP_ACCEPT='application/json', **auth())
        assert details.status_code == 200
        assert details.json()['result']['result']['draft_id'] == result['draft_id']
        detail_page = client.get(details_url, **auth())
        assert detail_page.status_code == 200
        assert b'data-report-reprepare-form' in detail_page.content
        repeated = client.post(prepare_url(fixture), payload, **auth())
        assert repeated.status_code == 302
        next_day = {**payload, 'command_id': draft_command(17901), 'meeting_date': '2026-11-03'}
        pending = client.post(prepare_url(fixture), next_day, **auth())
        assert pending.status_code == 409
        assert pending.context['daily_prepare_form']['command_id'].value() == next_day['command_id']
        assert pending.context['daily_prepare_form']['meeting_date'].value() == '2026-11-03'
        assert b'No saved drafts yet.' not in pending.content
        current = details.json()['result']
        reprepare = client.post(reverse('ui_web:report_preparation_reprepare', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
            'preparation_id': result['preparation_id'],
        }), {
            'command_id': draft_command(17902), 'preparation_id': result['preparation_id'],
            'expected_draft_revision': result['draft_revision'],
            'expected_draft_revision_hash': current['draft_revision_hash'],
            'template_choice': choice(fixture.template_selection),
            'source_mode': 'saved_capture', 'capture_id': fixture.retained_capture_id,
            'analysis_mode': 'manual_only',
        }, HTTP_ACCEPT='application/json', **auth())
        assert reprepare.status_code == 200, reprepare.content.decode()
        assert reprepare.json()['result']['draft_id']


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_baseline_and_capture_controls_share_one_verified_archive(daily_fixture, monkeypatch):
    from project_management.storage.repository import CaptureArchiveRepository

    fixture = daily_fixture
    original = CaptureArchiveRepository.verify_identity
    opened = []

    def verified(repository):
        opened.append(repository.stage.id)
        return original(repository)

    monkeypatch.setattr(CaptureArchiveRepository, 'verify_identity', verified)
    with patch_default_facade(monkeypatch, fixture):
        response = Client().get(preview_url(fixture), {
            'series_id': fixture.series.series_id, 'meeting_date': '2026-11-02',
            'template_choice': choice(fixture.template_selection),
        }, **auth())
    assert response.status_code == 200
    assert b'data-report-daily-baseline' in response.content
    assert fixture.retained_capture_id.encode() in response.content
    assert opened == [fixture.stage.id]


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_finalized_preparation_does_not_load_hidden_capture_controls(daily_fixture, monkeypatch):
    from project_management.tests.report_draft_fixtures import draft_command
    from ui_web.facades.project_reports import default_report_facade

    fixture = daily_fixture
    with patch_default_facade(monkeypatch, fixture):
        client = Client()
        response = client.post(prepare_url(fixture), preparation_payload(fixture, command=18400),
                               HTTP_ACCEPT='application/json', **auth())
        result = response.json()['result']
        draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, result['draft_id'])
        publication = fixture.draft_service.finalize_and_commit(
            fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
            command_id=draft_command(18401), expected_revision=draft.revision,
        )

        def hidden_controls(*args, **kwargs):
            raise AssertionError('Finalized detail loaded unrendered source controls')

        monkeypatch.setattr(fixture.archive, 'list_capture_metadata', hidden_controls)
        detail = client.get(reverse('ui_web:report_preparation_detail', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
            'preparation_id': result['preparation_id'],
        }), **auth())
    assert detail.status_code == 200
    assert publication.manifest.publication_id.encode() in detail.content
    assert b'data-report-reprepare-form' not in detail.content
