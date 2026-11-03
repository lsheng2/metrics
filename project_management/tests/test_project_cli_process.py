import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase


class TestProjectCliProcess(TestCase):
    def test_shouldPersistBetweenSeparateLocalCliProcesses(self):
        root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as directory:
            env = {**os.environ, 'PM_TEST_DATABASE': str(Path(directory) / 'catalog.sqlite3'),
                   'DJANGO_SETTINGS_MODULE': 'project_management.tests.process_settings'}

            def run(*arguments):
                return subprocess.run(
                    [sys.executable, 'manage.py', *arguments], cwd=root, env=env,
                    capture_output=True, text=True, timeout=40, check=False,
                )

            migration = run('migrate', 'project_management', '--noinput')
            self.assertEqual(0, migration.returncode, migration.stderr)
            created = run('project_catalog', 'create', '--key', 'standalone', '--name', 'Standalone')
            self.assertEqual(0, created.returncode, created.stderr)
            identity = json.loads(created.stdout)['result']['id']
            read = run('project_catalog', 'show', identity)
            self.assertEqual(0, read.returncode, read.stderr)
            self.assertEqual('standalone', json.loads(read.stdout)['result']['project']['key'])
            invalid = run('project_catalog', 'create', '--key', '../unsafe', '--name', 'Invalid')
            self.assertNotEqual(0, invalid.returncode)
            self.assertIn('"code": "INVALID_PROJECT"', invalid.stderr)
            self.assertNotIn('../unsafe', invalid.stderr)
