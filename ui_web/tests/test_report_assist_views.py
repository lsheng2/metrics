import json
from uuid import uuid4

from django.test import Client, override_settings
from django.urls import reverse

from project_management.tests.test_report_assist_service import make_assist_environment
from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header
from ui_web.views.report_assists import ReportAssistView


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_shouldExposeOwnerCheckedTargetsAndRejectStalePost(tmp_path, monkeypatch):
    env = make_assist_environment(tmp_path, actor_subject='basic:alice')
    monkeypatch.setattr(ReportAssistView, 'service_factory', staticmethod(lambda: env.service))
    url = reverse('ui_web:report_assists', kwargs={
        'project_id': env.archive.project.id, 'stage_id': env.archive.stage.id, 'draft_id': env.draft.draft_id,
    })
    client = Client()
    auth = {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}
    result = client.get(url, **auth)
    assert result.status_code == 200
    assert result.json()['result']['available'] is True
    assert result.headers['Cache-Control'] == 'private, no-store'
    assert client.get(url, HTTP_AUTHORIZATION=basic_header('bob', 'builder')).status_code == 404
    assert client.get(url).status_code == 401
    body = {
        'command_id': str(uuid4()), 'expected_revision': 2, 'expected_revision_hash': env.draft.revision_hash,
        'target_ids': [env.target.target_id], 'instruction': 'Summarize.',
    }
    stale = client.post(url, json.dumps(body), content_type='application/json', **auth)
    assert stale.status_code == 409
    assert env.requests == []
    forged = {**body, 'expected_revision': True}
    assert client.post(url, json.dumps(forged), content_type='application/json', **auth).status_code == 422
    assert Client(enforce_csrf_checks=True).post(url, json.dumps(body), content_type='application/json', **auth).status_code == 403
