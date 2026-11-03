import subprocess
import ssl
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import error, request

import requests
from atlassian import Jira

from bug_metrics.app.api import provider_connections as public_provider_connections
from bug_metrics.app.api.provider_connections import (
    ConnectionError as ProviderConnectionError,
    ProviderConnectionResolver,
)
from tasks.app.domain.model.config import JiraConfig

from provider_sync.tests.test_provider_connections import (
    CapturedClient,
    CapturingHsdesFactory,
    CapturingJiraFactory,
    ProtectedStore,
    RecordingOpener,
    SyntheticProfile,
    SyntheticRegistry,
    SyntheticSettings,
)


class ExplodingSettings:
    def __getattribute__(self, name):
        raise AssertionError(f"settings attribute {name} was read")


class CloseTrackingBody:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class RedirectingHttpsHandler(request.BaseHandler):
    handler_order = 0

    def __init__(self, body):
        self._body = body

    def https_open(self, http_request):
        raise error.HTTPError(http_request.full_url, 302, "Found", {}, self._body)


class TestProviderCredentialSourceStateMachine(unittest.TestCase):
    def test_shouldTreatProtectedFileReferenceAsProtectedAndNeverFallBackToSettings(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credential_storage": "protected_file",
                "credential_ref": "protected:pcred_0123456789abcdef0123456789abcdef",
                "credential_revision": "rev-a",
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        with self.assertRaises(ProviderConnectionError) as context:
            resolver.resolve_profile("jira-profile")

        self.assertEqual("PROVIDER_CREDENTIAL_UNAVAILABLE", context.exception.code)

    def test_shouldResolveProtectedFileReferenceThroughInjectedStoreWithExactBinding(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credential_storage": "protected_file",
                "credential_ref": "protected:pcred_0123456789abcdef0123456789abcdef",
                "credential_revision": "rev-a",
            },
        )
        store = ProtectedStore("protected-file-token")
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]), protected_store=store)

        resolved = resolver.resolve_profile("jira-profile")
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("protected", resolved.info.credential.kind)
        self.assertEqual("protected:pcred_0123456789abcdef0123456789abcdef", store.reads[0]["reference"])
        self.assertEqual(resolved.info.endpoint.endpoint_id, store.reads[0]["endpoint_id"])
        self.assertEqual("protected-file-token", factory.kwargs["token"])

    def test_shouldRejectUnknownCredentialReferenceEvenWhenInlineTokenIsPresent(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credential_ref": "vault:secret-a",
                "credentials": {"token": "inline-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        with self.assertRaises(ProviderConnectionError) as context:
            resolver.resolve_profile("jira-profile")

        self.assertEqual("PROVIDER_CREDENTIAL_INVALID", context.exception.code)

    def test_shouldRejectUnsupportedProtectedReferenceShapesWithoutStoreLookup(self):
        refs = [
            {"credential_storage": "protected_file", "credential_ref": "protected:secret-a", "credential_revision": "rev-a"},
            {"credential_storage": "protected", "credential_ref": "abc", "credential_revision": "rev-a"},
            {"credential_source": {"kind": "protected", "reference": "protected:nothex", "revision": "rev-a"}},
        ]
        for extra_settings in refs:
            with self.subTest(extra_settings=extra_settings):
                profile = SyntheticProfile(
                    "jira-profile",
                    "jira",
                    {"base_url": "https://jira.settings.example/jira", "auth_mode": "server_pat", **extra_settings},
                )
                resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]), protected_store=ProtectedStore())

                with self.assertRaises(ProviderConnectionError) as context:
                    resolver.resolve_profile("jira-profile")

                self.assertEqual("PROVIDER_CREDENTIAL_INVALID", context.exception.code)

    def test_shouldReportMalformedCredentialReferenceAsSafeStatusBlocker(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credential_ref": {"kind": "vault"},
                "credentials": {"token": "inline-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        info = resolver.status("jira-profile")

        self.assertEqual(("PROVIDER_CREDENTIAL_INVALID",), info.blocker_codes)

    def test_shouldRejectExplicitEmptyWhitespaceAndNonStringCredentialsWithoutSettingsFallback(self):
        cases = [
            {"credentials": {"token": ""}},
            {"credentials": {"token": "   "}},
            {"credentials": {"token": 12345}},
        ]
        for connection_settings in cases:
            with self.subTest(connection_settings=connection_settings):
                profile = SyntheticProfile(
                    "jira-profile",
                    "jira",
                    {
                        "base_url": "https://jira.settings.example/jira",
                        "auth_mode": "server_pat",
                        **connection_settings,
                    },
                )
                resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

                with self.assertRaises(ProviderConnectionError) as context:
                    resolver.resolve_profile("jira-profile")

                self.assertEqual("PROVIDER_CREDENTIAL_INVALID", context.exception.code)


class TestProviderResolverExplicitInputs(unittest.TestCase):
    def test_shouldResolveJiraConfigWithoutReadingInjectedSettingsOrRegistryDefaults(self):
        resolver = ProviderConnectionResolver(ExplodingSettings(), SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url="https://jira.explicit.example/path",
            jira_email=None,
            jira_api_token="explicit-token",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
            verify_ssl=True,
            ca_bundle=None,
        )

        resolved = resolver.resolve_jira_config(config)
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("https://jira.explicit.example/path", resolved.info.endpoint.base_url)
        self.assertEqual("explicit-token", factory.kwargs["token"])

    def test_shouldResolveJiraSettingsFromPassedSettingsSourceOnly(self):
        resolver = ProviderConnectionResolver(ExplodingSettings(), SyntheticRegistry([]))

        resolved = resolver.resolve_jira_settings(SyntheticSettings())
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("https://jira.settings.example/jira", resolved.info.endpoint.base_url)
        self.assertEqual("settings-jira-token", factory.kwargs["token"])

    def test_shouldResolveServerPatSettingsWithoutEmail(self):
        settings_source = SyntheticSettings(METRICS_JIRA_EMAIL="")
        resolver = ProviderConnectionResolver(ExplodingSettings(), SyntheticRegistry([]))

        resolved = resolver.resolve_jira_settings(settings_source)
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("settings-jira-token", factory.kwargs["token"])
        self.assertNotIn("username", factory.kwargs)

    def test_shouldResolveHsdesIntegratedAuthAfterSettingsAuthModeReferenceIsNormalized(self):
        profile = SyntheticProfile(
            "hsdes-profile",
            "hsdes",
            {
                "base_url": "settings:METRICS_HSDES_API_BASE_URL",
                "auth_mode": "settings:METRICS_HSDES_AUTH_MODE",
                "transport": "powershell",
                "credential_ref": "settings:METRICS_HSDES_* or Windows Integrated Auth",
            },
        )
        settings_source = SyntheticSettings(METRICS_HSDES_AUTH_MODE="windows_integrated", METRICS_HSDES_HTTP_TRANSPORT="powershell")
        resolver = ProviderConnectionResolver(settings_source, SyntheticRegistry([profile]))

        resolved = resolver.resolve_profile("hsdes-profile")

        self.assertEqual("integrated", resolved.info.credential.kind)
        self.assertEqual("windows_integrated", resolved.info.endpoint.auth_mode)

    def test_shouldTreatCredentialAliasSettingsReferenceAsSettingsSourceNotInline(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credentials": {"api_token": "settings:METRICS_JIRA_API_TOKEN"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        resolved = resolver.resolve_profile("jira-profile")
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("settings", resolved.info.credential.kind)
        self.assertEqual("settings-jira-token", factory.kwargs["token"])


class TestProviderConfigurationValidation(unittest.TestCase):
    def test_shouldRejectUnsupportedAuthModesAndTransportCombinationsBeforeOpeningClients(self):
        cases = [
            ("jira", {"base_url": "https://jira.settings.example/jira", "auth_mode": "oauth", "credentials": {"token": "t"}}),
            ("hsdes", {"base_url": "https://hsdes.settings.example/rest", "auth_mode": "oauth", "credentials": {"token": "t"}}),
            ("hsdes", {"base_url": "https://hsdes.settings.example/rest", "auth_mode": "token", "transport": "powershell", "credentials": {"token": "t"}}),
        ]
        for provider_id, connection_settings in cases:
            with self.subTest(provider_id=provider_id, connection_settings=connection_settings):
                profile = SyntheticProfile(f"{provider_id}-profile", provider_id, connection_settings)
                resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

                with self.assertRaises(ProviderConnectionError) as context:
                    resolver.resolve_profile(profile.profile_id)

                self.assertEqual("PROVIDER_UNSUPPORTED", context.exception.code)

    def test_shouldRejectNonPositiveTimeoutAndNonBoolTlsVerification(self):
        cases = [
            {"timeout_seconds": 0},
            {"verify_ssl": "true"},
            {"verify_ssl": None},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                profile = SyntheticProfile(
                    "jira-profile",
                    "jira",
                    {
                        "base_url": "https://jira.settings.example/jira",
                        "auth_mode": "server_pat",
                        "credentials": {"token": "inline-token"},
                        **overrides,
                    },
                )
                resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

                with self.assertRaises(ProviderConnectionError) as context:
                    resolver.resolve_profile("jira-profile")

                self.assertIn(context.exception.code, {"PROVIDER_ENDPOINT_INVALID", "PROVIDER_TRUST_INVALID"})

    def test_shouldRejectCrossProviderSettingReferencesPerField(self):
        profile = SyntheticProfile(
            "hsdes-profile",
            "hsdes",
            {
                "base_url": "settings:METRICS_JIRA_SERVER_URL",
                "auth_mode": "token",
                "credentials": {"token": "hsdes-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        with self.assertRaises(ProviderConnectionError) as context:
            resolver.resolve_profile("hsdes-profile")

        self.assertEqual("PROVIDER_CREDENTIAL_INVALID", context.exception.code)


class TestProviderEndpointNormalizationDefects(unittest.TestCase):
    def test_shouldRejectAmbiguousUrlFormsWithSafeConnectionError(self):
        urls = [
            " https://jira.settings.example/jira",
            "https://@jira.settings.example/jira",
            "https://jira.settings.example:0/jira",
            "https://[bad",
            "https://jira.settings.example/%252fadmin",
            "https://jira.settings.example/%2e/admin",
            "https://jira.settings.example/%09/admin",
        ]
        for url in urls:
            with self.subTest(url=url):
                profile = SyntheticProfile(
                    "jira-profile",
                    "jira",
                    {"base_url": url, "auth_mode": "server_pat", "credentials": {"token": "inline-token"}},
                )
                resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

                with self.assertRaises(ProviderConnectionError) as context:
                    resolver.resolve_profile("jira-profile")

                self.assertEqual("PROVIDER_ENDPOINT_INVALID", context.exception.code)


class TestProviderPublicFacadeBoundary(unittest.TestCase):
    def test_shouldNotExportInternalSecretReturningProtectedStoreSpiFromPublicFacade(self):
        self.assertFalse(hasattr(public_provider_connections, "read_source_toml"))
        self.assertFalse(hasattr(public_provider_connections, "ProtectedCredentialStore"))
        self.assertFalse(hasattr(public_provider_connections, "SourceFileReceipt"))


class TestProviderFactoryAndTransportDefects(unittest.TestCase):
    def test_shouldPassTimeoutSecondsToJiraFactory(self):
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url="https://jira.explicit.example",
            jira_email=None,
            jira_api_token="explicit-token",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
            verify_ssl=True,
            ca_bundle=None,
        )

        resolved = resolver.resolve_jira_config(config)
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual(30, factory.kwargs["timeout"])

    def test_shouldConstructActualAtlassianJiraWithInjectedSessionAndNoNetwork(self):
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url="https://jira.explicit.example",
            jira_email=None,
            jira_api_token="explicit-token",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
        )

        resolved = resolver.resolve_jira_config(config)
        with patch.object(requests.Session, "send", side_effect=AssertionError("constructor must not send")):
            client = resolved.open_jira_client(Jira)

        self.assertIsNotNone(client)

    def test_shouldRejectIntegratedHsdesCustomCaBeforeReturningClient(self):
        profile = SyntheticProfile(
            "hsdes-profile",
            "hsdes",
            {
                "base_url": "https://hsdes.settings.example/rest",
                "auth_mode": "windows_integrated",
                "transport": "powershell",
                "ca_bundle": str(Path.cwd() / ".tmp" / "hsdes-ca.pem"),
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))
        resolved = resolver.resolve_profile("hsdes-profile")

        with self.assertRaises(ProviderConnectionError) as context:
            resolved.open_hsdes_client(CapturingHsdesFactory())

        self.assertEqual("PROVIDER_TRUST_INVALID", context.exception.code)

    def test_shouldCreateHsdesHttpsHandlerWithSelectedCustomCaForTokenAuth(self):
        ca_path = str(Path.cwd() / ".tmp" / "hsdes-ca.pem")
        profile = SyntheticProfile(
            "hsdes-profile",
            "hsdes",
            {
                "base_url": "https://hsdes.settings.example/rest",
                "auth_mode": "token",
                "ca_bundle": ca_path,
                "credentials": {"token": "hsdes-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        with patch.object(ssl, "create_default_context") as create_context:
            create_context.return_value = object()
            resolved = resolver.resolve_profile("hsdes-profile")
            resolved.open_hsdes_client(CapturingHsdesFactory())

        create_context.assert_called_once_with(cafile=ca_path)

    def test_shouldRejectArbitraryEncodedHsdesPowershellCommandsAndUseHiddenWindow(self):
        calls = []

        def successful_runner(args, **kwargs):
            calls.append((args, kwargs))
            return subprocess.CompletedProcess(args, 0, "{}", "")

        profile = SyntheticProfile(
            "hsdes-profile",
            "hsdes",
            {
                "base_url": "https://hsdes.settings.example/rest",
                "auth_mode": "windows_integrated",
                "transport": "powershell",
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))
        resolved = resolver.resolve_profile("hsdes-profile")
        factory = CapturingHsdesFactory()
        resolved.open_hsdes_client(factory)
        runner = factory.kwargs["powershell_runner"]
        runner.set_runner(successful_runner)

        self.assertFalse(callable(runner))
        runner.run("https://hsdes.settings.example/rest/query/execution/42", 30)

        expected_flag = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.assertEqual(expected_flag, calls[0][1]["creationflags"])

    def test_shouldMapActualUrllibRedirectHttpErrorToSafeConnectionErrorAndCloseBody(self):
        body = CloseTrackingBody()
        actual_opener = request.build_opener(RedirectingHttpsHandler(body))

        profile = SyntheticProfile(
            "hsdes-profile",
            "hsdes",
            {
                "base_url": "https://hsdes.settings.example/rest",
                "auth_mode": "token",
                "credentials": {"token": "hsdes-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))
        resolved = resolver.resolve_profile("hsdes-profile")
        factory = CapturingHsdesFactory()
        resolved.open_hsdes_client(factory)
        opener = factory.kwargs["opener"]
        opener.set_transport(actual_opener.open)

        with self.assertRaises(ProviderConnectionError) as context:
            opener(request.Request("https://hsdes.settings.example/rest/query/execution/42"), timeout=30)

        self.assertEqual("PROVIDER_REDIRECT_UNSUPPORTED", context.exception.code)
        self.assertTrue(body.closed)

    def test_shouldAllowOnlyHsdesReadMethodsBeforeSending(self):
        profile = SyntheticProfile(
            "hsdes-profile",
            "hsdes",
            {
                "base_url": "https://hsdes.settings.example/rest",
                "auth_mode": "token",
                "credentials": {"token": "hsdes-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))
        resolved = resolver.resolve_profile("hsdes-profile")
        factory = CapturingHsdesFactory()
        resolved.open_hsdes_client(factory)
        opener = factory.kwargs["opener"]
        transport = RecordingOpener()
        opener.set_transport(transport)

        opener(request.Request("https://hsdes.settings.example/rest/query/execution/42"), timeout=30)
        post_request = request.Request("https://hsdes.settings.example/rest/query/execution/42", data=b"{}")

        with self.assertRaises(ProviderConnectionError) as context:
            opener(post_request, timeout=30)

        self.assertEqual("PROVIDER_METHOD_FORBIDDEN", context.exception.code)
        self.assertEqual(1, len(transport.requests))


if __name__ == "__main__":
    unittest.main()
