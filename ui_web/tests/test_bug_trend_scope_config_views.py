from datetime import datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue


class TestBugTrendScopeConfigViews(TestCase):
    def test_shouldLinkUnmappedAuditSeverityIntoConfigEditorWithoutSaving(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL config handoff',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            severity_field='priority',
            critical_high_values=['P2-High'],
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-9001',
            issue_type='Bug',
            status='New',
            severity_value='P1-Stopper',
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        # When
        audit_response = self.client.get(reverse('ui_web:bug_trend_scope_audit'), {'scope_id': scope.id})
        config_response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'scope_id': scope.id,
            'add_field': 'critical_high_values',
            'add_value': 'P1-Stopper',
        })
        scope.refresh_from_db()

        # Then
        self.assertEqual(200, audit_response.status_code)
        self.assertIn('Add as critical/high', audit_response.content.decode())
        self.assertEqual(200, config_response.status_code)
        self.assertIn('P1-Stopper', config_response.content.decode())
        self.assertEqual(['P2-High'], scope.critical_high_values)

    def test_shouldSaveScopeConfigAndShowRecalculationPromptWhenSemanticHashChanges(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL config save',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P2-High'],
            medium_low_values=['P3-Medium'],
            enabled=True,
        )
        original_hash = scope.config_version_hash
        BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=original_hash,
            source_coverage_start=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
            source_coverage_end=datetime(2026, 8, 31, tzinfo=timezone.utc).date(),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), self._post_payload(scope, 'P2-High\nP1-Stopper'), follow=True)
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertNotEqual(original_hash, scope.config_version_hash)
        self.assertEqual(['P2-High', 'P1-Stopper'], scope.critical_high_values)
        self.assertIn('Scope config saved.', content)
        self.assertIn('Semantic config changed. Recalculate this scope before using existing Bug Trend runs as current evidence.', content)

    def _post_payload(self, scope, critical_high_values):
        return {
            'id': str(scope.id),
            'name': scope.name,
            'ip': scope.ip,
            'project_label': scope.project_label,
            'jql': scope.jql,
            'bug_type_values': '\n'.join(scope.bug_type_values),
            'open_status_values': '\n'.join(scope.open_status_values),
            'fixed_status_values': '\n'.join(scope.fixed_status_values),
            'closed_status_values': '\n'.join(scope.closed_status_values),
            'terminal_excluded_status_values': '\n'.join(scope.terminal_excluded_status_values),
            'fixed_resolution_values': '\n'.join(scope.fixed_resolution_values),
            'closed_resolution_values': '\n'.join(scope.closed_resolution_values),
            'reopen_status_values': '\n'.join(scope.reopen_status_values),
            'severity_field': scope.severity_field,
            'critical_high_values': critical_high_values,
            'medium_low_values': '\n'.join(scope.medium_low_values),
            'component_field': scope.component_field,
            'owner_field': scope.owner_field,
            'team_field': scope.team_field,
            'milestone_field': scope.milestone_field,
            'fix_version_field': scope.fix_version_field,
            'package_version_field': scope.package_version_field,
            'display_fields': '\n'.join(scope.display_fields),
            'timezone': scope.timezone,
            'bucket_granularity': scope.bucket_granularity,
            'enabled': 'on',
        }