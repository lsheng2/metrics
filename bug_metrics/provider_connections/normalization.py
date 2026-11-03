import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib import parse

from .contracts import ConnectionError, TlsResolution, TlsTrust


_HEX_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")


@dataclass(frozen=True, slots=True)
class NormalizedUrl:
    base_url: str
    scheme: str
    host: str
    port: int | None
    path_prefix: str


def canonical_sha256(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def resolve_tls(verify_ssl, ca_bundle) -> TlsResolution:
    if type(verify_ssl) is not bool or not verify_ssl:
        raise ConnectionError("PROVIDER_TRUST_INVALID")
    if ca_bundle:
        if not isinstance(ca_bundle, str):
            raise ConnectionError("PROVIDER_TRUST_INVALID")
        path = Path(ca_bundle).expanduser()
        if not path.is_absolute() or "://" in ca_bundle:
            raise ConnectionError("PROVIDER_TRUST_INVALID")
        private_path = str(path)
        digest = canonical_sha256({"verification": True, "source": "custom_ca",
                                   "private_ca_configuration": private_path})
        return TlsResolution(TlsTrust(True, "custom_ca", "configured-ca", digest), private_path)
    digest = canonical_sha256({"verification": True, "source": "system",
                               "private_ca_configuration": "system-ca"})
    return TlsResolution(TlsTrust(True, "system", "system-ca", digest), True)


def endpoint_identifier(provider_id: str, base_url: str, auth_mode: str) -> str:
    return canonical_sha256({
        "provider_id": provider_id,
        "normalized_base_url": base_url,
        "auth_mode": auth_mode,
    })


def normalize_base_url(raw_url: str) -> NormalizedUrl:
    parts = _split_url(raw_url)
    if parts.query or parts.fragment:
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    path_prefix = _normalized_path_prefix(parts.path)
    host = str(parts.hostname or "").lower()
    port = _normalized_port(parts)
    netloc = _normalized_netloc(host, port)
    return NormalizedUrl(f"https://{netloc}{path_prefix}", "https", host, port, path_prefix)


def normalize_request_url(raw_url: str) -> NormalizedUrl:
    parts = _split_url(raw_url)
    path_prefix = _normalized_path_prefix(parts.path)
    host = str(parts.hostname or "").lower()
    port = _normalized_port(parts)
    netloc = _normalized_netloc(host, port)
    return NormalizedUrl(f"https://{netloc}{path_prefix}", "https", host, port, path_prefix)


def has_base_prefix(base: NormalizedUrl, candidate: NormalizedUrl) -> bool:
    if base.scheme != candidate.scheme or base.host != candidate.host or base.port != candidate.port:
        return False
    if not base.path_prefix:
        return True
    return candidate.path_prefix == base.path_prefix or candidate.path_prefix.startswith(f"{base.path_prefix}/")


def search_post_paths(base: NormalizedUrl) -> frozenset[str]:
    prefix = base.path_prefix
    return frozenset(f"{prefix}/rest/api/{version}/search" for version in ["2", "3", "latest"])


def _split_url(raw_url: str) -> parse.SplitResult:
    if not isinstance(raw_url, str):
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    text = raw_url
    if (
        not text
        or text != text.strip()
        or "\\" in text
        or any(character.isspace() or ord(character) < 32 for character in text)
    ):
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    _reject_bad_percent_encoding(text)
    try:
        parts = parse.urlsplit(text)
    except ValueError:
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID") from None
    if parts.scheme != "https" or not parts.netloc:
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    if parts.username is not None or parts.password is not None or not parts.hostname:
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    try:
        port = parts.port
    except ValueError:
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID") from None
    if port is not None and not 1 <= port <= 65535:
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    return parts


def _normalized_port(parts: parse.SplitResult) -> int | None:
    port = parts.port
    return None if port in {None, 443} else port


def _normalized_netloc(host: str, port: int | None) -> str:
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"{display_host}:{port}" if port is not None else display_host


def _normalized_path_prefix(path: str) -> str:
    if not path or path == "/":
        return ""
    lowered = path.lower()
    if "%2f" in lowered or "%5c" in lowered or "%25" in lowered or "//" in path:
        raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    for segment in path.split("/"):
        decoded = parse.unquote(segment)
        if decoded in {".", ".."} or "%" in decoded or any(ord(character) < 32 for character in decoded):
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
    return path.rstrip("/")


def _reject_bad_percent_encoding(text: str) -> None:
    index = 0
    while True:
        index = text.find("%", index)
        if index < 0:
            return
        if not _HEX_ESCAPE.match(text, index):
            raise ConnectionError("PROVIDER_ENDPOINT_INVALID")
        index += 3
