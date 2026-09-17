from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from service_lifecycle_engine import (
    ExternalServiceBinding,
    ExternalServiceMode,
    RuntimeInstanceIdentity,
    RuntimeResourceNamespace,
)


SCHEMA_VERSION = 1
PROJECT_NAME = "metrics-bug-trend"

DEFAULT_SERVICE_PORTS: dict[str, int] = {
    "django": 8002,
    "grafana": 3001,
    "ai-base-backend": 48300,
    "ai-base-frontend": 48310,
    "external-litellm": 4000,
}

PORT_PROFILE_OVERRIDES: dict[str, dict[str, int]] = {
    "default": {},
    "worktree-1": {"django": 8012, "grafana": 3051},
    "worktree-2": {"django": 8022, "grafana": 3151},
    "worktree-3": {"django": 8032, "grafana": 3251},
    "worktree-4": {"django": 8042, "grafana": 3351},
}


@dataclass(frozen=True, slots=True)
class ScrumDashboardRuntimeInstanceProfile:
    identity: RuntimeInstanceIdentity
    repo_root: Path
    workspace_root: Path
    port_profile: str
    service_ports: Mapping[str, int]

    @property
    def lifecycle_instance_name(self) -> str:
        return self.identity.instance_id

    @property
    def state_root(self) -> Path:
        return self.workspace_root / "state" / "local" / "instances" / self.identity.instance_id

    @property
    def service_lifecycle_state_dir(self) -> Path:
        return self.state_root / "service-lifecycle-engine"

    @property
    def e2e_summary_path(self) -> Path:
        return self.workspace_root / "state" / "e2e" / "bug_trend_ports.json"

    @property
    def dashboard_namespace(self) -> RuntimeResourceNamespace:
        return RuntimeResourceNamespace.from_identity(
            self.identity,
            service_group="dashboard",
            ports={
                "django": self.service_ports["django"],
                "grafana": self.service_ports["grafana"],
            },
        )

    @property
    def django_namespace(self) -> RuntimeResourceNamespace:
        return RuntimeResourceNamespace.from_identity(
            self.identity,
            service_group="django",
            ports={"http": self.service_ports["django"]},
        )

    @property
    def grafana_namespace(self) -> RuntimeResourceNamespace:
        return RuntimeResourceNamespace.from_identity(
            self.identity,
            service_group="grafana",
            ports={"http": self.service_ports["grafana"]},
        )

    @property
    def dedicated_bindings(self) -> tuple[ExternalServiceBinding, ...]:
        return (
            ExternalServiceBinding("django", ExternalServiceMode.DEDICATED, owner=self.identity, namespace=self.django_namespace),
            ExternalServiceBinding("grafana", ExternalServiceMode.DEDICATED, owner=self.identity, namespace=self.grafana_namespace),
        )

    @property
    def shared_consumed_bindings(self) -> tuple[ExternalServiceBinding, ...]:
        return (
            ExternalServiceBinding(
                "ai-base-backend",
                ExternalServiceMode.SHARED_CONSUMED,
                consumer=self.identity,
                endpoint=f"http://127.0.0.1:{self.service_ports['ai-base-backend']}",
            ),
            ExternalServiceBinding(
                "ai-base-frontend",
                ExternalServiceMode.SHARED_CONSUMED,
                consumer=self.identity,
                endpoint=f"http://127.0.0.1:{self.service_ports['ai-base-frontend']}",
            ),
            ExternalServiceBinding(
                "external-litellm",
                ExternalServiceMode.SHARED_CONSUMED,
                consumer=self.identity,
                endpoint=f"http://127.0.0.1:{self.service_ports['external-litellm']}",
            ),
        )

    @property
    def bindings(self) -> tuple[ExternalServiceBinding, ...]:
        return (*self.dedicated_bindings, *self.shared_consumed_bindings)

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "identity": self.identity.as_dict(),
            "repo_root": str(self.repo_root),
            "workspace_root": str(self.workspace_root),
            "port_profile": self.port_profile,
            "service_ports": dict(self.service_ports),
            "state_dirs": {
                "state_root": str(self.state_root),
                "service_lifecycle": str(self.service_lifecycle_state_dir),
                "e2e_summary": str(self.e2e_summary_path),
            },
            "namespaces": {
                "dashboard": self.dashboard_namespace.as_dict(),
                "lifecycle_instance_name": self.lifecycle_instance_name,
            },
            "external_services": [binding.as_dict() for binding in self.shared_consumed_bindings],
        }


def default_runtime_profile_path(workspace_root: Path) -> Path:
    return workspace_root / "state" / "local" / "runtime-instance.json"


def default_runtime_env_path(workspace_root: Path) -> Path:
    return workspace_root / "state" / "local" / "worktree-runtime.env"


def build_dashboard_runtime_instance_profile(
    *,
    repo_root: Path,
    workspace_root: Path,
    port_profile: str = "default",
    instance_id: str | None = None,
    service_port_overrides: Mapping[str, int | str | None] | None = None,
) -> ScrumDashboardRuntimeInstanceProfile:
    ports = _ports_for_profile(port_profile)
    for service, value in dict(service_port_overrides or {}).items():
        if value in (None, ""):
            continue
        ports[str(service)] = _parse_port(value, service_name=str(service))
    resolved_repo = repo_root.expanduser().resolve()
    resolved_workspace = workspace_root.expanduser().resolve()
    identity = (
        RuntimeInstanceIdentity(PROJECT_NAME, instance_id)
        if instance_id
        else RuntimeInstanceIdentity.derive(
            project_name=PROJECT_NAME,
            seed=str(resolved_workspace),
            label=port_profile,
        )
    )
    return ScrumDashboardRuntimeInstanceProfile(
        identity=identity,
        repo_root=resolved_repo,
        workspace_root=resolved_workspace,
        port_profile=port_profile,
        service_ports=ports,
    )


def load_or_create_dashboard_runtime_instance_profile(
    *,
    workspace_root: Path,
    repo_root: Path | None = None,
    profile_path: Path | None = None,
    env_path: Path | None = None,
    port_profile: str | None = None,
    instance_id: str | None = None,
    service_port_overrides: Mapping[str, int | str | None] | None = None,
) -> ScrumDashboardRuntimeInstanceProfile:
    resolved_workspace = workspace_root.expanduser().resolve()
    resolved_repo = (repo_root or resolved_workspace).expanduser().resolve()
    resolved_profile_path = profile_path or default_runtime_profile_path(resolved_workspace)
    explicit_values = bool(instance_id or port_profile or _has_port_override(service_port_overrides))
    if resolved_profile_path.exists() and not explicit_values:
        profile = read_dashboard_runtime_instance_profile(resolved_profile_path)
    else:
        profile = build_dashboard_runtime_instance_profile(
            repo_root=resolved_repo,
            workspace_root=resolved_workspace,
            port_profile=port_profile or "default",
            instance_id=instance_id,
            service_port_overrides=service_port_overrides,
        )
        write_dashboard_runtime_instance_profile(resolved_profile_path, profile)
    write_dashboard_runtime_env_projection(env_path or default_runtime_env_path(resolved_workspace), profile)
    return profile


def read_dashboard_runtime_instance_profile(path: Path) -> ScrumDashboardRuntimeInstanceProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Runtime instance profile must be a JSON object: {path}")
    if int(payload.get("schema_version") or 0) != SCHEMA_VERSION:
        raise ValueError(f"Unsupported runtime instance profile schema: {payload.get('schema_version')!r}")
    identity_payload = payload.get("identity")
    if not isinstance(identity_payload, dict):
        raise ValueError("Runtime instance profile is missing identity")
    return ScrumDashboardRuntimeInstanceProfile(
        identity=RuntimeInstanceIdentity(
            project_name=str(identity_payload.get("project_name") or ""),
            instance_id=str(identity_payload.get("instance_id") or ""),
        ),
        repo_root=Path(str(payload.get("repo_root") or "")).expanduser().resolve(),
        workspace_root=Path(str(payload.get("workspace_root") or "")).expanduser().resolve(),
        port_profile=str(payload.get("port_profile") or "default"),
        service_ports={str(key): int(value) for key, value in dict(payload.get("service_ports") or {}).items()},
    )


def write_dashboard_runtime_instance_profile(path: Path, profile: ScrumDashboardRuntimeInstanceProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_dashboard_runtime_env_projection(path: Path, profile: ScrumDashboardRuntimeInstanceProfile) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard_runtime_env_projection(profile), encoding="utf-8")


def render_dashboard_runtime_env_projection(profile: ScrumDashboardRuntimeInstanceProfile) -> str:
    lines = [
        "# Generated from state/local/runtime-instance.json. Do not commit.",
        f"METRICS_DASHBOARD_RUNTIME_INSTANCE_ID={profile.identity.instance_id}",
        f"METRICS_SERVICE_LIFECYCLE_PROJECT_NAME={profile.identity.project_name}",
        f"METRICS_SERVICE_LIFECYCLE_INSTANCE_NAME={profile.lifecycle_instance_name}",
        f"METRICS_DASHBOARD_WORKSPACE_ROOT={profile.workspace_root}",
        f"METRICS_DASHBOARD_PORT_PROFILE={profile.port_profile}",
        f"METRICS_DJANGO_PORT={profile.service_ports['django']}",
        f"METRICS_GRAFANA_PORT={profile.service_ports['grafana']}",
        f"METRICS_DASHBOARD_STATE_DIR={profile.state_root}",
        f"METRICS_DASHBOARD_SERVICE_LIFECYCLE_STATE_DIR={profile.service_lifecycle_state_dir}",
        f"DASHBOARD_METRICS_BASE_URL=http://127.0.0.1:{profile.service_ports['django']}",
        f"RCA_DASHBOARD_METRICS_BASE_URL=http://127.0.0.1:{profile.service_ports['django']}",
        f"METRICS_AI_BASE_URL=http://127.0.0.1:{profile.service_ports['ai-base-backend']}",
        f"METRICS_AI_BASE_FRONTEND_URL=http://127.0.0.1:{profile.service_ports['ai-base-frontend']}",
        f"METRICS_EXTERNAL_LITELLM_URL=http://127.0.0.1:{profile.service_ports['external-litellm']}",
    ]
    return "\n".join(lines) + "\n"


def primary_port_for_service(profile: ScrumDashboardRuntimeInstanceProfile, service_name: str) -> int | None:
    return profile.service_ports.get(service_name)


def prioritize_profile_port(preferred_ports: tuple[int, ...], profile: ScrumDashboardRuntimeInstanceProfile, service_name: str) -> tuple[int, ...]:
    profile_port = primary_port_for_service(profile, service_name)
    if profile_port is None:
        return preferred_ports
    return (profile_port, *(port for port in preferred_ports if port != profile_port))


def _ports_for_profile(port_profile: str) -> dict[str, int]:
    if port_profile not in PORT_PROFILE_OVERRIDES:
        raise ValueError(f"Unknown port profile: {port_profile}")
    return {**DEFAULT_SERVICE_PORTS, **PORT_PROFILE_OVERRIDES[port_profile]}


def _parse_port(value: int | str | None, *, service_name: str) -> int:
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{service_name} port must be an integer: {value!r}") from exc
    if port < 1 or port > 65535:
        raise ValueError(f"{service_name} port must be between 1 and 65535: {value!r}")
    return port


def _has_port_override(values: Mapping[str, int | str | None] | None) -> bool:
    return any(value not in (None, "") for value in dict(values or {}).values())


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Scrum Dashboard local runtime instance profile projections.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    write = subparsers.add_parser("write", help="Write runtime-instance.json and worktree-runtime.env projection.")
    write.add_argument("--repo-root", required=True)
    write.add_argument("--workspace-root", required=True)
    write.add_argument("--port-profile", default="default")
    write.add_argument("--instance-id", default="")
    write.add_argument("--django-port")
    write.add_argument("--grafana-port")
    write.add_argument("--ai-base-backend-port")
    write.add_argument("--ai-base-frontend-port")
    write.add_argument("--external-litellm-port")
    write.add_argument("--profile-path", required=True)
    write.add_argument("--env-path", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    if args.command == "write":
        profile = build_dashboard_runtime_instance_profile(
            repo_root=Path(args.repo_root),
            workspace_root=Path(args.workspace_root),
            port_profile=str(args.port_profile),
            instance_id=str(args.instance_id or "") or None,
            service_port_overrides={
                "django": args.django_port,
                "grafana": args.grafana_port,
                "ai-base-backend": args.ai_base_backend_port,
                "ai-base-frontend": args.ai_base_frontend_port,
                "external-litellm": args.external_litellm_port,
            },
        )
        write_dashboard_runtime_instance_profile(Path(args.profile_path), profile)
        write_dashboard_runtime_env_projection(Path(args.env_path), profile)
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


__all__ = [
    "DEFAULT_SERVICE_PORTS",
    "PORT_PROFILE_OVERRIDES",
    "PROJECT_NAME",
    "SCHEMA_VERSION",
    "ScrumDashboardRuntimeInstanceProfile",
    "build_dashboard_runtime_instance_profile",
    "default_runtime_env_path",
    "default_runtime_profile_path",
    "load_or_create_dashboard_runtime_instance_profile",
    "main",
    "primary_port_for_service",
    "prioritize_profile_port",
    "read_dashboard_runtime_instance_profile",
    "render_dashboard_runtime_env_projection",
    "write_dashboard_runtime_env_projection",
    "write_dashboard_runtime_instance_profile",
]


if __name__ == "__main__":
    raise SystemExit(main())
