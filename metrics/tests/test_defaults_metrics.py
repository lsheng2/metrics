import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from django.http.request import validate_host
from django.test import SimpleTestCase

from metrics.settings.defaults_metrics import metrics_list_setting

ROOT = Path(__file__).resolve().parents[2]
PRINT_ALLOWED_HOSTS = '\n'.join((
    'import importlib, json, sys',
    'from unittest.mock import patch',
    "with patch('environs.Env.read_env', lambda *args, **kwargs: None):",
    '    settings_module = importlib.import_module(sys.argv[1])',
    'print(json.dumps(settings_module.ALLOWED_HOSTS))',
))


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


class TestAllowedHostsDefault(SimpleTestCase):
    def effective_allowed_hosts(self, settings_module):
        environment = {key: value for key, value in os.environ.items() if key != 'ALLOWED_HOSTS'}
        result = subprocess.run(
            [sys.executable, '-c', PRINT_ALLOWED_HOSTS, settings_module],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_shouldRejectRebindingHostWhenAllowedHostsIsUnset(self):
        for settings_module in ('metrics.settings.production', 'metrics.settings.development'):
            with self.subTest(settings_module=settings_module):
                # When
                allowed_hosts = self.effective_allowed_hosts(settings_module)

                # Then
                self.assertFalse(validate_host('rebind.attacker.example', allowed_hosts))
                for host in ('127.0.0.1', 'localhost', '[::1]'):
                    self.assertTrue(validate_host(host, allowed_hosts))
