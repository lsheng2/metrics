import json
import copy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from django.db import IntegrityError, OperationalError, transaction
from django.utils import timezone

from bug_metrics.app.api.provider_profile_config import ProviderProfileConfigService
from bug_metrics.app.api.provider_profile_config_payload import provider_profile_config_from_dict
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.models import BugTrendAuditEvent, ProviderProfileConfig

from .contracts import ConnectionError
from .normalization import canonical_sha256
from .protected_store import ProtectedCredentialStore, read_source_toml
from .resolver import ProviderConnectionResolver


@dataclass(frozen=True, slots=True)
class AdoptionPreview:
    profile_id: str
    provider_id: str
    endpoint_id: str
    auth_mode: str
    profile_kind: str
    tls_readiness_id: str
    expected_mapping_hash: str
    expected_source_hash: str
    expected_updated_at: str
    expected_credential_reference: str
    expected_credential_revision: str
    source_identity: str
    source_last_write: str
    adoption_id: str
    conflict: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class AdoptionResult:
    status: str
    adoption_id: str
    profile_id: str
    credential_reference: str
    credential_revision: str
    mapping_hash: str
    source_hash: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CredentialAdoptionService:
    def __init__(self, settings_source, protected_store: ProtectedCredentialStore):
        self._settings = settings_source
        self._store = protected_store
        self._profile_service = ProviderProfileConfigService()

    def preview(self, profile_id: str, source_file) -> AdoptionPreview:
        profile, managed = self._profile(profile_id)
        self._ensure_supported_source_target(profile)
        _, receipt = read_source_toml(Path(source_file), max_bytes=self._store.max_bytes)
        return self._preview_from_receipt(profile, managed, receipt)

    def _preview_from_receipt(self, profile, managed, receipt) -> AdoptionPreview:
        info = self._resolve_endpoint_metadata(profile)
        credential = self._credential_metadata(profile.connection_settings)
        payload = {
            "profile_id": profile.profile_id,
            "provider_id": profile.provider_id,
            "endpoint_id": info.endpoint.endpoint_id,
            "auth_mode": info.endpoint.auth_mode,
            "profile_kind": "managed" if managed else "bundled",
            "tls_readiness_id": info.endpoint.tls.readiness_id,
            "expected_mapping_hash": profile.mapping_version_hash,
            "expected_source_hash": profile.source_version_hash,
            "expected_updated_at": managed.updated_at.isoformat() if managed else "",
            "expected_credential_reference": credential["reference"],
            "expected_credential_revision": credential["revision"],
            "source_identity": receipt.file_identity,
            "source_last_write": receipt.last_write,
            "conflict": credential["kind"] in {"settings", "inline", "protected"},
        }
        payload["adoption_id"] = canonical_sha256(payload)
        return AdoptionPreview(**payload)

    def apply(self, profile_id: str, source_file, *, expected_preview, replace=False) -> AdoptionResult:
        if type(replace) is not bool:
            raise ConnectionError("INVALID_ARGUMENTS")
        try:
            return self._apply(profile_id, source_file, expected_preview=expected_preview, replace=replace)
        except IntegrityError:
            raise ConnectionError("PROVIDER_CREDENTIAL_CAS_MISMATCH") from None
        except OperationalError as error:
            code = "PROVIDER_BUSY" if any(word in str(error).lower() for word in ("locked", "busy")) else "INTERNAL_ERROR"
            raise ConnectionError(code) from None

    def _apply(self, profile_id, source_file, *, expected_preview, replace):
        expected = _preview_from_any(expected_preview)
        profile, managed = self._profile(profile_id)
        self._ensure_supported_source_target(profile)
        token, receipt = read_source_toml(Path(source_file), max_bytes=self._store.max_bytes)
        if receipt.file_identity != expected.source_identity or receipt.last_write != expected.source_last_write:
            raise ConnectionError("PROVIDER_CREDENTIAL_CAS_MISMATCH")
        current_preview = self._preview_from_receipt(profile, managed, receipt)
        if current_preview.to_dict() != expected.to_dict():
            raise ConnectionError("PROVIDER_CREDENTIAL_CAS_MISMATCH")
        if current_preview.conflict and not replace:
            raise ConnectionError("PROVIDER_CREDENTIAL_CONFLICT")
        old_connection_settings = _connection_settings_copy(profile.connection_settings)
        with transaction.atomic():
            profile = self._locked_profile(profile_id, expected, old_connection_settings)
            credential = self._store.create_candidate(
                provider_id=profile.provider_id,
                profile_id=profile.profile_id,
                endpoint_id=expected.endpoint_id,
                auth_mode=expected.auth_mode,
                token=token,
            )
            connection_settings = _protected_connection_settings(profile.connection_settings, credential.reference, credential.revision)
            profile.connection_settings = connection_settings
            profile.save()
            self._record_audit(profile, expected, credential)
            result = AdoptionResult(
                "applied",
                expected.adoption_id,
                profile.profile_id,
                credential.reference,
                credential.revision,
                profile.mapping_version_hash,
                profile.source_version_hash,
                profile.updated_at.isoformat(),
            )
        return result

    def _profile(self, profile_id: str):
        managed = ProviderProfileConfig.objects.filter(profile_id=profile_id).first()
        if managed:
            return self._profile_service._to_saved_profile_config(managed), managed
        profile = self._profile_service.get_provider_profile_config(profile_id)
        return profile, None

    def _locked_profile(self, profile_id: str, preview: AdoptionPreview, expected_connection_settings: dict[str, Any]):
        managed = ProviderProfileConfig.objects.filter(profile_id=profile_id).first()
        if managed is None:
            saved = self._profile_service.get_provider_profile_config(profile_id)
            if saved.mapping_version_hash != preview.expected_mapping_hash or saved.source_version_hash != preview.expected_source_hash:
                raise ConnectionError("PROVIDER_CREDENTIAL_CAS_MISMATCH")
            with transaction.atomic():
                managed = self._materialize_bundled(saved)
            return managed
        if (
            managed.mapping_version_hash != preview.expected_mapping_hash
            or managed.source_version_hash != preview.expected_source_hash
            or managed.updated_at.isoformat() != preview.expected_updated_at
        ):
            raise ConnectionError("PROVIDER_CREDENTIAL_CAS_MISMATCH")
        if dict(managed.connection_settings or {}) != dict(expected_connection_settings or {}):
            raise ConnectionError("PROVIDER_CREDENTIAL_CAS_MISMATCH")
        matched = ProviderProfileConfig.objects.filter(
            pk=managed.pk,
            mapping_version_hash=preview.expected_mapping_hash,
            source_version_hash=preview.expected_source_hash,
            updated_at=managed.updated_at,
            connection_settings=expected_connection_settings,
        ).update(connection_settings=expected_connection_settings)
        if matched != 1:
            raise ConnectionError("PROVIDER_CREDENTIAL_CAS_MISMATCH")
        return ProviderProfileConfig.objects.get(pk=managed.pk)

    def _materialize_bundled(self, saved):
        config = provider_profile_config_from_dict(saved.to_dict() if hasattr(saved, "to_dict") else asdict(saved))
        profile = ProviderProfileConfig()
        self._profile_service._apply_config(profile, config)
        profile.provenance = {"source": "bundled_profile_override"}
        profile.save()
        return profile

    def _record_audit(self, profile, preview: AdoptionPreview, credential) -> None:
        BugTrendAuditEvent.objects.create(
            event_type=BugTrendAuditEvent.EVENT_PROVIDER_PROFILE_UPDATED,
            actor="local_operator",
            request_summary={
                "profile_id": profile.profile_id,
                "provider_id": profile.provider_id,
                "adoption_id": preview.adoption_id,
                "credential_reference": credential.reference,
                "credential_revision": credential.revision,
            },
        )

    def _resolve_endpoint_metadata(self, profile):
        return ProviderConnectionResolver(self._settings, ProjectProviderProfileRegistry.load_default(), self._store).describe_record(profile)

    def _ensure_supported_source_target(self, profile) -> None:
        info = self._resolve_endpoint_metadata(profile)
        if info.endpoint.provider_id != "jira" or info.endpoint.auth_mode != "server_pat":
            raise ConnectionError("PROVIDER_UNSUPPORTED")

    def _credential_metadata(self, connection_settings: dict[str, Any]) -> dict[str, str]:
        settings = dict(connection_settings or {})
        credential_ref = settings.get("credential_ref", "")
        if settings.get("credential_storage") == "protected_file" or str(credential_ref).startswith("protected:"):
            return {"kind": "protected", "reference": str(credential_ref), "revision": str(settings.get("credential_revision", ""))}
        if _has_inline_secret(settings):
            return {"kind": "inline", "reference": "profile", "revision": "unknown:profile"}
        if str(credential_ref).startswith("settings:"):
            return {"kind": "settings", "reference": str(credential_ref), "revision": "unknown:settings"}
        return {"kind": "none", "reference": "", "revision": ""}


def _protected_connection_settings(settings: dict[str, Any], reference: str, revision: str) -> dict[str, Any]:
    result = dict(settings or {})
    result.pop("credentials", None)
    for key in ["api_token", "token", "password", "username", "email"]:
        result.pop(key, None)
    result["credential_storage"] = "protected_file"
    result["credential_ref"] = reference
    result["credential_revision"] = revision
    return result


def _preview_from_any(value) -> AdoptionPreview:
    if isinstance(value, AdoptionPreview):
        value = value.to_dict()
    if isinstance(value, dict):
        allowed = set(AdoptionPreview.__dataclass_fields__)
        if (set(value) != allowed or type(value.get("conflict")) is not bool
                or any(not isinstance(item, str) or len(item) > 2048
                       for key, item in value.items() if key != "conflict")):
            raise ConnectionError("INVALID_ARGUMENTS")
        return AdoptionPreview(**value)
    raise ConnectionError("INVALID_ARGUMENTS")


def _has_inline_secret(settings: dict[str, Any]) -> bool:
    credentials = dict(settings.get("credentials") or {})
    for source in [credentials, settings]:
        for key in ["api_token", "token", "password", "username", "email"]:
            value = source.get(key)
            if isinstance(value, str) and value and not value.startswith("settings:"):
                return True
    return False


def _connection_settings_copy(settings: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(settings or {}))
