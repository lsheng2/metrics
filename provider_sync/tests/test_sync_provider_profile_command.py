import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig, ProviderProfileConfig
from jira_history.models import JiraIssue
from jira_sync.models import JiraSyncCursor


class TestSyncProviderProfileCommand(TestCase):
    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldSyncJiraProfileThroughGenericProviderProfileCommand(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Renamed chiplet Jira scope',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        ProviderProfileConfig.objects.create(
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            display_name='Chiplet Jira',
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_ENABLED,
            connection_settings={
                'base_url': 'https://jira.profile.example',
                'auth_mode': 'server_pat',
                'credentials': {
                    'email': 'profile-jira-user@example.com',
                    'api_token': 'profile-jira-token',
                },
                'onboarding_status': 'ready',
            },
            source_population={'native_query_text': scope.jql},
            field_bindings={'status': {'native_field': 'status'}},
            chart_bindings={'open_bug_trend': {'support_status': 'supported'}},
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]
        output = StringIO()

        # When
        call_command(
            'sync_provider_profile',
            '--profile-id', 'chiplet-2a-jira',
            '--begin-ww', '26WW32',
            '--end-ww', '26WW32',
            stdout=output,
        )

        # Then
        payload = json.loads(output.getvalue())
        cursor = JiraSyncCursor.objects.get(scope=scope)
        self.assertEqual('success', payload['status'])
        self.assertEqual('jira', payload['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['profile_id'])
        self.assertEqual(scope.id, payload['scope_id'])
        self.assertEqual('2026-08-03', payload['coverage_start'])
        self.assertEqual('2026-08-09', payload['coverage_end'])
        self.assertEqual(JiraSyncCursor.STATUS_SUCCESS, cursor.status)
        self.assertTrue(JiraIssue.objects.filter(scope=scope, issue_key='STDEL-8942').exists())
        self.assertEqual('profile-jira-token', create_jira_client.call_args.args[1]['credentials']['api_token'])

    def test_shouldReturnConfigurationRequiredWhenJiraProfileHasNoMappedScope(self):
        # Given
        output = StringIO()

        # When
        call_command(
            'sync_provider_profile',
            '--profile-id', 'chiplet-2a-jira',
            '--begin-ww', '26WW32',
            '--end-ww', '26WW32',
            stdout=output,
        )

        # Then
        payload = json.loads(output.getvalue())
        self.assertEqual('configuration_required', payload['status'])
        self.assertEqual('jira', payload['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['profile_id'])
        self.assertEqual('jira_scope_not_mapped', payload['blockers'][0]['code'])

    @override_settings(METRICS_SCOPE_BINDING_POLICY='explicit_only')
    def test_shouldReturnConfigurationRequiredWhenJiraScopeOnlyCompatibilityMatchesProfile(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='compatibility-only-profile',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        ProviderProfileConfig.objects.create(
            profile_id='compatibility-only-profile',
            provider_id='jira',
            display_name='Compatibility Only Jira',
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_ENABLED,
            connection_settings={'base_url': 'https://jira.profile.example'},
            source_population={'native_query_text': 'project = "131600" AND component = "team_int_qemu"'},
            field_bindings={'status': {'native_field': 'status'}},
            chart_bindings={'open_bug_trend': {'support_status': 'supported'}},
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='compatibility-only-profile',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'source': 'test', 'matched_by': 'provider_profile_registry'},
        )
        output = StringIO()

        # When
        call_command(
            'sync_provider_profile',
            '--profile-id', 'compatibility-only-profile',
            '--begin-ww', '26WW32',
            '--end-ww', '26WW32',
            stdout=output,
        )

        # Then
        payload = json.loads(output.getvalue())
        self.assertEqual('configuration_required', payload['status'])
        self.assertEqual('explicit_binding_required', payload['blockers'][0]['code'])

    def _jira_issue_payload(self):
        return {
            'key': 'STDEL-8942',
            'fields': {
                'summary': 'Failure in emulation flow',
                'issuetype': {'name': 'Bug'},
                'status': {'name': 'Fixed'},
                'resolution': {'name': 'Fixed'},
                'priority': {'name': 'P3-Medium'},
                'components': [{'name': 'team_int_qemu'}],
                'assignee': {'displayName': 'Alice'},
                'created': '2026-08-04T10:00:00.000+0000',
                'updated': '2026-08-05T10:00:00.000+0000',
                'resolutiondate': '2026-08-05T09:00:00.000+0000',
            },
            'changelog': {
                'histories': [
                    {
                        'created': '2026-08-05T09:00:00.000+0000',
                        'items': [
                            {'field': 'status', 'fromString': 'Open', 'toString': 'Fixed'},
                        ],
                    }
                ]
            },
        }
