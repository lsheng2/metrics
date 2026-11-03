import base64
import os
import pickle
import subprocess
import unittest
from dataclasses import asdict, dataclass, field
from pathlib import Path
from unittest.mock import patch
from urllib import request

import requests

from bug_metrics.app.api.provider_connections import (
    ConnectionError as ProviderConnectionError,
    ProviderConnectionResolver,
)
from tasks.app.domain.model.config import JiraConfig


@dataclass(slots=True)
class SyntheticSettings:
    METRICS_JIRA_SERVER_URL: str = "https://jira.settings.example/jira"
    METRICS_JIRA_AUTH_MODE: str = "server_pat"
    METRICS_JIRA_EMAIL: str = "settings-user@example.com"
    METRICS_JIRA_API_TOKEN: str = "settings-jira-token"
    METRICS_JIRA_VERIFY_SSL: bool = True
    METRICS_JIRA_CA_BUNDLE: str | None = None
    METRICS_HSDES_API_BASE_URL: str = "https://hsdes.settings.example/rest"
    METRICS_HSDES_AUTH_MODE: str = "kerberos"
    METRICS_HSDES_HTTP_TRANSPORT: str = "auto"
    METRICS_HSDES_USERNAME: str = ""
    METRICS_HSDES_PASSWORD: str = ""
    METRICS_HSDES_TOKEN: str = ""
    METRICS_HSDES_TIMEOUT_SECONDS: int = 30


@dataclass(slots=True)
class SyntheticProfile:
    profile_id: str
    provider_id: str
    connection_settings: dict
    enabled: bool = True


@dataclass(slots=True)
class SyntheticProfileResolution:
    status: str
    profile_id: str
    provider_id: str
    profile: SyntheticProfile | None
    blockers: list[dict[str, str]] = field(default_factory=list)


class SyntheticRegistry:
    def __init__(self, profiles):
        self._profiles = {profile.profile_id: profile for profile in profiles}

    def resolve_profile(self, profile_id):
        profile = self._profiles.get(profile_id)
        if profile is None:
            return SyntheticProfileResolution("unsupported", profile_id, "", None, [{"code": "profile_not_found"}])
        return SyntheticProfileResolution("available", profile.profile_id, profile.provider_id, profile, [])


class CapturingJiraFactory:
    def __init__(self):
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return CapturedClient(kwargs)


@dataclass(slots=True)
class CapturedClient:
    kwargs: dict


class CapturingHsdesFactory:
    def __init__(self):
        self.kwargs = None

    def __call__(self, **kwargs):
        self.kwargs = kwargs
        return CapturedClient(kwargs)


class ProtectedStore:
    def __init__(self, token="protected-token"):
        self.token = token
        self.reads = []

    def read_selected(self, *, reference, revision, provider_id, profile_id, endpoint_id, auth_mode):
        self.reads.append({
            "reference": reference,
            "revision": revision,
            "provider_id": provider_id,
            "profile_id": profile_id,
            "endpoint_id": endpoint_id,
            "auth_mode": auth_mode,
        })
        return self.token

    def create_candidate(self, **kwargs):
        raise AssertionError("adoption is outside W3.CREDENTIALS.A")

    def list_unreferenced(self, profile_references):
        return ()


class RecordingAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, status_code=200, headers=None):
        super().__init__()
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.requests = []
        self.send_kwargs = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        self.send_kwargs.append(kwargs)
        response = requests.Response()
        response.status_code = self.status_code
        response.url = request.url
        response.request = request
        response.headers.update(self.headers)
        response._content = b"{}"
        return response


class FakeHttpResponse:
    def __init__(self, status_code=200, body=b"{}"):
        self.status = status_code
        self.code = status_code
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def getcode(self):
        return self.status

    def read(self):
        return self._body


class RecordingOpener:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.requests = []

    def __call__(self, http_request, timeout=None):
        self.requests.append((http_request, timeout))
        return FakeHttpResponse(self.status_code)


class TestProviderConnectionResolver(unittest.TestCase):
    def test_shouldResolveJiraSettingsCredentialOnlyWhenEndpointAndAuthMatchDeployment(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://JIRA.Settings.Example:443/jira/",
                "auth_mode": "server_pat",
                "credential_ref": "settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN",
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        resolved = resolver.resolve_profile("jira-profile")
        factory = CapturingJiraFactory()
        client = resolved.open_jira_client(factory)

        self.assertIsInstance(client, CapturedClient)
        self.assertEqual("settings", resolved.info.credential.kind)
        self.assertEqual("unknown:settings", resolved.info.credential.revision)
        self.assertEqual("https://jira.settings.example/jira", resolved.info.endpoint.base_url)
        self.assertEqual("settings-jira-token", factory.kwargs["token"])
        self.assertNotIn("settings-jira-token", repr(resolved))
        self.assertNotIn("settings-jira-token", repr(resolved.info))

    def test_shouldRejectSettingsCredentialWhenProfileEndpointDriftsFromDeployment(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.other.example/jira",
                "auth_mode": "server_pat",
                "credential_ref": "settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN",
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        with self.assertRaises(ProviderConnectionError) as context:
            resolver.resolve_profile("jira-profile")

        self.assertEqual("PROVIDER_ENDPOINT_CREDENTIAL_MISMATCH", context.exception.code)

    def test_shouldRejectConflictingCredentialAliasesInsteadOfChoosingInsertionOrder(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.settings.example/jira",
                "auth_mode": "server_pat",
                "credentials": {"token": "first-token", "api_token": "second-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        with self.assertRaises(ProviderConnectionError) as context:
            resolver.resolve_profile("jira-profile")

        self.assertEqual("PROVIDER_CREDENTIAL_CONFLICT", context.exception.code)

    def test_shouldFailProtectedCredentialWithoutInjectedStoreInsteadOfFallingBackToSettings(self):
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

    def test_shouldReadProtectedCredentialWithExactEndpointBinding(self):
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
        store = ProtectedStore()
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]), protected_store=store)

        resolved = resolver.resolve_profile("jira-profile")
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("protected", resolved.info.credential.kind)
        self.assertEqual("protected:pcred_0123456789abcdef0123456789abcdef", resolved.info.credential.reference)
        self.assertEqual("rev-a", resolved.info.credential.revision)
        self.assertEqual("protected-token", factory.kwargs["token"])
        self.assertEqual("jira-profile", store.reads[0]["profile_id"])
        self.assertEqual(resolved.info.endpoint.endpoint_id, store.reads[0]["endpoint_id"])

    def test_shouldResolveExplicitJiraConfigWithoutGlobalSettingsOrProfileRegistry(self):
        settings_source = SyntheticSettings(
            METRICS_JIRA_SERVER_URL="https://wrong.example",
            METRICS_JIRA_API_TOKEN="wrong-token",
        )
        resolver = ProviderConnectionResolver(settings_source, SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url="https://jira.explicit.example/path",
            jira_email="explicit-user@example.com",
            jira_api_token="explicit-token",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
            verify_ssl=True,
            ca_bundle=None,
        )

        resolved = resolver.resolve_jira_config(config)
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("explicit_config", resolved.info.credential.kind)
        self.assertEqual("https://jira.explicit.example/path", resolved.info.endpoint.base_url)
        self.assertEqual("explicit-token", factory.kwargs["token"])

    def test_shouldRejectFalseTlsVerificationForProductionConnections(self):
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url="https://jira.explicit.example",
            jira_email=None,
            jira_api_token="explicit-token",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
            verify_ssl=False,
            ca_bundle=None,
        )

        with self.assertRaises(ProviderConnectionError) as context:
            resolver.resolve_jira_config(config)

        self.assertEqual("PROVIDER_TRUST_INVALID", context.exception.code)

    def test_shouldHideCustomCaPathInPublicStatusAndPassItPrivatelyToJiraFactory(self):
        ca_path = str(Path(os.getcwd()) / ".tmp" / "provider-ca.pem")
        global_ca_path = str(Path(os.getcwd()) / ".tmp" / "wrong-global-ca.pem")
        resolver = ProviderConnectionResolver(SyntheticSettings(METRICS_JIRA_CA_BUNDLE=global_ca_path), SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url="https://jira.explicit.example",
            jira_email=None,
            jira_api_token="explicit-token",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
            verify_ssl=True,
            ca_bundle=ca_path,
        )

        resolved = resolver.resolve_jira_config(config)
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)

        self.assertEqual("custom_ca", resolved.info.endpoint.tls.source)
        self.assertEqual("configured-ca", resolved.info.endpoint.tls.reference)
        self.assertNotIn(ca_path, repr(resolved.info))
        self.assertNotIn(ca_path, str(asdict(resolved.info)))
        self.assertNotIn(global_ca_path, str(asdict(resolved.info)))
        self.assertNotIn("explicit-token", str(asdict(resolved.info)))
        self.assertEqual(ca_path, factory.kwargs["verify_ssl"])

    def test_shouldRejectAmbiguousEndpointFormsBeforeCredentialsAreUsed(self):
        profile = SyntheticProfile(
            "jira-profile",
            "jira",
            {
                "base_url": "https://jira.settings.example/%2fadmin",
                "auth_mode": "server_pat",
                "credentials": {"token": "inline-token"},
            },
        )
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))

        with self.assertRaises(ProviderConnectionError) as context:
            resolver.resolve_profile("jira-profile")

        self.assertEqual("PROVIDER_ENDPOINT_INVALID", context.exception.code)

    def test_shouldMakeResolvedConnectionSafeToRepresentAndImpossibleToPickle(self):
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url="https://jira.explicit.example",
            jira_email=None,
            jira_api_token="pickle-token",
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
        )
        resolved = resolver.resolve_jira_config(config)

        with self.assertRaises(TypeError):
            pickle.dumps(resolved)

        self.assertNotIn("pickle-token", repr(resolved))


class TestJiraBoundSession(unittest.TestCase):
    def _session_for(self, base_url="https://jira.example/jira", token="selected-token"):
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([]))
        config = JiraConfig(
            jira_server_url=base_url,
            jira_email=None,
            jira_api_token=token,
            story_point_custom_field_id="customfield_10016",
            auth_mode="server_pat",
        )
        resolved = resolver.resolve_jira_config(config)
        factory = CapturingJiraFactory()
        resolved.open_jira_client(factory)
        return factory.kwargs["session"], factory.kwargs

    def test_shouldRejectWrongOriginAndBasePathBeforeSendingJiraRequest(self):
        session, _ = self._session_for()
        adapter = RecordingAdapter()
        session.mount("https://", adapter)

        with self.assertRaises(ProviderConnectionError) as context:
            session.get("https://evil.example/jira/rest/api/2/search")

        self.assertEqual("PROVIDER_ENDPOINT_INVALID", context.exception.code)
        self.assertEqual(0, len(adapter.requests))

        with self.assertRaises(ProviderConnectionError):
            session.get("https://jira.example/other/rest/api/2/search")
        self.assertEqual(0, len(adapter.requests))

    def test_shouldRejectJiraRedirectAfterOneSendAndNeverFollowIt(self):
        session, _ = self._session_for()
        adapter = RecordingAdapter(302, {"Location": "https://evil.example/"})
        session.mount("https://", adapter)

        with self.assertRaises(ProviderConnectionError) as context:
            session.get("https://jira.example/jira/rest/api/2/search")

        self.assertEqual("PROVIDER_REDIRECT_UNSUPPORTED", context.exception.code)
        self.assertEqual(1, len(adapter.requests))

    def test_shouldKeepOneCredentialWhenJiraReturnsUnauthorized(self):
        session, _ = self._session_for(token="selected-token")
        adapter = RecordingAdapter(401)
        session.mount("https://", adapter)

        response = session.get("https://jira.example/jira/rest/api/2/search")

        self.assertEqual(401, response.status_code)
        self.assertEqual(1, len(adapter.requests))
        self.assertEqual("Bearer selected-token", adapter.requests[0].headers["Authorization"])

    def test_shouldAllowOnlyJiraReadSearchPostAndReadMethods(self):
        session, _ = self._session_for()
        adapter = RecordingAdapter()
        session.mount("https://", adapter)

        session.get("https://jira.example/jira/rest/api/2/search")
        session.head("https://jira.example/jira/rest/api/3/search")
        session.post("https://jira.example/jira/rest/api/latest/search", json={"jql": "project = TEST"})

        self.assertEqual(3, len(adapter.requests))
        for method, url in [
            ("POST", "https://jira.example/jira/rest/api/2/issue"),
            ("PUT", "https://jira.example/jira/rest/api/2/search"),
            ("PATCH", "https://jira.example/jira/rest/api/2/search"),
            ("DELETE", "https://jira.example/jira/rest/api/2/search"),
        ]:
            with self.assertRaises(ProviderConnectionError) as context:
                session.request(method, url)
            self.assertEqual("PROVIDER_METHOD_FORBIDDEN", context.exception.code)
        self.assertEqual(3, len(adapter.requests))

    def test_shouldDisableRetriesCookiesNetrcAndRetainExplicitCorporateProxy(self):
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://proxy.example:914"}, clear=False):
            session, kwargs = self._session_for()
        adapter = RecordingAdapter()
        session.mount("https://", adapter)
        session.cookies.set("sessionid", "browser-cookie", domain="jira.example")

        session.get("https://jira.example/jira/rest/api/2/search", headers={"Cookie": "manual-cookie=1"})

        self.assertFalse(session.trust_env)
        self.assertEqual(False, kwargs["backoff_and_retry"])
        self.assertEqual(False, kwargs["retry_with_header"])
        self.assertIn("https", session.proxies)
        self.assertNotIn("Cookie", adapter.requests[0].headers)


class TestHsdesBoundTransport(unittest.TestCase):
    def _hsdes_client_args(self, connection_settings):
        profile = SyntheticProfile("hsdes-profile", "hsdes", connection_settings)
        resolver = ProviderConnectionResolver(SyntheticSettings(), SyntheticRegistry([profile]))
        resolved = resolver.resolve_profile("hsdes-profile")
        factory = CapturingHsdesFactory()
        resolved.open_hsdes_client(factory)
        return factory.kwargs

    def test_shouldRejectHsdesWrongOriginBeforeAuthAndSend(self):
        kwargs = self._hsdes_client_args({
            "base_url": "https://hsdes.settings.example/rest",
            "auth_mode": "token",
            "credentials": {"token": "hsdes-token"},
        })
        opener = kwargs["opener"]
        transport = RecordingOpener()
        opener.set_transport(transport)
        http_request = request.Request("https://evil.example/rest/query/execution/42")
        http_request.add_header("Authorization", "Bearer hsdes-token")

        with self.assertRaises(ProviderConnectionError) as context:
            opener(http_request, timeout=30)

        self.assertEqual("PROVIDER_ENDPOINT_INVALID", context.exception.code)
        self.assertEqual(0, len(transport.requests))

    def test_shouldRejectHsdesRedirectAfterSingleEndpointCall(self):
        kwargs = self._hsdes_client_args({
            "base_url": "https://hsdes.settings.example/rest",
            "auth_mode": "token",
            "credentials": {"token": "hsdes-token"},
        })
        opener = kwargs["opener"]
        transport = RecordingOpener(302)
        opener.set_transport(transport)
        http_request = request.Request("https://hsdes.settings.example/rest/query/execution/42")
        http_request.add_header("Authorization", "Bearer hsdes-token")

        with self.assertRaises(ProviderConnectionError) as context:
            opener(http_request, timeout=30)

        self.assertEqual("PROVIDER_REDIRECT_UNSUPPORTED", context.exception.code)
        self.assertEqual(1, len(transport.requests))

    def test_shouldProvideSelectedHsdesAuthOnlyToFactory(self):
        kwargs = self._hsdes_client_args({
            "base_url": "https://hsdes.settings.example/rest",
            "auth_mode": "token",
            "credentials": {"token": "hsdes-token"},
        })

        self.assertEqual("token", kwargs["auth_mode"])
        self.assertEqual("hsdes-token", kwargs["token"])
        self.assertEqual("", kwargs["username"])
        self.assertEqual("", kwargs["password"])

    def test_shouldBuildIntegratedHsdesPowerShellRequestWithNoRedirects(self):
        kwargs = self._hsdes_client_args({
            "base_url": "https://hsdes.settings.example/rest",
            "auth_mode": "windows_integrated",
            "transport": "powershell",
        })
        runner = kwargs["powershell_runner"]
        command = runner.build_command("https://hsdes.settings.example/rest/query/execution/42", 30)
        script = base64.b64decode(command[-1]).decode("utf-16le")

        self.assertIn("-MaximumRedirection 0", script)
        self.assertIn("-UseDefaultCredentials", script)
        with self.assertRaises(ProviderConnectionError) as context:
            runner.run("https://evil.example/rest/query/execution/42", 30)
        self.assertEqual("PROVIDER_ENDPOINT_INVALID", context.exception.code)

    def test_shouldReturnSafeFailureWhenIntegratedHsdesPowerShellFails(self):
        calls = []

        def failing_runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 1, "", "401 token-canary")

        kwargs = self._hsdes_client_args({
            "base_url": "https://hsdes.settings.example/rest",
            "auth_mode": "windows_integrated",
            "transport": "powershell",
        })
        runner = kwargs["powershell_runner"]
        runner.set_runner(failing_runner)

        with self.assertRaises(ProviderConnectionError) as context:
            runner.run("https://hsdes.settings.example/rest/query/execution/42", 30)

        self.assertEqual("PROVIDER_AUTH_FAILED", context.exception.code)
        self.assertEqual(1, len(calls))
        self.assertNotIn("token-canary", str(context.exception))


if __name__ == "__main__":
    unittest.main()
