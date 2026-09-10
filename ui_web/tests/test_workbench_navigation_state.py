from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import JiraScopeConfig
from ui_web.tests.workbench_browser_test_support import WorkbenchBrowserTestSupport


class TestWorkbenchNavigationState(WorkbenchBrowserTestSupport, TestCase):
    def test_shouldUseFirstScopeWhenWorkbenchScopeIsMissing(self):
        # Given
        default_scope = JiraScopeConfig.objects.create(
            name='aaa default trend',
            jql='project = EMPTY',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        profile_scope = JiraScopeConfig.objects.create(
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

        # When
        response = self.client.get(reverse('ui_web:workbench'), {
            'profile_id': 'chiplet-2a-jira',
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
        })

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn(f'value="{default_scope.id}"', content)
        self.assertIn(f'var-scope_id={default_scope.id}', content)
        self.assertNotIn(f'var-scope_id={profile_scope.id}', content)

    def test_shouldRestoreLastValidWorkbenchUrlForSidebarNavigation(self):
        # When
        restored_href, rejected_href, saved_url, saved_href = self._exercise_workbench_navigation_state_restore()

        # Then
        self.assertEqual('/workbench/?scope_id=7', restored_href)
        self.assertEqual('/workbench/', rejected_href)
        self.assertEqual('/workbench/?scope_id=11', saved_url)
        self.assertEqual('/workbench/?scope_id=11', saved_href)
