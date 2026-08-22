from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, Mapping, Protocol, Sequence, TypeVar

from port_lifecycle import PortLifecycle, ServiceSpec, load_project_name, load_service_specs

T = TypeVar("T")


class LifecycleProfiler(Protocol):
    def profile_step(self, label: str, callback: Callable[[], T], run_id: str | None = None, prefix: str = "PortLifecycle timing") -> T:
        ...


def main() -> None:
    parser = argparse.ArgumentParser(description="Start/stop the Bug Trend E2E runtime.")
    parser.add_argument("action", choices=("start", "stop", "restart"))
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--instance", default="default")
    parser.add_argument("--service-config", default=str(Path(__file__).with_name("e2e_bug_trend.services.json")))
    parser.add_argument("--django-ports", default="")
    parser.add_argument("--grafana-ports", default="")
    parser.add_argument("--scope-id", default="3")
    parser.add_argument("--begin", default="2026-06-01")
    parser.add_argument("--end", default="2026-08-09")
    parser.add_argument("--grafana-bin", default=os.environ.get("GRAFANA_BIN", ""))
    parser.add_argument("--grafana-homepath", default=os.environ.get("GRAFANA_HOMEPATH", ""))
    parser.add_argument("--force-by-port", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    service_config = Path(args.service_config).resolve()
    lifecycle = PortLifecycle(
        project_name=load_project_name(service_config, "metrics-bug-trend"),
        workspace=workspace,
        instance_name=args.instance,
        state_directory=workspace / "state" / "e2e" / "port-lifecycle",
    )
    run_id = str(uuid.uuid4())

    if args.action == "stop":
        stop_runtime(lifecycle, args, run_id)
    else:
        start_runtime(args, workspace, lifecycle, run_id)


def start_runtime(args: argparse.Namespace, workspace: Path, lifecycle: PortLifecycle, run_id: str | None = None) -> None:
    grafana_bin = resolve_grafana_bin(args.grafana_bin)
    grafana_homepath = resolve_grafana_homepath(args.grafana_homepath, grafana_bin)
    python_executable = sys.executable
    specs = load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath)

    def after_prepare(stop_results: Sequence[object]) -> None:
        print_stop_results(stop_results)
        profile_step(lifecycle, "migrate", lambda: run([python_executable, "manage.py", "migrate"], workspace), run_id=run_id)
        profile_step(lifecycle, "seed_bug_trend_sample", lambda: run([python_executable, "manage.py", "seed_bug_trend_sample"], workspace), run_id=run_id)
        profile_step(
            lifecycle,
            "validate_grafana_artifacts",
            lambda: run([
                python_executable,
                "scripts/validate_grafana_artifacts.py",
                "--artifact-root",
                "ops/grafana",
                "--allowlist",
                "docs/grafana-approved-data-surfaces.json",
            ], workspace),
            run_id=run_id,
        )
        profile_step(lifecycle, "django_check", lambda: run([python_executable, "manage.py", "check"], workspace), run_id=run_id)

    def before_start(port_plan: Mapping[str, int], service_specs: Sequence[ServiceSpec]) -> Sequence[ServiceSpec]:
        django_port = port_plan["django"]
        grafana_port = port_plan["grafana"]
        runtime_grafana_config = profile_step(lifecycle, "write_grafana_config", lambda: write_runtime_grafana_config(workspace, grafana_port), run_id=run_id)
        runtime_specs = load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath, grafana_config=runtime_grafana_config)
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
    profile_step(lifecycle, "import_grafana_dashboard", lambda: import_grafana_dashboard(workspace, grafana_port, args.scope_id, args.begin, args.end), run_id=run_id)
    profile_step(lifecycle, "validate_runtime", lambda: validate_runtime(workspace, grafana_port, django_port, args.scope_id, args.begin, args.end), run_id=run_id)

    dashboard_url = grafana_dashboard_url(grafana_port, args.scope_id, args.begin, args.end)
    profile_step(lifecycle, "write_e2e_summary", lambda: write_e2e_summary(workspace, django_port, grafana_port, dashboard_url), run_id=run_id)
    profile_step(lifecycle, "open_browser", lambda: open_browser(dashboard_url), run_id=run_id)
    print(f"E2E Bug Trend is ready: {dashboard_url}")


def stop_runtime(lifecycle: PortLifecycle, args: argparse.Namespace, run_id: str | None = None) -> None:
    results = profile_step(lifecycle, "stop_registered_services", lambda: lifecycle.stop_all(graceful_timeout_seconds=5.0), run_id=run_id)
    if args.force_by_port:
        results.extend(profile_step(lifecycle, "force_stop_by_ports", lambda: lifecycle.force_stop_by_ports(force_stop_specs(args), graceful_timeout_seconds=0.5), run_id=run_id))
    print_stop_results(results, empty_message="No E2E services registered.")


def print_stop_results(results: Sequence[object], empty_message: str = "") -> None:
    if not results:
        if empty_message:
            print(empty_message)
        return
    for result in results:
        status = "stopped" if result.stopped else result.reason
        print(f"{result.name} {status} on 127.0.0.1:{result.port}")


def force_stop_specs(args: argparse.Namespace) -> tuple[ServiceSpec, ...]:
    specs = load_specs(args, Path(args.workspace).resolve(), sys.executable, args.grafana_bin or "grafana", args.grafana_homepath or "")
    return tuple(specs.values())


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


def run(command: list[str], workspace: Path) -> None:
    subprocess.run(command, cwd=workspace, check=True)


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


def write_runtime_grafana_config(workspace: Path, grafana_port: int) -> Path:
    source = workspace / "state" / "grafana" / "grafana.ini"
    runtime_directory = workspace / "state" / "grafana" / "runtime"
    runtime_directory.mkdir(parents=True, exist_ok=True)
    target = runtime_directory / f"grafana-e2e-{grafana_port}.ini"
    content = source.read_text(encoding="utf-8")
    lines = []
    for line in content.splitlines():
        if line.strip().startswith("http_port"):
            lines.append(f"http_port = {grafana_port}")
        elif line.strip().startswith("root_url"):
            lines.append(f"root_url = http://127.0.0.1:{grafana_port}/")
        else:
            lines.append(line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def configure_grafana_datasource(grafana_port: int, django_port: int) -> None:
    metrics_url = f"http://127.0.0.1:{django_port}"
    payload = {
        "name": "Metrics Bug Trend API",
        "uid": "metrics-bug-trend-api",
        "type": "yesoreyeram-infinity-datasource",
        "access": "proxy",
        "url": metrics_url,
        "isDefault": True,
        "jsonData": {
            "allowedHosts": [metrics_url],
            "auth_method": "none",
            "global_queries": [],
            "timeoutInSeconds": 60,
        },
        "editable": True,
    }
    upsert_grafana_datasource(grafana_port, payload)


def upsert_grafana_datasource(grafana_port: int, payload: dict[str, object]) -> None:
    try:
        request_json("PUT", f"http://127.0.0.1:{grafana_port}/api/datasources/uid/metrics-bug-trend-api", payload)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
        request_json("POST", f"http://127.0.0.1:{grafana_port}/api/datasources", payload)


def import_grafana_dashboard(workspace: Path, grafana_port: int, scope_id: str, begin: str, end: str) -> None:
    artifact = workspace / "ops" / "grafana" / "bug_trend_dashboard.json"
    dashboard = json.loads(artifact.read_text(encoding="utf-8"))
    for variable in dashboard["templating"]["list"]:
        if variable["name"] == "scope_id":
            variable["query"] = scope_id
            variable["current"] = {"text": scope_id, "value": scope_id}
        if variable["name"] == "begin":
            variable["query"] = begin
            variable["current"] = {"text": begin, "value": begin}
        if variable["name"] == "end":
            variable["query"] = end
            variable["current"] = {"text": end, "value": end}
    request_json(
        "POST",
        f"http://127.0.0.1:{grafana_port}/api/dashboards/db",
        {"dashboard": dashboard, "overwrite": True, "message": "Import Metrics Bug Trend C-stock dashboard"},
    )


def validate_runtime(workspace: Path, grafana_port: int, django_port: int, scope_id: str, begin: str, end: str) -> None:
    assert_http_ok(f"http://127.0.0.1:{django_port}/api/bug-trend/chart-data/?scope_id={scope_id}&begin={begin}&end={end}&chart_id=default_bug_trend")
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/datasources/uid/metrics-bug-trend-api", auth=True)
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/plugins/yesoreyeram-infinity-datasource/settings", auth=True)
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/datasources/proxy/uid/metrics-bug-trend-api/api/bug-trend/chart-data/?scope_id={scope_id}&begin={begin}&end={end}&chart_id=default_bug_trend", auth=True)
    dashboard = request_json("GET", f"http://127.0.0.1:{grafana_port}/api/dashboards/uid/metrics-bug-trend-c-stock")
    target_url = dashboard["dashboard"]["panels"][0]["targets"][0]["url"]
    link_url = dashboard["dashboard"]["panels"][0]["fieldConfig"]["defaults"]["links"][0]["url"]
    if "chart_id=default_bug_trend" not in target_url or "chart_id=default_bug_trend" not in link_url:
        raise RuntimeError("Imported Grafana dashboard is missing chart_id=default_bug_trend")


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", basic_auth())
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def assert_http_ok(url: str, auth: bool = False) -> None:
    request = urllib.request.Request(url)
    if auth:
        request.add_header("Authorization", basic_auth())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(f"Expected HTTP 2xx from {url}, got {response.status}")
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Expected HTTP 2xx from {url}, got {error.code}") from error


def basic_auth() -> str:
    token = base64.b64encode(b"admin:admin").decode("ascii")
    return f"Basic {token}"


def grafana_dashboard_url(grafana_port: int, scope_id: str, begin: str, end: str) -> str:
    return f"http://127.0.0.1:{grafana_port}/d/metrics-bug-trend-c-stock/metrics-bug-trend-c-stock-spike?orgId=1&var-scope_id={scope_id}&var-begin={begin}&var-end={end}"


def write_e2e_summary(workspace: Path, django_port: int, grafana_port: int, dashboard_url: str) -> None:
    summary_path = workspace / "state" / "e2e" / "bug_trend_ports.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "django_port": django_port,
                "grafana_port": grafana_port,
                "dashboard_url": dashboard_url,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def open_browser(url: str) -> None:
    if sys.platform == "win32":
        os.startfile(url)  # type: ignore[attr-defined]
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    if shutil.which(opener):
        subprocess.Popen([opener, url])


if __name__ == "__main__":
    main()
