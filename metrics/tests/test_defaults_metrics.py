from unittest.mock import patch

from django.test import SimpleTestCase

from metrics.settings.defaults_metrics import metrics_list_setting


class TestMetricsListSetting(SimpleTestCase):
    def test_shouldParseJsonArrayWhenEnvironmentUsesReadmeStyleList(self):
        # Given
        env_values = {
            'METRICS_IN_PROGRESS_STATUS_CODES': '["Analysis", "Active", "In Progress", "Review"]',
        }

        # When
        with patch.dict('os.environ', env_values, clear=False):
            values = metrics_list_setting('METRICS_IN_PROGRESS_STATUS_CODES')

        # Then
        self.assertEqual(['Analysis', 'Active', 'In Progress', 'Review'], values)

    def test_shouldParseCommaSeparatedListWhenEnvironmentUsesDotenvList(self):
        # Given
        env_values = {
            'METRICS_PROJECT_KEYS': 'STDEL, NPU, MEDIA',
        }

        # When
        with patch.dict('os.environ', env_values, clear=False):
            values = metrics_list_setting('METRICS_PROJECT_KEYS')

        # Then
        self.assertEqual(['STDEL', 'NPU', 'MEDIA'], values)

    def test_shouldParseQuotedJsonArrayWhenDotenvKeepsOuterQuotes(self):
        # Given
        env_values = {
            'METRICS_PR_MAIN_REVIEWER_LEVELS': '\'["lead", "arch"]\'',
        }

        # When
        with patch.dict('os.environ', env_values, clear=False):
            values = metrics_list_setting('METRICS_PR_MAIN_REVIEWER_LEVELS')

        # Then
        self.assertEqual(['lead', 'arch'], values)

    def test_shouldReturnDefaultWhenEnvironmentValueIsMissing(self):
        # When
        with patch.dict('os.environ', {}, clear=True):
            values = metrics_list_setting('METRICS_TEST_UNKNOWN_LIST', default=['Done'])

        # Then
        self.assertEqual(['Done'], values)
