import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from django.test import SimpleTestCase

from scripts.validation.project_ui_fixture_guard import DB_FILE_NAME, OWNER_FILE_NAME, owner_payload


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / 'scripts' / 'validation' / 'project_ui_fixture.py'
OWNED_ROOT = REPO_ROOT / '.tmp' / 'project-reporting-w2'


class TestProjectUiFixtureSafety(SimpleTestCase):
    def run_fixture(self, fixture_root, extra_env=None):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {'DJANGO_SETTINGS_MODULE', 'METRICS_SQLITE_DATABASE_PATH', 'METRICS_STATE_DIR'}
        }
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(SCRIPT), '--migrate', '--fixture-root', str(fixture_root)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_settings_setup(self, fixture_root, extra_env=None):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in {
                'DJANGO_SETTINGS_MODULE',
                'METRICS_SQLITE_DATABASE_PATH',
                'METRICS_STATE_DIR',
                'METRICS_PROJECT_UI_FIXTURE_ROOT',
                'METRICS_PROJECT_UI_FIXTURE_NAME',
                'METRICS_PROJECT_UI_FIXTURE_BOOTSTRAP',
            }
        }
        env.update({
            'DJANGO_SETTINGS_MODULE': 'scripts.validation.project_ui_settings',
            'METRICS_PROJECT_UI_FIXTURE_ROOT': str(fixture_root),
            'METRICS_PROJECT_UI_FIXTURE_NAME': 'project-ui-w2',
        })
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            [sys.executable, '-c', 'import django; django.setup(); print("settings-ok")'],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def fresh_root(self, name):
        root = OWNED_ROOT / 'test-runs' / f'{name}-{uuid.uuid4().hex}'
        if root.exists():
            shutil.rmtree(root)
        return root

    def test_shouldRejectConflictingSettingsBeforeTouchingAmbientDatabase(self):
        # Given
        sentinel = self.fresh_root('sentinel')
        sentinel.mkdir(parents=True)
        db_path = sentinel / 'sentinel.sqlite3'
        db_path.write_bytes(b'sentinel-db')

        # When
        result = self.run_fixture(
            self.fresh_root('conflict'),
            {
                'DJANGO_SETTINGS_MODULE': 'metrics.settings.defaults_metrics',
                'METRICS_SQLITE_DATABASE_PATH': str(db_path),
            },
        )

        # Then
        self.assertNotEqual(0, result.returncode)
        self.assertIn('conflicting DJANGO_SETTINGS_MODULE', result.stderr)
        self.assertEqual(b'sentinel-db', db_path.read_bytes())

    def test_shouldRejectPathEscapeAndUnknownNonemptyRoots(self):
        # Given
        escaped = OWNED_ROOT / '..' / f'escape-{uuid.uuid4().hex}'
        nonempty = self.fresh_root('nonempty')
        nonempty.mkdir(parents=True)
        sentinel = nonempty / 'sentinel.txt'
        sentinel.write_text('keep', encoding='utf-8')

        # When
        escaped_result = self.run_fixture(escaped)
        nonempty_result = self.run_fixture(nonempty)

        # Then
        self.assertNotEqual(0, escaped_result.returncode)
        self.assertIn('inside .tmp/project-reporting-w2', escaped_result.stderr)
        self.assertNotEqual(0, nonempty_result.returncode)
        self.assertIn('unowned fixture root', nonempty_result.stderr)
        self.assertEqual('keep', sentinel.read_text(encoding='utf-8'))

    def test_shouldRejectReparseFixtureRootWhenSupported(self):
        # Given
        target = self.fresh_root('target')
        target.mkdir(parents=True)
        link = self.fresh_root('link')
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'symlink or junction setup is not available: {error}')

        # When
        result = self.run_fixture(link)

        # Then
        self.assertNotEqual(0, result.returncode)
        self.assertIn('reparse', result.stderr.lower())

    def test_shouldRejectDirectSettingsStartupForOutsideOrUnownedRootWithoutMutatingSentinelDb(self):
        # Given
        outside = REPO_ROOT / '.tmp' / f'project-ui-outside-{uuid.uuid4().hex}'
        outside.mkdir(parents=True)
        outside_db = outside / DB_FILE_NAME
        outside_db.write_bytes(b'outside-db')

        unowned = self.fresh_root('direct-unowned')
        unowned.mkdir(parents=True)
        unowned_db = unowned / DB_FILE_NAME
        unowned_db.write_bytes(b'unowned-db')

        # When
        outside_result = self.run_settings_setup(outside)
        unowned_result = self.run_settings_setup(unowned)

        # Then
        self.assertNotEqual(0, outside_result.returncode)
        self.assertIn('inside .tmp/project-reporting-w2', outside_result.stderr)
        self.assertNotEqual(0, unowned_result.returncode)
        self.assertIn('unowned fixture root', unowned_result.stderr)
        self.assertEqual(b'outside-db', outside_db.read_bytes())
        self.assertEqual(b'unowned-db', unowned_db.read_bytes())

    def test_shouldRejectDirectSettingsStartupWhenExistingDatabaseMarkerIsMissing(self):
        # Given
        fixture_root = self.fresh_root('missing-db-marker')
        fixture_root.mkdir(parents=True)
        (fixture_root / OWNER_FILE_NAME).write_text(
            __import__('json').dumps(owner_payload(fixture_root), sort_keys=True),
            encoding='utf-8',
        )
        db_path = fixture_root / DB_FILE_NAME
        db_path.write_bytes(b'not-a-fixture-db')

        # When
        result = self.run_settings_setup(fixture_root)

        # Then
        self.assertNotEqual(0, result.returncode)
        self.assertIn('without owner marker', result.stderr)
        self.assertEqual(b'not-a-fixture-db', db_path.read_bytes())

    def test_shouldAcceptDirectSettingsStartupForFixtureOwnedDatabase(self):
        # Given
        fixture_root = self.fresh_root('valid-direct')
        seed = self.run_fixture(fixture_root)
        self.assertEqual(0, seed.returncode, seed.stderr)

        # When
        result = self.run_settings_setup(fixture_root)

        # Then
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('settings-ok', result.stdout)

    def test_shouldRejectLinkedOwnerAndDatabaseFilesWhenSupported(self):
        # Given
        linked_owner_root = self.fresh_root('linked-owner')
        linked_owner_root.mkdir(parents=True)
        owner_target = linked_owner_root / 'owner-target.json'
        owner_target.write_text(
            __import__('json').dumps(owner_payload(linked_owner_root), sort_keys=True),
            encoding='utf-8',
        )

        linked_db_root = self.fresh_root('linked-db')
        linked_db_root.mkdir(parents=True)
        (linked_db_root / OWNER_FILE_NAME).write_text(
            __import__('json').dumps(owner_payload(linked_db_root), sort_keys=True),
            encoding='utf-8',
        )
        db_target = linked_db_root / 'target.sqlite3'
        db_target.write_bytes(b'not-a-fixture-db')
        try:
            os.symlink(owner_target, linked_owner_root / OWNER_FILE_NAME)
            os.symlink(db_target, linked_db_root / DB_FILE_NAME)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'symlink setup is not available: {error}')

        # When
        owner_result = self.run_settings_setup(linked_owner_root)
        db_result = self.run_settings_setup(linked_db_root)

        # Then
        self.assertNotEqual(0, owner_result.returncode)
        self.assertIn('owner file', owner_result.stderr)
        self.assertNotEqual(0, db_result.returncode)
        self.assertIn('fixture database', db_result.stderr)
