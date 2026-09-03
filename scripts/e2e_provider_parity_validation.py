from __future__ import annotations

import urllib.parse
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None

import e2e_bug_trend

DASHBOARD_UID = "ip-quality-dashboard"
DATASOURCE_UID = "metrics-bug-trend-api"
SUPPORTED_STATE = "supported"
HSDES_CONFIGURATION_REQUIRED_STATE = "configuration_required"
LIVE_SYNCED_STATE = "live_synced"
FIRST_WAVE_DEFERRED_STATE = "deferred"

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


def validate_runtime(workspace: Path, grafana_port: int, django_port: int, settings) -> None:
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
            resolved_url = resolve_target_url(target["url"], settings.target_variables())
            direct_url = f"http://127.0.0.1:{django_port}{resolved_url}"
            proxy_url = f"http://127.0.0.1:{grafana_port}/api/datasources/proxy/uid/{DATASOURCE_UID}{resolved_url}"
            assert_http_ok(direct_url)
            assert_http_ok(proxy_url, auth=True)
            state = validate_target_payload(panel["title"], target, request_json("GET", direct_url))
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
        states = payload.get("provider_series_state") or []
        state_reason = str(states[0].get("reason", "")) if states and isinstance(states[0], dict) else ""
        if not (payload.get("reason") or state_reason):
            raise RuntimeError(f"{panel_title} returned {status} without a visible reason")
        return status
    rows = payload.get("grafana_rows") or []
    if not rows:
        raise RuntimeError(f"{panel_title} expected nonblank Grafana rows")
    provider_prefixed_fields = sorted({key for row in rows if isinstance(row, dict) for key in row if key.startswith(("jira_", "hsdes_"))})
    if provider_prefixed_fields:
        raise RuntimeError(f"{panel_title} returned provider-prefixed Grafana row fields: {', '.join(provider_prefixed_fields)}")
    value_fields = contract.get("valueFields") or [key for row in rows for key, value in row.items() if isinstance(value, (int, float)) and key not in {"chart_version", "mapping_version"}]
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
    missing_fields = [field for field in sorted({"provider_id", "profile_id", "status", "data_status", "data_status_reason", "time_range_action_label", "time_range_action_url"}) if field not in rows[0]]
    if missing_fields:
        raise RuntimeError(f"{panel_title} missing profile readiness fields: {', '.join(missing_fields)}")
    if not rows[0].get("provider_id") or not rows[0].get("profile_id"):
        raise RuntimeError(f"{panel_title} expected resolved provider and profile")
    data_status = str(rows[0].get("data_status"))
    valid_statuses = {SUPPORTED_STATE, LIVE_SYNCED_STATE, "ready", "seeded_preview", HSDES_CONFIGURATION_REQUIRED_STATE, FIRST_WAVE_DEFERRED_STATE, "unsupported", "stale", "unavailable", "blocked"}
    if data_status not in valid_statuses:
        raise RuntimeError(f"{panel_title} returned unsupported profile data status {data_status}")
    if data_status not in {SUPPORTED_STATE, "ready"} and not rows[0].get("data_status_reason"):
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
    return urllib.parse.urlunparse(("", "", parsed.path, "", urllib.parse.urlencode(query), ""))


def query_value(url: str, name: str) -> str:
    return url_query_values(url).get(name, "")


def url_query_values(url: str) -> dict[str, str]:
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query, keep_blank_values=True))


def grafana_dashboard_url(grafana_port: int, settings) -> str:
    query_values = {"orgId": "1", **{f"var-{name}": value for name, value in settings.variables().items()}, **settings.grafana_time_range(), "timezone": "browser"}
    return f"http://127.0.0.1:{grafana_port}/d/{DASHBOARD_UID}/ip-quality-dashboard?{urllib.parse.urlencode(query_values)}"


def validate_visible_dashboard(grafana_port: int, dashboard_url: str, workspace: Path) -> None:
    if sync_playwright is None:
        raise RuntimeError("Playwright is required for browser dashboard validation. Install playwright or use --skip-browser.")
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    try:
        page.goto(dashboard_url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_function("document.body && document.body.innerText.includes('Open Bug Trend')", timeout=60000)
        assert_visible_dashboard_text(page.locator("body").inner_text(timeout=30000))
        page.wait_for_function(f"() => ({NONBLANK_CANVAS_SCRIPT})(Array.from(document.querySelectorAll('canvas')))", timeout=60000)
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
    required_labels = ("QUALITY", "Open Bug Trend", "Quality Chart Health", "EXECUTION", "Execution Metrics Not Mapped Yet", "EFFICIENCY", "Open Bug Aging", "Efficiency Metrics Not Mapped Yet")
    for label in required_labels:
        if label not in body_text:
            raise RuntimeError(f"Grafana dashboard did not visibly render {label}")


def has_nonblank_canvas(page) -> bool:
    return page.locator("canvas").evaluate_all(NONBLANK_CANVAS_SCRIPT)


def request_json(method: str, url: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    return e2e_bug_trend.request_json(method, url, payload)


def assert_http_ok(url: str, auth: bool = False) -> None:
    e2e_bug_trend.assert_http_ok(url, auth)
