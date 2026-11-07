import json
from unittest.mock import patch

from django.test import Client, override_settings
from django.urls import reverse
import pytest

from project_management.tests.test_report_recovery import setup_recovery
from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header


@pytest.mark.django_db
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users, METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_recovery_routes_require_owner_csrf_and_exact_json(tmp_path):
    from ui_web.views.report_recovery import ReportRecoveryView
    _, _, draft, recovery, args, payload = setup_recovery(tmp_path)
    url = reverse('ui_web:report_recovery', kwargs={'project_id': args[1], 'stage_id': args[2], 'draft_id': draft.draft_id})
    auth = {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}
    client = Client(enforce_csrf_checks=True)
    with patch.object(ReportRecoveryView, 'service_factory', staticmethod(lambda: recovery)):
        assert client.get(url).status_code == 401
        assert client.post(url, data=json.dumps(payload), content_type='application/json', **auth).status_code == 403
        # This actor is authenticated but not the draft owner.
        response = Client().get(url, **auth)
        assert response.status_code in {404, 400}
        with patch.object(ReportRecoveryView, 'actor', lambda self, request: args[0]):
            response = Client().post(url, data=json.dumps(payload), content_type='application/json', **auth)
            assert response.status_code == 200, response.content
            assert response.json()['result']['restorable']
            assert 'no-store' in response['Cache-Control']
            malformed = Client().post(url, data=json.dumps({**payload, 'unexpected': True}),
                                      content_type='application/json', **auth)
            assert malformed.status_code == 400
            checkpoint = reverse('ui_web:report_recovery_item', kwargs={
                'project_id': args[1], 'stage_id': args[2], 'draft_id': draft.draft_id, 'client_id': payload['client_id'],
            })
            assert Client().get(checkpoint, **auth).json()['result']['content']['edits']


@pytest.mark.django_db
@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users, METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
def test_unconfigured_recovery_factory_returns_safe_unavailable_json(tmp_path):
    from project_management.app.api.capture_archive import ArchiveError
    from ui_web.views.report_recovery import ReportRecoveryView
    _, _, draft, _, args, payload = setup_recovery(tmp_path)
    url = reverse('ui_web:report_recovery', kwargs={'project_id': args[1], 'stage_id': args[2], 'draft_id': draft.draft_id})
    auth = {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}
    with patch.object(ReportRecoveryView, 'service_factory', side_effect=ArchiveError('ARCHIVE_MANIFEST_INVALID')):
        get = Client().get(url, **auth)
        post = Client().post(url, data=json.dumps(payload), content_type='application/json', **auth)
    for response in (get, post):
        assert response.status_code == 503
        assert response.json()['error']['code'] == 'REPORT_STORAGE_UNAVAILABLE'
        assert 'no-store' in response['Cache-Control']
