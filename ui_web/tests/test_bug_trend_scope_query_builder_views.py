from django.test import TestCase
from django.urls import reverse

from ui_web.tests.bug_trend_scope_config_test_support import BugTrendScopeConfigViewTestSupport


class TestBugTrendScopeQueryBuilderViews(BugTrendScopeConfigViewTestSupport, TestCase):
    def test_shouldEnablePickerButtonsWhenSwitchingFromCustomJqlToQueryBuilderInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
        })

        # Then
        result = self._measure_scope_query_builder_picker_after_mode_switch(response.content.decode())
        self.assertEqual(200, response.status_code)
        self.assertFalse(result['before']['query_checked'])
        self.assertTrue(result['before']['project_disabled'])
        self.assertTrue(result['before']['toggle_disabled'])
        self.assertTrue(result['after']['query_checked'])
        self.assertFalse(result['after']['project_disabled'])
        self.assertFalse(result['after']['toggle_disabled'])
        self.assertEqual('', result['after']['toggle_text'])

    def test_shouldKeepEditablePickersVisibleBeforeMetadataRefreshInBrowser(self):
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
        self.assertEqual(0, result['advanced_summary_count'])
        self.assertGreater(result['editable_picker_count'], 0)
        self.assertIn('Click the picker to refresh metadata, or type manually.', result['picker_statuses'])
        self.assertNotIn('Metadata discovery context', result['body_text'])
        self.assertNotIn('Manual field id', result['body_text'])
