import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from bug_metrics.app.api.provider_connections import ConnectionError
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig, ProviderProfileConfig
from jira_sync.models import JiraSyncCursor
from provider_sync.app.api.hsdes import HsdesHttpClient, HsdesProviderError


class TestProviderSyncErrorConsumers(TestCase):
    def test_hsd_transport_errors_keep_public_categories(self):
        def refused(*args, **kwargs):
            raise ConnectionError("PROVIDER_AUTH_FAILED")

        for transport in ("requests", "powershell"):
            client = HsdesHttpClient(
                "https://hsd.example/rest", auth_mode="windows_integrated",
                transport=transport, opener=refused, powershell_runner=SimpleNamespace(run=refused),
            )
            with self.subTest(transport=transport), self.assertRaises(HsdesProviderError) as caught:
                client.execute_saved_query("123", "tenant", "bug", ["id"], 1, 10)
            self.assertEqual("auth_failed", caught.exception.category)

    @override_settings(METRICS_HSDES_LIVE_SYNC_ENABLED=True)
    def test_both_hsd_commands_return_failed_json_for_bad_selected_connection(self):
        registry = ProjectProviderProfileRegistry.from_records([{
            "profile_id": "bad-hsd", "provider_id": "hsdes", "enabled": True,
            "connection_settings": {"base_url": "https://wrong.example/rest", "auth_mode": "basic",
                                    "credential_ref": "settings:METRICS_HSDES_*"},
        }])
        with patch.object(ProjectProviderProfileRegistry, "load_default", return_value=registry):
            for command in ("sync_provider_profile", "sync_hsdes_profile"):
                output = StringIO()
                call_command(command, "--profile-id", "bad-hsd", "--begin-ww", "26WW32",
                             "--end-ww", "26WW32", stdout=output)
                self.assertEqual("failed", json.loads(output.getvalue())["status"])
                self.assertNotIn("Traceback", output.getvalue())

    def test_jira_connection_failure_retains_failed_cursor_and_legacy_safe_error(self):
        scope = JiraScopeConfig.objects.create(name="Connection failure", jql="project = SAMPLE", enabled=True)
        ProviderProfileConfig.objects.create(
            profile_id="bad-jira", provider_id="jira", display_name="Bad",
            lifecycle_state="enabled",
            connection_settings={"base_url": "https://other.example/jira", "auth_mode": "server_pat",
                                 "credential_ref": "settings:METRICS_JIRA_*"},
        )
        BugTrendScopeProviderBinding.objects.create(scope=scope, profile_id="bad-jira",
                                                   provider_id="jira", status="explicit")
        with self.assertRaises(CommandError):
            call_command("sync_jira_scope", str(scope.id), "--coverage-start", "2026-08-03",
                         "--coverage-end", "2026-08-09", stdout=StringIO())
        cursor = JiraSyncCursor.objects.get(scope=scope)
        self.assertEqual(JiraSyncCursor.STATUS_FAILED, cursor.status)
        self.assertNotIn("settings-jira-token", cursor.last_error)
