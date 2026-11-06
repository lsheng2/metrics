import pytest
from django.test import Client, override_settings
from django.urls import reverse

from project_management.app.api import reports as report_api
from project_management.tests.test_report_meetings import calendar_read, change_request
from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header
from ui_web.tests.test_report_daily_ui_views import auth, daily_fixture, patch_default_facade


def url(fixture):
    return reverse('ui_web:report_meetings', kwargs={
        'project_id': fixture.project.id, 'stage_id': fixture.stage.id,
    })


def query(fixture):
    return {'series_id': fixture.series.series_id, 'from_date': '2026-11-09', 'through_date': '2026-11-22'}


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_calendar_get_skip_restore_and_stale_form_keep_user_input(daily_fixture, monkeypatch):
    fixture = daily_fixture
    service = report_api.ReportMeetingService(fixture.continuity)
    request = change_request(fixture, calendar_read(fixture, service), reason='<b>Holiday</b>')
    with patch_default_facade(monkeypatch, fixture):
        client = Client()
        page = client.get(url(fixture), query(fixture), **auth())
        assert page.status_code == 200
        assert 'Unrecorded' in page.content.decode()
        assert 'data-meeting-change-form' in page.content.decode()
        created = client.post(url(fixture), request, **auth())
        assert created.status_code == 302, created.content.decode()
        after = client.get(created['Location'], **auth())
        assert 'Skipped' in after.content.decode()
        assert '&lt;b&gt;Holiday&lt;/b&gt;' in after.content.decode()
        assert '<b>Holiday</b>' not in after.content.decode()

        stale = client.post(url(fixture), {**request, 'command_id': 'bbbbbbbb-bbbb-4bbb-8bbb-000000015030',
                                         'reason': 'Retain this reason'}, **auth())
        assert stale.status_code == 409, stale.content.decode()
        assert 'Retain this reason' in stale.content.decode()
        assert 'data-meeting-error' in stale.content.decode()
        invalid_dates = client.post(url(fixture), {
            **request, 'from_date': '2026-11-22', 'through_date': '2026-11-09',
            'reason': 'Keep invalid-range note',
        }, **auth())
        assert invalid_dates.status_code == 422
        assert 'Keep invalid-range note' in invalid_dates.content.decode()
        assert '2026-11-22' in invalid_dates.content.decode()
        view = calendar_read(fixture, service)
        restored = client.post(url(fixture), change_request(fixture, view, command=15031, action='restore'),
                               HTTP_ACCEPT='application/json', **auth())
        assert restored.status_code == 200
        assert restored.json()['result']['revision'] == 2
        assert {day.state for day in calendar_read(fixture, service).days} == {'unrecorded'}


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_calendar_denies_foreign_auth_csrf_unknown_fields_and_duplicate_json(daily_fixture, monkeypatch):
    fixture = daily_fixture
    service = report_api.ReportMeetingService(fixture.continuity)
    request = change_request(fixture, calendar_read(fixture, service))
    with patch_default_facade(monkeypatch, fixture):
        client = Client()
        assert client.get(url(fixture)).status_code == 401
        foreign = client.get(url(fixture), query(fixture), HTTP_AUTHORIZATION=basic_header('bob', 'builder'))
        assert foreign.status_code == 404
        assert Client(enforce_csrf_checks=True).post(url(fixture), request, **auth()).status_code == 403
        invalid = client.post(url(fixture), {**request, 'endpoint': 'https://untrusted.example'},
                              HTTP_ACCEPT='application/json', **auth())
        assert invalid.status_code == 422
        duplicate = client.post(url(fixture), '{"action":"skip","action":"restore"}',
                                content_type='application/json', HTTP_ACCEPT='application/json', **auth())
        assert duplicate.status_code == 422
        bad_range = client.post(url(fixture), {**request, 'through_date': '2027-12-31'},
                                HTTP_ACCEPT='application/json', **auth())
        assert bad_range.status_code in {413, 422}
    assert calendar_read(fixture, service).revision == 0


@pytest.mark.django_db(transaction=True)
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_json_calendar_and_skipped_prepare_error_are_explicit(daily_fixture, monkeypatch):
    fixture = daily_fixture
    service = report_api.ReportMeetingService(fixture.continuity)
    view = calendar_read(fixture, service, '2026-11-03', '2026-11-03')
    request = change_request(fixture, view)
    with patch_default_facade(monkeypatch, fixture):
        client = Client()
        response = client.post(url(fixture), request, content_type='application/json', HTTP_ACCEPT='application/json', **auth())
        assert response.status_code == 200, response.content.decode()
        read = client.get(url(fixture), {
            'series_id': fixture.series.series_id, 'from_date': '2026-11-03', 'through_date': '2026-11-03',
        }, HTTP_ACCEPT='application/json', **auth())
        assert read.status_code == 200
        assert read.json()['result']['days'][0]['state'] == 'skipped'
        assert 'no-store' in read['Cache-Control']
        from ui_web.tests.test_report_daily_ui_views import choice, preparation_payload, prepare_url, preview_url

        preview = client.get(preview_url(fixture), {
            'series_id': fixture.series.series_id, 'meeting_date': '2026-11-03',
            'template_choice': choice(fixture.template_selection),
        }, HTTP_ACCEPT='application/json', **auth())
        assert preview.status_code == 200
        assert preview.json()['result']['preview']['meeting_skipped'] is True

        payload = preparation_payload(fixture, day='2026-11-03', command=15032)
        refused = client.post(prepare_url(fixture), payload, HTTP_ACCEPT='application/json', **auth())
        assert refused.status_code == 409
        assert refused.json()['error']['code'] == 'REPORT_MEETING_SKIPPED'
