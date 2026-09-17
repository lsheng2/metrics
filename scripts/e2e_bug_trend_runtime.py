from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


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


def import_grafana_dashboard(workspace: Path, grafana_port: int, django_port: int, scope_id: str, begin: str, end: str) -> None:
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
    rewrite_workbench_links(dashboard, django_port)
    request_json(
        "POST",
        f"http://127.0.0.1:{grafana_port}/api/dashboards/db",
        {"dashboard": dashboard, "overwrite": True, "message": "Import Metrics Bug Trend C-stock dashboard"},
    )


def rewrite_workbench_links(dashboard: dict[str, object], django_port: int) -> None:
    base_url = f"http://127.0.0.1:{django_port}"
    for panel in dashboard.get("panels", []):
        if not isinstance(panel, dict):
            continue
        defaults = panel.get("fieldConfig", {}).get("defaults", {})
        for link in defaults.get("links", []):
            if not isinstance(link, dict):
                continue
            link_url = str(link.get("url", ""))
            if link_url.startswith("/workbench/"):
                link["url"] = base_url + link_url


def validate_runtime(workspace: Path, grafana_port: int, django_port: int, scope_id: str, begin: str, end: str) -> None:
    assert_http_ok(f"http://127.0.0.1:{django_port}/api/charts/data/?scope_id={scope_id}&begin={begin}&end={end}&chart_id=default_bug_trend")
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/datasources/uid/metrics-bug-trend-api", auth=True)
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/plugins/yesoreyeram-infinity-datasource/settings", auth=True)
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/datasources/proxy/uid/metrics-bug-trend-api/api/charts/data/?scope_id={scope_id}&begin={begin}&end={end}&chart_id=default_bug_trend", auth=True)
    dashboard = request_json("GET", f"http://127.0.0.1:{grafana_port}/api/dashboards/uid/metrics-bug-trend-c-stock")
    target_url = dashboard["dashboard"]["panels"][0]["targets"][0]["url"]
    link_url = dashboard["dashboard"]["panels"][0]["fieldConfig"]["defaults"]["links"][0]["url"]
    if "chart_id=default_bug_trend" not in target_url or "chart_id=default_bug_trend" not in link_url:
        raise RuntimeError("Imported Grafana dashboard is missing chart_id=default_bug_trend")
    if f"http://127.0.0.1:{django_port}/workbench/grafana-selection/" not in link_url:
        raise RuntimeError("Imported Grafana dashboard evidence link does not return to the Dashboard workbench")


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
    deadline = time.monotonic() + 10.0
    while True:
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise RuntimeError(f"Expected HTTP 2xx from {url}, got {response.status}")
                return
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Expected HTTP 2xx from {url}, got {error.code}") from error
        except urllib.error.URLError as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Expected HTTP 2xx from {url}, got connection error {type(error.reason).__name__}") from error
            time.sleep(0.25)


def basic_auth() -> str:
    token = base64.b64encode(b"admin:admin").decode("ascii")
    return f"Basic {token}"


def grafana_dashboard_url(grafana_port: int, scope_id: str, begin: str, end: str) -> str:
    return f"http://127.0.0.1:{grafana_port}/d/metrics-bug-trend-c-stock/metrics-bug-trend-c-stock-spike?orgId=1&var-scope_id={scope_id}&var-begin={begin}&var-end={end}"


def workbench_url_for(django_port: int, scope_id: str, begin: str, end: str) -> str:
    return f"http://127.0.0.1:{django_port}/workbench/?scope_id={scope_id}&begin={begin}&end={end}&chart_id=default_bug_trend"


def entrypoint_url_for(open_entrypoint: str, dashboard_url: str, workbench_url: str) -> str:
    if open_entrypoint == "grafana":
        return dashboard_url
    if open_entrypoint == "workbench":
        return workbench_url
    return ""


def write_e2e_summary(workspace: Path, django_port: int, grafana_port: int, dashboard_url: str, workbench_url: str) -> None:
    summary_path = workspace / "state" / "e2e" / "bug_trend_ports.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "django_port": django_port,
                "grafana_port": grafana_port,
                "dashboard_url": dashboard_url,
                "workbench_url": workbench_url,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def open_browser(url: str) -> None:
    if sys.platform == "win32":
        os.startfile(url)
        return
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    if shutil.which(opener):
        subprocess.Popen([opener, url])
