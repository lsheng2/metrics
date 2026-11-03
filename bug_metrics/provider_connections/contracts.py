from dataclasses import dataclass


ERROR_MESSAGES = {
    "PROVIDER_PROFILE_UNAVAILABLE": "Provider profile is unavailable.",
    "PROVIDER_UNSUPPORTED": "Provider is not supported.",
    "PROVIDER_ENDPOINT_INVALID": "Provider endpoint is invalid.",
    "PROVIDER_ENDPOINT_CREDENTIAL_MISMATCH": "Provider endpoint and credential source do not match.",
    "PROVIDER_TRUST_INVALID": "Provider TLS trust configuration is invalid.",
    "PROVIDER_CREDENTIAL_UNAVAILABLE": "Provider credential is unavailable.",
    "PROVIDER_CREDENTIAL_INVALID": "Provider credential is invalid.",
    "PROVIDER_CREDENTIAL_UNPROTECTED": "Provider credential file is not protected.",
    "PROVIDER_CREDENTIAL_PLATFORM_UNSUPPORTED": "Provider credential platform is unsupported.",
    "PROVIDER_CREDENTIAL_CONFLICT": "Provider credential selection conflicts.",
    "PROVIDER_CREDENTIAL_CAS_MISMATCH": "Provider credential preview is stale.",
    "PROVIDER_REDIRECT_UNSUPPORTED": "Provider redirect is not supported.",
    "PROVIDER_METHOD_FORBIDDEN": "Provider request method is forbidden.",
    "PROVIDER_AUTH_FAILED": "Provider authentication failed.",
    "PROVIDER_PERMISSION_DENIED": "Provider permission was denied.",
    "PROVIDER_NETWORK_ERROR": "Provider network request failed.",
    "PROVIDER_BUSY": "Provider credential store is busy.",
    "INVALID_ARGUMENTS": "Arguments are invalid.",
    "INTERNAL_ERROR": "Internal provider connection error.",
}


class ConnectionError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(ERROR_MESSAGES.get(code, ERROR_MESSAGES["INTERNAL_ERROR"]))


@dataclass(frozen=True, slots=True)
class TlsTrust:
    verification: bool
    source: str
    reference: str
    readiness_id: str


@dataclass(frozen=True, slots=True)
class ProviderEndpoint:
    provider_id: str
    base_url: str
    endpoint_id: str
    auth_mode: str
    timeout_seconds: int
    tls: TlsTrust
    transport: str


@dataclass(frozen=True, slots=True)
class CredentialSource:
    kind: str
    reference: str
    revision: str


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    profile_id: str
    endpoint: ProviderEndpoint
    credential: CredentialSource
    principal_id: str | None
    principal_verified: bool
    readiness: str
    blocker_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CredentialResolution:
    source: CredentialSource
    material: dict[str, str]


@dataclass(frozen=True, slots=True)
class TlsResolution:
    public: TlsTrust
    private_verify: bool | str


@dataclass(frozen=True, slots=True)
class CredentialSelection:
    kind: str
    reference: str
    revision: str


JIRA_AUTH_MODES = frozenset({"server_pat", "cloud_basic"})
HSDES_AUTH_MODES = frozenset({"token", "basic", "kerberos", "windows_integrated"})
INTEGRATED_HSD_AUTH_MODES = frozenset({"kerberos", "windows_integrated"})
SETTING_FIELDS = {
    "jira": {
        "base_url": {"settings:METRICS_JIRA_SERVER_URL": "METRICS_JIRA_SERVER_URL"},
        "auth_mode": {"settings:METRICS_JIRA_AUTH_MODE": "METRICS_JIRA_AUTH_MODE"},
        "verify_ssl": {"settings:METRICS_JIRA_VERIFY_SSL": "METRICS_JIRA_VERIFY_SSL"},
        "ca_bundle": {"settings:METRICS_JIRA_CA_BUNDLE": "METRICS_JIRA_CA_BUNDLE"},
    },
    "hsdes": {
        "base_url": {"settings:METRICS_HSDES_API_BASE_URL": "METRICS_HSDES_API_BASE_URL"},
        "auth_mode": {"settings:METRICS_HSDES_AUTH_MODE": "METRICS_HSDES_AUTH_MODE"},
        "transport": {"settings:METRICS_HSDES_HTTP_TRANSPORT": "METRICS_HSDES_HTTP_TRANSPORT"},
        "timeout_seconds": {"settings:METRICS_HSDES_TIMEOUT_SECONDS": "METRICS_HSDES_TIMEOUT_SECONDS"},
    },
}
CREDENTIAL_SETTING_REFS = {
    "jira": frozenset({"settings:METRICS_JIRA_*", "settings:METRICS_JIRA_EMAIL", "settings:METRICS_JIRA_API_TOKEN", "settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN"}),
    "hsdes": frozenset({"settings:METRICS_HSDES_*", "settings:METRICS_HSDES_* or Windows Integrated Auth", "settings:METRICS_HSDES_USERNAME", "settings:METRICS_HSDES_PASSWORD", "settings:METRICS_HSDES_TOKEN", "settings:METRICS_HSDES_USERNAME/METRICS_HSDES_PASSWORD"}),
}


def record_value(record, key: str, default):
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def is_settings_ref(value) -> bool:
    return isinstance(value, str) and value.startswith("settings:")


def is_protected_ref(value) -> bool:
    if not isinstance(value, str) or not value.startswith("protected:pcred_"):
        return False
    suffix = value.removeprefix("protected:pcred_")
    return len(suffix) == 32 and all(character in "0123456789abcdef" for character in suffix)


def is_credential_settings_ref(provider_id: str, value) -> bool:
    return isinstance(value, str) and value in CREDENTIAL_SETTING_REFS.get(provider_id, frozenset())


def default_settings_reference(provider_id: str) -> str:
    if provider_id == "jira":
        return "settings:METRICS_JIRA_EMAIL/METRICS_JIRA_API_TOKEN"
    return "settings:METRICS_HSDES_*"
