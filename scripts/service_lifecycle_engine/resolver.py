from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlsplit

from .models import LiveServiceResolution, LiveServiceResolutionSource


class LiveServiceResolver:
    def __init__(
        self,
        lifecycle_state: Mapping[str, Mapping[str, object]] | None = None,
        projection: Mapping[str, Mapping[str, object]] | None = None,
        default_ports: Mapping[str, int] | None = None,
        projection_enabled: bool = True,
        default_host: str = "127.0.0.1",
        diagnostics_authority_directory: str | None = None,
    ) -> None:
        self.lifecycle_state = lifecycle_state or {}
        self.projection = projection or {}
        self.default_ports = default_ports or {}
        self.projection_enabled = projection_enabled
        self.default_host = default_host
        self.diagnostics_authority_directory = diagnostics_authority_directory

    def resolve(self, service_name: str, explicit_base_url: str = "", explicit_host: str = "", explicit_port: int | None = None) -> LiveServiceResolution:
        if explicit_base_url:
            return self._from_base_url(service_name, explicit_base_url, LiveServiceResolutionSource.EXPLICIT)
        if explicit_port is not None:
            return LiveServiceResolution(service_name, explicit_host or self.default_host, int(explicit_port), LiveServiceResolutionSource.EXPLICIT)
        lifecycle_resolution = self._from_mapping(service_name, self.lifecycle_state, LiveServiceResolutionSource.LIFECYCLE_STATE)
        if lifecycle_resolution is not None:
            return lifecycle_resolution
        if self.projection_enabled:
            projection_resolution = self._from_mapping(service_name, self.projection, LiveServiceResolutionSource.PROJECT_PROJECTION)
            if projection_resolution is not None:
                return projection_resolution
        if service_name not in self.default_ports:
            raise KeyError(service_name)
        return LiveServiceResolution(
            service_name=service_name,
            host=self.default_host,
            port=int(self.default_ports[service_name]),
            source=LiveServiceResolutionSource.DEFAULT,
            diagnostics=("default_port_fallback",),
        )

    def _from_mapping(
        self,
        service_name: str,
        values_by_service: Mapping[str, Mapping[str, object]],
        source: LiveServiceResolutionSource,
    ) -> LiveServiceResolution | None:
        values = values_by_service.get(service_name)
        if values is None:
            return None
        base_url = str(values.get("base_url") or "")
        if base_url:
            return self._from_base_url(service_name, base_url, source)
        port = values.get("port")
        if port is None:
            return None
        return LiveServiceResolution(
            service_name=service_name,
            host=str(values.get("host") or self.default_host),
            port=int(port),
            source=source,
        )

    def _from_base_url(self, service_name: str, base_url: str, source: LiveServiceResolutionSource) -> LiveServiceResolution:
        parsed = urlsplit(base_url.rstrip("/"))
        if not parsed.hostname or parsed.port is None:
            raise ValueError(f"Service base URL must include host and port: {base_url}")
        return LiveServiceResolution(
            service_name=service_name,
            host=parsed.hostname,
            port=int(parsed.port),
            source=source,
            scheme=parsed.scheme or "http",
        )
