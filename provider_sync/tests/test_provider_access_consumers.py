import json
import unittest
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from bug_metrics.app.api.provider_connections import ConnectionError as ProviderConnectionError
from bug_metrics.app.api.provider_profile_config import provider_profile_config_from_dict
from bug_metrics.app.api.provider_profile_connection_test import ProviderProfileConnectionTestService
from bug_metrics.models import BugTrendScopeProviderBinding, JiraScopeConfig, ProviderProfileConfig
from jira_sync.out.jira_scope_issue_adapter import create_jira_client
from provider_sync.app.api.hsdes import HsdesHttpClient
from provider_sync.tests.test_api_hsdes_live_sync import FakeHsdesClient
from provider_sync.tests.test_provider_connections import SyntheticSettings
from tasks.app.domain.model.config import JiraConfig
from tasks.out.jira_task_repository import JiraTaskRepository
from tasks.tests.test_unit_jira_task_repository_auth import _build_tasks_config


class TestProviderAccessConsumerBoundaries(TestCase):
    def test_shouldRejectLegacyJiraHelperSettingsCredentialWhenEndpointDrifts(self):
        with patch("jira_sync.out.jira_scope_issue_adapter.Jira"):
            with self.assertRaises(ProviderConnectionError):
                create_jira_client(SyntheticSettings(), {
                    "base_url": "https://jira.other.example/jira",
                    "auth_mode": "server_pat",
                    "credential_ref": "settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN",
                })

    @patch("tasks.out.jira_task_repository.Jira")
    def test_shouldOpenTaskRepositoryJiraClientThroughResolvedTasksConfig(self, jira_factory):
        config = _build_tasks_config(JiraConfig(
            jira_server_url="https://jira.devtools.intel.com",
            jira_email=None,
            jira_api_token="pat",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
            ca_bundle="C:/certs/intel-ca.pem",
        ))

        JiraTaskRepository(config)

        kwargs = jira_factory.call_args.kwargs
        self.assertEqual("https://jira.devtools.intel.com", kwargs["url"])
        self.assertEqual("pat", kwargs["token"])
        self.assertEqual("C:\\certs\\intel-ca.pem", kwargs["verify_ssl"])
        self.assertIn("session", kwargs)
        self.assertEqual(30, kwargs["timeout"])
        self.assertFalse(kwargs["backoff_and_retry"])
        self.assertFalse(kwargs["retry_with_header"])

    def test_shouldDelegateHsdesIntegratedPowerShellExecutionToBoundRunner(self):
        calls = []

        class BoundRunner:
            def run(self, url, timeout_seconds):
                calls.append((url, timeout_seconds))
                return SimpleNamespace(stdout=json.dumps({"data": [{"id": "1"}], "total": 1}), stderr="", returncode=0)

        client = HsdesHttpClient(
            base_url="https://hsdes-api.intel.com/rest",
            auth_mode="windows_integrated",
            timeout_seconds=15,
            transport="powershell",
            powershell_runner=BoundRunner(),
        )

        page = client.execute_saved_query("15017652869", "tenant", "subject", ["id"], 0, 1)

        self.assertEqual(1, page["total"])
        self.assertEqual(15, calls[0][1])
        self.assertIn("/rest/query/execution/15017652869?", calls[0][0])

    def test_shouldNotBorrowSavedProfileCredentialsForDraftConnectionWithChangedEndpoint(self):
        saved = provider_profile_config_from_dict({
            "profile_id": "draft-jira",
            "provider_id": "jira",
            "display_name": "Draft Jira",
            "lifecycle_state": ProviderProfileConfig.LIFECYCLE_ENABLED,
            "connection_settings": {
                "base_url": "https://jira.saved.example",
                "auth_mode": "server_pat",
                "credentials": {"api_token": "saved-token"},
            },
        })
        draft = provider_profile_config_from_dict({
            "profile_id": "draft-jira",
            "provider_id": "jira",
            "display_name": "Draft Jira",
            "lifecycle_state": ProviderProfileConfig.LIFECYCLE_DRAFT,
            "connection_settings": {
                "base_url": "https://jira.changed.example",
                "auth_mode": "server_pat",
            },
        })
        calls = []

        class FakeProfileService:
            def get_provider_profile_config(self, profile_id):
                return saved

        def jira_factory(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(get_server_info=lambda: {"serverTitle": "bad reuse"})

        result = ProviderProfileConnectionTestService(FakeProfileService(), jira_client_factory=jira_factory).test_connection(draft)

        self.assertEqual("failed", result.status)
        self.assertEqual([], calls)

    @override_settings(METRICS_HSDES_LIVE_SYNC_ENABLED=True)
    def test_shouldOpenSyncProviderProfileHsdesClientThroughResolvedHandle(self):
        self._save_hsdes_profile()
        output = StringIO()
        client_kwargs = {}
        fake_client = FakeHsdesClient([{"data": [], "total": 0}])

        def hsdes_factory(**kwargs):
            client_kwargs.update(kwargs)
            return fake_client

        with patch("provider_sync.management.commands.sync_provider_profile.HsdesHttpClient", side_effect=hsdes_factory):
            call_command("sync_provider_profile", "--profile-id", "hsdes-provider-default", "--begin-ww", "26WW32", "--end-ww", "26WW32", stdout=output)

        self.assertEqual("success", json.loads(output.getvalue())["status"])
        self.assertIn("opener", client_kwargs)
        self.assertEqual("profile-hsdes-token", client_kwargs["token"])

    @patch("jira_sync.management.commands.sync_jira_scope.Jira", create=True)
    @patch("jira_sync.management.commands.sync_jira_scope.JiraScopeIssueAdapter")
    def test_shouldOpenSyncJiraScopeClientThroughResolvedProfileHandle(self, adapter_class, jira_factory):
        scope = self._save_jira_scope()
        self._bind_jira_profile(scope)
        adapter_class.return_value.fetch_issues.return_value = [self._jira_issue_payload()]

        call_command("sync_jira_scope", str(scope.id), "--coverage-start", "2026-08-03", "--coverage-end", "2026-08-09", stdout=StringIO())

        adapter_class.assert_called_once_with(jira_factory.return_value)

    def _save_hsdes_profile(self):
        ProviderProfileConfig.objects.create(
            profile_id="hsdes-provider-default",
            provider_id="hsdes",
            display_name="HSD-ES Provider Default",
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_ENABLED,
            connection_settings={
                "base_url": "https://custom-hsdes.example/rest",
                "auth_mode": "token",
                "credentials": {"token": "profile-hsdes-token"},
                "timeout_seconds": "17",
            },
            source_population={"source_query_ref": "123", "tenant_or_site": "tenant", "subject_or_issue_type": "subject"},
            field_bindings={"item_id": {"native_field": "id"}},
            chart_bindings={"component_bug": {"support_status": "supported_from_seed_facts"}},
        )

    def _save_jira_scope(self):
        return JiraScopeConfig.objects.create(name="STDEL emulation", jql="project = STDEL AND issuetype = Bug", bug_type_values=["Bug"])

    def _bind_jira_profile(self, scope):
        ProviderProfileConfig.objects.create(
            profile_id="sync-jira-profile",
            provider_id="jira",
            display_name="Sync Jira Profile",
            lifecycle_state=ProviderProfileConfig.LIFECYCLE_ENABLED,
            connection_settings={"base_url": "https://jira.profile.example", "auth_mode": "server_pat", "credentials": {"api_token": "profile-jira-token"}},
            source_population={"native_query_text": scope.jql},
            field_bindings={"status": {"native_field": "status"}},
            chart_bindings={"open_bug_trend": {"support_status": "supported"}},
        )
        BugTrendScopeProviderBinding.objects.create(scope=scope, profile_id="sync-jira-profile", provider_id="jira", status=BugTrendScopeProviderBinding.STATUS_EXPLICIT)

    def _jira_issue_payload(self):
        return {
            "key": "STDEL-8942",
            "fields": {"summary": "Failure", "issuetype": {"name": "Bug"}, "status": {"name": "Fixed"}, "created": "2026-08-04T10:00:00.000+0000", "updated": "2026-08-05T10:00:00.000+0000"},
            "changelog": {"histories": []},
        }


if __name__ == "__main__":
    unittest.main()
