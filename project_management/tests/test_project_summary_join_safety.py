import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from project_management.storage.paths import ensure_configured_archive_root
from scripts.validation.project_summary_support import (
    assert_checkpoint_not_dispatched, checked_connection, owned_data_root, owned_work_root,
    probe_base_imports, verify_base_source, verify_source_inventory, worker_record_matches,
)


class TestProjectSummaryJoinSafety(unittest.TestCase):
    def test_shouldRejectAReplacedBaseTreeArchiveBeforeTrustingItsOwnFileHashes(self):
        with TemporaryDirectory() as root:
            work = Path(root)
            source = work / 'base-source'
            source.mkdir()
            (work / 'base-tree-full.zip').write_bytes(b'replaced archive')
            with self.assertRaisesRegex(ValueError, 'Base commit archive digest mismatch'):
                verify_base_source(work, source)

    def test_shouldRejectUnregisteredNonPythonResources(self):
        with TemporaryDirectory() as root:
            source = Path(root)
            (source / 'known.py').write_text('pass\n', encoding='utf-8')
            verify_source_inventory(source, {'known.py'})
            (source / 'unregistered-config.json').write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                verify_source_inventory(source, {'known.py'})

    def test_shouldBlockConnectExDuringTheBaseFactoryImportProbe(self):
        with TemporaryDirectory() as root:
            directory = Path(root)
            source = directory / 'source'
            package = source / 'services/app-service/app'
            package.mkdir(parents=True)
            (package / '__init__.py').write_text('', encoding='utf-8')
            (package / 'task_run_candidate.py').write_text(
                "import socket\n"
                "with socket.socket() as connection:\n"
                "    try:\n"
                "        connection.connect_ex(('127.0.0.1', 1))\n"
                "    except RuntimeError:\n"
                "        pass\n"
                "    else:\n"
                "        raise ValueError('connect_ex bypassed the guard')\n",
                encoding='utf-8',
            )
            data, evidence = directory / 'data', directory / 'evidence'
            data.mkdir()
            evidence.mkdir()
            probe_base_imports(Path(sys.executable), source, data, evidence)
            self.assertIn('BASE_FACTORY_IMPORT_OK', (evidence / 'base-import-probe.log').read_text())

    def test_shouldMatchWorkerToKernelParentAndExactFixtureArguments(self):
        command = ['D:/venv/python.exe', '-I', 'D:/fixture.py', '--data-dir', 'D:/owned']
        record = {'ProcessId': 124, 'ParentProcessId': 123, 'ExecutablePath': 'C:/Python314/python.exe',
                  'CommandLine': '"C:/Python314/python.exe" -I D:/fixture.py --data-dir D:/owned'}
        self.assertTrue(worker_record_matches(record, 124, 123, command))
        self.assertFalse(worker_record_matches({**record, 'ParentProcessId': 999}, 124, 123, command))
        self.assertFalse(worker_record_matches(
            {**record, 'CommandLine': record['CommandLine'].replace('D:/owned', 'D:/another')}, 124, 123, command,
        ))

    def test_shouldRefuseAFreshBaseStoreWhenTheSourceAlreadyHasAnAnalysisAttempt(self):
        def runner(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0, stdout=b'analysis_attempts\n', stderr=b'')

        with self.assertRaises(ValueError):
            assert_checkpoint_not_dispatched(Path('owned-archive'), runner=runner)

    def test_shouldAdmitAnOwnedExternalArchiveRootAndRejectCodeRepositoryData(self):
        with TemporaryDirectory() as root:
            repository = Path(root) / 'code'
            repository.mkdir()
            (repository / '.git').mkdir()
            target = Path(root) / 'validation'
            admitted = owned_data_root(target, repository)
            data = admitted / 'data'
            data.mkdir()
            ensure_configured_archive_root(data)
            self.assertEqual(admitted, owned_data_root(target, repository))
            forbidden = repository / '.tmp' / 'data'
            with self.assertRaises(ValueError):
                owned_data_root(forbidden, repository)
            self.assertFalse(forbidden.exists())

    def test_shouldBootstrapActualProviderConsumersWithoutAmbientDatabase(self):
        repository = Path(__file__).resolve().parents[2]
        code = """
import importlib
from pathlib import Path
import sys
from django.db import connections
from scripts.validation.project_summary_join import configure_catalog
try:
    configure_catalog(Path(sys.argv[1]))
    importlib.import_module('provider_sync.tests.capture_gateway_fixtures')
    from django.conf import settings
    assert Path(settings.DATABASES['default']['NAME']).resolve() == Path(sys.argv[1]).resolve() / 'catalog.sqlite3'
    print('bootstrap-ok')
finally:
    connections.close_all()
"""
        with TemporaryDirectory() as root:
            directory = Path(root)
            canary = directory / 'ambient-must-not-be-created.sqlite3'
            environment = {**os.environ, 'METRICS_SQLITE_DATABASE_PATH': str(canary)}
            result = subprocess.run([sys.executable, '-c', code, str(directory)], cwd=repository,
                                    env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn('bootstrap-ok', result.stdout)
            self.assertFalse(canary.exists())

    def test_shouldRejectForeignWorkRootWithoutCreatingIt(self):
        with TemporaryDirectory() as root:
            repository = Path(root) / 'repository'
            outside = Path(root) / 'outside'
            with self.assertRaises(ValueError):
                owned_work_root(outside, repository)
            self.assertFalse(outside.exists())

    def test_shouldAcceptOnlyTheOwnedTemporaryRoot(self):
        with TemporaryDirectory() as root:
            repository = Path(root)
            work = repository / '.tmp' / 'task-run-w5'
            work.mkdir(parents=True)
            self.assertEqual(work.resolve(), owned_work_root(work, repository))

    def test_shouldRefuseWrongProcessOrEscapedStopFileBeforeCleanup(self):
        with TemporaryDirectory() as root:
            directory = Path(root).resolve()
            value = {
                'executionMode': 'synthetic', 'qualification': 'synthetic_only', 'contractVersion': 'task-run/1',
                'packVersion': '0.1.0a2', 'pid': 123, 'scopeKey': 'projects.alpha.stages.one',
                'sourceAppId': 'metrics-dashboard', 'baseUrl': 'http://127.0.0.1:18444',
                'runStoreId': 'synthetic-store', 'token': 'synthetic-only',
                'credentialRef': 'synthetic-integration', 'stopFile': str(directory / 'stop-one'),
                'grantRevision': 'dashboard-join-1', 'limitPolicyRevision': 'base-b-cancel-synthetic-1',
            }
            self.assertEqual(123, checked_connection(value, directory, 123, value['scopeKey'])['pid'])
            worker = {**value, 'pid': 124}
            verified = checked_connection(worker, directory, 123, value['scopeKey'],
                                          worker_matches=lambda child: child == 124)
            self.assertEqual((124, 123), (verified['pid'], verified['launcherPid']))
            with self.assertRaises(ValueError):
                checked_connection(worker, directory, 123, value['scopeKey'], worker_matches=lambda child: False)
            for change in ({'pid': 999}, {'stopFile': str(directory.parent / 'unowned')},
                           {'baseUrl': 'https://external.example'}, {'sourceAppId': 'other-app'}):
                with self.subTest(change=change), self.assertRaises(ValueError):
                    checked_connection({**value, **change}, directory, 123, value['scopeKey'])
