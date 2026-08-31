from django.test import TestCase

from bug_metrics.app.api import bug_trend_api


class TestHsdesProviderProfile(TestCase):
    def test_shouldResolveProviderReadinessFromProfileRegistryWhenProviderIsOmitted(self):
        # When
        hsdes_readiness = bug_trend_api.get_provider_profile_readiness('', 'nvu-ttl-hsdes')
        jira_readiness = bug_trend_api.get_provider_profile_readiness('', 'chiplet-2a-jira')

        # Then
        self.assertEqual('hsdes', hsdes_readiness['provider_id'])
        self.assertEqual('nvu-ttl-hsdes', hsdes_readiness['profile_id'])
        self.assertEqual('NVU', hsdes_readiness['scope_labels']['ip']['value'])
        self.assertEqual('jira', jira_readiness['provider_id'])
        self.assertEqual('chiplet-2a-jira', jira_readiness['profile_id'])
        self.assertEqual('chiplet_ip', jira_readiness['scope_labels']['ip']['value'])

    def test_shouldReturnStructuredUnsupportedReadinessForUnknownProfileWithoutDefaultFallback(self):
        # When
        readiness = bug_trend_api.get_provider_profile_readiness('', 'unknown-profile')

        # Then
        self.assertEqual('unsupported', readiness['status'])
        self.assertEqual('unknown-profile', readiness['profile_id'])
        self.assertEqual('', readiness['provider_id'])
        self.assertEqual('profile_not_found', readiness['blockers'][0]['code'])

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

    def test_shouldExposeRegistryDerivedReadinessMetadataForJiraAndHsdesProfiles(self):
        # When
        jira_readiness = bug_trend_api.get_provider_profile_readiness('', 'chiplet-2a-jira')
        hsdes_readiness = bug_trend_api.get_provider_profile_readiness('', 'nvu-ttl-hsdes')

        # Then
        jira_support = {item['chart_id']: item for item in jira_readiness['chart_support']}
        hsdes_support = {item['chart_id']: item for item in hsdes_readiness['chart_support']}
        self.assertEqual('metrics_managed_native_query', jira_readiness['source_population']['ownership_type'])
        self.assertEqual('provider_owned_saved_query', hsdes_readiness['source_population']['ownership_type'])
        self.assertEqual(jira_readiness['mapping_version_hash'], jira_readiness['source_population']['mapping_version_hash'])
        self.assertEqual(hsdes_readiness['mapping_version_hash'], hsdes_readiness['source_population']['mapping_version_hash'])
        self.assertEqual('ready', jira_readiness['freshness_status'])
        self.assertEqual('seeded_preview', hsdes_readiness['freshness_status'])
        self.assertEqual('supported', jira_support['open_bug_trend']['support_status'])
        self.assertEqual('supported', hsdes_support['open_bug_trend']['support_status'])
        self.assertEqual('deferred', jira_support['execution_statistics']['support_status'])
        self.assertEqual('deferred', hsdes_support['execution_statistics']['support_status'])

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
