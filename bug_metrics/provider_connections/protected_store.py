import json
import os
import importlib
import re
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .contracts import CredentialSource
from .contracts import ConnectionError

_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]{1,160}$")
_REVISION = re.compile(r"^rev_[0-9]{8}T[0-9]{12}Z_[0-9a-f]{16}$")
_RESERVED = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", re.IGNORECASE)

@dataclass(frozen=True, slots=True)
class SourceFileReceipt:
    file_identity: str
    last_write: str
    owner_class: str


@dataclass(frozen=True, slots=True)
class PendingCredential:
    reference: str
    revision: str
    status: str = "pending_cleanup"


class ProtectedCredentialStore:
    def __init__(self, root: Path, max_bytes: int):
        self.root = Path(root)
        if not self.root.is_absolute() or type(max_bytes) is not int or not 0 < max_bytes <= 16 * 1024**2:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        self.max_bytes = max_bytes

    def create_candidate(self, *, provider_id, profile_id, endpoint_id, auth_mode, token: str) -> CredentialSource:
        create_new_protected_file = _windows_files().create_new_protected_file

        provider_id = _safe_segment(provider_id)
        profile_id = _safe_segment(profile_id)
        endpoint_id = _safe_segment(endpoint_id, limit=96)
        auth_mode = _safe_segment(auth_mode)
        _validate_token(token)
        secret_id = f"pcred_{secrets.token_hex(16)}"
        revision = f"rev_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}_{secrets.token_hex(8)}"
        reference = f"protected:{secret_id}"
        directory = self.root / str(provider_id) / str(profile_id) / secret_id
        metadata = {
            "schema_version": 1,
            "kind": "credential_candidate",
            "secret_id": secret_id,
            "revision": revision,
            "provider_id": str(provider_id),
            "profile_id": str(profile_id),
            "endpoint_id": str(endpoint_id),
            "auth_mode": str(auth_mode),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        create_new_protected_file(directory / f"{revision}.intent.json", _json_bytes(metadata), root=self.root)
        create_new_protected_file(directory / f"{revision}.secret", token.encode("ascii"), root=self.root)
        create_new_protected_file(directory / f"{revision}.meta.json", _json_bytes(metadata), root=self.root)
        return CredentialSource("protected", reference, revision)

    def read_selected(self, *, reference, revision, provider_id, profile_id, endpoint_id, auth_mode) -> str:
        windows = _windows_files()

        provider_id = _safe_segment(provider_id)
        profile_id = _safe_segment(profile_id)
        endpoint_id = _safe_segment(endpoint_id, limit=96)
        auth_mode = _safe_segment(auth_mode)
        revision = _revision(revision)
        secret_id = _secret_id(reference)
        directory = self.root / str(provider_id) / str(profile_id) / secret_id
        for parent in (self.root, self.root / provider_id, self.root / provider_id / profile_id, directory):
            windows.validate_named_path_protection(parent)
        secret_path = directory / f"{revision}.secret"
        meta_path = directory / f"{revision}.meta.json"
        intent_path = directory / f"{revision}.intent.json"
        metadata = _read_json_file(meta_path, self.max_bytes)
        intent = _read_json_file(intent_path, self.max_bytes)
        if metadata != intent or metadata.get("schema_version") != 1:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
        expected = {
            "kind": "credential_candidate",
            "secret_id": secret_id,
            "revision": str(revision),
            "provider_id": str(provider_id),
            "profile_id": str(profile_id),
            "endpoint_id": str(endpoint_id),
            "auth_mode": str(auth_mode),
        }
        for key, value in expected.items():
            if metadata.get(key) != value or intent.get(key) != value:
                raise ConnectionError("PROVIDER_CREDENTIAL_UNAVAILABLE")
        token_bytes, _ = windows.read_protected_bytes(secret_path, max_bytes=self.max_bytes)
        try:
            token = token_bytes.decode("ascii")
        except UnicodeError:
            raise ConnectionError("PROVIDER_CREDENTIAL_INVALID") from None
        _validate_token(token)
        return token

    def list_unreferenced(self, profile_references: frozenset[tuple[str, str]]) -> tuple[PendingCredential, ...]:
        windows = _windows_files()

        pending = []
        active = set(profile_references)
        if not self.root.exists():
            return ()
        count = 0
        for parent, directories, files in os.walk(self.root, followlinks=False):
            parent_path = Path(parent)
            windows.validate_named_path_protection(parent_path)
            for name in directories:
                _safe_segment(name)
                windows.validate_named_path_protection(parent_path / name)
            for name in files:
                count += 1
                if count > 100000:
                    raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
                if not name.endswith(".intent.json"):
                    continue
                intent_path = parent_path / name
                parts = intent_path.relative_to(self.root).parts
                if len(parts) != 4:
                    raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
                provider, profile, secret_id, filename = parts
                metadata = _read_json_file(intent_path, self.max_bytes)
                reference = "protected:" + _secret_id("protected:" + secret_id)
                revision = _revision(filename.removesuffix(".intent.json"))
                if any(metadata.get(key) != value for key, value in {
                    "schema_version": 1, "kind": "credential_candidate", "provider_id": provider,
                    "profile_id": profile, "secret_id": secret_id, "revision": revision,
                }.items()):
                    raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
                if (reference, revision) not in active:
                    pending.append(PendingCredential(reference, revision))
        return tuple(sorted(pending, key=lambda item: (item.reference, item.revision)))


def read_source_toml(path: Path, *, max_bytes: int) -> tuple[str, SourceFileReceipt]:
    return _windows_files().read_source_toml_same_handle(Path(path), max_bytes=max_bytes)


def _secret_id(reference: str) -> str:
    if not isinstance(reference, str) or not reference.startswith("protected:pcred_"):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    secret_id = reference.removeprefix("protected:")
    if not re.fullmatch(r"pcred_[0-9a-f]{32}", secret_id):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    return secret_id


def _revision(value) -> str:
    if not isinstance(value, str) or not _REVISION.fullmatch(value):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    return value


def _safe_segment(value, *, limit=160) -> str:
    text = value
    if (not isinstance(text, str) or len(text) > limit or not _SEGMENT.fullmatch(text)
            or text in {".", ".."} or text.endswith(".") or _RESERVED.match(text)):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    return text


def _validate_token(token: str) -> None:
    if not isinstance(token, str) or not 1 <= len(token) <= 8192:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    if any(ord(character) < 33 or ord(character) > 126 for character in token):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")


def _json_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json_file(path: Path, max_bytes: int) -> dict:
    try:
        data, _ = _windows_files().read_protected_bytes(path, max_bytes=max_bytes)
        payload = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except ConnectionError:
        raise
    except Exception:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID") from None
    fields = {"schema_version", "kind", "secret_id", "revision", "provider_id", "profile_id",
              "endpoint_id", "auth_mode", "created_at"}
    if (not isinstance(payload, dict) or set(payload) != fields
            or any(not isinstance(value, str) for key, value in payload.items() if key != "schema_version")
            or payload.get("kind") != "credential_candidate"):
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    _secret_id("protected:" + payload["secret_id"])
    _revision(payload["revision"])
    for name in ("provider_id", "profile_id", "endpoint_id", "auth_mode"):
        _safe_segment(payload[name])
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ConnectionError("PROVIDER_CREDENTIAL_INVALID")
    return payload


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate metadata key")
        result[key] = value
    return result


def _windows_files():
    if sys.platform != "win32":
        raise ConnectionError("PROVIDER_CREDENTIAL_PLATFORM_UNSUPPORTED")
    return importlib.import_module(".windows_files", __package__)
