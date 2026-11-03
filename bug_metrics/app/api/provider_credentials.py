from pathlib import Path

from django.conf import settings

from bug_metrics.provider_connections.adoption import AdoptionPreview, AdoptionResult, CredentialAdoptionService
from bug_metrics.provider_connections.protected_store import ProtectedCredentialStore


def create_credential_adoption_service(settings_source=None, protected_store=None):
    settings_source = settings_source or settings
    store = protected_store or ProtectedCredentialStore(
        Path(settings_source.METRICS_PROVIDER_SECRET_DIR),
        settings_source.METRICS_PROVIDER_SECRET_MAX_BYTES,
    )
    return CredentialAdoptionService(settings_source, store)


__all__ = [
    "AdoptionPreview",
    "AdoptionResult",
    "CredentialAdoptionService",
    "create_credential_adoption_service",
]
