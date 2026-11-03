from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from django.test import TestCase as DjangoTestCase
from django.urls import reverse

from bug_metrics.app.api.provider_connections import ConnectionError, ProviderConnectionResolver
from bug_metrics.models import ProviderProfileConfig
from provider_sync.tests.test_provider_connections import SyntheticSettings


class TestLocalProfileCredentials(TestCase):
    def test_integrated_hsd_profile_local_marker_requires_no_token(self):
        connection = ProviderConnectionResolver(SyntheticSettings(), None).resolve_record({
            "profile_id": "local-hsd", "provider_id": "hsdes",
            "connection_settings": {"base_url": "https://hsd.example/rest", "auth_mode": "kerberos",
                                    "credential_ref": "profile:local"},
        })
        self.assertEqual("integrated", connection.info.credential.kind)

    def test_explicit_local_reference_preserves_each_supported_auth_material(self):
        resolver = ProviderConnectionResolver(SyntheticSettings(), None)
        cases = [
            ("jira", "server_pat", {"api_token": "local-token"}),
            ("jira", "cloud_basic", {"email": "local@example.test", "api_token": "local-token"}),
            ("hsdes", "token", {"token": "local-token"}),
            ("hsdes", "basic", {"username": "local-user", "password": "local-password"}),
        ]
        for provider, mode, credentials in cases:
            with self.subTest(provider=provider, mode=mode):
                connection = resolver.resolve_record({
                    "profile_id": "local-profile", "provider_id": provider,
                    "connection_settings": {
                        "base_url": "https://local.example/rest", "auth_mode": mode,
                        "credential_ref": "profile:local", "credential_storage": "profile_local",
                        "credentials": credentials,
                    },
                })
                self.assertEqual("inline", connection.info.credential.kind)
                factory = lambda **kwargs: SimpleNamespace(kwargs=kwargs)
                client = connection.open_jira_client(factory) if provider == "jira" else connection.open_hsdes_client(factory)
                self.assertEqual("local-password" if mode == "basic" else "local-token",
                                 client.kwargs["password" if mode == "basic" else "token" if mode in {"token", "server_pat"} else "password"])

    def test_empty_selected_local_source_never_falls_back_to_settings(self):
        resolver = ProviderConnectionResolver(SyntheticSettings(), None)
        for selection in ({"credential_ref": "profile:local"}, {"credential_storage": "profile_local"}):
            with self.subTest(selection=selection), self.assertRaises(ConnectionError):
                resolver.resolve_record({
                    "profile_id": "local-profile", "provider_id": "jira",
                    "connection_settings": {
                        "base_url": "https://jira.settings.example/jira", "auth_mode": "server_pat",
                        **selection,
                    },
                })


class TestProviderSetupConnectionFlow(DjangoTestCase):
    def test_jira_ui_probe_uses_local_material_without_saving_or_leaking_it(self):
        payload = {
            "action": "test_connection", "profile_id": "transient-jira", "provider_id": "jira",
            "display_name": "Transient", "connection_base_url": "https://jira.ui.example",
            "connection_auth_mode": "server_pat", "credential_ref": "profile:local",
            "connection_api_token": "local-ui-secret", "lifecycle_state": "draft",
        }
        with patch("bug_metrics.app.api.provider_profile_connection_test.Jira") as factory:
            factory.return_value.get_server_info.return_value = {"serverTitle": "Synthetic", "version": "10"}
            response = self.client.post(reverse("ui_web:provider_setup"), payload)
        self.assertContains(response, "Jira connection succeeded.")
        self.assertNotContains(response, "local-ui-secret")
        self.assertFalse(ProviderProfileConfig.objects.filter(profile_id="transient-jira").exists())
