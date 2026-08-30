from django.test import TestCase

from bug_metrics.app.api import bug_trend_api


class TestHsdesProviderProfile(TestCase):
    def test_shouldExposeHsdesApiReviewWithExplicitBlockers(self):
        # When
        readiness = bug_trend_api.get_provider_profile_readiness('hsdes', 'nvu-ttl-hsdes')

        # Then
        self.assertEqual('seeded_preview', readiness['status'])
        self.assertEqual('hsdes', readiness['provider_id'])
        self.assertEqual('nvu-ttl-hsdes', readiness['profile_id'])
        self.assertEqual('id', readiness['api_contract']['identity_fields']['article_id'])
        self.assertEqual('rev', readiness['api_contract']['identity_fields']['revision'])
        self.assertEqual('/rest/article/{id}', readiness['api_contract']['detail']['endpoint'])
        self.assertEqual('/rest/query/execution/eql', readiness['api_contract']['search']['endpoint'])
        self.assertEqual('start_at', readiness['api_contract']['pagination']['offset_parameter'])
        self.assertEqual('max_results', readiness['api_contract']['pagination']['limit_parameter'])
        self.assertEqual('fieldValues', readiness['api_contract']['payload']['field_values'])
        blocker_codes = {blocker['code'] for blocker in readiness['blockers']}
        self.assertTrue({
            'hsdes_service_account_permission_not_runtime_verified',
            'hsdes_lookup_group_ids_not_runtime_verified',
            'hsdes_chart_field_bindings_not_runtime_verified',
        }.issubset(blocker_codes))

    def test_shouldExposeHsdesSeededQualityBindingsWhileLiveSyncRemainsConfigurationRequired(self):
        # When
        readiness = bug_trend_api.get_provider_profile_readiness('hsdes', 'nvu-ttl-hsdes')

        # Then
        bindings_by_chart = {binding['chart_id']: binding for binding in readiness['chart_bindings']}
        self.assertEqual('supported_from_seed_facts', bindings_by_chart['open_bug_trend']['support_status'])
        self.assertEqual('supported_from_seed_facts', bindings_by_chart['component_bug']['support_status'])
        self.assertEqual('deferred', bindings_by_chart['execution_statistics']['support_status'])
        self.assertIn('submitted_date', bindings_by_chart['open_bug_trend']['candidate_native_fields'])
        self.assertIn('component', bindings_by_chart['component_bug']['candidate_native_fields'])

    def test_shouldDetectHsdesSavedQueryDriftBeforeAggregateGeneration(self):
        # When
        result = bug_trend_api.validate_provider_profile_drift('hsdes', 'nvu-ttl-hsdes', {
            'source_query_ref': '15017652869',
            'tenant_or_site': 'ip_fw_sw_sensing.tenant',
            'subject_or_issue_type': 'ip_fw_sw_sensing.feature',
            'criteria_snapshot': 'id > 0; family in NVU-FW; HSD_type in feature',
            'field_set': ['id', 'fieldValues'],
        })

        # Then
        self.assertEqual('drifted', result['status'])
        self.assertFalse(result['aggregate_generation_allowed'])
        self.assertEqual({
            'subject_or_issue_type',
            'criteria_snapshot',
            'field_set',
        }, {item['field'] for item in result['drift_items']})
        self.assertIn('review the HSD-ES profile before aggregate generation', result['reason'])

    def test_shouldExposeHsdesCapabilityManifestWithUnsupportedWriteAndPlanningReasons(self):
        # When
        manifest = bug_trend_api.get_provider_capability_manifest('hsdes', 'nvu-ttl-hsdes')

        # Then
        capabilities = {capability['capability_id']: capability for capability in manifest['capabilities']}
        self.assertEqual('hsdes', manifest['provider_id'])
        self.assertEqual('nvu-ttl-hsdes', manifest['profile_id'])
        self.assertEqual('configuration_required', capabilities['article_search']['status'])
        self.assertEqual('configuration_required', capabilities['article_detail']['status'])
        self.assertEqual('seeded_preview', capabilities['quality_facts']['status'])
        self.assertEqual('unsupported', capabilities['planning_actions']['status'])
        self.assertEqual('unsupported', capabilities['write_actions']['status'])
        self.assertIn('Jira-owned planning concepts', capabilities['planning_actions']['reason'])
        self.assertIn('HSD-ES writes remain disabled', capabilities['write_actions']['reason'])
