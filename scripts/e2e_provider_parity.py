from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence, TypeVar

from playwright.sync_api import sync_playwright

import e2e_bug_trend
from port_lifecycle import PortLifecycle, ServiceSpec, load_project_name

T = TypeVar("T")

DASHBOARD_UID = "metrics-provider-parity-dashboard"
DATASOURCE_UID = "metrics-bug-trend-api"
SUPPORTED_STATE = "supported"
HSDES_CONFIGURATION_REQUIRED_STATE = "configuration_required"
LIVE_SYNCED_STATE = "live_synced"
FIRST_WAVE_DEFERRED_STATE = "deferred"
PROVIDER_ID_BY_PROFILE = {
    "chiplet-2a-jira": "jira",
    "nvu-ttl-hsdes": "hsdes",
}
NONBLANK_CANVAS_SCRIPT = """
canvases => canvases.some(canvas => {
    if (canvas.width === 0 || canvas.height === 0) return false;
    const context = canvas.getContext('2d');
    if (!context) return false;
    const sampleWidth = Math.min(canvas.width, 320);
    const sampleHeight = Math.min(canvas.height, 240);
    const pixels = context.getImageData(0, 0, sampleWidth, sampleHeight).data;
    for (let index = 3; index < pixels.length; index += 4) {
        if (pixels[index] !== 0) return true;
    }
    return false;
})
"""


@dataclass(frozen=True, slots=True)
class ProviderParitySettings:
    provider_id: str = ""
    profile_id: str = "chiplet-2a-jira"
    space_id: str = "chiplet_ip"
    release_target: str = "chiplet"
    milestone: str = "2a"
    begin_ww: str = "26WW32"
    end_ww: str = "26WW32"
    skip_browser: bool = False

    def variables(self) -> dict[str, str]:
        return {
            "profile_id": self.profile_id,
            "begin_ww": self.begin_ww,
            "end_ww": self.end_ww,
        }

    def resolved_provider_id(self) -> str:
        profile_provider_id = PROVIDER_ID_BY_PROFILE.get(self.profile_id, "")
        if self.provider_id and profile_provider_id and self.provider_id != profile_provider_id:
            raise ValueError(f"Provider {self.provider_id} does not match selected profile {self.profile_id}.")
        return self.provider_id or profile_provider_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Start/stop the Provider Parity Grafana E2E runtime.")
    parser.add_argument("action", choices=("start", "stop", "restart"))
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--instance", default="provider-parity")
    parser.add_argument("--service-config", default=str(Path(__file__).with_name("e2e_bug_trend.services.json")))
    parser.add_argument("--django-ports", default="")
    parser.add_argument("--grafana-ports", default="")
    parser.add_argument("--grafana-bin", default="")
    parser.add_argument("--grafana-homepath", default="")
    parser.add_argument("--force-by-port", action="store_true")
    parser.add_argument("--provider-id", default="")
    parser.add_argument("--profile-id", default="chiplet-2a-jira")
    parser.add_argument("--space-id", default="chiplet_ip")
    parser.add_argument("--release-target", default="chiplet")
    parser.add_argument("--milestone", default="2a")
    parser.add_argument("--begin-ww", default="26WW32")
    parser.add_argument("--end-ww", default="26WW32")
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    lifecycle = PortLifecycle(
        project_name=load_project_name(Path(args.service_config), "metrics-provider-parity"),
        workspace=workspace,
        instance_name=args.instance,
        state_directory=workspace / "state" / "e2e" / "port-lifecycle",
    )
    run_id = f"provider-parity-{int(time.time())}"
    settings = ProviderParitySettings(
        provider_id=args.provider_id,
        profile_id=args.profile_id,
        space_id=args.space_id,
        release_target=args.release_target,
        milestone=args.milestone,
        begin_ww=args.begin_ww,
        end_ww=args.end_ww,
        skip_browser=args.skip_browser,
    )

    if args.action == "stop":
        e2e_bug_trend.stop_runtime(lifecycle, args, run_id)
        return
    start_runtime(args, workspace, lifecycle, settings, run_id)


def start_runtime(args: argparse.Namespace, workspace: Path, lifecycle: PortLifecycle, settings: ProviderParitySettings, run_id: str | None = None) -> None:
    grafana_bin = e2e_bug_trend.resolve_grafana_bin(args.grafana_bin)
    grafana_homepath = e2e_bug_trend.resolve_grafana_homepath(args.grafana_homepath, grafana_bin)
    python_executable = sys.executable
    specs = e2e_bug_trend.load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath)

    def after_prepare(stop_results: Sequence[object]) -> None:
        e2e_bug_trend.print_stop_results(stop_results)
        profile_step(lifecycle, "migrate", lambda: e2e_bug_trend.run([python_executable, "manage.py", "migrate"], workspace), run_id=run_id)
        profile_step(lifecycle, "seed_bug_trend_sample", lambda: e2e_bug_trend.run([python_executable, "manage.py", "seed_bug_trend_sample"], workspace), run_id=run_id)
        profile_step(
            lifecycle,
            "validate_grafana_artifacts",
            lambda: e2e_bug_trend.run([
                python_executable,
                "scripts/validate_grafana_artifacts.py",
                "--artifact-root",
                "ops/grafana",
                "--allowlist",
                "openspec/docs/current-baseline/grafana-approved-data-surfaces.json",
            ], workspace),
            run_id=run_id,
        )
        profile_step(lifecycle, "django_check", lambda: e2e_bug_trend.run([python_executable, "manage.py", "check"], workspace), run_id=run_id)

    def before_start(port_plan: Mapping[str, int], service_specs: Sequence[ServiceSpec]) -> Sequence[ServiceSpec]:
        grafana_port = port_plan["grafana"]
        runtime_grafana_config = profile_step(lifecycle, "write_grafana_config", lambda: e2e_bug_trend.write_runtime_grafana_config(workspace, grafana_port), run_id=run_id)
        runtime_specs = e2e_bug_trend.load_specs(args, workspace, python_executable, grafana_bin, grafana_homepath, grafana_config=runtime_grafana_config)
        print(f"E2E selected ports: Django={port_plan['django']}, Grafana={grafana_port}")
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

    profile_step(lifecycle, "configure_grafana_datasource", lambda: e2e_bug_trend.configure_grafana_datasource(grafana_port, django_port), run_id=run_id)
    profile_step(lifecycle, "import_provider_parity_dashboard", lambda: import_grafana_dashboard(workspace, grafana_port, settings), run_id=run_id)
    profile_step(lifecycle, "validate_provider_parity_runtime", lambda: validate_runtime(workspace, grafana_port, django_port, settings), run_id=run_id)

    dashboard_url = grafana_dashboard_url(grafana_port, settings)
    profile_step(lifecycle, "write_provider_parity_summary", lambda: write_e2e_summary(workspace, django_port, grafana_port, dashboard_url), run_id=run_id)
    if not settings.skip_browser:
        profile_step(lifecycle, "open_browser", lambda: e2e_bug_trend.open_browser(dashboard_url), run_id=run_id)
    print(f"E2E Provider Parity Dashboard is ready: {dashboard_url}")


def profile_step(lifecycle: object, label: str, callback: Callable[[], T], run_id: str | None = None) -> T:
    if hasattr(lifecycle, "profile_step"):
        return lifecycle.profile_step(label, callback, run_id=run_id, prefix="E2E timing")
    return e2e_bug_trend.timed_step(label, callback)


def import_grafana_dashboard(workspace: Path, grafana_port: int, settings: ProviderParitySettings) -> None:
    artifact = workspace / "ops" / "grafana" / "provider_parity_dashboard.json"
    dashboard = json.loads(artifact.read_text(encoding="utf-8"))
    variables = settings.variables()
    for variable in dashboard["templating"]["list"]:
        value = variables.get(variable["name"])
        if value is None:
            continue
        if variable.get("type") != "custom":
            variable["query"] = value
        variable["current"] = {"text": value, "value": value}
        for option in variable.get("options", []):
            if isinstance(option, dict):
                option["selected"] = option.get("value") == value
    request_json(
        "POST",
        f"http://127.0.0.1:{grafana_port}/api/dashboards/db",
        {"dashboard": dashboard, "overwrite": True, "message": "Import Metrics Provider Parity dashboard"},
    )


def validate_runtime(workspace: Path, grafana_port: int, django_port: int, settings: ProviderParitySettings) -> None:
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/datasources/uid/{DATASOURCE_UID}", auth=True)
    assert_http_ok(f"http://127.0.0.1:{grafana_port}/api/plugins/yesoreyeram-infinity-datasource/settings", auth=True)
    dashboard = request_json("GET", f"http://127.0.0.1:{grafana_port}/api/dashboards/uid/{DASHBOARD_UID}")
    if dashboard["dashboard"]["uid"] != DASHBOARD_UID:
        raise RuntimeError(f"Imported Grafana dashboard uid mismatch: {dashboard['dashboard']['uid']}")

    validated_states = {"supported": 0, "configuration_required": 0, "deferred": 0}
    for panel in dashboard["dashboard"]["panels"]:
        for target in panel.get("targets", []):
            contract = target.get("metricsContract", {})
            if not contract:
                continue
            resolved_url = resolve_target_url(target["url"], settings.variables())
            direct_url = f"http://127.0.0.1:{django_port}{resolved_url}"
            proxy_url = f"http://127.0.0.1:{grafana_port}/api/datasources/proxy/uid/{DATASOURCE_UID}{resolved_url}"
            assert_http_ok(direct_url)
            assert_http_ok(proxy_url, auth=True)
            payload = request_json("GET", direct_url)
            state = validate_target_payload(panel["title"], target, payload)
            if state in validated_states:
                validated_states[state] += 1

    missing_states = [state for state in expected_runtime_states(settings.resolved_provider_id()) if validated_states.get(state, 0) == 0]
    if missing_states:
        raise RuntimeError(f"Provider parity runtime did not validate expected states: {', '.join(missing_states)}")
    if not settings.skip_browser:
        validate_visible_dashboard(grafana_port, grafana_dashboard_url(grafana_port, settings), workspace)


def validate_target_payload(panel_title: str, target: dict[str, object], payload: dict[str, object]) -> str:
    contract = target["metricsContract"]
    shape = contract["shape"]
    if shape == "wide_bucket_series":
        return validate_supported_payload(panel_title, contract, payload)
    if shape == "provider_series_state":
        return validate_state_payload(panel_title, contract, payload)
    if shape == "profile_readiness_summary":
        return validate_profile_readiness_payload(panel_title, payload)
    raise RuntimeError(f"Unsupported provider parity target shape {shape} in {panel_title}")


def validate_supported_payload(panel_title: str, contract: dict[str, object], payload: dict[str, object]) -> str:
    status = str(payload.get("status"))
    if status != SUPPORTED_STATE:
        if status not in {LIVE_SYNCED_STATE, HSDES_CONFIGURATION_REQUIRED_STATE, FIRST_WAVE_DEFERRED_STATE, "unsupported", "stale", "unavailable"}:
            raise RuntimeError(f"{panel_title} returned unsupported wide-series state {status}")
        if payload.get("grafana_rows"):
            raise RuntimeError(f"{panel_title} returned {status} with unexpected Grafana rows")
        state_reason = ""
        states = payload.get("provider_series_state") or []
        if states and isinstance(states[0], dict):
            state_reason = str(states[0].get("reason", ""))
        if not (payload.get("reason") or state_reason):
            raise RuntimeError(f"{panel_title} returned {status} without a visible reason")
        return status
    rows = payload.get("grafana_rows") or []
    if not rows:
        raise RuntimeError(f"{panel_title} expected nonblank Grafana rows")
    provider_prefixed_fields = sorted({
        key
        for row in rows
        if isinstance(row, dict)
        for key in row
        if key.startswith(("jira_", "hsdes_"))
    })
    if provider_prefixed_fields:
        raise RuntimeError(f"{panel_title} returned provider-prefixed Grafana row fields: {', '.join(provider_prefixed_fields)}")
    value_fields = contract.get("valueFields") or [
        key
        for row in rows
        for key, value in row.items()
        if isinstance(value, (int, float)) and key not in {"chart_version", "mapping_version"}
    ]
    if not any(isinstance(row.get(field), (int, float)) for row in rows for field in value_fields):
        raise RuntimeError(f"{panel_title} expected at least one numeric provider series value")
    return SUPPORTED_STATE


def validate_state_payload(panel_title: str, contract: dict[str, object], payload: dict[str, object]) -> str:
    states = payload.get("provider_series_state") or []
    if not states:
        raise RuntimeError(f"{panel_title} expected provider_series_state rows")
    state = states[0].get("status")
    reason = states[0].get("reason")
    expected_state = expected_state_for_binding(str(contract.get("providerBinding", "")))
    if expected_state != "selected_provider_runtime_state" and state != expected_state:
        raise RuntimeError(f"{panel_title} expected {expected_state} state, got {state}")
    if expected_state == "selected_provider_runtime_state" and state not in {SUPPORTED_STATE, LIVE_SYNCED_STATE, HSDES_CONFIGURATION_REQUIRED_STATE, FIRST_WAVE_DEFERRED_STATE, "unsupported", "stale", "unavailable"}:
        raise RuntimeError(f"{panel_title} returned unsupported selected-provider state {state}")
    if not reason and state != SUPPORTED_STATE:
        raise RuntimeError(f"{panel_title} expected a visible state reason")
    return str(state)


def validate_profile_readiness_payload(panel_title: str, payload: dict[str, object]) -> str:
    rows = payload.get("profile_status_rows") or []
    if not rows or not isinstance(rows[0], dict):
        raise RuntimeError(f"{panel_title} expected profile_status_rows")
    row = rows[0]
    required_fields = {"provider_id", "profile_id", "status", "data_status", "data_status_reason"}
    missing_fields = [field for field in sorted(required_fields) if field not in row]
    if missing_fields:
        raise RuntimeError(f"{panel_title} missing profile readiness fields: {', '.join(missing_fields)}")
    if not row.get("provider_id") or not row.get("profile_id"):
        raise RuntimeError(f"{panel_title} expected resolved provider and profile")
    data_status = str(row.get("data_status"))
    if data_status not in {SUPPORTED_STATE, LIVE_SYNCED_STATE, "ready", "seeded_preview", HSDES_CONFIGURATION_REQUIRED_STATE, FIRST_WAVE_DEFERRED_STATE, "unsupported", "stale", "unavailable", "blocked"}:
        raise RuntimeError(f"{panel_title} returned unsupported profile data status {data_status}")
    if data_status not in {SUPPORTED_STATE, "ready"} and not row.get("data_status_reason"):
        raise RuntimeError(f"{panel_title} expected a visible profile status reason")
    return "profile_readiness"


def expected_state_for_binding(provider_binding: str) -> str:
    if provider_binding == "selected_provider_state":
        return "selected_provider_runtime_state"
    if provider_binding == "first_wave_deferred":
        return FIRST_WAVE_DEFERRED_STATE
    return SUPPORTED_STATE


def expected_runtime_states(provider_id: str) -> tuple[str, ...]:
    if provider_id == "hsdes":
        return (SUPPORTED_STATE, FIRST_WAVE_DEFERRED_STATE)
    return (SUPPORTED_STATE, FIRST_WAVE_DEFERRED_STATE)


def resolve_target_url(url: str, variables: dict[str, str]) -> str:
    parsed = urllib.parse.urlparse(url)
    query = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        resolved = variables.get(value[1:], value) if value.startswith("$") else value
        query.append((key, resolved))
    encoded = urllib.parse.urlencode(query)
    return urllib.parse.urlunparse(("", "", parsed.path, "", encoded, ""))


def query_value(url: str, name: str) -> str:
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query, keep_blank_values=True)).get(name, "")


def validate_visible_dashboard(grafana_port: int, dashboard_url: str, workspace: Path) -> None:
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    try:
        page.goto(dashboard_url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_function(
            "document.body && document.body.innerText.includes('QUALITY / Open Bug Trend')",
            timeout=60000,
        )
        body_text = page.locator("body").inner_text(timeout=30000)
        assert_visible_dashboard_text(body_text)
        page.wait_for_function(
            f"() => ({NONBLANK_CANVAS_SCRIPT})(Array.from(document.querySelectorAll('canvas')))",
            timeout=60000,
        )
        if not has_nonblank_canvas(page):
            raise RuntimeError("Grafana dashboard did not render a nonblank chart canvas")
        screenshot_path = workspace / "state" / "e2e" / "provider_parity_dashboard.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"Provider parity screenshot: {screenshot_path}")
    finally:
        page.close()
        browser.close()
        playwright.stop()


def assert_visible_dashboard_text(body_text: str) -> None:
    required_labels = (
        "QUALITY",
        "QUALITY / Open Bug Trend",
        "QUALITY / Selected Provider States",
        "EXECUTION",
        "EXECUTION / Deferred States",
        "EFFICIENCY",
        "EFFICIENCY / Open Bug Aging",
        "EFFICIENCY / Deferred States",
    )
    for label in required_labels:
        if label not in body_text:
            raise RuntimeError(f"Grafana dashboard did not visibly render {label}")


def has_nonblank_canvas(page) -> bool:
    return page.locator("canvas").evaluate_all(NONBLANK_CANVAS_SCRIPT)


def grafana_dashboard_url(grafana_port: int, settings: ProviderParitySettings) -> str:
    variables = urllib.parse.urlencode({
        f"var-{name}": value
        for name, value in settings.variables().items()
    })
    return f"http://127.0.0.1:{grafana_port}/d/{DASHBOARD_UID}/metrics-provider-parity-dashboard?orgId=1&{variables}"


def write_e2e_summary(workspace: Path, django_port: int, grafana_port: int, dashboard_url: str) -> None:
    summary_path = workspace / "state" / "e2e" / "provider_parity_ports.json"
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


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return e2e_bug_trend.request_json(method, url, payload)


def assert_http_ok(url: str, auth: bool = False) -> None:
    e2e_bug_trend.assert_http_ok(url, auth)


if __name__ == "__main__":
    main()
