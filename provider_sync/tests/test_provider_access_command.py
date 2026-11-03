import json
from datetime import UTC, datetime, timedelta
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import uuid

from django.core.management import call_command
from django.test import override_settings

from project_management.tests.capture_archive_fixtures import CaptureArchiveScenario
from provider_sync.tests.capture_gateway_fixtures import JiraFixture

PROCESS_ENTRY = '''
import runpy
import socket
import sys
def forbidden(*args, **kwargs):
    raise AssertionError("Network is forbidden in offline command tests.")
socket.socket.connect = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden
sys.argv = ["manage.py"] + sys.argv[1:]
runpy.run_path("manage.py", run_name="__main__")
'''


class TestProviderAccessCommand(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(__file__).resolve().parents[2]
        self.environment = {
            **os.environ,
            'DJANGO_SETTINGS_MODULE': 'provider_sync.tests.provider_access_process_settings',
            'PROVIDER_ACCESS_TEST_DB': str(Path(self.temporary.name) / 'commands.sqlite3'),
        }

    def run_command(self, *arguments):
        return subprocess.run([sys.executable, '-c', PROCESS_ENTRY, 'provider_access', *arguments],
                              cwd=self.root, env=self.environment, capture_output=True, text=True,
                              encoding='utf-8', timeout=30, check=False)

    def test_shouldListPublicProfilesWithNoNetworkOrCredentials(self):
        result = self.run_command('profiles', '--provider-id', 'jira')
        self.assertEqual(0, result.returncode, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data['result'])
        for profile in data['result']:
            self.assertEqual({'profile_id', 'provider_id', 'display_name', 'enabled'}, set(profile))
        self.assertEqual('', result.stderr)
        self.assertNotIn('settings-jira-token', result.stdout)

    def test_shouldDescribeUnavailableProfileWithoutNetworkFallback(self):
        result = self.run_command('status', '--profile-id', 'missing-synthetic-profile')
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(('blocked', False),
                         (json.loads(result.stdout)['result']['readiness'],
                          json.loads(result.stdout)['result']['principal_verified']))

    def test_shouldRefuseCaptureAndOperationBeforeAnyRuntimeExists(self):
        for operation in ('capture', 'operation'):
            with self.subTest(operation=operation):
                result = self.run_command(operation)
                self.assertEqual(1, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertEqual('CAPABILITY_UNAVAILABLE', json.loads(result.stderr)['error']['code'])

    def test_shouldRequireExplicitOnlineAndStageBeforeVerification(self):
        result = self.run_command('verify', '--project-id', str(uuid.uuid4()), '--stage-id', str(uuid.uuid4()))
        self.assertEqual(1, result.returncode)
        self.assertEqual('CAPABILITY_UNAVAILABLE', json.loads(result.stderr)['error']['code'])
        self.assertEqual('', result.stdout)

    def test_shouldRejectCredentialUrlActorAndUnboundProfileArgumentsSafely(self):
        for arguments in [
            ('profiles', '--token', 'canary-secret'),
            ('profiles', '--actor', 'other-owner'),
            ('verify', '--profile-id', 'profile'),
            ('profiles', '--url', 'https://other.example/path'),
        ]:
            with self.subTest(arguments=arguments[:2]):
                result = self.run_command(*arguments)
                self.assertEqual(2, result.returncode)
                self.assertEqual('', result.stdout)
                self.assertEqual('INVALID_ARGUMENTS', json.loads(result.stderr)['error']['code'])
                self.assertNotIn('canary-secret', result.stderr)


class TestProviderAccessOnlineCommand(CaptureArchiveScenario, unittest.TestCase):
    def test_shouldUseTheBoundLeaseAndReportUsageForExplicitVerification(self):
        fixture = JiraFixture(self)
        fixture.project_api.owner_subject = 'local_operator'
        output = StringIO()
        deadline = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        with patch('provider_sync.management.commands.provider_access.create_provider_access_service',
                   return_value=fixture.service):
            call_command('provider_access', 'verify', '--project-id', self.project.id, '--stage-id',
                         self.stage.id, '--online', '--deadline-at', deadline, '--max-requests', '2',
                         stdout=output)
        result = json.loads(output.getvalue())['result']
        self.assertEqual(('principal-1', 2, False),
                         (result['principal']['principal_id'], result['usage']['requests'], result['archived']))
        self.assertTrue(all(response.raw.closed for response in fixture.transport.responses))

    @override_settings(METRICS_PROJECT_CAPTURE_MAX_REQUESTS=256)
    def test_shouldRejectIncreasedLimitsOrNaiveDeadlineBeforeConstructingClients(self):
        deadline = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        for arguments in [('--deadline-at', deadline, '--max-requests', '257'),
                          ('--deadline-at', '2026-11-02T00:00:00')]:
            output, errors = StringIO(), StringIO()
            with self.subTest(arguments=arguments), patch(
                'provider_sync.management.commands.provider_access.create_provider_access_service',
                side_effect=AssertionError('Invalid diagnostics must not construct a client.'),
            ), self.assertRaises(SystemExit) as caught:
                call_command('provider_access', 'verify', '--project-id', self.project.id,
                             '--stage-id', self.stage.id, '--online', *arguments,
                             stdout=output, stderr=errors)
            self.assertEqual((1, 'INVALID_ARGUMENTS', ''),
                             (caught.exception.code, json.loads(errors.getvalue())['error']['code'], output.getvalue()))
