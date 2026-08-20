from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig
from jira_sync.models import JiraSyncCursor


class TestDataHealthViews(TestCase):
    def test_shouldRenderReadOnlySyncAndCalculationHealth(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL data health',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        old_hash = scope.config_version_hash
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_FAILED,
            last_successful_sync_at=datetime(2026, 8, 19, 1, 2, tzinfo=timezone.utc),
            last_jira_updated_cutoff=datetime(2026, 8, 19, 3, 4, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=date(2026, 8, 1),
            latest_reliable_bucket_end=date(2026, 8, 9),
            changelog_coverage_status='partial',
            materialized_config_version_hash=old_hash,
            last_error='Jira timeout',
        )
        scope.fixed_status_values = ['Fixed']
        scope.save()
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=old_hash,
            source_coverage_start=date(2026, 8, 1),
            source_coverage_end=date(2026, 8, 31),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        before_counts = self._counts()

        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        self.assertEqual(before_counts, self._counts())
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Data Health', content)
        self.assertIn('STDEL data health', content)
        self.assertIn('Jira timeout', content)
        self.assertIn('partial', content)
        self.assertIn('stale_config', content)
        self.assertIn(str(run.id), content)
        self.assertNotIn('Recalculate now', content)
        self.assertNotIn('Sync now', content)

    def _counts(self):
        return {
            'scopes': JiraScopeConfig.objects.count(),
            'cursors': JiraSyncCursor.objects.count(),
            'runs': BugTrendCalculationRun.objects.count(),
        }