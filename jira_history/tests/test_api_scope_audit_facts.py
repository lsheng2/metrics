from datetime import datetime, timezone

from django.test import TestCase

from bug_metrics.models import JiraScopeConfig
from jira_history.app.api import jira_history_api
from jira_history.models import JiraIssue, JiraTransition


class TestScopeAuditFacts(TestCase):
    def test_shouldReturnObservedValuesAndCoverageFromLocalHistory(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL audit facts',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Stopper bug',
            issue_type='Bug',
            status='Closed',
            resolution_value='Fixed',
            severity_value='P1-Stopper',
            component_value='Emulation',
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
            resolved_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1002',
            summary='High bug',
            issue_type='Bug',
            status='In Progress',
            resolution_value='',
            severity_value='P2-High',
            component_value='Validation',
            created_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1003',
            summary='Task outside bug trend',
            issue_type='Task',
            status='Archived',
            resolution_value='Obsolete',
            severity_value='P3-Medium',
            component_value='Validation',
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            transitioned_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
            field='status',
            from_value='In Progress',
            to_value='Closed',
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            transitioned_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            field='resolution',
            from_value='',
            to_value='Fixed',
        )

        # When
        result = jira_history_api.get_scope_audit_facts(scope)

        # Then
        observed = {(item.category, item.value): item.count for item in result.observed_values}
        self.assertEqual(2, observed[('issue_type', 'Bug')])
        self.assertEqual(1, observed[('issue_type', 'Task')])
        self.assertEqual(2, observed[('status', 'In Progress')])
        self.assertEqual(2, observed[('status', 'Closed')])
        self.assertEqual(1, observed[('status', 'Archived')])
        self.assertEqual(2, observed[('resolution', 'Fixed')])
        self.assertEqual(1, observed[('resolution', 'Obsolete')])
        self.assertEqual(1, observed[('severity', 'P1-Stopper')])
        self.assertEqual(1, observed[('severity', 'P2-High')])
        self.assertEqual(1, observed[('component', 'Emulation')])
        self.assertEqual(2, observed[('component', 'Validation')])
        self.assertEqual(3, result.coverage.total_issue_count)
        self.assertEqual(2, result.coverage.created_count)
        self.assertEqual(2, result.coverage.updated_count)
        self.assertEqual(1, result.coverage.resolved_count)
        self.assertEqual(1, result.coverage.status_transition_count)
        self.assertEqual(1, result.coverage.resolution_transition_count)
