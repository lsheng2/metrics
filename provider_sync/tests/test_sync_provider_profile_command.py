import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from bug_metrics.models import JiraScopeConfig
from jira_history.models import JiraIssue
from jira_sync.models import JiraSyncCursor


class TestSyncProviderProfileCommand(TestCase):
    @patch('jira_sync.management.commands.sync_jira_scope.create_jira_client')
    @patch('jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter')
    def test_shouldSyncJiraProfileThroughGenericProviderProfileCommand(self, adapter_class, create_jira_client):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
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
