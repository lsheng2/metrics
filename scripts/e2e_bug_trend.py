from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from port_lifecycle import PortLifecycle, ServiceSpec, load_project_name, load_service_specs


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

    if args.action in {"stop", "restart"}:
        stop_runtime(lifecycle, args)
    if args.action in {"start", "restart"}:
        start_runtime(args, workspace, lifecycle)


def start_runtime(args: argparse.Namespace, workspace: Path, lifecycle: PortLifecycle) -> None:
    grafana_bin = resolve_grafana_bin(args.grafana_bin)
    grafana_homepath = resolve_grafana_homepath(args.grafana_homepath, grafana_bin)
    python_executable = sys.executable
    specs = load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath)

    lifecycle.prepare_startup(tuple(specs.values()), graceful_timeout_seconds=5.0, force_by_port=args.force_by_port)

    run([python_executable, "manage.py", "migrate"], workspace)
    run([python_executable, "manage.py", "seed_bug_trend_sample"], workspace)
    run([
        python_executable,
        "scripts/validate_grafana_artifacts.py",
        "--artifact-root",
        "ops/grafana",
        "--allowlist",
        "docs/grafana-approved-data-surfaces.json",
    ], workspace)
    run([python_executable, "manage.py", "check"], workspace)

    django_spec = specs["django"]
    grafana_probe_spec = specs["grafana"]
    port_plan = lifecycle.resolve_plan((django_spec, grafana_probe_spec))
    django_port = port_plan["django"]
    grafana_port = port_plan["grafana"]
    runtime_grafana_config = write_runtime_grafana_config(workspace, grafana_port)
    specs = load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath, grafana_config=runtime_grafana_config)
    grafana_spec = specs["grafana"]

    print(f"E2E selected ports: Django={django_port}, Grafana={grafana_port}")
    lifecycle.start_service(django_spec, port=django_port)
    lifecycle.start_service(grafana_spec, port=grafana_port)

    configure_grafana_datasource(grafana_port, django_port)
    import_grafana_dashboard(workspace, grafana_port, args.scope_id, args.begin, args.end)
    validate_runtime(workspace, grafana_port, django_port, args.scope_id, args.begin, args.end)

    dashboard_url = grafana_dashboard_url(grafana_port, args.scope_id, args.begin, args.end)
    write_e2e_summary(workspace, django_port, grafana_port, dashboard_url)
    open_browser(dashboard_url)
    print(f"E2E Bug Trend is ready: {dashboard_url}")


def stop_runtime(lifecycle: PortLifecycle, args: argparse.Namespace) -> None:
    results = lifecycle.stop_all(graceful_timeout_seconds=5.0)
    if args.force_by_port:
        results.extend(lifecycle.force_stop_by_ports(force_stop_specs(args), graceful_timeout_seconds=0.5))
    if not results:
        print("No E2E services registered.")
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
