from django.test import TestCase

from bug_metrics.app.api import bug_trend_api


class TestProviderCorrelation(TestCase):
    def test_shouldGenerateCorrelationCandidateWithEvidenceAndConfidence(self):
        # Given
        jira_fact = self._jira_fact('STDEL-1001')
        hsdes_fact = self._hsdes_fact('16000000001')

        # When
        candidates = bug_trend_api.generate_provider_correlation_candidates([jira_fact], [hsdes_fact])

        # Then
        candidate = candidates[0]
        self.assertEqual('candidate', candidate['state'])
        self.assertEqual('jira', candidate['source']['provider_id'])
        self.assertEqual('hsdes', candidate['target']['provider_id'])
        self.assertGreaterEqual(candidate['confidence'], 0.8)
        evidence_types = {evidence['type'] for evidence in candidate['evidence']}
        self.assertTrue({'explicit_link', 'title_fingerprint', 'component_overlap', 'release_overlap', 'owner_overlap', 'time_window'}.issubset(evidence_types))

    def test_shouldRecordCorrelationReviewStateWithoutMergingNativeTruth(self):
        # Given
        candidate = bug_trend_api.generate_provider_correlation_candidates([self._jira_fact('STDEL-1001')], [self._hsdes_fact('16000000001')])[0]

        # When
        artifact = bug_trend_api.review_provider_correlation(candidate, 'confirmed', 'local_operator')

        # Then
        self.assertEqual('confirmed', artifact['state'])
        self.assertEqual('Open', artifact['source']['native_fields']['status'])
        self.assertEqual('open', artifact['target']['native_fields']['status'])
        self.assertNotEqual(artifact['source']['native_fields'], artifact['target']['native_fields'])

    def test_shouldBuildProviderNamedCorrelationEvidenceRows(self):
        # Given
        confirmed = bug_trend_api.review_provider_correlation(
            bug_trend_api.generate_provider_correlation_candidates([self._jira_fact('STDEL-1001')], [self._hsdes_fact('16000000001')])[0],
            'confirmed',
            'local_operator',
        )

        # When
        view = bug_trend_api.get_provider_correlation_evidence_view([confirmed])

        # Then
        self.assertEqual({'jira', 'hsdes'}, {row['provider_id'] for row in view['rows']})
        self.assertEqual({'confirmed'}, {row['correlation_state'] for row in view['rows']})
        self.assertTrue(all(row['source_item_id'] for row in view['rows']))

    def test_shouldExplainCrossProviderRiskByCorrelationState(self):
        # Given
        candidate = bug_trend_api.generate_provider_correlation_candidates([self._jira_fact('STDEL-1001')], [self._hsdes_fact('16000000001')])[0]
        correlations = [
            bug_trend_api.review_provider_correlation(candidate, 'confirmed', 'local_operator'),
            bug_trend_api.review_provider_correlation(candidate, 'candidate', 'local_operator'),
            bug_trend_api.review_provider_correlation(candidate, 'rejected', 'local_operator'),
            bug_trend_api.review_provider_correlation(candidate, 'stale', 'local_operator'),
        ]

        # When
        explanation = bug_trend_api.explain_cross_provider_correlation_risk(correlations)

        # Then
        self.assertEqual({'confirmed', 'candidate', 'rejected', 'stale'}, set(explanation['state_counts'].keys()))
        self.assertIn('confirmed', explanation['answer'])
        self.assertIn('candidate', explanation['answer'])
        self.assertIn('rejected', explanation['answer'])
        self.assertIn('stale', explanation['answer'])

    def _jira_fact(self, source_item_id):
        return {
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'source_item_id': source_item_id,
            'canonical_fields': {
                'title': 'NVU firmware boot failure',
                'component_or_area': 'fwsw',
                'release_target': 'NVU-FW.trunk',
                'owner': 'alice',
                'created_at': '2026-08-03T08:00:00Z',
                'source_state': 'Open',
            },
            'native_fields': {
                'key': source_item_id,
                'status': 'Open',
                'priority': 'P2-High',
            },
        }

    def _hsdes_fact(self, source_item_id):
        return {
            'provider_id': 'hsdes',
            'profile_id': 'nvu-ttl-hsdes',
            'source_item_id': source_item_id,
            'canonical_fields': {
                'title': 'NVU firmware boot failure',
                'component_or_area': 'fwsw',
                'release_target': 'NVU-FW.trunk',
                'owner': 'alice',
                'created_at': '2026-08-05T08:00:00Z',
                'source_state': 'open',
            },
            'native_fields': {
                'id': source_item_id,
                'status': 'open',
                'exposure': 'high',
                'external_id': 'STDEL-1001',
            },
            'links': [{'target_id': 'STDEL-1001'}],
        }
