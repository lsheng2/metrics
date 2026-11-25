import json

from django.urls import reverse
from django.test import override_settings

from ui_web.tests.project_fixtures import ProjectRouteTestSupport, basic_header
from ui_web.tests.report_authoring_browser_support import ReportAuthoringBrowserTestCase


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestReportBrowserRecoveryFixture(ReportAuthoringBrowserTestCase):
    def test_existing_preview_recovery_uses_the_shared_draft_service(self):
        draft = self.create_draft(9701)
        url = reverse('ui_web:report_recovery', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
        })
        auth = {'HTTP_AUTHORIZATION': basic_header('alice', 'wonder')}
        payload = {
            'client_id': '97010000-0000-4000-8000-000000000001',
            'sequence': 1,
            'base_revision': draft.revision,
            'base_revision_hash': draft.revision_hash,
            'snapshot_hash': draft.snapshot_hash,
            'template_hash': draft.template_definition.template_hash,
            'content': {'edits': [], 'continuity_changes': [], 'save_request': None},
        }

        listed = self.client.get(url, **auth)
        stored = self.client.post(url, data=json.dumps(payload), content_type='application/json', **auth)
        item_url = reverse('ui_web:report_recovery_item', kwargs={
            'project_id': self.project.id,
            'stage_id': self.stage.id,
            'draft_id': draft.draft_id,
            'client_id': payload['client_id'],
        })
        reopened = self.client.get(item_url, **auth)

        assert listed.status_code == 200, listed.content
        assert listed.json()['error'] is None
        assert stored.status_code == 200, stored.content
        assert stored.json()['result']['restorable']
        assert reopened.status_code == 200, reopened.content
        assert reopened.json()['result']['content'] == payload['content']
