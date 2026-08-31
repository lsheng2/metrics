import hashlib

from django.test import SimpleTestCase

from bug_metrics.app.api.provider_profile_registry import ChartRecipeRequirement, ProjectProviderProfileRegistry


class TestProjectProviderProfileRegistry(SimpleTestCase):
    def test_shouldLoadJiraProfileFromVersionedConfigWithProviderFactsAndBindings(self):
        # Given
        registry = ProjectProviderProfileRegistry.load_default()

        # When
        profile = registry.get_profile('chiplet-2a-jira')

        # Then
        self.assertEqual('jira', profile.provider_id)
        self.assertEqual('chiplet-2a-jira', profile.profile_id)
        self.assertEqual(1, profile.mapping_version)
        self.assertEqual(hashlib.sha256('project = "131600" AND component = "team_int_qemu"'.encode('utf-8')).hexdigest(), profile.source_population['source_query_hash'])
        self.assertEqual('metrics_managed_native_query', profile.source_population['ownership_type'])
        self.assertEqual('chiplet_ip', profile.scope_labels['ip'])
        self.assertEqual('customfield:project_literal:2a', profile.field_bindings['milestone']['native_field'])
        self.assertEqual('supported', profile.chart_bindings['open_bug_trend']['support_status'])
        self.assertIn('submitted_date', profile.chart_bindings['open_bug_trend']['required_canonical_fields'])
        self.assertTrue(profile.mapping_version_hash)

    def test_shouldLoadHsdesProfileFromVersionedConfigWithSavedQueryPopulation(self):
        # Given
        registry = ProjectProviderProfileRegistry.load_default()

        # When
        profile = registry.get_profile('nvu-ttl-hsdes')

        # Then
        self.assertEqual('hsdes', profile.provider_id)
        self.assertEqual('provider_owned_saved_query', profile.source_population['ownership_type'])
        self.assertEqual('15017652869', profile.source_population['source_query_ref'])
        self.assertEqual('ip_fw_sw_sensing.tenant', profile.source_population['tenant_or_site'])
        self.assertEqual('ip_fw_sw_sensing.bug', profile.source_population['subject_or_issue_type'])
        self.assertEqual('NVU', profile.scope_labels['ip'])
        self.assertEqual('HSD_type', profile.field_bindings['item_type']['native_field'])
        self.assertEqual('supported_from_seed_facts', profile.chart_bindings['component_bug']['support_status'])
        self.assertIn('component', profile.chart_bindings['component_bug']['candidate_native_fields'])

    def test_shouldReturnUnavailableResolutionForDisabledProfileWithoutFallback(self):
        # Given
        registry = ProjectProviderProfileRegistry.from_records([
            {
                'profile_id': 'disabled-demo',
                'provider_id': 'jira',
                'display_name': 'Disabled Demo',
                'enabled': False,
                'mapping_version': 1,
                'source_population': {'ownership_type': 'metrics_managed_native_query'},
                'scope_labels': {'ip': 'demo'},
                'field_bindings': {},
                'chart_bindings': {},
            },
        ])

        # When
        resolution = registry.resolve_profile('disabled-demo')
        missing_resolution = registry.resolve_profile('missing-demo')

        # Then
        self.assertEqual('unavailable', resolution.status)
        self.assertEqual('profile_disabled', resolution.blockers[0]['code'])
        self.assertIsNone(resolution.profile)
        self.assertEqual('unsupported', missing_resolution.status)
        self.assertEqual('profile_not_found', missing_resolution.blockers[0]['code'])

    def test_shouldResolveSupportedChartFromProviderCapabilityAndFieldBindings(self):
        # Given
        registry = ProjectProviderProfileRegistry.load_default()

        # When
        support = registry.resolve_chart_support(
            'chiplet-2a-jira',
            ChartRecipeRequirement(
                chart_id='open_bug_trend',
                chart_version=1,
                required_canonical_fields=['submitted_date', 'status', 'severity'],
                provider_capability='quality_facts',
                evidence_capability='bucket_series',
            ),
            {'quality_facts': 'supported'},
        )

        # Then
        self.assertEqual('supported', support.status)
        self.assertEqual([], support.missing_canonical_fields)
        self.assertEqual('bucket_series', support.evidence_capability)
        self.assertEqual(['submitted_date', 'status', 'severity'], support.required_canonical_fields)

    def test_shouldResolveDeferredUnsupportedAndConfigurationRequiredChartStates(self):
        # Given
        registry = ProjectProviderProfileRegistry.load_default()

        # When
        deferred = registry.resolve_chart_support(
            'chiplet-2a-jira',
            ChartRecipeRequirement('execution_statistics', 1, [], 'quality_facts', 'summary_only'),
            {'quality_facts': 'supported'},
        )
        unsupported = registry.resolve_chart_support(
            'chiplet-2a-jira',
            ChartRecipeRequirement('unknown_chart', 1, ['submitted_date'], 'quality_facts', 'summary_only'),
            {'quality_facts': 'supported'},
        )
        missing_fields = registry.resolve_chart_support(
            'chiplet-2a-jira',
            ChartRecipeRequirement('open_bug_trend', 1, ['submitted_date', 'escaped_classification'], 'quality_facts', 'bucket_series'),
            {'quality_facts': 'supported'},
        )
        missing_capability = registry.resolve_chart_support(
            'chiplet-2a-jira',
            ChartRecipeRequirement('open_bug_trend', 1, ['submitted_date'], 'quality_facts', 'bucket_series'),
            {'quality_facts': 'configuration_required'},
        )

        # Then
        self.assertEqual('deferred', deferred.status)
        self.assertEqual('unsupported', unsupported.status)
        self.assertEqual('configuration_required', missing_fields.status)
        self.assertEqual(['escaped_classification'], missing_fields.missing_canonical_fields)
        self.assertEqual('configuration_required', missing_capability.status)
        self.assertEqual('provider_capability_not_ready', missing_capability.blockers[0]['code'])
