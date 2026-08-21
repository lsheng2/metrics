from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .models import ServiceSpec


class TemplateValues(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_service_specs(path: str | Path, workspace: str | Path, variables: Mapping[str, object] | None = None) -> dict[str, ServiceSpec]:
    config_path = Path(path)
    workspace_path = Path(workspace).resolve()
    template_values = TemplateValues({"workspace": str(workspace_path)})
    template_values.update({key: str(value) for key, value in (variables or {}).items()})
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    services = payload.get("services", [])
    return {service["name"]: service_spec_from_payload(service, workspace_path, template_values) for service in services}


def load_project_name(path: str | Path, default: str) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return str(payload.get("project_name") or default)


def service_spec_from_payload(payload: Mapping[str, object], workspace: Path, template_values: TemplateValues) -> ServiceSpec:
    return ServiceSpec.from_values(
        name=str(payload["name"]),
        preferred_ports=[int(port) for port in payload.get("preferred_ports", [])],
        command=format_sequence(payload.get("command", []), template_values),
        stop_command=format_sequence(payload.get("stop_command", []), template_values),
        host=format_value(payload.get("host", "127.0.0.1"), template_values),
        cwd=resolve_cwd(payload.get("cwd"), workspace, template_values),
        env=format_mapping(payload.get("env", {}), template_values),
        health_url=format_optional(payload.get("health_url"), template_values),
        listener_identity_url=format_optional(payload.get("listener_identity_url"), template_values),
        startup_timeout_seconds=float(payload.get("startup_timeout_seconds", 30.0)),
        graceful_timeout_seconds=float(payload.get("graceful_timeout_seconds", 5.0)),
        port_release_timeout_seconds=float(payload.get("port_release_timeout_seconds", 2.0)),
    )


def format_sequence(value: object, template_values: TemplateValues) -> list[str]:
    if not isinstance(value, list):
        return []
    return [format_value(item, template_values) for item in value]


def format_mapping(value: object, template_values: TemplateValues) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): format_value(item, template_values) for key, item in value.items()}


def format_optional(value: object, template_values: TemplateValues) -> str | None:
    if value is None:
        return None
    return format_value(value, template_values)


def format_value(value: object, template_values: TemplateValues) -> str:
    return str(value).format_map(template_values)


def resolve_cwd(value: object, workspace: Path, template_values: TemplateValues) -> Path | None:
    if value is None:
        return None
    path = Path(format_value(value, template_values))
    if path.is_absolute():
        return path
    return workspace / path
