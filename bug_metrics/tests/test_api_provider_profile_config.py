from unittest.mock import patch

from django.test import TestCase

from bug_metrics.app.api.provider_profile_connection_test import ProviderProfileConnectionTestService
from bug_metrics.app.api.provider_profile_config import ProviderProfileConfigService, provider_profile_config_from_dict, provider_profile_config_from_post
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.models import BugTrendAuditEvent, BugTrendScopeProviderBinding, JiraScopeConfig, ProviderProfileConfig


class TestProviderProfileConfigService(TestCase):
    def test_shouldCreateBlankDraftForNewProviderProfile(self):
        # When
        config = ProviderProfileConfigService().new_provider_profile_config('hsdes')

        # Then
        self.assertIsNone(config.id)
        self.assertEqual('', config.profile_id)
        self.assertEqual('', config.display_name)
        self.assertEqual('hsdes', config.provider_id)
        self.assertEqual('', config.connection_settings['base_url'])
        self.assertEqual('', config.connection_settings['auth_mode'])
        self.assertEqual('', config.connection_settings['credential_ref'])
        self.assertEqual('provider_owned_saved_query', config.source_population['ownership_type'])

    @patch('bug_metrics.app.api.provider_profile_connection_test.create_jira_client')
    def test_shouldTestJiraProfileConnectionThroughServerInfo(self, create_jira_client):
        # Given
        create_jira_client.return_value.get_server_info.return_value = {
            'serverTitle': 'Jira Test',
            'version': '10.0',
        }
        config = provider_profile_config_from_dict({
            'profile_id': 'jira-connection-test',
            'provider_id': 'jira',
            'display_name': 'Jira Connection Test',
            'connection_settings': {
                'base_url': 'https://jira.profile.example',
                'auth_mode': 'server_pat',
                'credential_ref': 'profile:local',
                'credentials': {'api_token': 'secret-token'},
            },
        })

        # When
        result = ProviderProfileConnectionTestService().test_connection(config)

        # Then
        self.assertEqual('success', result.status)
        self.assertEqual('Jira Test', result.details['server_title'])
        self.assertEqual('https://jira.profile.example', create_jira_client.call_args.args[1]['base_url'])

    def test_shouldAskForHsdesProbeSourceBeforeSavedQueryConnectionTest(self):
        # Given
        config = provider_profile_config_from_dict({
            'profile_id': 'hsdes-connection-test',
            'provider_id': 'hsdes',
            'display_name': 'HSD-ES Connection Test',
            'connection_settings': {
                'base_url': 'https://hsdes.example/rest',
                'auth_mode': 'kerberos',
                'credential_ref': 'profile:local',
            },
        })

        # When
        result = ProviderProfileConnectionTestService().test_connection(config)

        # Then
        self.assertEqual('configuration_required', result.status)
        self.assertIn('saved query id', result.summary)
        self.assertIn('HSD-ES Connection Probe', result.summary)
        self.assertEqual('HSD-ES saved query id, Tenant, Subject', result.details['missing_fields'])
        self.assertNotIn('saved_query_id', str(result.details))

    def test_shouldLoadManagedProfileThroughRegistryContract(self):
        # Given
        service = ProviderProfileConfigService()
        service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'managed-jira',
            'provider_id': 'jira',
            'display_name': 'Managed Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'source_population': {'native_query_text': 'project = MANAGED'},
            'scope_labels': {'ip': 'managed'},
            'field_bindings': {'severity': {'native_field': 'priority'}},
            'value_mappings': {'bug_type_values': ['Bug']},
            'chart_bindings': {'open_bug_trend': {'support_status': 'supported'}},
            'sync_policy': {'live_sync': 'supported'},
            'readiness_policy': {'ready_status': 'ready'},
        }))

        # When
        profile = ProjectProviderProfileRegistry.load_default().get_profile('managed-jira')

        # Then
        self.assertEqual('managed-jira', profile.profile_id)
        self.assertEqual('managed', profile.source_kind)
        self.assertEqual('priority', profile.field_bindings['severity']['native_field'])
        self.assertEqual('settings:METRICS_JIRA_SERVER_URL', profile.connection_settings['base_url'])
        self.assertEqual('settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN', profile.connection_settings['credential_ref'])

    def test_shouldStoreProviderOnboardingCredentialsInProfileAndRedactExports(self):
        # Given
        service = ProviderProfileConfigService()
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'onboarded-hsdes',
            'provider_id': 'hsdes',
            'display_name': 'Onboarded HSD-ES',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'connection_settings': {
                'base_url': 'settings:METRICS_HSDES_API_BASE_URL',
                'auth_mode': 'kerberos',
                'credential_ref': 'settings:METRICS_HSDES_*',
                'credential_storage': 'profile_local',
                'onboarding_status': 'ready',
                'credentials': {
                    'username': 'hsdes-user',
                    'password': 'must-not-export',
                    'token': 'also-must-not-export',
                },
            },
            'source_population': {'ownership_type': 'provider_owned_saved_query'},
            'field_bindings': {'status': {'native_field': 'status'}},
            'chart_bindings': {'open_bug_trend': {'support_status': 'supported_from_seed_facts'}},
        }))

        # When
        profile = ProjectProviderProfileRegistry.load_default().get_profile(saved.profile_id)
        package = service.export_provider_profile_package(saved.profile_id)

        # Then
        self.assertEqual('ready', profile.connection_settings['onboarding_status'])
        self.assertEqual('hsdes-user', profile.connection_settings['credentials']['username'])
        self.assertEqual('settings:METRICS_HSDES_*', package['profile']['connection_settings']['credential_ref'])
        self.assertNotIn('credentials', package['profile']['connection_settings'])
        self.assertNotIn('must-not-export', str(package))
        self.assertNotIn('also-must-not-export', str(package))
        self.assertIn('credentials', package['excludes'])

    def test_shouldPreserveExistingProfileCredentialsWhenEditingNonSecretConnectionFields(self):
        # Given
        service = ProviderProfileConfigService()
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'credential-preserve-jira',
            'provider_id': 'jira',
            'display_name': 'Credential Preserve Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'connection_settings': {
                'auth_mode': 'server_pat',
                'credentials': {
                    'email': 'owner@example.com',
                    'api_token': 'saved-api-token',
                },
            },
            'source_population': {},
            'field_bindings': {},
            'chart_bindings': {},
        }))

        # When
        updated = service.save_provider_profile_config(provider_profile_config_from_dict({
            'id': saved.id,
            'profile_id': 'credential-preserve-jira',
            'provider_id': 'jira',
            'display_name': 'Credential Preserve Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'connection_settings': {
                'auth_mode': 'server_pat',
                'onboarding_status': 'ready',
            },
            'source_population': {},
            'field_bindings': {},
            'chart_bindings': {},
        }))

        # Then
        self.assertEqual('ready', updated.connection_settings['onboarding_status'])
        self.assertEqual('saved-api-token', updated.connection_settings['credentials']['api_token'])

    def test_shouldPreserveExistingTokenWhenPostedValueIsMaskedStars(self):
        # Given
        service = ProviderProfileConfigService()
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'masked-token-jira',
            'provider_id': 'jira',
            'display_name': 'Masked Token Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'connection_settings': {
                'base_url': 'https://jira.example',
                'auth_mode': 'server_pat',
                'credential_ref': 'profile:local',
                'credentials': {
                    'api_token': 'real-api-token',
                    'token': 'real-bearer-token',
                },
            },
            'source_population': {},
            'field_bindings': {},
            'chart_bindings': {},
        }))

        # When
        updated = service.save_provider_profile_config(provider_profile_config_from_post({
            'id': str(saved.id),
            'profile_id': 'masked-token-jira',
            'provider_id': 'jira',
            'display_name': 'Masked Token Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'mapping_version': '1',
            'connection_settings': '{}',
            'connection_base_url': 'https://jira.example',
            'connection_auth_mode': 'server_pat',
            'credential_ref': 'profile:local',
            'connection_api_token': '********',
            'connection_token': '********',
            'source_population': '{}',
            'scope_labels': '{}',
            'field_bindings': '{}',
            'value_mappings': '{}',
            'chart_bindings': '{}',
            'sync_policy': '{}',
            'readiness_policy': '{}',
        }))

        # Then
        self.assertEqual('real-api-token', updated.connection_settings['credentials']['api_token'])
        self.assertEqual('real-bearer-token', updated.connection_settings['credentials']['token'])

    def test_shouldAcceptOnlyActiveAuthMethodCredentialsFromPost(self):
        # When
        config = provider_profile_config_from_post({
            'id': '',
            'profile_id': 'posted-jira-auth-method',
            'provider_id': 'jira',
            'display_name': 'Posted Jira Auth Method',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'mapping_version': '1',
            'connection_settings': '{}',
            'connection_base_url': 'https://jira.example',
            'connection_auth_mode': 'server_pat',
            'credential_ref': 'profile:local',
            'onboarding_status': 'ready',
            'connection_email': 'unused@example.com',
            'connection_api_token': 'active-api-token',
            'connection_password': 'unused-password',
            'connection_token': 'unused-bearer-token',
            'source_population': '{}',
            'scope_labels': '{}',
            'field_bindings': '{}',
            'value_mappings': '{}',
            'chart_bindings': '{}',
            'sync_policy': '{}',
            'readiness_policy': '{}',
        })

        # Then
        self.assertEqual({'api_token': 'active-api-token'}, config.connection_settings['credentials'])
        self.assertEqual('deployment_configured', config.connection_settings['onboarding_status'])

    def test_shouldMapHsdesProbeFieldsFromPostIntoSourcePopulation(self):
        # When
        config = provider_profile_config_from_post({
            'id': '',
            'profile_id': 'posted-hsdes-probe',
            'provider_id': 'hsdes',
            'display_name': 'Posted HSD-ES Probe',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'mapping_version': '1',
            'connection_settings': '{}',
            'connection_base_url': 'https://hsdes.example/rest',
            'connection_auth_mode': 'kerberos',
            'credential_ref': 'profile:local',
            'hsdes_saved_query_id': '15017652869',
            'hsdes_tenant': 'ip_fw_sw_sensing.tenant',
            'hsdes_subject': 'ip_fw_sw_sensing.bug',
            'source_population': '{}',
            'scope_labels': '{}',
            'field_bindings': '{}',
            'value_mappings': '{}',
            'chart_bindings': '{}',
            'sync_policy': '{}',
            'readiness_policy': '{}',
        })

        # Then
        self.assertEqual('15017652869', config.source_population['source_query_ref'])
        self.assertEqual('ip_fw_sw_sensing.tenant', config.source_population['tenant_or_site'])
        self.assertEqual('ip_fw_sw_sensing.bug', config.source_population['subject_or_issue_type'])
        self.assertEqual('provider_owned_saved_query', config.source_population['ownership_type'])

    def test_shouldEnableProviderOnboardingProfileWithoutAdvancedMappings(self):
        # Given
        service = ProviderProfileConfigService()

        # When
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'connection-only-jira',
            'provider_id': 'jira',
            'display_name': 'Connection Only Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'connection_settings': {
                'base_url': 'https://jira.profile.example',
                'auth_mode': 'server_pat',
                'credential_ref': 'profile:local',
                'onboarding_status': 'ready',
            },
            'source_population': {},
            'field_bindings': {},
            'chart_bindings': {},
        }))

        # Then
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_ENABLED, saved.lifecycle_state)

    def test_shouldEditExistingManagedProfileWithoutCreatingDuplicate(self):
        # Given
        service = ProviderProfileConfigService()
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'editable-jira',
            'provider_id': 'jira',
            'display_name': 'Editable Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'source_population': {'native_query_text': 'project = BEFORE'},
            'field_bindings': {'severity': {'native_field': 'priority'}},
            'chart_bindings': {},
        }))

        # When
        loaded = service.get_provider_profile_config('editable-jira')
        edited = service.save_provider_profile_config(provider_profile_config_from_dict({
            'id': loaded.id,
            'profile_id': loaded.profile_id,
            'provider_id': loaded.provider_id,
            'display_name': 'Editable Jira Renamed',
            'lifecycle_state': loaded.lifecycle_state,
            'source_population': {'native_query_text': 'project = AFTER'},
            'field_bindings': loaded.field_bindings,
            'chart_bindings': loaded.chart_bindings,
        }))

        # Then
        self.assertEqual(saved.id, loaded.id)
        self.assertEqual(saved.id, edited.id)
        self.assertEqual(1, ProviderProfileConfig.objects.filter(profile_id='editable-jira').count())
        self.assertEqual('Editable Jira Renamed', ProviderProfileConfig.objects.get(profile_id='editable-jira').display_name)

    def test_shouldReturnUnavailableWhenManagedProfileIsArchived(self):
        # Given
        service = ProviderProfileConfigService()
        service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'archived-jira',
            'provider_id': 'jira',
            'display_name': 'Archived Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'source_population': {'native_query_text': 'project = ARCHIVED'},
            'field_bindings': {'severity': {'native_field': 'priority'}},
            'chart_bindings': {'open_bug_trend': {'support_status': 'supported'}},
        }))

        # When
        service.archive_provider_profile_config('archived-jira')
        resolution = ProjectProviderProfileRegistry.load_default().resolve_profile('archived-jira')

        # Then
        self.assertEqual('unavailable', resolution.status)
        self.assertEqual('profile_disabled', resolution.blockers[0]['code'])

    def test_shouldRejectEnablementWhenChartRequiredCanonicalFieldsAreMissing(self):
        # Given
        service = ProviderProfileConfigService()
        config = provider_profile_config_from_dict({
            'profile_id': 'missing-chart-mapping',
            'provider_id': 'jira',
            'display_name': 'Missing Chart Mapping',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'source_population': {'native_query_text': 'project = MISSING'},
            'field_bindings': {'submitted_date': {'native_field': 'created'}},
            'chart_bindings': {
                'open_bug_trend': {
                    'support_status': 'supported',
                    'required_canonical_fields': ['submitted_date', 'severity'],
                },
            },
        })

        # When / Then
        with self.assertRaises(ValueError) as context:
            service.save_provider_profile_config(config)
        self.assertIn('severity', context.exception.args[0]['chart_bindings'])
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id='missing-chart-mapping').exists())

    def test_shouldExportImportProfilePackageWithoutSecrets(self):
        # Given
        service = ProviderProfileConfigService()
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'portable-jira',
            'provider_id': 'jira',
            'display_name': 'Portable Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'source_population': {'native_query_text': 'project = PORTABLE', 'token': 'must-not-be-special'},
            'field_bindings': {'status': {'native_field': 'status'}},
            'chart_bindings': {},
        }))

        # When
        package = service.export_provider_profile_package(saved.profile_id)
        imported = service.import_provider_profile_package(package)

        # Then
        self.assertEqual('metrics.provider-profile', package['format'])
        self.assertIn('credentials', package['excludes'])
        self.assertIn('tokens', package['excludes'])
        self.assertNotIn('must-not-be-special', str(package))
        self.assertEqual('portable-jira-imported', imported.profile_id)
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_DRAFT, imported.lifecycle_state)

    def test_shouldImportProfilePackageWithoutOverwritingEnabledConflict(self):
        # Given
        service = ProviderProfileConfigService()
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'portable-jira',
            'provider_id': 'jira',
            'display_name': 'Portable Jira',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'source_population': {'native_query_text': 'project = PORTABLE'},
            'field_bindings': {'status': {'native_field': 'status'}},
            'chart_bindings': {},
        }))
        service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'portable-jira-imported',
            'provider_id': 'jira',
            'display_name': 'Existing Enabled',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'source_population': {'native_query_text': 'project = EXISTING'},
            'field_bindings': {'status': {'native_field': 'status'}},
            'chart_bindings': {'open_bug_trend': {'support_status': 'supported'}},
        }))
        package = service.export_provider_profile_package(saved.profile_id)

        # When
        imported = service.import_provider_profile_package(package)

        # Then
        existing = ProviderProfileConfig.objects.get(profile_id='portable-jira-imported')
        self.assertEqual('portable-jira-imported-2', imported.profile_id)
        self.assertEqual('Existing Enabled', existing.display_name)
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_ENABLED, existing.lifecycle_state)

    def test_shouldDuplicateProfileWithUniqueDraftIds(self):
        # Given
        service = ProviderProfileConfigService()
        service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'duplicate-source',
            'provider_id': 'jira',
            'display_name': 'Duplicate Source',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'source_population': {'native_query_text': 'project = DUPLICATE'},
            'field_bindings': {'status': {'native_field': 'status'}},
            'chart_bindings': {'open_bug_trend': {'support_status': 'supported'}},
        }))

        # When
        first = service.duplicate_provider_profile_config('duplicate-source')
        second = service.duplicate_provider_profile_config('duplicate-source')

        # Then
        self.assertEqual('duplicate-source-copy', first.profile_id)
        self.assertEqual('duplicate-source-copy-2', second.profile_id)
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_DRAFT, second.lifecycle_state)

    def test_shouldAuditProfileMutationsWithFingerprintsAndConfirmationEvidence(self):
        # Given
        service = ProviderProfileConfigService()
        saved = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'audited-profile',
            'provider_id': 'jira',
            'display_name': 'Audited Profile',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'source_population': {'native_query_text': 'project = BEFORE'},
            'field_bindings': {'status': {'native_field': 'status'}},
            'chart_bindings': {'open_bug_trend': {'support_status': 'supported'}},
        }))

        # When
        updated = service.save_provider_profile_config(provider_profile_config_from_dict({
            'id': saved.id,
            'profile_id': 'audited-profile',
            'provider_id': 'jira',
            'display_name': 'Audited Profile',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_ENABLED,
            'source_population': {'native_query_text': 'project = AFTER'},
            'field_bindings': {'status': {'native_field': 'status'}},
            'chart_bindings': {'open_bug_trend': {'support_status': 'supported'}},
        }))
        service.archive_provider_profile_config(updated.profile_id)
        service.delete_archived_provider_profile_config(updated.profile_id, 'DELETE audited-profile')

        # Then
        update_event = BugTrendAuditEvent.objects.filter(
            event_type=BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_UPDATED,
        ).latest('created_at')
        delete_event = BugTrendAuditEvent.objects.get(event_type=BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_DELETED)
        self.assertNotEqual(
            update_event.request_summary['before']['source_version_hash'],
            update_event.request_summary['after']['source_version_hash'],
        )
        self.assertEqual('DELETE audited-profile', delete_event.request_summary['after']['confirmation'])
        self.assertGreaterEqual(delete_event.request_summary['after']['impact']['audit_events'], 3)

    def test_shouldAuditBundledProfileExportWithoutCreatingManagedOverride(self):
        # Given
        service = ProviderProfileConfigService()

        # When
        package = service.export_provider_profile_package('chiplet-2a-jira')

        # Then
        event = BugTrendAuditEvent.objects.get(event_type=BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_EXPORTED)
        self.assertEqual('chiplet-2a-jira', package['profile']['profile_id'])
        self.assertNotIn('id', package['profile'])
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id='chiplet-2a-jira').exists())
        self.assertEqual('chiplet-2a-jira', event.request_summary['profile_id'])
        self.assertEqual(False, event.request_summary['after']['included_runtime_data'])

    def test_shouldDeleteOnlyArchivedManagedProfileWithConfirmation(self):
        # Given
        service = ProviderProfileConfigService()
        profile = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'delete-profile',
            'provider_id': 'jira',
            'display_name': 'Delete Profile',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'source_population': {},
            'field_bindings': {},
            'chart_bindings': {},
        }))

        # When
        with self.assertRaises(ValueError):
            service.delete_archived_provider_profile_config(profile.profile_id, 'DELETE delete-profile')
        service.archive_provider_profile_config(profile.profile_id)
        impact = service.delete_archived_provider_profile_config(profile.profile_id, 'DELETE delete-profile')

        # Then
        self.assertEqual('delete-profile', impact.profile_id)
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id='delete-profile').exists())
        self.assertTrue(BugTrendAuditEvent.objects.filter(event_type=BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_DELETED).exists())

    def test_shouldReleaseScopeBindingsWhenArchivedProfileIsDeleted(self):
        # Given
        service = ProviderProfileConfigService()
        profile = service.save_provider_profile_config(provider_profile_config_from_dict({
            'profile_id': 'delete-bound-profile',
            'provider_id': 'jira',
            'display_name': 'Delete Bound Profile',
            'lifecycle_state': ProviderProfileConfig.LIFECYCLE_DRAFT,
            'source_population': {},
            'field_bindings': {},
            'chart_bindings': {},
        }))
        scope = JiraScopeConfig.objects.create(
            name='Bound profile cleanup scope',
            jql='project = CLEANUP',
            bug_type_values=['Bug'],
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id=profile.profile_id,
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            provenance={'source': 'operator_confirmed'},
        )

        # When
        service.archive_provider_profile_config(profile.profile_id)
        impact = service.delete_archived_provider_profile_config(profile.profile_id, 'DELETE delete-bound-profile')

        # Then
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(1, impact.scope_bindings)
        self.assertEqual('', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED, binding.status)
        self.assertEqual('provider_profile_deleted', binding.blockers[0]['code'])
        self.assertIn('delete-bound-profile', binding.blockers[0]['message'])
        self.assertTrue(BugTrendAuditEvent.objects.filter(
            event_type=BugTrendAuditEvent.EVENT_SCOPE_BINDING_UPDATED,
            scope=scope,
            request_summary__operation='provider_profile_deleted_binding_cleanup',
        ).exists())
