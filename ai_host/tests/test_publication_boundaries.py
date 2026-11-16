from copy import deepcopy

from django.test import TestCase, override_settings

from bug_metrics.app.api.ai_chart_inputs import draft_crosses_boundary
from bug_metrics.app.api.ai_chart_workflow import AiChartWorkflowService
from bug_metrics.tests.ai_publication_fixtures import chart_request, seed_publication_data


@override_settings(METRICS_AI_GRAFANA_BASE_URL='http://127.0.0.1:39999')
class TestPublicationBoundaries(TestCase):
    def test_operator_draft_cannot_select_a_different_profile(self):
        seed_publication_data()
        service = AiChartWorkflowService()
        draft = deepcopy(service.run(chart_request())['normalized_render_config'])
        draft['variables'][0].update(values=['nvu-ttl-hsdes'], current='nvu-ttl-hsdes')
        result = service.preview(chart_request(render_config=draft))
        self.assertFalse(result.ready)
        self.assertEqual('validation_failed', result.workflow['status'])
        self.assertTrue(result.workflow['findings'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='not-a-url')
    def test_operator_readiness_and_tool_preview_agree_on_invalid_target(self):
        seed_publication_data()
        service = AiChartWorkflowService()
        workflow = service.run(chart_request())
        preview = service.preview(chart_request())
        self.assertFalse(workflow['publish_readiness']['ready'])
        self.assertEqual('grafana_not_configured', workflow['publish_readiness']['status'])
        self.assertFalse(preview.ready)

    def test_malformed_boundary_values_are_rejected_without_type_errors(self):
        for draft in (
            {'profile_id': {}}, {'provider_id': {'name': 'jira'}},
            {'variables': None}, {'variables': 7},
            {'profile_id': []}, {'url': 'http://[invalid/?profile_id=x'},
        ):
            with self.subTest(draft=draft):
                self.assertTrue(draft_crosses_boundary(
                    draft, profile_id='chiplet-2a-jira', provider_id='jira', scope_id='1',
                ))
