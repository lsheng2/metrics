import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date, datetime, timezone

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from bug_metrics.models import BugTrendBucket, BugTrendBucketIssue, BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue, JiraIssueSnapshot, JiraTransition
from jira_sync.models import JiraSyncCursor
from jira_sync.out.jira_scope_issue_adapter import JiraScopeIssueAdapter


class FailingCalculationJiraHistoryApi:
    def list_issues(self, scope):
        raise RuntimeError('calculation history unavailable')


class FailingCalculationJiraHistoryContainer:
    jira_history_api = FailingCalculationJiraHistoryApi()


class TestSyncJiraScopeCommand(TestCase):
    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldSyncSavedScopeIntoDurableHistoryAndTrendBuckets(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]

        # When
        call_command(
            'sync_jira_scope',
            str(scope.id),
            '--coverage-start', '2026-08-03',
            '--coverage-end', '2026-08-09',
            stdout=StringIO(),
        )

        # Then
        cursor = JiraSyncCursor.objects.get(scope=scope)
        self.assertEqual(JiraSyncCursor.STATUS_SUCCESS, cursor.status)
        self.assertEqual('covered', cursor.changelog_coverage_status)
        self.assertEqual(1, JiraIssue.objects.filter(scope=scope, issue_key='STDEL-8942').count())
        self.assertEqual(1, JiraIssueSnapshot.objects.filter(scope=scope, issue_key='STDEL-8942').count())
        self.assertEqual(1, JiraTransition.objects.filter(scope=scope, issue_key='STDEL-8942', to_value='Fixed').count())
        self.assertEqual(1, BugTrendCalculationRun.objects.filter(scope=scope, status=BugTrendCalculationRun.STATUS_COMPLETED).count())
        self.assertEqual(1, BugTrendBucket.objects.filter(scope=scope, fixed_or_closed_count=1).count())
        self.assertEqual(1, BugTrendBucketIssue.objects.filter(scope=scope, issue_key='STDEL-8942', series_name='fixed_or_closed_bugs').count())

    def test_shouldRejectIncrementalSyncWhenRequestedRangeExpandsReliableCoverage(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_SUCCESS,
            last_jira_updated_cutoff=datetime(2026, 8, 10, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=datetime(2026, 8, 3, tzinfo=timezone.utc).date(),
            latest_reliable_bucket_end=datetime(2026, 8, 9, tzinfo=timezone.utc).date(),
            changelog_coverage_status='covered',
            materialized_config_version_hash=scope.config_version_hash,
        )

        # When / Then
        with self.assertRaises(CommandError):
            call_command(
                'sync_jira_scope',
                str(scope.id),
                '--coverage-start', '2026-08-01',
                '--coverage-end', '2026-08-09',
                stdout=StringIO(),
            )

    def test_shouldRejectSecondSyncWhenScopeCursorIsRunning(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        JiraSyncCursor.objects.create(scope=scope, status=JiraSyncCursor.STATUS_RUNNING)

        # When / Then
        with self.assertRaises(CommandError):
            call_command(
                'sync_jira_scope',
                str(scope.id),
                '--coverage-start', '2026-08-03',
                '--coverage-end', '2026-08-09',
                stdout=StringIO(),
            )

    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldUseBaseScopeJqlAndClearCurrentStateWhenFullSyncExpandsCoverage(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_SUCCESS,
            last_jira_updated_cutoff=datetime(2026, 8, 10, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=datetime(2026, 8, 3, tzinfo=timezone.utc).date(),
            latest_reliable_bucket_end=datetime(2026, 8, 9, tzinfo=timezone.utc).date(),
            changelog_coverage_status='covered',
            materialized_config_version_hash=scope.config_version_hash,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STALE-1',
            issue_type='Bug',
            status='Open',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]

        # When
        call_command(
            'sync_jira_scope',
            str(scope.id),
            '--coverage-start', '2026-08-01',
            '--coverage-end', '2026-08-09',
            '--full',
            stdout=StringIO(),
        )

        # Then
        adapter_class.return_value.fetch_issues.assert_called_once()
        self.assertEqual(scope.jql, adapter_class.return_value.fetch_issues.call_args.args[0])
        self.assertFalse(JiraIssue.objects.filter(scope=scope, issue_key='STALE-1').exists())

    @patch('jira_sync.management.commands.sync_jira_scope.bug_metrics_container')
    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldNotPromoteFullSyncCoverageWhenRecalculationFails(self, adapter_class, create_jira_client, bug_metrics_container):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        cursor = JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_SUCCESS,
            last_jira_updated_cutoff=datetime(2026, 8, 10, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=datetime(2026, 8, 3, tzinfo=timezone.utc).date(),
            latest_reliable_bucket_end=datetime(2026, 8, 9, tzinfo=timezone.utc).date(),
            changelog_coverage_status='covered',
            materialized_config_version_hash=scope.config_version_hash,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STABLE-1',
            issue_type='Bug',
            status='Open',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]
        bug_metrics_container.bug_trend_api.recalculate_scope.side_effect = RuntimeError('calculation failed')
        bug_metrics_container.bug_trend_api.get_scope.return_value = scope

        # When / Then
        with self.assertRaises(RuntimeError):
            call_command(
                'sync_jira_scope',
                str(scope.id),
                '--coverage-start', '2026-08-01',
                '--coverage-end', '2026-08-09',
                '--full',
                stdout=StringIO(),
            )

        cursor.refresh_from_db()
        self.assertEqual(JiraSyncCursor.STATUS_FAILED, cursor.status)
        self.assertEqual(datetime(2026, 8, 3, tzinfo=timezone.utc).date(), cursor.earliest_reliable_bucket_start)
        self.assertEqual(datetime(2026, 8, 9, tzinfo=timezone.utc).date(), cursor.latest_reliable_bucket_end)
        self.assertTrue(JiraIssue.objects.filter(scope=scope, issue_key='STABLE-1').exists())

    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldPersistFailedCalculationRunWhenRecalculationRollsBackSyncTransaction(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL failed calculation artifact',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]

        # When / Then
        with patch('bug_metrics.app.api.calculation.jira_history_container', FailingCalculationJiraHistoryContainer()):
            with self.assertRaises(RuntimeError):
                call_command(
                    'sync_jira_scope',
                    str(scope.id),
                    '--coverage-start', '2026-08-03',
                    '--coverage-end', '2026-08-09',
                    stdout=StringIO(),
                )

        failed_run = BugTrendCalculationRun.objects.get(scope=scope)
        self.assertEqual(BugTrendCalculationRun.STATUS_FAILED, failed_run.status)
        self.assertEqual(date(2026, 8, 3), failed_run.source_coverage_start)
        self.assertEqual(date(2026, 8, 9), failed_run.source_coverage_end)

    def test_shouldRejectIncrementalSyncWhenScopeConfigChangedSinceMaterialization(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        old_hash = scope.config_version_hash
        scope.jql = 'project = STDEL AND issuetype = Bug AND component = Emulation'
        scope.save()
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_SUCCESS,
            last_jira_updated_cutoff=datetime(2026, 8, 10, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=datetime(2026, 8, 3, tzinfo=timezone.utc).date(),
            latest_reliable_bucket_end=datetime(2026, 8, 9, tzinfo=timezone.utc).date(),
            changelog_coverage_status='covered',
            materialized_config_version_hash=old_hash,
        )

        # When / Then
        with self.assertRaises(CommandError):
            call_command(
                'sync_jira_scope',
                str(scope.id),
                '--coverage-start', '2026-08-03',
                '--coverage-end', '2026-08-09',
                stdout=StringIO(),
            )

    def test_shouldRejectIncrementalSyncWhenFieldMappingChangedSinceMaterialization(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            severity_field='priority',
        )
        old_hash = scope.config_version_hash
        scope.severity_field = 'customfield_12345'
        scope.save()
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_SUCCESS,
            last_jira_updated_cutoff=datetime(2026, 8, 10, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=datetime(2026, 8, 3, tzinfo=timezone.utc).date(),
            latest_reliable_bucket_end=datetime(2026, 8, 9, tzinfo=timezone.utc).date(),
            changelog_coverage_status='covered',
            materialized_config_version_hash=old_hash,
        )

        # When / Then
        with self.assertRaises(CommandError):
            call_command(
                'sync_jira_scope',
                str(scope.id),
                '--coverage-start', '2026-08-03',
                '--coverage-end', '2026-08-09',
                stdout=StringIO(),
            )

    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldRemoveKnownIssueFromCurrentScopeWhenIncrementalUpdateNoLongerMatchesScopeJql(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL emulation',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            open_status_values=['Open'],
        )
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_SUCCESS,
            last_jira_updated_cutoff=datetime(2026, 8, 10, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=datetime(2026, 8, 3, tzinfo=timezone.utc).date(),
            latest_reliable_bucket_end=datetime(2026, 8, 9, tzinfo=timezone.utc).date(),
            changelog_coverage_status='covered',
            materialized_config_version_hash=scope.config_version_hash,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-3002',
            summary='Moved out of scope',
            issue_type='Bug',
            status='Open',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        adapter_class.return_value.fetch_issues.side_effect = [[], [self._jira_issue_payload('STDEL-3002')]]

        # When
        call_command(
            'sync_jira_scope',
            str(scope.id),
            '--coverage-start', '2026-08-03',
            '--coverage-end', '2026-08-09',
            stdout=StringIO(),
        )

        # Then
        issue = JiraIssue.objects.get(scope=scope, issue_key='STDEL-3002')
        self.assertFalse(issue.is_in_current_scope)
        self.assertEqual(0, BugTrendBucket.objects.get(scope=scope).open_count)

    def _jira_issue_payload(self, issue_key='STDEL-8942'):
        return {
            'key': issue_key,
            'fields': {
                'summary': 'Failure in emulation flow',
                'issuetype': {'name': 'Bug'},
                'status': {'name': 'Fixed'},
                'resolution': {'name': 'Fixed'},
                'priority': {'name': 'P3-Medium'},
                'components': [{'name': 'team_emulation'}],
                'assignee': {'displayName': 'Alice'},
                'created': '2026-08-04T10:00:00.000+0000',
                'updated': '2026-08-05T10:00:00.000+0000',
                'resolutiondate': '2026-08-05T09:00:00.000+0000',
            },
            'changelog': {
                'histories': [
                    {
                        'created': '2026-08-05T09:00:00.000+0000',
                        'items': [
                            {'field': 'status', 'fromString': 'Open', 'toString': 'Fixed'},
                        ],
                    }
                ]
            },
        }


class TestDumpRealJiraBugTrendFixtureCommand(TestCase):
    @patch('jira_sync.management.commands.dump_real_jira_bug_trend_fixture.create_jira_client')
    @patch('jira_sync.management.commands.dump_real_jira_bug_trend_fixture.JiraScopeIssueAdapter')
    def test_shouldDumpRealJiraRestFixtureWithoutSeedingDatabase(self, adapter_class, create_jira_client):
        # Given
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]

        # When
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'real-jira.json'
            call_command(
                'dump_real_jira_bug_trend_fixture',
                '--project', '131600',
                '--issue-limit', '2',
                '--page-size', '25',
                '--output', str(output_path),
                stdout=StringIO(),
            )
            fixture = json.loads(output_path.read_text(encoding='utf-8'))

        # Then
        adapter_class.assert_called_once_with(create_jira_client.return_value, page_size=25)
        adapter_class.return_value.fetch_issues.assert_called_once()
        self.assertEqual('project = 131600 ORDER BY updated DESC', adapter_class.return_value.fetch_issues.call_args.args[0])
        self.assertEqual(2, adapter_class.return_value.fetch_issues.call_args.kwargs['issue_limit'])
        self.assertEqual('jira-rest-read-only', fixture['source'])
        self.assertEqual('STDEL-8942', fixture['issues'][0]['key'])
        self.assertEqual('Failure in emulation flow', fixture['issues'][0]['fields']['summary'])
        self.assertIn('changelog', fixture['issues'][0])
        self.assertFalse(JiraScopeConfig.objects.exists())
        self.assertFalse(JiraIssue.objects.exists())

    @patch('jira_sync.management.commands.dump_real_jira_bug_trend_fixture.create_jira_client')
    @patch('jira_sync.management.commands.dump_real_jira_bug_trend_fixture.JiraScopeIssueAdapter')
    def test_shouldSeedDumpedRealJiraFixtureWhenRequested(self, adapter_class, create_jira_client):
        # Given
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]

        # When
        with TemporaryDirectory() as temp_dir:
            call_command(
                'dump_real_jira_bug_trend_fixture',
                '--project', '131600',
                '--seed-db',
                '--output', str(Path(temp_dir) / 'real-jira.json'),
                stdout=StringIO(),
            )

        # Then
        scope = JiraScopeConfig.objects.get(project_label='131600')
        issue = JiraIssue.objects.get(scope=scope, issue_key='STDEL-8942')
        self.assertEqual('Failure in emulation flow', issue.summary)
        self.assertEqual({'name': 'P3-Medium'}, issue.raw_fields_json['priority'])
        self.assertTrue(JiraTransition.objects.filter(scope=scope, issue_key='STDEL-8942', to_value='Fixed').exists())

    def _jira_issue_payload(self):
        return {
            'key': 'STDEL-8942',
            'fields': {
                'summary': 'Failure in emulation flow',
                'issuetype': {'name': 'Bug'},
                'status': {'name': 'Fixed'},
                'resolution': {'name': 'Fixed'},
                'priority': {'name': 'P3-Medium'},
                'components': [{'name': 'team_emulation'}],
                'assignee': {'displayName': 'Alice'},
                'created': '2026-08-04T10:00:00.000+0000',
                'updated': '2026-08-05T10:00:00.000+0000',
                'resolutiondate': '2026-08-05T09:00:00.000+0000',
            },
            'changelog': {
                'histories': [
                    {
                        'created': '2026-08-05T09:00:00.000+0000',
                        'items': [
                            {'field': 'status', 'fromString': 'Open', 'toString': 'Fixed'},
                        ],
                    }
                ]
            },
        }


class TestJiraScopeIssueAdapter(TestCase):
    def test_shouldRejectPartialExpandedChangelog(self):
        # Given
        jira_client = FakeJiraClient({
            'issues': [
                {
                    'key': 'STDEL-8942',
                    'changelog': {'total': 2, 'histories': [{}]},
                }
            ],
            'total': 1,
        })
        adapter = JiraScopeIssueAdapter(jira_client)

        # When / Then
        with self.assertRaises(ValueError):
            adapter.fetch_issues('project = STDEL', ['summary'])

    def test_shouldStopFetchingWhenIssueLimitIsReached(self):
        # Given
        jira_client = PagedFakeJiraClient()
        adapter = JiraScopeIssueAdapter(jira_client, page_size=2)

        # When
        issues = adapter.fetch_issues('project = STDEL', ['summary'], issue_limit=3)

        # Then
        self.assertEqual(['STDEL-1', 'STDEL-2', 'STDEL-3'], [issue['key'] for issue in issues])
        self.assertEqual([2, 1], [call['limit'] for call in jira_client.calls])


class FakeJiraClient:
    def __init__(self, response):
        self._response = response

    def jql(self, *args, **kwargs):
        return self._response


class PagedFakeJiraClient:
    def __init__(self):
        self.calls = []

    def jql(self, *args, **kwargs):
        self.calls.append(kwargs)
        start = kwargs['start']
        limit = kwargs['limit']
        issues = []
        for index in range(start + 1, start + limit + 1):
            issues.append({
                'key': f'STDEL-{index}',
                'changelog': {'total': 0, 'histories': []},
            })
        return {'issues': issues, 'total': 10}