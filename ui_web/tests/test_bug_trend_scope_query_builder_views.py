from django.test import TestCase
from django.urls import reverse

from ui_web.tests.bug_trend_scope_config_test_support import BugTrendScopeConfigViewTestSupport


class TestBugTrendScopeQueryBuilderViews(BugTrendScopeConfigViewTestSupport, TestCase):
    def test_shouldKeepAdvancedInputsCollapsedBeforeMetadataRefreshInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'source_mode': 'query_builder',
        })

        # Then
        result = self._measure_scope_query_builder_empty_metadata_layout(response.content.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, result['visible_advanced_control_count'])
        self.assertEqual(0, result['open_advanced_count'])
        self.assertGreater(result['advanced_summary_count'], 0)
        self.assertIn('Add Jira project context, then refresh metadata to choose issue types values.', result['empty_messages'])
        self.assertNotIn('Manual fallback values', result['body_text'])
        self.assertNotIn('Manual field id', result['body_text'])
