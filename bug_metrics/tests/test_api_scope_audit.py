from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase

from bug_metrics.app.api import bug_trend_api
from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig
from jira_history.app.api import ScopeAuditCoverage, ScopeAuditFacts, ScopeAuditObservedValue
from jira_history.container import jira_history_container
from jira_history.models import JiraIssue, JiraTransition


@dataclass(slots=True)
class FakeJiraHistoryApi:
    facts: ScopeAuditFacts

    def get_scope_audit_facts(self, scope):
        return self.facts


@dataclass(slots=True)
class FakeJiraHistoryContainer:
    jira_history_api: FakeJiraHistoryApi


class TestScopeAuditApi(TestCase):
    def test_shouldClassifyObservedValuesAgainstScopeConfigAuthority(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL audit',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            open_status_values=['New', 'In Progress'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            fixed_resolution_values=['Fixed'],
            closed_resolution_values=['Done'],
            severity_field='priority',
            critical_high_values=['P2-High'],
            medium_low_values=['P3-Medium'],
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
            status='Archived',
            resolution_value='Obsolete',
            severity_value='P2-High',
            component_value='Validation',
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            transitioned_at=datetime(2026, 8, 2, tzinfo=timezone.utc),
            field='status',
            from_value='In Progress',
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
        result = bug_trend_api.get_scope_audit(scope.id)

        # Then
        values = {(item.category, item.value): item for item in result.observed_values}
        self.assertTrue(values[('issue_type', 'Bug')].mapped)
        self.assertEqual('bug_type', values[('issue_type', 'Bug')].mapping_group)
        self.assertTrue(values[('status', 'Closed')].mapped)
        self.assertEqual('closed_status', values[('status', 'Closed')].mapping_group)
        self.assertTrue(values[('resolution', 'Fixed')].mapped)
        self.assertEqual('fixed_resolution', values[('resolution', 'Fixed')].mapping_group)
        self.assertFalse(values[('status', 'Archived')].mapped)
        self.assertFalse(values[('resolution', 'Obsolete')].mapped)
        self.assertFalse(values[('severity', 'P1-Stopper')].mapped)
        self.assertTrue(values[('severity', 'P2-High')].mapped)
        self.assertEqual('critical_high', values[('severity', 'P2-High')].mapping_group)
        self.assertTrue(values[('component', 'Emulation')].mapped)
        self.assertEqual('component_field', values[('component', 'Emulation')].mapping_group)

    def test_shouldTransportCoverageCountsUnchangedFromJiraHistory(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL coverage transport',
            jql='project = STDEL AND issuetype = Bug',
        )
        fake_container = FakeJiraHistoryContainer(FakeJiraHistoryApi(
            ScopeAuditFacts(
                observed_values=[ScopeAuditObservedValue('severity', 'P1-Stopper', 7)],
                coverage=ScopeAuditCoverage(
                    total_issue_count=42,
                    created_count=10,
                    updated_count=25,
                    resolved_count=7,
                    status_transition_count=68,
                    resolution_transition_count=12,
                ),
            )
        ))

        # When
        with patch('bug_metrics.app.api.jira_history_container', fake_container):
            result = bug_trend_api.get_scope_audit(scope.id)

        # Then
        self.assertEqual(42, result.coverage.total_issue_count)
        self.assertEqual(10, result.coverage.created_count)
        self.assertEqual(25, result.coverage.updated_count)
        self.assertEqual(7, result.coverage.resolved_count)
        self.assertEqual(68, result.coverage.status_transition_count)
        self.assertEqual(12, result.coverage.resolution_transition_count)

    def test_shouldNotMutateScopeHistoryOrCalculationRowsDuringAudit(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL readonly audit',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        JiraIssue.objects.create(scope=scope, issue_key='STDEL-2001', issue_type='Bug', status='New')
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-2001',
            transitioned_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            field='status',
            from_value='Open',
            to_value='New',
        )
        BugTrendCalculationRun.objects.create(
            scope=scope,
            config_version_hash=scope.config_version_hash,
            source_coverage_start=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
            source_coverage_end=datetime(2026, 8, 7, tzinfo=timezone.utc).date(),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        before_counts = self._model_counts()
        before_hash = scope.config_version_hash

        # When
        bug_trend_api.get_scope_audit(scope.id)
        scope.refresh_from_db()

        # Then
        self.assertEqual(before_counts, self._model_counts())
        self.assertEqual(before_hash, scope.config_version_hash)

    def _model_counts(self):
        return {
            'scopes': JiraScopeConfig.objects.count(),
            'issues': JiraIssue.objects.count(),
            'transitions': JiraTransition.objects.count(),
            'runs': BugTrendCalculationRun.objects.count(),
        }
