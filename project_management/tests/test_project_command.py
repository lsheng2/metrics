from io import StringIO
import json
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from project_management.models import ProjectAuditEvent
from project_management.tests.fakes import FixedCatalog


class TestProjectCatalogCommand(TestCase):
    def invoke(self, *arguments):
        output = StringIO()
        call_command('project_catalog', *arguments, stdout=output)
        return json.loads(output.getvalue())

    def test_shouldExposeProjectLifecycleThroughLocalCommand(self):
        created = self.invoke('create', '--key', 'my-project', '--name', 'My Project')
        project_id = created['result']['id']
        listed = self.invoke('list')
        self.assertEqual(project_id, listed['result'][0]['id'])
        with patch('project_management.container.DashboardScopeCatalog', return_value=FixedCatalog()):
            added = self.invoke(
                'add-stage', project_id, '--key', 'release', '--name', 'Release',
                '--profile-id', 'alpha-jira', '--scope-id', '1',
            )
            detail = self.invoke('show', project_id)
        self.assertEqual(added['result']['id'], detail['result']['stages'][0]['id'])
        self.assertEqual('current', detail['result']['stages'][0]['source_status'])
        self.assertTrue(self.invoke('archive', project_id)['result']['archived'])
        self.assertEqual(3, ProjectAuditEvent.objects.count())

    def test_shouldFailInvalidCommandsWithSafeStructuredError(self):
        with self.assertRaises(CommandError) as raised:
            self.invoke('create', '--key', '../invalid', '--name', 'Example')
        payload = json.loads(str(raised.exception))
        self.assertEqual('INVALID_PROJECT', payload['error']['code'])
        self.assertEqual(1, raised.exception.returncode)
        self.assertNotIn('../invalid', str(raised.exception))

    def test_shouldNotAllowCallerToChooseActor(self):
        with self.assertRaisesRegex(CommandError, 'unrecognized arguments: --actor'):
            self.invoke('list', '--actor', 'some-other-owner')

    def test_shouldExposeShowNotFoundAsNonzeroSafeError(self):
        with self.assertRaises(CommandError) as raised:
            self.invoke('show', 'not-an-id')
        self.assertEqual('PROJECT_NOT_FOUND', json.loads(str(raised.exception))['error']['code'])

    def test_shouldKeepSchemaAndPaginationAcrossIndependentInvocations(self):
        self.invoke('create', '--key', 'alpha', '--name', 'Alpha')
        self.invoke('create', '--key', 'beta', '--name', 'Beta')
        result = self.invoke('list', '--limit', '1', '--offset', '1')
        self.assertEqual(1, result['schema_version'])
        self.assertEqual(['beta'], [row['key'] for row in result['result']])
        self.assertIsNone(result['error'])
