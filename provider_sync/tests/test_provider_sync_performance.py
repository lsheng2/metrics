import time

from django.conf import settings
from django.test import TestCase

from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService


class TestProviderSyncPerformance(TestCase):
    def test_shouldMaterializeLargeDeterministicProviderPayloadWithinDocumentedThreshold(self):
        # Given
        if not getattr(settings, 'METRICS_RUN_PROVIDER_PERF_TESTS', False):
            self.skipTest('Provider sync performance tests require METRICS_RUN_PROVIDER_PERF_TESTS=true.')
        service = ProviderSyncCacheService()
        thresholds = {
            10000: 15.0,
            50000: 75.0,
        }
        for fact_count, threshold_seconds in thresholds.items():
            with self.subTest(fact_count=fact_count):
                facts = [
                    {
                        'source_item_id': f'{fact_count}-{index}',
                        'source_item_revision': '1',
                        'canonical_fields': {'source_item_type': 'bug'},
                        'project_fields': {},
                        'field_values': {'HSD_type': 'bug'},
                        'provider_fields': {'id': f'{fact_count}-{index}', 'rev': '1'},
                        'mapping_version': 1,
                    }
                    for index in range(fact_count)
                ]

                # When
                started_at = time.perf_counter()
                snapshot = service.materialize_snapshot(
                    provider_id='fake',
                    profile_id=f'fake-profile-{fact_count}',
                    source_query={
                        'ownership_type': 'metrics_managed_native_query',
                        'source_query_ref': f'fake-query-{fact_count}',
                        'source_query_hash': f'fake-source-hash-{fact_count}',
                    },
                    field_set_hash='fake-field-set',
                    mapping_version_hash='fake-mapping',
                    facts=facts,
                    raw_payload={'total': len(facts)},
                    freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
                )
                elapsed_seconds = time.perf_counter() - started_at

                # Then
                self.assertEqual(fact_count, snapshot.record_count)
                self.assertLess(elapsed_seconds, threshold_seconds)
