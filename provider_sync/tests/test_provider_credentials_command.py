import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import TestCase, override_settings

from bug_metrics.app.api.provider_profile_config import ProviderProfileConfigService, provider_profile_config_from_dict
from bug_metrics.models import ProviderProfileConfig
from provider_sync.tests.test_provider_credentials_native import create_protected_source_toml


@override_settings(METRICS_PROVIDER_SECRET_MAX_BYTES=65536)
class TestProviderCredentialsCommand(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = override_settings(METRICS_PROVIDER_SECRET_DIR=str(Path(temporary.name) / "secrets"))
        settings.enable()
        self.addCleanup(settings.disable)

    def test_shouldPreviewAndApplyProtectedCredentialWithSafeJsonProtocol(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_file = create_protected_source_toml(root / "source.toml", "cli-token")
            preview_file = root / "preview.json"
            self._save_profile("cli-jira")
            stdout = StringIO()

            call_command("provider_credentials", "preview", "--profile-id", "cli-jira", "--source-file", str(source_file), stdout=stdout)
            preview_payload = json.loads(stdout.getvalue())
            preview_file.write_text(json.dumps(preview_payload), encoding="utf-8")

            self.assertEqual(1, preview_payload["schema_version"])
            self.assertEqual("cli-jira", preview_payload["result"]["profile_id"])
            self.assertNotIn("cli-token", stdout.getvalue())
            self.assertNotIn(str(source_file), stdout.getvalue())

            apply_stdout = StringIO()
            call_command(
                "provider_credentials",
                "apply",
                "--profile-id",
                "cli-jira",
                "--source-file",
                str(source_file),
                "--preview-file",
                str(preview_file),
                "--apply",
                "--replace",
                stdout=apply_stdout,
            )

            apply_payload = json.loads(apply_stdout.getvalue())
            self.assertEqual("applied", apply_payload["result"]["status"])
            self.assertNotIn("cli-token", apply_stdout.getvalue())
            self.assertNotIn(str(source_file), apply_stdout.getvalue())

    def test_shouldReturnSafeJsonErrorForInvalidArgumentsWithoutTracebackOrSourcePath(self):
        stderr = StringIO()

        with self.assertRaises(SystemExit):
            call_command("provider_credentials", "preview", "--profile-id", "missing", "--source-file", "", stderr=stderr)

        payload = json.loads(stderr.getvalue())
        self.assertEqual("INVALID_ARGUMENTS", payload["error"]["code"])
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_shouldReturnSafeJsonErrorFromSubprocessWithoutStdoutOrTraceback(self):
        completed = subprocess.run(
            [
                sys.executable,
                "manage.py",
                "provider_credentials",
                "preview",
                "--profile-id",
                "missing",
                "--source-file",
                "",
            ],
            cwd=Path(__file__).resolve().parents[2],
            env={**os.environ, "DJANGO_SETTINGS_MODULE": "provider_sync.tests.connection_test_settings"},
            capture_output=True,
            text=True,
            timeout=20,
        )

        self.assertNotEqual(0, completed.returncode)
        self.assertEqual("", completed.stdout)
        payload = json.loads(completed.stderr)
        self.assertEqual("INVALID_ARGUMENTS", payload["error"]["code"])
        self.assertNotIn("Traceback", completed.stderr)

    def test_shouldAllowOnlyOneSubprocessApplyForSamePreview(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "db.sqlite3"
            secret_dir = root / "secrets"
            source_file = create_protected_source_toml(root / "source.toml", "process-token")
            env = {
                **os.environ,
                "DJANGO_SETTINGS_MODULE": "provider_sync.tests.provider_credentials_process_settings",
                "PROVIDER_CREDENTIALS_PROCESS_DB": str(db_path),
                "PROVIDER_CREDENTIALS_PROCESS_SECRET_DIR": str(secret_dir),
            }
            self._run_process(["manage.py", "migrate", "--noinput"], env)
            self._run_process(["-c", self._create_profile_script()], env)
            preview = self._run_process([
                "manage.py", "provider_credentials", "preview",
                "--profile-id", "process-jira", "--source-file", str(source_file),
            ], env)
            preview_file = root / "preview.json"
            preview_file.write_text(json.dumps(json.loads(preview.stdout)["result"]), encoding="utf-8")
            apply_args = [
                sys.executable, "manage.py", "provider_credentials", "apply",
                "--profile-id", "process-jira", "--source-file", str(source_file),
                "--preview-file", str(preview_file), "--apply", "--replace",
            ]

            first = subprocess.Popen(apply_args, cwd=Path(__file__).resolve().parents[2], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            second = subprocess.Popen(apply_args, cwd=Path(__file__).resolve().parents[2], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                results = [first.communicate(timeout=30), second.communicate(timeout=30)]
            finally:
                for process in (first, second):
                    if process.poll() is None:
                        process.terminate()
                        process.communicate(timeout=10)
            return_codes = [first.returncode, second.returncode]

            self.assertEqual(1, return_codes.count(0))
            self.assertEqual(1, len(list(secret_dir.glob("*/*/*/*.intent.json"))))
            self.assertEqual(1, len([stdout for stdout, _ in results if '"status": "applied"' in stdout]))

    def _run_process(self, args, env):
        completed = subprocess.run([sys.executable, *args], cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(0, completed.returncode, completed.stderr)
        return completed

    def _create_profile_script(self):
        return (
            "import django; django.setup(); "
            "from bug_metrics.app.api.provider_profile_config import ProviderProfileConfigService, provider_profile_config_from_dict; "
            "from bug_metrics.models import ProviderProfileConfig; "
            "ProviderProfileConfigService().save_provider_profile_config(provider_profile_config_from_dict({"
            "'profile_id':'process-jira','provider_id':'jira','display_name':'Process Jira',"
            "'lifecycle_state':ProviderProfileConfig.LIFECYCLE_ENABLED,"
            "'connection_settings':{'base_url':'https://jira.settings.example/jira','auth_mode':'server_pat','credentials':{'api_token':'old-token'}},"
            "'source_population':{'native_query_text':'project = PROCESS'},"
            "'field_bindings':{'status':{'native_field':'status'}},"
            "'chart_bindings':{'open_bug_trend':{'support_status':'supported'}}"
            "}))"
        )

    def _save_profile(self, profile_id: str):
        ProviderProfileConfigService().save_provider_profile_config(provider_profile_config_from_dict({
            "profile_id": profile_id,
            "provider_id": "jira",
            "display_name": profile_id,
            "lifecycle_state": ProviderProfileConfig.LIFECYCLE_ENABLED,
            "connection_settings": {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credentials": {"api_token": "old-token"},
            },
            "source_population": {"native_query_text": "project = CLI"},
            "field_bindings": {"status": {"native_field": "status"}},
            "chart_bindings": {"open_bug_trend": {"support_status": "supported"}},
        }))
