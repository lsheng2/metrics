from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import JiraScopeConfig


class TestWorkbenchScopeProfileSync(TestCase):
    def test_shouldResolveProfileAndProviderFromSelectedScope(self):
        stale_scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        hsdes_scope = JiraScopeConfig.objects.create(
            name='nvu-ttl-hsdes',
            jql='project = NVU AND type = bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['critical'],
            medium_low_values=['medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

        response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': hsdes_scope.id,
            'profile_id': stale_scope.name,
            'provider_id': 'jira',
            'range_mode': 'ww',
            'begin': '2026-08-03',
            'end': '2026-08-30',
            'chart_id': 'default_bug_trend',
        })

        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn(f'value="{hsdes_scope.id}"', content)
        self.assertIn('id="workbench-profile" name="profile_id" value="nvu-ttl-hsdes"', content)
        self.assertIn('id="workbench-provider" name="provider_id" value="hsdes" readonly', content)
        self.assertIn('data-profile-id="nvu-ttl-hsdes"', content)
        self.assertIn('data-provider-id="hsdes"', content)
        self.assertIn('workspace_key=metrics.hsdes.nvu-ttl-hsdes', content)
