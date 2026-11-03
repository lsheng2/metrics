from bug_metrics.provider_connections import (
    ConnectionError,
    ConnectionInfo,
    CredentialSource,
    ProviderConnectionResolver,
    ProviderEndpoint,
    ResolvedConnection,
    TlsTrust,
)
from bug_metrics.provider_connections.hsd_opener import BoundHsdesIntegratedPowershellRunner, BoundHsdesOpener
from bug_metrics.provider_connections.normalization import normalize_base_url


def source_endpoint_matches(info, source_endpoint):
    return normalize_base_url(source_endpoint).base_url == info.endpoint.base_url


def create_provider_connection_resolver(settings_source=None, profile_registry=None, protected_store=None):
    if settings_source is None:
        from django.conf import settings

        settings_source = settings
    if profile_registry is None:
        from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry

        profile_registry = ProjectProviderProfileRegistry.load_default()
    if protected_store is None and hasattr(settings_source, "METRICS_PROVIDER_SECRET_DIR"):
        from pathlib import Path

        from bug_metrics.provider_connections.protected_store import ProtectedCredentialStore

        protected_store = ProtectedCredentialStore(
            Path(settings_source.METRICS_PROVIDER_SECRET_DIR),
            settings_source.METRICS_PROVIDER_SECRET_MAX_BYTES,
        )
    return ProviderConnectionResolver(settings_source, profile_registry, protected_store)


def create_bound_hsdes_opener(base_url: str, verify=True):
    return BoundHsdesOpener(base_url, verify=verify)


def create_bound_hsdes_powershell_runner(base_url: str):
    return BoundHsdesIntegratedPowershellRunner(base_url)


__all__ = [
    "ConnectionError",
    "ConnectionInfo",
    "CredentialSource",
    "ProviderConnectionResolver",
    "ProviderEndpoint",
    "ResolvedConnection",
    "TlsTrust",
    "create_bound_hsdes_opener",
    "create_bound_hsdes_powershell_runner",
    "create_provider_connection_resolver",
    "source_endpoint_matches",
]
