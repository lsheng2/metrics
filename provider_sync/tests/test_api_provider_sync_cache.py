from datetime import date, datetime, timedelta, timezone as datetime_timezone

from django.test import TestCase, override_settings
from django.utils import timezone

from bug_metrics.app.api import ProviderChartAggregateQuery, bug_trend_api
from provider_sync.models import ProviderAggregateArtifact, ProviderSyncCursor
from provider_sync.app.api import (
    ProviderCacheIdentity,
    ProviderCacheSettings,
    ProviderFreshnessStatus,
    ProviderSyncCacheService,
)


class TestProviderSyncCache(TestCase):
    def test_shouldBuildProviderAgnosticCacheIdentityForDifferentNativeQueries(self):
        # Given
        jira_identity = ProviderCacheIdentity(
            provider_id='jira',
            profile_id='chiplet-2a-jira',
            source_query_ownership='metrics_managed_native_query',
            source_query_ref='',
            source_query_hash='jql-hash',
            tenant_or_space='131600',
            subject_or_item_type='Bug',
            field_set_hash='jira-fields',
            mapping_version_hash='mapping-v1',
            chart_id='open_bug_trend',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            fact_snapshot_id='',
        )
        hsdes_identity = ProviderCacheIdentity(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            source_query_ownership='provider_owned_saved_query',
            source_query_ref='15017652869',
            source_query_hash='saved-query-hash',
            tenant_or_space='ip_fw_sw_sensing.tenant',
            subject_or_item_type='ip_fw_sw_sensing.bug',
            field_set_hash='hsdes-fields',
            mapping_version_hash='mapping-v1',
            chart_id='open_bug_trend',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            fact_snapshot_id='',
        )

        # When
        jira_key = jira_identity.cache_key()
        hsdes_key = hsdes_identity.cache_key()

        # Then
        self.assertEqual(jira_key, jira_identity.cache_key())
        self.assertEqual(hsdes_key, hsdes_identity.cache_key())
        self.assertNotEqual(jira_key, hsdes_key)
        self.assertNotIn('project = "131600"', jira_key)
        self.assertNotIn('HSD_type', hsdes_key)

    def test_shouldUseGenericCacheSettingsByDefaultAndProviderOverrideWhenConfigured(self):
        # Given
        with override_settings(
            METRICS_PROVIDER_CACHE_ENABLED=True,
            METRICS_PROVIDER_CACHE_TTL_SECONDS=900,
            METRICS_PROVIDER_METADATA_CACHE_SECONDS=300,
            METRICS_PROVIDER_SYNC_STALE_AFTER_SECONDS=1800,
            METRICS_PROVIDER_CACHE_OVERRIDES={
                'hsdes': {
                    'cache_enabled': False,
                    'cache_ttl_seconds': 60,
                },
            },
        ):
            # When
            generic_settings = ProviderCacheSettings.for_provider('jira')
            hsdes_settings = ProviderCacheSettings.for_provider('hsdes')

        # Then
        self.assertTrue(generic_settings.cache_enabled)
        self.assertEqual(900, generic_settings.cache_ttl_seconds)
        self.assertEqual(300, generic_settings.metadata_cache_seconds)
        self.assertEqual(1800, generic_settings.sync_stale_after_seconds)
        self.assertFalse(hsdes_settings.cache_enabled)
        self.assertEqual(60, hsdes_settings.cache_ttl_seconds)
        self.assertEqual(300, hsdes_settings.metadata_cache_seconds)

    def test_shouldPersistProviderSnapshotFactsAndAggregateArtifactWithFreshness(self):
        # Given
        service = ProviderSyncCacheService()
        source_query = {
            'ownership_type': 'provider_owned_saved_query',
            'source_query_ref': '15017652869',
            'source_query_hash': 'source-hash',
        }
        facts = [{
            'provider_id': 'hsdes',
            'profile_id': 'nvu-ttl-hsdes',
            'source_item_id': '16000000001',
            'source_item_revision': '1',
            'canonical_fields': {'source_item_type': 'bug'},
            'project_fields': {'team_found': 'fwsw'},
            'field_values': {'HSD_type': 'bug'},
            'provider_fields': {'id': '16000000001', 'rev': '1'},
            'mapping_version': 1,
        }]

        # When
        snapshot = service.materialize_snapshot(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            source_query=source_query,
            field_set_hash='field-hash',
            mapping_version_hash='mapping-hash',
            facts=facts,
            raw_payload={'total': 1},
            freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
        )
        service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[{'metric_id': 'component_bug_count', 'value': 1}],
            grafana_rows=[{'provider_id': 'hsdes', 'profile_id': 'nvu-ttl-hsdes', 'component_bug_count': 1}],
            source_population=source_query,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )

        # Then
        latest_snapshot = service.latest_successful_snapshot('hsdes', 'nvu-ttl-hsdes')
        latest_artifact = service.latest_aggregate_artifact('hsdes', 'nvu-ttl-hsdes', 'component_bug', 1, '26WW32', '26WW32')
        self.assertEqual(snapshot.id, latest_snapshot.id)
        self.assertEqual(1, latest_snapshot.facts.count())
        self.assertEqual(ProviderFreshnessStatus.LIVE_SYNCED, latest_snapshot.freshness_status)
        self.assertEqual(ProviderFreshnessStatus.LIVE_SYNCED, latest_artifact.run_metadata_json['freshness_status'])
        self.assertEqual(1, latest_artifact.grafana_rows_json[0]['component_bug_count'])

    def test_shouldStoreWorkWeekAggregateArtifactWithNormalizedRangeIdentity(self):
        # Given
        service = ProviderSyncCacheService()
        snapshot = self._live_snapshot(service)

        # When
        artifact = service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{'component_bug_count': 7}],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )

        # Then
        self.assertEqual('ww', artifact.range_mode)
        self.assertEqual('2026-08-03', artifact.range_start)
        self.assertEqual('2026-08-09', artifact.range_end)
        self.assertEqual('week', artifact.range_grain)
        self.assertEqual('26WW32', artifact.range_label_start)
        self.assertEqual('26WW32', artifact.range_label_end)

    def test_shouldNotReuseWorkWeekArtifactWhenDateModeUsesSameLegacyWorkWeekLabels(self):
        # Given
        service = ProviderSyncCacheService()
        snapshot = self._live_snapshot(service)
        workweek_artifact = service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='open_bug_trend',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{'bucket_start': '2026-08-03', 'all_open_bugs': 3}],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )
        date_artifact = service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='open_bug_trend',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{'bucket_start': '2026-08-10', 'all_open_bugs': 5}],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
            range_mode='date',
            range_start='2026-08-10',
            range_end='2026-08-16',
            range_grain='day',
            range_label_start='2026-08-10',
            range_label_end='2026-08-16',
        )

        # When
        workweek_result = service.latest_aggregate_artifact(
            'hsdes',
            'nvu-ttl-hsdes',
            'open_bug_trend',
            1,
            '26WW32',
            '26WW32',
        )
        date_result = service.latest_aggregate_artifact(
            'hsdes',
            'nvu-ttl-hsdes',
            'open_bug_trend',
            1,
            '26WW32',
            '26WW32',
            range_mode='date',
            range_start='2026-08-10',
            range_end='2026-08-16',
        )

        # Then
        self.assertEqual(workweek_artifact.id, workweek_result.id)
        self.assertEqual(date_artifact.id, date_result.id)
        self.assertNotEqual(workweek_artifact.cache_identity_hash, date_artifact.cache_identity_hash)

    def test_shouldFindLegacyWorkWeekArtifactWhenNewRangeFieldsAreBlank(self):
        # Given
        service = ProviderSyncCacheService()
        snapshot = self._live_snapshot(service)
        artifact = service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{'component_bug_count': 7}],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )
        ProviderAggregateArtifact.objects.filter(id=artifact.id).update(
            range_mode='',
            range_start='',
            range_end='',
            range_grain='',
            range_label_start='',
            range_label_end='',
        )

        # When
        result = service.latest_aggregate_artifact(
            'hsdes',
            'nvu-ttl-hsdes',
            'component_bug',
            1,
            '26WW32',
            '26WW32',
        )

        # Then
        self.assertEqual(artifact.id, result.id)

    def test_shouldExposeProviderNeutralFreshnessStates(self):
        # Given / When / Then
        self.assertEqual('live_synced', ProviderFreshnessStatus.LIVE_SYNCED)
        self.assertEqual('seeded_preview', ProviderFreshnessStatus.SEEDED_PREVIEW)
        self.assertEqual('stale', ProviderFreshnessStatus.STALE)
        self.assertEqual('unavailable', ProviderFreshnessStatus.UNAVAILABLE)
        self.assertEqual('configuration_required', ProviderFreshnessStatus.CONFIGURATION_REQUIRED)
        self.assertEqual('running', ProviderFreshnessStatus.RUNNING)
        self.assertEqual('failed', ProviderFreshnessStatus.FAILED)

    def test_shouldReturnFreshAggregateArtifactWithinTtl(self):
        # Given
        service = ProviderSyncCacheService()
        snapshot = self._live_snapshot(service)
        artifact = service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{'component_bug_count': 7}],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )
        ProviderAggregateArtifact = artifact.__class__
        ProviderAggregateArtifact.objects.filter(id=artifact.id).update(
            created_at=datetime(2026, 8, 30, 1, 0, tzinfo=datetime_timezone.utc)
        )

        # When
        with override_settings(METRICS_PROVIDER_CACHE_TTL_SECONDS=900):
            result = service.cached_aggregate_artifact(
                provider_id='hsdes',
                profile_id='nvu-ttl-hsdes',
                chart_id='component_bug',
                chart_version=1,
                begin_ww='26WW32',
                end_ww='26WW32',
                now=datetime(2026, 8, 30, 1, 5, tzinfo=datetime_timezone.utc),
            )

        # Then
        self.assertEqual(ProviderFreshnessStatus.LIVE_SYNCED, result.freshness_status)
        self.assertEqual(artifact.id, result.artifact.id)
        self.assertEqual(300, result.cache_age_seconds)

    def test_shouldReturnStaleAggregateArtifactAfterTtlWithoutDeletingRows(self):
        # Given
        service = ProviderSyncCacheService()
        snapshot = self._live_snapshot(service)
        artifact = service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{'component_bug_count': 7}],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )
        artifact.__class__.objects.filter(id=artifact.id).update(
            created_at=datetime(2026, 8, 30, 1, 0, tzinfo=datetime_timezone.utc)
        )

        # When
        with override_settings(METRICS_PROVIDER_CACHE_TTL_SECONDS=60):
            result = service.cached_aggregate_artifact(
                provider_id='hsdes',
                profile_id='nvu-ttl-hsdes',
                chart_id='component_bug',
                chart_version=1,
                begin_ww='26WW32',
                end_ww='26WW32',
                now=datetime(2026, 8, 30, 1, 5, tzinfo=datetime_timezone.utc),
            )

        # Then
        self.assertEqual(ProviderFreshnessStatus.STALE, result.freshness_status)
        self.assertEqual('cache_ttl_expired', result.reason)
        self.assertEqual([{'component_bug_count': 7}], result.artifact.grafana_rows_json)

    def test_shouldReturnUnavailableWhenNoAggregateArtifactExists(self):
        # Given
        service = ProviderSyncCacheService()

        # When
        result = service.cached_aggregate_artifact(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
        )

        # Then
        self.assertEqual(ProviderFreshnessStatus.UNAVAILABLE, result.freshness_status)
        self.assertIsNone(result.artifact)

    def test_shouldBypassCacheWhenDisabledOrForcedRefresh(self):
        # Given
        service = ProviderSyncCacheService()

        # When / Then
        with override_settings(METRICS_PROVIDER_CACHE_ENABLED=False):
            self.assertTrue(service.should_bypass_cache('hsdes'))
        with override_settings(METRICS_PROVIDER_CACHE_ENABLED=True):
            self.assertTrue(service.should_bypass_cache('hsdes', force_refresh=True))
            self.assertFalse(service.should_bypass_cache('hsdes', force_refresh=False))

    def test_shouldAllowOnlyOneRefreshOwnerForSameProviderProfile(self):
        # Given
        service = ProviderSyncCacheService()

        # When
        first = service.try_start_refresh('hsdes', 'nvu-ttl-hsdes', '15017652869')
        second = service.try_start_refresh('hsdes', 'nvu-ttl-hsdes', '15017652869')

        # Then
        self.assertTrue(first.acquired)
        self.assertFalse(second.acquired)
        self.assertEqual(ProviderFreshnessStatus.RUNNING, second.status)
        self.assertEqual(ProviderSyncCursor.STATUS_RUNNING, ProviderSyncCursor.objects.get(provider_id='hsdes', profile_id='nvu-ttl-hsdes').status)

    def test_shouldPreferLiveHsdesAggregateArtifactBeforeSeedPreview(self):
        # Given
        service = ProviderSyncCacheService()
        source_query = {
            'ownership_type': 'provider_owned_saved_query',
            'source_query_ref': '15017652869',
            'source_query_hash': 'source-hash',
        }
        snapshot = service.materialize_snapshot(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            source_query=source_query,
            field_set_hash='field-hash',
            mapping_version_hash='mapping-hash',
            facts=[],
            raw_payload={'total': 0},
            freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
            completed_at=timezone.now(),
        )
        service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[{'metric_id': 'component_bug_count', 'value': 99}],
            grafana_rows=[{
                'provider_id': 'hsdes',
                'profile_id': 'nvu-ttl-hsdes',
                'component_bug_count': 99,
                'bucket_label': '26WW32',
            }],
            source_population=source_query,
            run_metadata={
                'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED,
                'source_coverage_start': date(2026, 8, 3).isoformat(),
                'source_coverage_end': date(2026, 8, 9).isoformat(),
            },
        )

        # When
        result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('hsdes', 'nvu-ttl-hsdes', '26WW32', '26WW32', 'component_bug')
        )

        # Then
        self.assertEqual('supported', result.status)
        self.assertEqual(ProviderFreshnessStatus.LIVE_SYNCED, result.run_metadata['freshness_status'])
        self.assertEqual(99, result.grafana_rows[0]['component_bug_count'])

    def _live_snapshot(self, service):
        return service.materialize_snapshot(
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
