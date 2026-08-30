from datetime import date, datetime, timezone

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig
from jira_sync.models import JiraSyncCursor
from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService


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

    def test_shouldRenderProviderSyncCacheHealthWithoutSecrets(self):
        # Given
        cache_service = ProviderSyncCacheService()
        cache_service.materialize_snapshot(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            source_query={
                'ownership_type': 'provider_owned_saved_query',
                'source_query_ref': '15017652869',
                'source_query_hash': 'source-hash',
            },
            field_set_hash='field-hash',
            mapping_version_hash='mapping-hash',
            facts=[],
            raw_payload={'total': 0},
            freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
        )
        cache_service.record_failure(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            error_category='auth_failed',
            message='Bearer secret-token failed',
        )

        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Provider Sync Cache Health', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('auth_failed', content)
        self.assertIn('Bearer [redacted]', content)
        self.assertNotIn('secret-token', content)

    def _counts(self):
        return {
            'scopes': JiraScopeConfig.objects.count(),
            'cursors': JiraSyncCursor.objects.count(),
            'runs': BugTrendCalculationRun.objects.count(),
        }
