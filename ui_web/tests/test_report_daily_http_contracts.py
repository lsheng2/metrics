import json

import pytest
from django.conf import settings
from django.test import Client, override_settings
from django.urls import reverse

from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_preparation_read import runtime_files
from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header
from ui_web.tests.test_report_daily_ui_views import (
    auth, choice, daily_fixture, patch_default_facade, preparation_payload, prepare_url, preview_url,
)


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldEnforceAuthCsrfStrictJsonAndPrivatePreparationResponse(daily_fixture, monkeypatch):
    fixture = daily_fixture
    payload = preparation_payload(fixture)
    client = Client(enforce_csrf_checks=True)
    with patch_default_facade(monkeypatch, fixture):
        stage_url = reverse('ui_web:project_stage_reports', kwargs={
            'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
        })
        client.get(stage_url, **auth())
        csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
        headers = {**auth(), 'HTTP_X_CSRFTOKEN': csrf, 'HTTP_ACCEPT': 'application/json'}
        before = runtime_files(fixture)
        unauthenticated = client.post(prepare_url(fixture), json.dumps(payload), content_type='application/json',
                                      HTTP_X_CSRFTOKEN=csrf, HTTP_ACCEPT='application/json')
        assert unauthenticated.status_code == 401
        forbidden = client.post(prepare_url(fixture), json.dumps(payload), content_type='application/json', **auth())
        assert forbidden.status_code == 403
        foreign = client.post(prepare_url(fixture), json.dumps(payload), content_type='application/json',
                              **{**headers, 'HTTP_AUTHORIZATION': basic_header('bob', 'builder')})
        assert foreign.status_code == 404
        assert b'Retained daily source' not in foreign.content
        invalid_bodies = (
            json.dumps({**payload, 'credentials': 'DO_NOT_ECHO_LOCAL_PROVIDER_CREDENTIAL'}),
            json.dumps(payload)[:-1] + ',"command_id":"' + draft_command(9480) + '"}',
            json.dumps({**payload, 'template_choice': {'unexpected': 'object'}}),
            '[]',
        )
        for body in invalid_bodies:
            response = client.post(prepare_url(fixture), body, content_type='application/json', **headers)
            assert response.status_code == 400
            assert response.json()['schema_version'] == 1
            assert response.json()['error']['code'] == 'REPORT_INVALID'
            assert 'DO_NOT_ECHO' not in response.content.decode('utf-8')
        oversized = client.post(prepare_url(fixture), 'x' * 65537, content_type='application/json', **headers)
        assert oversized.status_code == 413
        assert runtime_files(fixture) == before
        accepted = client.post(prepare_url(fixture), json.dumps(payload), content_type='application/json', **headers)

    assert accepted.status_code == 200
    assert accepted['Cache-Control'] == 'private, no-store'
    assert accepted.json()['error'] is None
    assert accepted.json()['result']['draft_id']


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldRetainDisplayedOldBaselineWhenAnotherWindowFinalizes(daily_fixture, monkeypatch):
    fixture = daily_fixture
    old_tuesday = preparation_payload(fixture, command=9490, day='2026-11-03')
    with patch_default_facade(monkeypatch, fixture):
        client = Client()
        created = client.post(prepare_url(fixture), preparation_payload(fixture), **auth())
        draft_id = created['Location'].rstrip('/').rsplit('/', 1)[-1]
        draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, draft_id)
        published = fixture.draft_service.finalize_and_commit(
            fixture.actor, fixture.project.id, fixture.stage.id, draft_id,
            command_id=draft_command(9491), expected_revision=draft.revision,
        )
        before = runtime_files(fixture)

        stale = client.post(prepare_url(fixture), old_tuesday, **auth())
        assert stale.status_code == 409
        assert stale.context['daily_prepare_form']['meeting_date'].value() == '2026-11-03'
        assert stale.context['daily_prepare_form']['baseline_publication_id'].value() == ''
        assert stale.context['daily_preview'].baseline_ref.publication_id == published.manifest.publication_id
        assert runtime_files(fixture) == before


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldTranslatePreparationControlsWithoutChangingCanonicalData(daily_fixture, monkeypatch):
    fixture = daily_fixture
    client = Client()
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'zh-hans'
    with patch_default_facade(monkeypatch, fixture):
        response = client.get(preview_url(fixture), {
            'series_id': fixture.series.series_id, 'meeting_date': '2026-11-02',
            'template_choice': choice(fixture.template_selection),
        }, **auth())

    text = response.content.decode('utf-8')
    assert response.status_code == 200
    assert '\u751f\u6210\u5f53\u65e5\u8349\u7a3f' in text
    assert '\u9884\u89c8\u57fa\u7ebf' in text
    assert response.context['daily_prepare_form']['meeting_date'].value() == '2026-11-02'
    assert response.context['daily_prepare_form']['analysis_mode'].value() == 'manual_only'
