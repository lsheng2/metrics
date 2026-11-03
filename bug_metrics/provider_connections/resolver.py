from typing import Any

from .contracts import ConnectionError, ConnectionInfo, CredentialResolution, CredentialSelection, CredentialSource, ProviderEndpoint, TlsResolution, TlsTrust
from .contracts import HSDES_AUTH_MODES, INTEGRATED_HSD_AUTH_MODES, JIRA_AUTH_MODES, SETTING_FIELDS
from .contracts import default_settings_reference, is_credential_settings_ref, is_protected_ref, is_settings_ref, record_value
from .handle import ResolvedConnection
from .normalization import endpoint_identifier, normalize_base_url, resolve_tls
class ProviderConnectionResolver:
    def __init__(self, settings_source, profile_registry, protected_store=None):
        self._settings = settings_source
        self._profile_registry = profile_registry
        self._protected_store = protected_store

    def resolve_profile(self, profile_id, *, expected_provider_id=None) -> ResolvedConnection:
        resolution = self._profile_registry.resolve_profile(profile_id)
        if resolution.profile is None:
            raise ConnectionError("PROVIDER_PROFILE_UNAVAILABLE")
        profile = resolution.profile
        if expected_provider_id and profile.provider_id != expected_provider_id:
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        return self.resolve_record(profile)
    def resolve_record(self, profile_record) -> ResolvedConnection:
        provider_id = str(record_value(profile_record, "provider_id", "") or "").strip().lower()
        profile_id = str(record_value(profile_record, "profile_id", "") or "").strip()
        connection_settings = dict(record_value(profile_record, "connection_settings", {}) or {})
        return self._resolve_from_connection_settings(provider_id, profile_id, connection_settings, "profile")

    def describe_profile(self, profile_id, *, expected_provider_id=None) -> ConnectionInfo:
        resolution = self._profile_registry.resolve_profile(profile_id)
        if resolution.profile is None:
            raise ConnectionError("PROVIDER_PROFILE_UNAVAILABLE")
        if expected_provider_id and resolution.profile.provider_id != expected_provider_id:
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        return self.describe_record(resolution.profile)
    def describe_record(self, profile_record) -> ConnectionInfo:
        provider_id = str(record_value(profile_record, "provider_id", "") or "").strip().lower()
        profile_id = str(record_value(profile_record, "profile_id", "") or "").strip()
        connection_settings = dict(record_value(profile_record, "connection_settings", {}) or {})
        return self._describe_from_connection_settings(provider_id, profile_id, connection_settings, "profile")
    def resolve_jira_settings(self, settings_source) -> ResolvedConnection:
        connection_settings = {
            "base_url": getattr(settings_source, "METRICS_JIRA_SERVER_URL", ""),
            "auth_mode": getattr(settings_source, "METRICS_JIRA_AUTH_MODE", "cloud_basic"),
            "verify_ssl": getattr(settings_source, "METRICS_JIRA_VERIFY_SSL", True), "ca_bundle": getattr(settings_source, "METRICS_JIRA_CA_BUNDLE", None),
            "credential_ref": "settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN",
        }
        return self._resolve_from_connection_settings("jira", "settings:jira", connection_settings, "settings", settings_source)

    def resolve_jira_config(self, jira_config) -> ResolvedConnection:
        connection_settings = {
            "base_url": jira_config.jira_server_url, "auth_mode": jira_config.auth_mode,
            "verify_ssl": jira_config.verify_ssl, "ca_bundle": jira_config.ca_bundle,
            "credentials": {"email": jira_config.jira_email, "api_token": jira_config.jira_api_token},
        }
        return self._resolve_from_connection_settings("jira", "explicit_config", connection_settings, "explicit_config")

    def status(self, profile_id) -> ConnectionInfo:
        try:
            return self.resolve_profile(profile_id).info
        except ConnectionError as error:
            endpoint = ProviderEndpoint("", "", "", "", 0, TlsTrust(False, "unavailable", "unavailable", ""), "")
            return ConnectionInfo(str(profile_id), endpoint, CredentialSource("unavailable", "", "unknown"), None, False, "blocked", (error.code,))

    def _resolve_from_connection_settings(
        self,
        provider_id: str,
        profile_id: str,
        connection_settings: dict[str, Any],
        source_kind: str,
        settings_source=None,
    ) -> ResolvedConnection:
        if provider_id not in {"jira", "hsdes"}:
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        settings_source = settings_source if settings_source is not None else self._settings
        base_url = self._connection_value(provider_id, connection_settings, "base_url", self._field_default(provider_id, "base_url", settings_source, source_kind), settings_source)
        auth_mode = self._normalized_auth_mode(provider_id, self._connection_value(provider_id, connection_settings, "auth_mode", self._field_default(provider_id, "auth_mode", settings_source, source_kind), settings_source))
        selection = self._classify_credential_source(provider_id, connection_settings, source_kind, auth_mode)
        transport = self._transport(provider_id, connection_settings, settings_source, source_kind)
        self._validate_transport(provider_id, auth_mode, transport)
        endpoint, tls = self._endpoint(provider_id, auth_mode, base_url, connection_settings, settings_source, source_kind, transport)
        credential = self._resolve_credential(provider_id, profile_id, endpoint, connection_settings, source_kind, settings_source, selection)
        info = ConnectionInfo(profile_id, endpoint, credential.source, None, False, "ready", ())
        return ResolvedConnection(info=info, material=credential.material, verify=tls.private_verify)

    def _describe_from_connection_settings(self, provider_id: str, profile_id: str, connection_settings: dict[str, Any], source_kind: str) -> ConnectionInfo:
        if provider_id not in {"jira", "hsdes"}:
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        base_url = self._connection_value(provider_id, connection_settings, "base_url", self._field_default(provider_id, "base_url", self._settings, source_kind), self._settings)
        auth_mode = self._normalized_auth_mode(provider_id, self._connection_value(provider_id, connection_settings, "auth_mode", self._field_default(provider_id, "auth_mode", self._settings, source_kind), self._settings))
        selection = self._classify_credential_source(provider_id, connection_settings, source_kind, auth_mode)
        transport = self._transport(provider_id, connection_settings, self._settings, source_kind)
        self._validate_transport(provider_id, auth_mode, transport)
        endpoint, _ = self._endpoint(provider_id, auth_mode, base_url, connection_settings, self._settings, source_kind, transport)
        credential = CredentialSource(selection.kind, selection.reference, selection.revision)
        return ConnectionInfo(profile_id, endpoint, credential, None, False, "ready", ())

    def _endpoint(self, provider_id, auth_mode, base_url, connection_settings, settings_source, source_kind, transport):
        normalized = normalize_base_url(base_url)
        tls = self._resolve_tls(provider_id, connection_settings, settings_source)
        endpoint = ProviderEndpoint(provider_id, normalized.base_url, endpoint_identifier(provider_id, normalized.base_url, auth_mode), auth_mode, self._timeout_seconds(provider_id, connection_settings, settings_source, source_kind), tls.public, transport)
        return endpoint, tls

    def _classify_credential_source(self, provider_id: str, connection_settings: dict[str, Any], source_kind: str, auth_mode: str) -> CredentialSelection:
        self._validate_explicit_references(provider_id, connection_settings)
        protected = self._protected_reference(connection_settings)
        if protected is not None:
            return CredentialSelection("protected", protected["reference"], protected["revision"])
        if (provider_id == "hsdes" and auth_mode in INTEGRATED_HSD_AUTH_MODES
                and not self._has_literal_credential_alias(provider_id, connection_settings)):
            return CredentialSelection("integrated", "windows-integrated", "unknown:windows_integrated")
        if (connection_settings.get("credential_ref") == "profile:local"
                or connection_settings.get("credential_storage") == "profile_local"):
            return CredentialSelection("inline", "profile:local", "unknown:profile")
        if self._has_literal_credential_alias(provider_id, connection_settings):
            return CredentialSelection("explicit_config" if source_kind == "explicit_config" else "inline", source_kind, f"unknown:{source_kind}")
        if self._has_settings_credential_alias(provider_id, connection_settings):
            return CredentialSelection("settings", default_settings_reference(provider_id), "unknown:settings")
        if provider_id == "hsdes" and auth_mode in INTEGRATED_HSD_AUTH_MODES:
            return CredentialSelection("integrated", "windows-integrated", "unknown:windows_integrated")
        credential_ref = connection_settings.get("credential_ref")
        if is_credential_settings_ref(provider_id, credential_ref) or credential_ref in {None, ""}:
            return CredentialSelection("settings", str(credential_ref or default_settings_reference(provider_id)), "unknown:settings")
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")

    def _resolve_tls(self, provider_id: str, connection_settings: dict[str, Any], settings_source) -> TlsResolution:
        verify_ssl = self._connection_value(provider_id, connection_settings, "verify_ssl", True, settings_source)
        ca_bundle = self._connection_value(provider_id, connection_settings, "ca_bundle", None, settings_source)
        return resolve_tls(verify_ssl, ca_bundle)

    def _resolve_credential(
        self,
        provider_id: str,
        profile_id: str,
        endpoint: ProviderEndpoint,
        connection_settings: dict[str, Any],
        source_kind: str,
        settings_source,
        selection: CredentialSelection,
    ) -> CredentialResolution:
        if selection.kind == "protected":
            return self._resolve_protected_credential(provider_id, profile_id, endpoint, selection)
        if selection.kind in {"inline", "explicit_config"}:
            source = CredentialSource(selection.kind, selection.reference, selection.revision)
            return CredentialResolution(source, self._inline_credential(provider_id, endpoint.auth_mode, connection_settings))
        if selection.kind == "integrated":
            return CredentialResolution(CredentialSource("integrated", selection.reference, selection.revision), {"token": "", "username": "", "password": ""})
        if source_kind not in {"settings", "explicit_config"}:
            self._require_settings_endpoint_match(provider_id, endpoint, settings_source)
        return self._settings_credential(provider_id, endpoint.auth_mode, settings_source, selection.reference)

    def _resolve_protected_credential(self, provider_id: str, profile_id: str, endpoint: ProviderEndpoint, selection: CredentialSelection) -> CredentialResolution:
        if self._protected_store is None or not all(hasattr(self._protected_store, name) for name in ["create_candidate", "read_selected", "list_unreferenced"]):
            raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE")
        if not selection.reference or not selection.revision:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        try:
            token = self._protected_store.read_selected(
                reference=selection.reference, revision=selection.revision, provider_id=provider_id,
                profile_id=profile_id, endpoint_id=endpoint.endpoint_id, auth_mode=endpoint.auth_mode,
            )
        except ConnectionError:
            raise
        except Exception:
            raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE") from None
        if not isinstance(token, str) or not token.strip():
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        return CredentialResolution(CredentialSource("protected", selection.reference, selection.revision), {"token": token, "username": "", "password": ""})

    def _settings_credential(self, provider_id: str, auth_mode: str, settings_source, reference: str) -> CredentialResolution:
        if provider_id == "jira":
            token = self._settings_secret(settings_source, "METRICS_JIRA_API_TOKEN")
            email = "" if auth_mode == "server_pat" else self._settings_secret(settings_source, "METRICS_JIRA_EMAIL")
            return CredentialResolution(CredentialSource("settings", reference, "unknown:settings"), self._jira_material(auth_mode, token, email))
        if auth_mode == "token":
            token = self._settings_secret(settings_source, "METRICS_HSDES_TOKEN")
            return CredentialResolution(CredentialSource("settings", reference, "unknown:settings"), {"token": token, "username": "", "password": ""})
        if auth_mode == "basic":
            username = self._settings_secret(settings_source, "METRICS_HSDES_USERNAME")
            password = self._settings_secret(settings_source, "METRICS_HSDES_PASSWORD")
            return CredentialResolution(CredentialSource("settings", reference, "unknown:settings"), {"token": "", "username": username, "password": password})
        raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE")

    def _inline_credential(self, provider_id: str, auth_mode: str, connection_settings: dict[str, Any]) -> dict[str, str]:
        if provider_id == "jira":
            token = self._required_literal(connection_settings, ["api_token", "token", "password"])
            email = self._optional_literal(connection_settings, ["email", "username"])
            return self._jira_material(auth_mode, token, email or "")
        if provider_id == "hsdes" and auth_mode == "token":
            token = self._required_literal(connection_settings, ["api_token", "token"])
            return {"token": token, "username": "", "password": ""}
        if provider_id == "hsdes" and auth_mode == "basic":
            username = self._required_literal(connection_settings, ["username"])
            password = self._required_literal(connection_settings, ["password"])
            return {"token": "", "username": username, "password": password}
        raise ConnectionError("PROVIDER_UNSUPPORTED")

    def _jira_material(self, auth_mode: str, token: str, email: str) -> dict[str, str]:
        if not token:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        if auth_mode != "server_pat" and not email:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        return {"token": token, "username": "" if auth_mode == "server_pat" else email, "password": ""}

    def _protected_reference(self, connection_settings: dict[str, Any]) -> dict[str, str] | None:
        source = connection_settings.get("credential_source")
        if isinstance(source, dict) and source.get("kind") == "protected":
            return {"reference": self._protected_reference_value(source.get("reference")), "revision": self._revision_value(source.get("revision"))}
        credential_storage = connection_settings.get("credential_storage")
        credential_ref = connection_settings.get("credential_ref")
        if credential_storage == "protected_file" or is_protected_ref(credential_ref):
            return {"reference": self._protected_reference_value(credential_ref), "revision": self._revision_value(connection_settings.get("credential_revision"))}
        return None

    def _protected_reference_value(self, value) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        if not is_protected_ref(value):
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        return value.strip()

    def _revision_value(self, value) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        return value.strip()

    def _validate_explicit_references(self, provider_id: str, connection_settings: dict[str, Any]) -> None:
        credential_ref = connection_settings.get("credential_ref")
        if credential_ref is None or credential_ref == "":
            return
        if credential_ref == "profile:local":
            return
        if is_credential_settings_ref(provider_id, credential_ref) or is_protected_ref(credential_ref):
            return
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")

    def _has_literal_credential_alias(self, provider_id: str, connection_settings: dict[str, Any]) -> bool:
        if provider_id == "jira":
            return self._aliases_present(connection_settings, ["api_token", "token", "password", "email", "username"], settings_ref=False)
        if provider_id == "hsdes":
            return self._aliases_present(connection_settings, ["api_token", "token", "password", "username"], settings_ref=False)
        return False

    def _has_settings_credential_alias(self, provider_id: str, connection_settings: dict[str, Any]) -> bool:
        if provider_id == "jira":
            return self._aliases_present(connection_settings, ["api_token", "token", "password", "email", "username"], settings_ref=True)
        if provider_id == "hsdes":
            return self._aliases_present(connection_settings, ["api_token", "token", "password", "username"], settings_ref=True)
        return False

    def _required_literal(self, connection_settings: dict[str, Any], aliases: list[str]) -> str:
        value = self._selected_literal(connection_settings, aliases)
        if value is None:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        return value

    def _optional_literal(self, connection_settings: dict[str, Any], aliases: list[str]) -> str | None:
        values = []
        for source in [dict(connection_settings.get("credentials") or {}), connection_settings]:
            for alias in aliases:
                if alias not in source:
                    continue
                value = source[alias]
                if is_settings_ref(value) or value in {None, ""}:
                    continue
                if not isinstance(value, str) or not value.strip():
                    continue
                values.append(value)
        if not values:
            return None
        if len(set(values)) > 1:
            raise ConnectionError("PROVIDER_CREDENTIAL_CONFLICT")
        return values[0]

    def _selected_literal(self, connection_settings: dict[str, Any], aliases: list[str]) -> str | None:
        values = []
        present = False
        for source in [dict(connection_settings.get("credentials") or {}), connection_settings]:
            for alias in aliases:
                if alias not in source:
                    continue
                present = True
                value = source[alias]
                if is_settings_ref(value):
                    continue
                values.append(self._literal_secret_value(value))
        if not values:
            if present:
                raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
            return None
        if len(set(values)) > 1:
            raise ConnectionError("PROVIDER_CREDENTIAL_CONFLICT")
        return values[0]

    def _literal_secret_value(self, value) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        return value

    def _aliases_present(self, connection_settings: dict[str, Any], aliases: list[str], *, settings_ref: bool) -> bool:
        credentials = dict(connection_settings.get("credentials") or {})
        for source in [credentials, connection_settings]:
            for alias in aliases:
                if alias in source and is_settings_ref(source[alias]) is settings_ref:
                    return True
        return False

    def _require_settings_endpoint_match(self, provider_id: str, endpoint: ProviderEndpoint, settings_source) -> None:
        deployment_base_url = normalize_base_url(self._deployment_base_url(provider_id, settings_source)).base_url
        deployment_auth_mode = self._deployment_auth_mode(provider_id, settings_source)
        if endpoint.base_url != deployment_base_url or endpoint.auth_mode != deployment_auth_mode:
            raise ConnectionError("PROVIDER_ENDPOINT_CREDENTIAL_MISMATCH")

    def _connection_value(self, provider_id: str, connection_settings: dict[str, Any], key: str, default, settings_source):
        if key not in connection_settings:
            return default
        value = connection_settings[key]
        if value == "":
            return default
        if is_settings_ref(value):
            return self._setting_reference_value(provider_id, key, str(value), settings_source)
        return value

    def _setting_reference_value(self, provider_id: str, field_name: str, reference: str, settings_source):
        allowed = SETTING_FIELDS.get(provider_id, {}).get(field_name, {})
        if reference not in allowed:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        return getattr(settings_source, allowed[reference])

    def _field_default(self, provider_id: str, field_name: str, settings_source, source_kind: str):
        if source_kind == "explicit_config":
            return ""
        if field_name == "base_url":
            return self._deployment_base_url(provider_id, settings_source)
        if field_name == "auth_mode":
            return self._deployment_auth_mode(provider_id, settings_source)
        return ""

    def _deployment_base_url(self, provider_id: str, settings_source) -> str:
        if provider_id == "jira":
            return getattr(settings_source, "METRICS_JIRA_SERVER_URL", "")
        return getattr(settings_source, "METRICS_HSDES_API_BASE_URL", "")

    def _deployment_auth_mode(self, provider_id: str, settings_source) -> str:
        if provider_id == "jira":
            return getattr(settings_source, "METRICS_JIRA_AUTH_MODE", "")
        return getattr(settings_source, "METRICS_HSDES_AUTH_MODE", "")

    def _normalized_auth_mode(self, provider_id: str, value) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        auth_mode = value.strip()
        if provider_id == "jira" and auth_mode not in JIRA_AUTH_MODES:
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        if provider_id == "hsdes" and auth_mode not in HSDES_AUTH_MODES:
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        return auth_mode

    def _transport(self, provider_id: str, connection_settings: dict[str, Any], settings_source, source_kind: str) -> str:
        if provider_id != "hsdes":
            return "requests"
        default = "auto" if source_kind == "explicit_config" else getattr(settings_source, "METRICS_HSDES_HTTP_TRANSPORT", "auto")
        transport = self._connection_value(provider_id, connection_settings, "transport", default, settings_source)
        if not isinstance(transport, str) or not transport.strip():
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        return transport.strip()

    def _validate_transport(self, provider_id: str, auth_mode: str, transport: str) -> None:
        if provider_id != "hsdes":
            return
        if transport not in {"auto", "requests", "urllib", "powershell"}:
            raise ConnectionError("PROVIDER_UNSUPPORTED")
        if transport == "powershell" and auth_mode not in INTEGRATED_HSD_AUTH_MODES:
            raise ConnectionError("PROVIDER_UNSUPPORTED")

    def _timeout_seconds(self, provider_id: str, connection_settings: dict[str, Any], settings_source, source_kind: str) -> int:
        default = 30 if provider_id != "hsdes" or source_kind == "explicit_config" else getattr(settings_source, "METRICS_HSDES_TIMEOUT_SECONDS", 30)
        value = self._connection_value(provider_id, connection_settings, "timeout_seconds", default, settings_source)
        if isinstance(value, bool):
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
        try:
            timeout_seconds = int(value)
        except (TypeError, ValueError):
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID") from None
        if timeout_seconds <= 0 or timeout_seconds > 300:
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
        return timeout_seconds

    def _settings_secret(self, settings_source, name: str) -> str:
        value = getattr(settings_source, name, "")
        if not isinstance(value, str) or not value.strip():
            raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE")
        return value
