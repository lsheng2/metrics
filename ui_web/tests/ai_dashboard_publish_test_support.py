from datetime import date, datetime, timezone
from unittest.mock import patch
import json

from django.urls import reverse

from bug_metrics.app.api import DashboardAiPublishApprovalRequest, bug_trend_api
from bug_metrics.models import JiraScopeConfig
from jira_history.models import JiraIssue


class AiDashboardPublishTestSupport:
    def seed_jira_aggregate_for_publish(self):
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            open_status_values=['Open', 'In Progress', 'Reopened'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Stopper', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            milestone_field='2a',
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Open stopper bug',
            issue_type='Bug',
            status='Open',
            severity_value='P1-Stopper',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1002',
            summary='Open high bug',
            issue_type='Bug',
            status='Open',
            severity_value='P2-High',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        )
        return bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 30))

    def approved_publish_request(self):
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
        return bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')

    def publish_jira_demo(self, proof_id, from_time):
        pending = bug_trend_api.request_ai_grafana_publish_approval(
            DashboardAiPublishApprovalRequest(
                profile_id='chiplet-2a-jira',
                dashboard_uid='ai-open-bug-trend-demo',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW32',
                range_end='26WW35',
                dry_run_proof_id=proof_id,
                actor='ai_sidecar',
                artifact_ref=f'ai-base-artifact://workspace/{proof_id}',
                artifact_version=1,
                artifact_hash=f'sha256:{proof_id}',
            )
        )
        approval = bug_trend_api.decide_ai_grafana_publish_approval(pending['approval_id'], 'approved', 'local_operator')
        with patch('bug_metrics.app.api.ai_dashboard_composition.import_grafana_dashboard_payload') as importer:
            importer.return_value = {'status': 'imported', 'uid': 'ai-open-bug-trend-demo'}
            response = self.client.post(
                reverse('ui_web:ai_dashboard_publish_demo_api'),
                data=self.publish_request_json({
                    'visualization': 'barchart',
                    'approval_id': approval['approval_id'],
                    'dry_run_proof_id': proof_id,
                    'artifact_ref': f'ai-base-artifact://workspace/{proof_id}',
                    'artifact_version': 1,
                    'artifact_hash': f'sha256:{proof_id}',
                    'correlation_id': f'corr-{proof_id}',
                }),
                content_type='application/json',
                HTTP_X_TEST_FROM_TIME=from_time,
            )
        payload = response.json()
        self.assertEqual('published', payload['status'])
        return payload

    def publish_request_json(self, overrides: dict | None = None) -> str:
        payload = {
            'profile_id': 'chiplet-2a-jira',
            'dashboard_uid': 'ai-open-bug-trend-demo',
            'chart_id': 'open_bug_trend',
            'requested_series': ['new_critical_high'],
            'range_mode': 'ww',
            'range_start': '26WW32',
            'range_end': '26WW35',
            'operation': 'grafana_import',
            'actor': 'ai_sidecar',
        }
        payload.update(overrides or {})
        return json.dumps(payload)
