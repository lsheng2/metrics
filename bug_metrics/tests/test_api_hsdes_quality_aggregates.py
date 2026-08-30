from django.test import TestCase

from bug_metrics.app.api import ProviderChartAggregateQuery, bug_trend_api


class TestHsdesQualityAggregates(TestCase):
    def test_shouldBuildHsdesComponentBugAggregateWithProviderProvenance(self):
        # Given
        facts = bug_trend_api.normalize_hsdes_search_page('nvu-ttl-hsdes', {
            'articles': [
                {'id': '16000000001', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'fwsw', 'submitted_date': '2026-08-04T08:00:00Z'}},
                {'id': '16000000002', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'fwsw', 'submitted_date': '2026-08-05T08:00:00Z'}},
                {'id': '16000000003', 'rev': '1', 'fieldValues': {'HSD_type': 'bug', 'component': 'media', 'submitted_date': '2026-08-05T08:00:00Z'}},
            ],
        })['facts']

        # When
        result = bug_trend_api.build_hsdes_quality_aggregate_artifact(
            ProviderChartAggregateQuery('hsdes', 'nvu-ttl-hsdes', '26WW32', '26WW32', 'component_bug'),
            facts,
        )

        # Then
        self.assertEqual('supported', result.status)
        self.assertEqual('hsdes', result.provider_id)
        self.assertEqual('15017652869', result.source_population['source_query_ref'])
        self.assertEqual('NVU', result.scope_labels['ip']['value'])
        self.assertEqual(2, self._row_value(result, 'component_bug_count', {'component': 'fwsw'}))
        self.assertEqual(1, self._row_value(result, 'component_bug_count', {'component': 'media'}))
        self.assertEqual('hsdes', result.grafana_rows[0]['provider_id'])
        self.assertIn('component_bug_count', result.grafana_rows[0])
        self.assertNotIn('hsdes_component_bug_count', result.grafana_rows[0])

    def _row_value(self, result, metric_id, dimensions):
        for row in result.rows:
            if row.metric_id == metric_id and all(row.dimensions.get(key) == value for key, value in dimensions.items()):
                return row.value
        return None
