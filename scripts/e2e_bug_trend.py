from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence, TypeVar

from dashboard_runtime_instance_profile import (
    ScrumDashboardRuntimeInstanceProfile,
    load_or_create_dashboard_runtime_instance_profile,
    prioritize_profile_port,
)
import e2e_bug_trend_runtime as runtime_ops
from e2e_grafana_runtime import write_runtime_grafana_config
from service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec, load_project_name, load_service_specs

T = TypeVar("T")


class LifecycleProfiler(Protocol):
    def profile_step(self, label: str, callback: Callable[[], T], run_id: str | None = None, prefix: str = "ServiceLifecycleEngine timing") -> T:
        ...


def main() -> None:
    parser = argparse.ArgumentParser(description="Start/stop the Bug Trend E2E runtime.")
    parser.add_argument("action", choices=("start", "stop", "restart"))
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--instance", default="")
    parser.add_argument("--port-profile", default=os.environ.get("METRICS_DASHBOARD_PORT_PROFILE", ""))
    parser.add_argument("--service-config", default=str(Path(__file__).with_name("e2e_bug_trend.services.json")))
    parser.add_argument("--django-ports", default="")
    parser.add_argument("--grafana-ports", default="")
    parser.add_argument("--scope-id", default="")
    parser.add_argument("--scope-name", default="chiplet-2a-jira")
    parser.add_argument("--begin", default="2026-06-01")
    parser.add_argument("--end", default="2026-08-09")
    parser.add_argument("--grafana-bin", default=os.environ.get("GRAFANA_BIN", ""))
    parser.add_argument("--grafana-homepath", default=os.environ.get("GRAFANA_HOMEPATH", ""))
    parser.add_argument("--open-entrypoint", choices=("grafana", "workbench", "none"), default="workbench")
    parser.add_argument("--force-by-port", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    service_config = Path(args.service_config).resolve()
    runtime_profile = load_or_create_dashboard_runtime_instance_profile(
        workspace_root=workspace,
        repo_root=workspace,
        port_profile=_blank_to_none(args.port_profile),
        instance_id=_blank_to_none(args.instance) or _blank_to_none(os.environ.get("METRICS_DASHBOARD_RUNTIME_INSTANCE_ID", "")),
    )
    lifecycle = ServiceLifecycleEngine(
        project_name=load_project_name(service_config, "metrics-bug-trend"),
        workspace=workspace,
        instance_name=runtime_profile.lifecycle_instance_name,
        state_directory=runtime_profile.service_lifecycle_state_dir,
    )
    run_id = str(uuid.uuid4())

    if args.action == "stop":
        stop_runtime(lifecycle, args, run_id, runtime_profile)
    else:
        start_runtime(args, workspace, lifecycle, runtime_profile, run_id)


def start_runtime(
    args: argparse.Namespace,
    workspace: Path,
    lifecycle: ServiceLifecycleEngine,
    runtime_profile: ScrumDashboardRuntimeInstanceProfile | None = None,
    run_id: str | None = None,
) -> None:
    grafana_bin = resolve_grafana_bin(args.grafana_bin)
    grafana_homepath = resolve_grafana_homepath(args.grafana_homepath, grafana_bin)
    python_executable = sys.executable
    specs = apply_runtime_profile_to_specs(load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath), runtime_profile)
    runtime_scope_id = args.scope_id

    def after_prepare(stop_results: Sequence[object]) -> None:
        nonlocal runtime_scope_id
        print_stop_results(stop_results)
        profile_step(lifecycle, "migrate", lambda: run([python_executable, "manage.py", "migrate"], workspace), run_id=run_id)
        profile_step(lifecycle, "seed_bug_trend_sample", lambda: run([python_executable, "manage.py", "seed_bug_trend_sample"], workspace), run_id=run_id)
        if not runtime_scope_id:
            runtime_scope_id = profile_step(lifecycle, "resolve_bug_trend_scope", lambda: resolve_scope_id_by_name(workspace, python_executable, args.scope_name), run_id=run_id)
        profile_step(
            lifecycle,
            "validate_grafana_artifacts",
            lambda: run([
                python_executable,
                "scripts/validate_grafana_artifacts.py",
                "--artifact-root",
                "ops/grafana",
                "--allowlist",
                "openspec/docs/current-baseline/grafana-approved-data-surfaces.json",
            ], workspace),
            run_id=run_id,
        )
        profile_step(lifecycle, "django_check", lambda: run([python_executable, "manage.py", "check"], workspace), run_id=run_id)

    def before_start(port_plan: Mapping[str, int], service_specs: Sequence[ServiceSpec]) -> Sequence[ServiceSpec]:
        django_port = port_plan["django"]
        grafana_port = port_plan["grafana"]
        runtime_grafana_config = profile_step(lifecycle, "write_grafana_config", lambda: write_runtime_grafana_config(workspace, grafana_port), run_id=run_id)
        runtime_specs = apply_runtime_profile_to_specs(
            load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath, grafana_config=runtime_grafana_config),
            runtime_profile,
        )
        print(f"E2E selected ports: Django={django_port}, Grafana={grafana_port}")
        return (runtime_specs["django"], runtime_specs["grafana"])

    restart_result = lifecycle.restart_services(
        tuple(specs.values()),
        graceful_timeout_seconds=5.0,
        force_by_port=args.force_by_port,
        run_id=run_id,
        after_prepare=after_prepare,
        before_start=before_start,
    )
    django_port = restart_result.port_plan["django"]
    grafana_port = restart_result.port_plan["grafana"]

    profile_step(lifecycle, "configure_grafana_datasource", lambda: configure_grafana_datasource(grafana_port, django_port), run_id=run_id)
    profile_step(lifecycle, "import_grafana_dashboard", lambda: import_grafana_dashboard(workspace, grafana_port, django_port, runtime_scope_id, args.begin, args.end), run_id=run_id)
    profile_step(lifecycle, "validate_runtime", lambda: validate_runtime(workspace, grafana_port, django_port, runtime_scope_id, args.begin, args.end), run_id=run_id)

    dashboard_url = grafana_dashboard_url(grafana_port, runtime_scope_id, args.begin, args.end)
    workbench_url = workbench_url_for(django_port, runtime_scope_id, args.begin, args.end)
    profile_step(lifecycle, "write_e2e_summary", lambda: write_e2e_summary(workspace, django_port, grafana_port, dashboard_url, workbench_url), run_id=run_id)
    entrypoint_url = entrypoint_url_for(args.open_entrypoint, dashboard_url, workbench_url)
    if entrypoint_url:
        profile_step(lifecycle, "open_browser", lambda: open_browser(entrypoint_url), run_id=run_id)
    print(f"E2E Bug Trend is ready: {entrypoint_url or workbench_url}")

def stop_runtime(
    lifecycle: ServiceLifecycleEngine,
    args: argparse.Namespace,
    run_id: str | None = None,
    runtime_profile: ScrumDashboardRuntimeInstanceProfile | None = None,
) -> None:
    results = profile_step(lifecycle, "stop_registered_services", lambda: lifecycle.stop_all(graceful_timeout_seconds=5.0), run_id=run_id)
    if args.force_by_port:
        results.extend(profile_step(lifecycle, "force_stop_by_ports", lambda: lifecycle.force_stop_by_ports(force_stop_specs(args, runtime_profile), graceful_timeout_seconds=0.5), run_id=run_id))
    print_stop_results(results, empty_message="No E2E services registered.")

def print_stop_results(results: Sequence[object], empty_message: str = "") -> None:
    if not results:
        if empty_message:
            print(empty_message)
        return
    for result in results:
        status = "stopped" if result.stopped else result.reason
        print(f"{result.name} {status} on 127.0.0.1:{result.port}")


def force_stop_specs(args: argparse.Namespace, runtime_profile: ScrumDashboardRuntimeInstanceProfile | None = None) -> tuple[ServiceSpec, ...]:
    specs = load_specs(args, Path(args.workspace).resolve(), sys.executable, args.grafana_bin or "grafana", args.grafana_homepath or "")
    return tuple(apply_runtime_profile_to_specs(specs, runtime_profile).values())

def load_specs(
    args: argparse.Namespace,
    workspace: Path,
    python_executable: str,
    grafana_bin: str,
    grafana_homepath: str,
    grafana_config: Path | str = "{grafana_config}",
) -> dict[str, ServiceSpec]:
    specs = load_service_specs(
        args.service_config,
        workspace,
        {
            "python": python_executable,
            "grafana_bin": grafana_bin,
            "grafana_homepath": grafana_homepath,
            "grafana_config": str(grafana_config),
        },
    )
    return {
        "django": replace_ports(specs["django"], parse_ports(args.django_ports)) if args.django_ports else specs["django"],
        "grafana": replace_ports(specs["grafana"], parse_ports(args.grafana_ports)) if args.grafana_ports else specs["grafana"],
    }

def replace_ports(spec: ServiceSpec, ports: tuple[int, ...]) -> ServiceSpec:
    return ServiceSpec(
        name=spec.name,
        preferred_ports=ports or spec.preferred_ports,
        command=spec.command,
        stop_command=spec.stop_command,
        host=spec.host,
        cwd=spec.cwd,
        env=spec.env,
        health_url=spec.health_url,
        listener_identity_url=spec.listener_identity_url,
        startup_timeout_seconds=spec.startup_timeout_seconds,
        graceful_timeout_seconds=spec.graceful_timeout_seconds,
        port_release_timeout_seconds=spec.port_release_timeout_seconds,
    )


def apply_runtime_profile_to_specs(
    specs: Mapping[str, ServiceSpec],
    runtime_profile: ScrumDashboardRuntimeInstanceProfile | None,
) -> dict[str, ServiceSpec]:
    if runtime_profile is None:
        return dict(specs)
    return {
        name: replace_ports(spec, prioritize_profile_port(spec.preferred_ports, runtime_profile, name))
        for name, spec in specs.items()
    }


def _blank_to_none(value: str | None) -> str | None:
    text = str(value or "").strip()
    return text or None


def run(command: list[str], workspace: Path) -> None:
    subprocess.run(command, cwd=workspace, check=True)


def resolve_scope_id_by_name(workspace: Path, python_executable: str, scope_name: str) -> str:
    command = [
        python_executable,
        "manage.py",
        "shell",
        "-c",
        f"from bug_metrics.models import JiraScopeConfig; print(JiraScopeConfig.objects.get(name={scope_name!r}).id)",
    ]
    completed = subprocess.run(command, cwd=workspace, check=True, text=True, capture_output=True)
    for line in reversed(completed.stdout.splitlines()):
        normalized = line.strip()
        if normalized.isdigit():
            return normalized
    raise RuntimeError(f"Could not resolve Bug Trend scope id for {scope_name}.")


def timed_step(label: str, callback: Callable[[], T]) -> T:
    started_at = time.perf_counter()
    try:
        return callback()
    finally:
        elapsed_seconds = time.perf_counter() - started_at
        print(f"E2E timing {label}: {elapsed_seconds:.2f}s")


def profile_step(lifecycle: LifecycleProfiler, label: str, callback: Callable[[], T], run_id: str | None = None) -> T:
    if hasattr(lifecycle, "profile_step"):
        return lifecycle.profile_step(label, callback, run_id=run_id, prefix="E2E timing")
    return timed_step(label, callback)


def parse_ports(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def resolve_grafana_bin(configured: str) -> str:
    if configured:
        return configured
    windows_default = Path(r"C:\Program Files\GrafanaLabs\grafana\bin\grafana.exe")
    if windows_default.exists():
        return str(windows_default)
    found = shutil.which("grafana")
    if found:
        return found
    raise RuntimeError("Grafana executable not found. Set GRAFANA_BIN or pass --grafana-bin.")


def resolve_grafana_homepath(configured: str, grafana_bin: str) -> str:
    if configured:
        return configured
    binary_path = Path(grafana_bin)
    if binary_path.name.lower().startswith("grafana") and binary_path.parent.name.lower() == "bin":
        return str(binary_path.parent.parent)
    return str(binary_path.parent)


request_json = runtime_ops.request_json
assert_http_ok = runtime_ops.assert_http_ok
grafana_dashboard_url = runtime_ops.grafana_dashboard_url
workbench_url_for = runtime_ops.workbench_url_for
entrypoint_url_for = runtime_ops.entrypoint_url_for
write_e2e_summary = runtime_ops.write_e2e_summary
open_browser = runtime_ops.open_browser


def configure_grafana_datasource(grafana_port: int, django_port: int) -> None:
    runtime_ops.request_json = request_json
    runtime_ops.configure_grafana_datasource(grafana_port, django_port)


def import_grafana_dashboard(workspace: Path, grafana_port: int, django_port: int, scope_id: str, begin: str, end: str) -> None:
    runtime_ops.request_json = request_json
    runtime_ops.import_grafana_dashboard(workspace, grafana_port, django_port, scope_id, begin, end)


def validate_runtime(workspace: Path, grafana_port: int, django_port: int, scope_id: str, begin: str, end: str) -> None:
    runtime_ops.request_json = request_json
    runtime_ops.assert_http_ok = assert_http_ok
    runtime_ops.validate_runtime(workspace, grafana_port, django_port, scope_id, begin, end)


if __name__ == "__main__":
    main()
