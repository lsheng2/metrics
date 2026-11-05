from copy import deepcopy
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ai_base_application_sdk import TaskRunClient
import httpx

from project_management.app.domain.summary_contracts import AnalysisError
from project_management.out.ai_task_contract import AiTaskContract
from project_management.tests.summary_fixtures import PACK_ROOT, SummaryScenario


ROOT = Path(__file__).resolve().parents[2]


class TestPreintegrationCommand(unittest.TestCase):
    def run_command(self, work_root):
        completed = subprocess.run(
            [
                sys.executable, '-I', 'scripts/validation/run_project_sdk_preintegration.py',
                '--work-root', str(work_root),
            ],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(2, completed.returncode, completed.stderr)
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_command_refuses_a_work_root_outside_the_workspace(self):
        with TemporaryDirectory() as temporary:
            result = self.run_command(temporary)
        self.assertEqual('PREINTEGRATION_REFUSED', result['status'])
        self.assertEqual('invalid_work_root', result['code'])

    def test_command_refuses_a_changed_wheel_before_loading_an_sdk(self):
        with TemporaryDirectory(dir=ROOT / '.tmp') as temporary:
            artifacts = Path(temporary) / 'artifacts'
            artifacts.mkdir()
            (artifacts / 'ai_base_application_sdk-0.2.0a1-py3-none-any.whl').write_bytes(b'not-the-release')
            result = self.run_command(temporary)
        self.assertEqual('PREINTEGRATION_REFUSED', result['status'])
        self.assertEqual('wheel_hash_mismatch', result['code'])


class TestPreintegrationNetworkPolicy(unittest.TestCase):
    def test_isolation_entry_is_import_safe(self):
        runner = import_module('scripts.validation.run_report_authoring_tests')
        self.assertTrue(callable(runner.run_tests))

    def test_strict_connect_rejects_loopback_and_external_before_delegation(self):
        runner = import_module('scripts.validation.run_report_authoring_tests')
        attempts = []

        def forbidden(*args, **kwargs):
            self.fail('A refused connection reached the underlying transport.')

        guarded = runner.guarded_connect(
            forbidden, allow_loopback=False, network_attempts=attempts,
        )
        for host in ('127.0.0.1', 'localhost', '::1', 'tracker.example.test'):
            with self.subTest(host=host), self.assertRaises(AssertionError):
                guarded(None, (host, 443))
        self.assertEqual(['connect'] * 4, attempts)

    def test_strict_dns_and_connection_factory_record_refusals(self):
        runner = import_module('scripts.validation.run_report_authoring_tests')
        attempts = []

        def forbidden(*args, **kwargs):
            self.fail('A refused lookup reached the underlying transport.')

        resolver = runner.guarded_getaddrinfo(
            forbidden, allow_loopback=False, network_attempts=attempts,
        )
        connection = runner.guarded_create_connection(
            forbidden, allow_loopback=False, network_attempts=attempts,
        )
        with self.assertRaises(AssertionError):
            resolver('localhost', 80)
        with self.assertRaises(AssertionError):
            connection(('127.0.0.1', 80))
        self.assertEqual(['getaddrinfo', 'create_connection'], attempts)

    def test_default_policy_preserves_only_loopback_delegation(self):
        runner = import_module('scripts.validation.run_report_authoring_tests')
        attempts = []
        guarded = runner.guarded_connect(
            lambda instance, address: address, network_attempts=attempts,
        )
        self.assertEqual(('127.0.0.1', 8080), guarded(None, ('127.0.0.1', 8080)))
        with self.assertRaises(AssertionError):
            guarded(None, ('tracker.example.test', 443))
        self.assertEqual(['connect'], attempts)

    def test_socketpair_scope_is_counted_and_does_not_allow_later_connections(self):
        runner = import_module('scripts.validation.run_report_authoring_tests')
        attempts, runtime_ipc = [], []
        guarded = runner.guarded_connect(
            lambda instance, address: address, allow_loopback=False,
            network_attempts=attempts, runtime_ipc_attempts=runtime_ipc,
        )
        create_pair = runner.guarded_socketpair(lambda: guarded(None, ('127.0.0.1', 32100)))
        self.assertEqual(('127.0.0.1', 32100), create_pair())
        with self.assertRaises(AssertionError):
            guarded(None, ('127.0.0.1', 32100))
        self.assertEqual(['socketpair.connect'], runtime_ipc)
        self.assertEqual(['connect'], attempts)

    def test_socketpair_failure_cannot_leave_an_allowance_active(self):
        runner = import_module('scripts.validation.run_report_authoring_tests')

        def fail_pair():
            raise ValueError('synthetic pair failure')

        with self.assertRaises(ValueError):
            runner.guarded_socketpair(fail_pair)()
        guarded = runner.guarded_connect(
            lambda *args: self.fail('The runtime allowance leaked.'),
            allow_loopback=False,
        )
        with self.assertRaises(AssertionError):
            guarded(None, ('127.0.0.1', 32100))


class TestSdk020Compatibility(unittest.TestCase):
    def test_delivered_sdk_loads_the_original_summary_profile(self):
        self.assertEqual('0.2.0a1', version('ai-base-application-sdk'))
        contract = AiTaskContract.load(PACK_ROOT)
        self.assertEqual(
            {'key': 'project-reporting.summary', 'revision': 'review-1'},
            contract.profile_ref,
        )

    def test_unapproved_sdk_versions_are_not_silently_admitted(self):
        for sdk_version in ('0.1.0a2', '0.2.0', '0.2.0a2', '1.0.0'):
            with self.subTest(sdk_version=sdk_version):
                with patch(
                    'project_management.out.ai_task_contract.version', return_value=sdk_version,
                ), self.assertRaises(AnalysisError) as caught:
                    AiTaskContract.load(PACK_ROOT)
                self.assertEqual('ANALYSIS_CONTRACT_INVALID', caught.exception.code)

    def test_missing_installed_distribution_is_a_contract_refusal(self):
        with patch(
            'project_management.out.ai_task_contract.version',
            side_effect=PackageNotFoundError('synthetic missing SDK'),
        ), self.assertRaises(AnalysisError) as caught:
            AiTaskContract.load(PACK_ROOT)
        self.assertEqual('ANALYSIS_CONTRACT_INVALID', caught.exception.code)

    def test_changed_manifest_is_rejected_without_requiring_other_files(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = json.loads((PACK_ROOT / 'manifest.json').read_text(encoding='utf-8'))
            manifest['qualification'] = 'provider'
            (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            with self.assertRaises(AnalysisError) as caught:
                AiTaskContract.load(root)
        self.assertEqual('ANALYSIS_CONTRACT_INVALID', caught.exception.code)

    def test_changed_profile_bytes_do_not_inherit_the_original_pack_trust(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / 'pack'
            shutil.copytree(PACK_ROOT, root)
            manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
            selected = manifest['profiles']['project-reporting.summary@review-1']['profile']
            profile = root / selected
            profile.write_bytes(profile.read_bytes() + b'\n ')
            with self.assertRaises(AnalysisError) as caught:
                AiTaskContract.load(root)
        self.assertEqual('ANALYSIS_CONTRACT_INVALID', caught.exception.code)


class TestSdk020DomainBoundary(SummaryScenario, unittest.IsolatedAsyncioTestCase):
    async def test_valid_sdk_envelope_does_not_admit_an_ungrounded_action_owner(self):
        attempt = self.attempt()
        output = deepcopy(self.output(attempt.prepared))
        output['next_actions'][0]['owner_id'] = 'not-in-source'
        snapshot, result = self.responses(attempt, output)
        async with TaskRunClient(
            base_url=attempt.backend.base_url,
            source_app_id=attempt.backend.source_app_id,
            run_store_id=attempt.backend.run_store_id,
            credential_ref='synthetic-test',
            token='synthetic-only',
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=result)),
        ) as client:
            decoded = await client.get_result(attempt.backend.scope_key, result['runId'])
        with self.assertRaises(AnalysisError) as caught:
            self.contract.validate_result(attempt, snapshot, decoded)
        self.assertEqual('ANALYSIS_OWNER_INVALID', caught.exception.code)
