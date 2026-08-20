from datetime import datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import JiraScopeConfig
from jira_history.models import JiraIssue, JiraTransition


class TestBugTrendScopeAuditViews(TestCase):
    def test_shouldRenderReadOnlyScopeAuditForSavedScope(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL audit UI',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            closed_status_values=['Closed'],
            fixed_resolution_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P2-High'],
            component_field='components',
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            issue_type='Bug',
            status='Closed',
            resolution_value='Fixed',
            severity_value='P1-Stopper',
            component_value='Emulation',
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            resolved_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1002',
            issue_type='Bug',
            status='New',
            resolution_value='',
            severity_value='P2-High',
            component_value='Validation',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            transitioned_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            field='status',
            from_value='New',
            to_value='Closed',
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            transitioned_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
            field='resolution',
            from_value='',
            to_value='Fixed',
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_audit'), {'scope_id': scope.id})

        # Then
        self.assertEqual(200, response.status_code)
        content = response.content.decode()
        self.assertIn('Bug Trend Scope Audit', content)
        self.assertIn('STDEL audit UI', content)
        self.assertIn(scope.config_version_hash, content)
        self.assertIn('P1-Stopper', content)
        self.assertIn('P2-High', content)
        self.assertIn('unmapped', content)
        self.assertIn('critical_high', content)
        self.assertIn('closed_status', content)
        self.assertIn('fixed_resolution', content)
        self.assertIn('component_field', content)
        self.assertIn('Total issues', content)
        self.assertIn('Issues with created date', content)
        self.assertIn('Issues with updated date', content)
        self.assertIn('Issues with resolved date', content)
        self.assertIn('Status transitions', content)
        self.assertIn('Resolution transitions', content)
        self.assertIn('2', content)
        self.assertIn('1', content)

    def test_shouldLinkBugTrendPageToSelectedScopeAudit(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL audit link',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend'), {'scope_id': scope.id})

        # Then
        self.assertEqual(200, response.status_code)
        self.assertIn(f"{reverse('ui_web:bug_trend_scope_audit')}?scope_id={scope.id}", response.content.decode())
