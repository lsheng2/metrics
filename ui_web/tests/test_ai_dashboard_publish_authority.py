import json
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bug_metrics.app.api import DashboardAiPublishApprovalRequest, bug_trend_api
from bug_metrics.models import BugTrendAuditEvent
from ui_web.tests.ai_dashboard_publish_test_support import AiDashboardPublishTestSupport


class TestAiDashboardPublishAuthority(AiDashboardPublishTestSupport, TestCase):
    def test_shouldRecordGcxPublicationCallbackAudit(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_gcx_publication_callback_api'),
            data=json.dumps({
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
                'dashboard_uid': 'ip-quality-dashboard',
                'artifact_ref': 'ai-base-artifact://run-123/ip-quality-dashboard.json',
                'mutation_status': 'succeeded',
                'correlation_id': 'corr-123',
                'dry_run_proof_id': 'proof-123',
            }),
            content_type='application/json',
        )

        payload = response.json()
        event = BugTrendAuditEvent.objects.get(event_type='ai_gcx_publication_callback_recorded')
        self.assertEqual(200, response.status_code)
        self.assertEqual('recorded', payload['status'])
        self.assertEqual('corr-123', payload['correlation_id'])
        self.assertEqual('ai_sidecar', event.actor)
        self.assertEqual('ip-quality-dashboard', event.request_summary['dashboard_uid'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldPublishApprovedAiDashboardDraftToGrafanaAndReturnUrl(self):
        self.seed_jira_aggregate_for_publish()
        approval = self.approved_publish_request()
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'imported', 'uid': 'ai-open-bug-trend-demo'}

            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=self.publish_request_json({
                    'visualization': 'barchart',
                    'approval_id': approval['approval_id'],
                    'dry_run_proof_id': 'dryrun-local-demo',
                    'artifact_ref': 'ai-base-artifact://workspace/art_publish',
                    'artifact_version': 3,
                    'artifact_hash': 'sha256:publishhash',
                }),
                content_type='application/json',
            )

        payload = response.json()
        event = BugTrendAuditEvent.objects.get(event_type='ai_gcx_publication_callback_recorded')
        imported_dashboard = importer.call_args.args[1]
        self.assertEqual(200, response.status_code)
        self.assertEqual('published', payload['status'])
        self.assertEqual('ai-open-bug-trend-demo', payload['dashboard_uid'])
        self.assertIn('/d/ai-open-bug-trend-demo/', payload['dashboard_url'])
        self.assertEqual('recorded', payload['audit']['status'])
        self.assertEqual('published', payload['approval']['status'])
        self.assertEqual('jira', payload['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['profile_id'])
        self.assertEqual('open_bug_trend', payload['chart_id'])
        self.assertEqual(1, payload['chart_version'])
        self.assertEqual(['new_critical_high'], payload['requested_series'])
        self.assertEqual('barchart', payload['visualization'])
        self.assertEqual('ai-base-artifact://workspace/art_publish', payload['artifact_ref'])
        self.assertEqual(3, payload['artifact_version'])
        self.assertEqual('sha256:publishhash', payload['artifact_hash'])
        self.assertEqual('metrics.jira.chiplet-2a-jira', payload['workspace_key'])
        self.assertEqual('dryrun-local-demo', event.request_summary['dry_run_proof_id'])
        self.assertEqual('ai-base-artifact://workspace/art_publish', event.request_summary['artifact_ref'])
        self.assertEqual('ai-open-bug-trend-demo', imported_dashboard['uid'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldBlockJiraAiDashboardPublishWhenAggregateRowsAreMissing(self):
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=self.publish_request_json({
                    'approval_id': 'approval_chat_demo_missing_data',
                    'dry_run_proof_id': 'dryrun-local-demo',
                }),
                content_type='application/json',
            )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertEqual('approval_not_granted', payload['reason'])
        self.assertEqual('missing', payload['approval']['status'])
        self.assertFalse(importer.called)
        self.assertFalse(BugTrendAuditEvent.objects.filter(event_type='ai_gcx_publication_callback_recorded').exists())

    def test_shouldTrackAiGrafanaPublishApprovalStateTransitions(self):
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-local-demo',
                actor='ai_sidecar',
                artifact_ref='ai-base-artifact://workspace/art_publish',
                artifact_version=3,
                artifact_hash='sha256:publishhash',
            )
        )

        approved = bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')
        rejected_seed = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo-rejected',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-rejected-demo',
                actor='ai_sidecar',
                artifact_ref='ai-base-artifact://workspace/rejected-proof',
                artifact_version=1,
                artifact_hash='sha256:rejected',
            )
        )
        rejected = bug_trend_api.decide_ai_grafana_publish_approval(rejected_seed['approval_id'], 'rejected', 'local_operator')

        self.assertEqual('pending_approval', pending['status'])
        self.assertEqual('approved', approved['status'])
        self.assertEqual('rejected', rejected['status'])
        self.assertEqual('approved', bug_trend_api.get_ai_grafana_publish_approval(pending['approval_id'])['status'])

    def test_shouldExposeAiGrafanaPublishApprovalApi(self):
        create_response = self.client.post(
            reverse('ui_web:ai_dashboard_publish_approval_api'),
            data=self.publish_request_json({
                'dry_run_proof_id': 'dryrun-local-demo',
                'artifact_ref': 'ai-base-artifact://workspace/art_publish',
                'artifact_version': 3,
                'artifact_hash': 'sha256:publishhash',
            }),
            content_type='application/json',
        )

        approval_id = create_response.json()['approval_id']
        created = create_response.json()
        decide_response = self.client.post(
            reverse('ui_web:ai_dashboard_publish_approval_decision_api'),
            data=json.dumps({
                'approval_id': approval_id,
                'decision': 'approved',
                'actor': 'local_operator',
            }),
            content_type='application/json',
        )
        state_response = self.client.get(reverse('ui_web:ai_dashboard_publish_approval_api'), {'approval_id': approval_id})

        self.assertEqual(200, create_response.status_code)
        self.assertEqual('pending_approval', created['status'])
        self.assertEqual('jira', created['request_summary']['provider_id'])
        self.assertEqual('metrics.jira.chiplet-2a-jira', created['request_summary']['workspace_key'])
        self.assertEqual('sha256:publishhash', created['request_summary']['artifact_hash'])
        self.assertTrue(created['request_summary']['created_at'])
        self.assertTrue(created['request_summary']['expires_at'])
        self.assertEqual(200, decide_response.status_code)
        self.assertEqual('approved', decide_response.json()['status'])
        self.assertEqual(200, state_response.status_code)
        self.assertEqual('approved', state_response.json()['status'])

    def test_shouldRejectAiGrafanaPublishApprovalWithoutArtifactHash(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_publish_approval_api'),
            data=self.publish_request_json({
                'dry_run_proof_id': 'dryrun-local-demo',
                'artifact_ref': 'ai-base-artifact://workspace/art_publish',
                'artifact_version': 3,
            }),
            content_type='application/json',
        )

        self.assertEqual(400, response.status_code)
        self.assertIn('artifact_hash', response.json()['error'])

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldBlockAiDashboardPublishWhenApprovalIsNotApproved(self):
        self.seed_jira_aggregate_for_publish()
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-local-demo',
                actor='ai_sidecar',
                artifact_ref='ai-base-artifact://workspace/art_publish',
                artifact_version=3,
                artifact_hash='sha256:publishhash',
            )
        )
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=self.publish_request_json({
                    'approval_id': pending['approval_id'],
                    'dry_run_proof_id': 'dryrun-local-demo',
                }),
                content_type='application/json',
            )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertEqual('approval_not_granted', payload['reason'])
        self.assertEqual('pending_approval', payload['approval']['status'])
        self.assertFalse(importer.called)

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldBlockAiDashboardPublishWithForgedDemoApprovalPrefix(self):
        self.seed_jira_aggregate_for_publish()
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=self.publish_request_json({
                    'approval_id': 'approval_chat_demo_forged',
                    'dry_run_proof_id': 'dryrun-forged',
                    'artifact_ref': 'ai-base-artifact://workspace/forged',
                    'artifact_version': 1,
                }),
                content_type='application/json',
            )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertEqual('approval_not_granted', payload['reason'])
        self.assertEqual('missing', payload['approval']['status'])
        self.assertFalse(importer.called)

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldBlockAiDashboardPublishWhenApprovalScopeDoesNotMatchRequest(self):
        self.seed_jira_aggregate_for_publish()
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-approved',
                actor='ai_sidecar',
                artifact_ref='ai-base-artifact://workspace/art-approved',
                artifact_version=3,
                artifact_hash='sha256:approved',
            )
        )
        approval = bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=self.publish_request_json({
                    'approval_id': approval['approval_id'],
                    'dry_run_proof_id': 'dryrun-mismatched',
                    'artifact_ref': 'ai-base-artifact://workspace/art-approved',
                    'artifact_version': 3,
                    'artifact_hash': 'sha256:approved',
                }),
                content_type='application/json',
            )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertEqual('approval_not_granted', payload['reason'])
        self.assertEqual('scope_mismatch', payload['approval']['status'])
        self.assertFalse(importer.called)

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldBlockAiDashboardPublishWhenApprovalIsExpired(self):
        self.seed_jira_aggregate_for_publish()
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id='dryrun-expired',
                actor='ai_sidecar',
                artifact_ref='ai-base-artifact://workspace/art-expired',
                artifact_version=3,
                artifact_hash='sha256:expired',
            )
        )
        summary = bug_trend_api.get_ai_grafana_publish_approval(pending['approval_id'])['request_summary']
        summary['expires_at'] = (timezone.now() - timedelta(minutes=1)).isoformat()
        request_event = BugTrendAuditEvent.objects.get(event_type='ai_grafana_publish_approval_requested')
        request_event.request_summary = summary
        request_event.save(update_fields=['request_summary'])
        approval = bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=self.publish_request_json({
                    'approval_id': approval['approval_id'],
                    'dry_run_proof_id': 'dryrun-expired',
                    'artifact_ref': 'ai-base-artifact://workspace/art-expired',
                    'artifact_version': 3,
                    'artifact_hash': 'sha256:expired',
                }),
                content_type='application/json',
            )

        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('blocked', payload['status'])
        self.assertEqual('approval_not_granted', payload['reason'])
        self.assertEqual('expired', payload['approval']['status'])
        self.assertFalse(importer.called)

    @override_settings(METRICS_AI_GRAFANA_BASE_URL='http://grafana.test')
    def test_shouldListAiGrafanaPublishHistoryWithLatestMarker(self):
        self.seed_jira_aggregate_for_publish()
        first = self.publish_jira_demo('first-proof', '2026-08-03T00:00:00')
        second = self.publish_jira_demo('second-proof', '2026-08-10T00:00:00')

        response = self.client.get(reverse('ui_web:ai_dashboard_publish_history_api'))

        payload = response.json()
        rows = payload['items']
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.2', payload['contract_version'])
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(second['approval']['approval_id'], rows[0]['approval_id'])
        self.assertEqual(first['approval']['approval_id'], rows[1]['approval_id'])
        self.assertTrue(rows[0]['latest'])
        self.assertFalse(rows[1]['latest'])
        self.assertEqual('jira', rows[0]['provider_id'])
        self.assertEqual('chiplet-2a-jira', rows[0]['profile_id'])
        self.assertEqual('open_bug_trend', rows[0]['chart_id'])
        self.assertEqual('ai-base-artifact://workspace/second-proof', rows[0]['artifact_ref'])
        self.assertEqual(1, rows[0]['artifact_version'])
        self.assertEqual('sha256:second-proof', rows[0]['artifact_hash'])
        self.assertEqual('metrics.jira.chiplet-2a-jira', rows[0]['workspace_key'])
        self.assertIn('/d/ai-open-bug-trend-demo/', rows[0]['dashboard_url'])

    def test_shouldRejectAiDashboardPublishWithoutApprovalAndProof(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_publish_demo_api'),
            data=self.publish_request_json(),
            content_type='application/json',
        )

        self.assertEqual(400, response.status_code)
        self.assertIn('approval_id', response.json()['error'])
        self.assertFalse(BugTrendAuditEvent.objects.filter(event_type='ai_gcx_publication_callback_recorded').exists())

    def test_shouldRejectIncompleteGcxPublicationCallbackWithoutAuditRecord(self):
        response = self.client.post(
            reverse('ui_web:ai_dashboard_gcx_publication_callback_api'),
            data=json.dumps({
                'operation': 'grafana_import',
                'actor': 'ai_sidecar',
                'dashboard_uid': 'ip-quality-dashboard',
                'artifact_ref': 'ai-base-artifact://run-123/ip-quality-dashboard.json',
                'mutation_status': 'succeeded',
            }),
            content_type='application/json',
        )

        self.assertEqual(400, response.status_code)
        self.assertIn('correlation_id', response.json()['error'])
        self.assertFalse(BugTrendAuditEvent.objects.filter(event_type='ai_gcx_publication_callback_recorded').exists())
