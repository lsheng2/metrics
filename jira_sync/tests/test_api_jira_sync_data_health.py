from datetime import datetime, timezone

from django.test import TestCase

from bug_metrics.models import JiraScopeConfig
from jira_sync.app.api import jira_sync_api
from jira_sync.models import JiraSyncCursor


class TestJiraSyncHealthApi(TestCase):
    def test_shouldExposeLatestSyncHealthFromCursorWithoutWrites(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL sync health',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_FAILED,
            last_successful_sync_at=datetime(2026, 8, 19, 1, 2, tzinfo=timezone.utc),
            last_jira_updated_cutoff=datetime(2026, 8, 19, 3, 4, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
            latest_reliable_bucket_end=datetime(2026, 8, 9, tzinfo=timezone.utc).date(),
            changelog_coverage_status='partial',
            materialized_config_version_hash='old-hash',
            last_error='Jira timeout',
        )
        before_counts = self._counts()

        # When
        result = jira_sync_api.list_sync_health()

        # Then
        self.assertEqual(before_counts, self._counts())
        self.assertEqual(1, len(result))
        health = result[0]
        self.assertEqual(scope.id, health.scope_id)
        self.assertEqual('STDEL sync health', health.scope_name)
        self.assertEqual(JiraSyncCursor.STATUS_FAILED, health.status)
        self.assertEqual('2026-08-19T01:02:00+00:00', health.last_successful_sync_at)
        self.assertEqual('2026-08-19T03:04:00+00:00', health.last_jira_updated_cutoff)
        self.assertEqual('2026-08-01', health.earliest_reliable_bucket_start)
        self.assertEqual('2026-08-09', health.latest_reliable_bucket_end)
        self.assertEqual('partial', health.changelog_coverage_status)
        self.assertEqual('old-hash', health.materialized_config_version_hash)
        self.assertEqual(scope.config_version_hash, health.current_config_version_hash)
        self.assertEqual('Jira timeout', health.last_error)

    def _counts(self):
        return {
            'scopes': JiraScopeConfig.objects.count(),
            'cursors': JiraSyncCursor.objects.count(),
        }