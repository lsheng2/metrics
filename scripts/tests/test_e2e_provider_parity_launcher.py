from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import e2e_provider_parity


def test_provider_parity_import_uses_provider_dashboard_and_profile_variables(monkeypatch, tmp_path):
    dashboard = {
        "uid": "ip-quality-dashboard",
        "title": "IP Quality Dashboard",
        "templating": {
            "list": [
                {"name": "profile_id", "type": "custom", "query": "chiplet-2a-jira,nvu-ttl-hsdes", "current": {}},
                {"name": "range_mode", "type": "custom", "query": "Work Week : ww,Date : date", "current": {}, "options": [
                    {"text": "Work Week", "value": "ww"},
                    {"text": "Date", "value": "date"},
                ]},
                {"name": "begin_ww", "query": "", "current": {}},
                {"name": "end_ww", "query": "", "current": {}},
            ]
        },
        "panels": [],
    }
    artifact = tmp_path / "ops" / "grafana" / "provider_parity_dashboard.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps(dashboard), encoding="utf-8")
    requests = []

    monkeypatch.setattr(e2e_provider_parity, "request_json", lambda method, url, payload=None: requests.append((method, url, payload)) or {})

    e2e_provider_parity.import_grafana_dashboard(
        tmp_path,
        3999,
        e2e_provider_parity.ProviderParitySettings(profile_id="chiplet-2a-jira", begin_ww="26WW32", end_ww="26WW32"),
    )

    imported = requests[0][2]["dashboard"]
    variables = {item["name"]: item for item in imported["templating"]["list"]}
    assert requests[0][1] == "http://127.0.0.1:3999/api/dashboards/db"
    assert imported["uid"] == "ip-quality-dashboard"
    assert "provider_id" not in variables
    assert "space_id" not in variables
    assert "release_target" not in variables
    assert "milestone" not in variables
    assert variables["profile_id"]["query"] == "chiplet-2a-jira,nvu-ttl-hsdes"
    assert variables["profile_id"]["current"]["value"] == "chiplet-2a-jira"
    assert variables["range_mode"]["current"]["text"] == "Work Week"
    assert variables["range_mode"]["current"]["value"] == "ww"
    assert variables["begin_ww"]["current"]["value"] == "26WW32"

    dashboard_url = e2e_provider_parity.grafana_dashboard_url(
        3999,
        e2e_provider_parity.ProviderParitySettings(profile_id="nvu-ttl-hsdes", begin_ww="26WW32", end_ww="26WW32"),
    )
    assert "/d/ip-quality-dashboard/ip-quality-dashboard" in dashboard_url
    assert "var-profile_id=nvu-ttl-hsdes" in dashboard_url
    assert "var-space_id" not in dashboard_url
    assert "var-release_target" not in dashboard_url
    assert "var-milestone" not in dashboard_url


def test_provider_parity_runtime_validation_checks_jira_supported_and_deferred_states(monkeypatch, tmp_path):
    dashboard = {
        "dashboard": {
            "uid": "ip-quality-dashboard",
            "panels": [
                {
                    "title": "Profile Status",
                    "targets": [{
                        "url": "/api/provider-profiles/readiness/?profile_id=$profile_id",
                        "metricsContract": {"shape": "profile_readiness_summary"},
                    }],
                },
                {
                    "title": "Open Bug Trend",
                    "targets": [{
                        "url": "/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=open_bug_trend&chart_version=1",
                        "metricsContract": {"shape": "wide_bucket_series"},
                    }],
                },
                {
                    "title": "Quality Chart Health",
                    "targets": [{
                        "url": "/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=open_bug_trend&chart_version=1",
                        "metricsContract": {"shape": "provider_series_state", "providerBinding": "selected_provider_state"},
                    }],
                },
                {
                    "title": "Execution Metrics Not Mapped Yet",
                    "targets": [{
                        "url": "/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=execution_statistics&chart_version=1",
                        "metricsContract": {"shape": "provider_series_state", "providerBinding": "first_wave_deferred"},
                    }],
                },
            ],
        }
    }
    json_responses = {
        "open_bug_trend:jira": {
            "status": "supported",
            "grafana_rows": [{"provider_id": "jira", "profile_id": "chiplet-2a-jira", "all_open_bugs": 3}],
            "provider_series_state": [{"status": "supported", "reason": ""}],
        },
        "execution_statistics:jira": {
            "status": "deferred",
            "grafana_rows": [],
            "provider_series_state": [{"status": "deferred", "reason": "Execution mappings deferred"}],
        },
    }
    checked_urls = []

    def fake_request_json(method, url, payload=None):
        if url.endswith("/api/dashboards/uid/ip-quality-dashboard"):
            return dashboard
        if "api/provider-profiles/readiness/" in url:
            return {
                "profile_status_rows": [{
                    "provider_id": "jira",
                    "profile_id": "chiplet-2a-jira",
                    "status": "ready",
                    "data_status": "ready",
                    "data_status_reason": "",
                }],
            }
        if "api/provider-charts/data/" in url:
            profile_id = e2e_provider_parity.query_value(url, "profile_id")
            provider_id = e2e_provider_parity.PROVIDER_ID_BY_PROFILE[profile_id]
            chart_id = e2e_provider_parity.query_value(url, "chart_id")
            return json_responses[f"{chart_id}:{provider_id}"]
        return {}

    monkeypatch.setattr(e2e_provider_parity, "request_json", fake_request_json)
    monkeypatch.setattr(e2e_provider_parity, "assert_http_ok", lambda url, auth=False: checked_urls.append((url, auth)))
    monkeypatch.setattr(e2e_provider_parity, "validate_visible_dashboard", lambda *args, **kwargs: None)

    e2e_provider_parity.validate_runtime(
        tmp_path,
        3999,
        8999,
        e2e_provider_parity.ProviderParitySettings(profile_id="chiplet-2a-jira", begin_ww="26WW32", end_ww="26WW32"),
    )

    assert any("127.0.0.1:8999/api/provider-charts/data/" in url for url, _ in checked_urls)
    assert any("127.0.0.1:3999/api/datasources/proxy/uid/metrics-bug-trend-api/api/provider-charts/data/" in url for url, _ in checked_urls)


def test_provider_parity_runtime_validation_resolves_grafana_date_macros(monkeypatch, tmp_path):
    dashboard = {
        "dashboard": {
            "uid": "ip-quality-dashboard",
            "panels": [{
                "title": "Open Bug Trend",
                "targets": [{
                    "url": "/api/provider-charts/data/?profile_id=$profile_id&chart_id=open_bug_trend&chart_version=1&range_mode=$range_mode&begin_date=${__from:date:YYYY-MM-DD}&end_date=${__to:date:YYYY-MM-DD}",
                    "metricsContract": {"shape": "wide_bucket_series"},
                }],
            }, {
                "title": "Execution Metrics Not Mapped Yet",
                "targets": [{
                    "url": "/api/provider-charts/data/?profile_id=$profile_id&chart_id=execution_statistics&chart_version=1&range_mode=$range_mode&begin_date=${__from:date:YYYY-MM-DD}&end_date=${__to:date:YYYY-MM-DD}",
                    "metricsContract": {"shape": "provider_series_state", "providerBinding": "first_wave_deferred"},
                }],
            }],
        }
    }
    checked_urls = []

    def fake_request_json(method, url, payload=None):
        if url.endswith("/api/dashboards/uid/ip-quality-dashboard"):
            return dashboard
        if "api/provider-charts/data/" in url:
            checked_urls.append(url)
            if e2e_provider_parity.query_value(url, "chart_id") == "execution_statistics":
                return {
                    "status": "deferred",
                    "grafana_rows": [],
                    "provider_series_state": [{"status": "deferred", "reason": "Execution mappings deferred"}],
                }
            return {
                "status": "supported",
                "grafana_rows": [{"provider_id": "hsdes", "profile_id": "nvu-ttl-hsdes", "all_open_bugs": 3}],
                "provider_series_state": [{"status": "supported", "reason": ""}],
            }
        return {}

    monkeypatch.setattr(e2e_provider_parity, "request_json", fake_request_json)
    monkeypatch.setattr(e2e_provider_parity, "assert_http_ok", lambda url, auth=False: checked_urls.append(url))
    monkeypatch.setattr(e2e_provider_parity, "validate_visible_dashboard", lambda *args, **kwargs: None)

    e2e_provider_parity.validate_runtime(
        tmp_path,
        3999,
        8999,
        e2e_provider_parity.ProviderParitySettings(
            profile_id="nvu-ttl-hsdes",
            range_mode="date",
            begin_date="2026-08-10",
            end_date="2026-08-16",
        ),
    )

    assert all("${__from" not in url for url in checked_urls)
    assert any("range_mode=date" in url for url in checked_urls)
    assert any("begin_date=2026-08-10" in url for url in checked_urls)
    assert any("end_date=2026-08-16" in url for url in checked_urls)


def test_provider_parity_runtime_validates_hsdes_through_same_provider_selection(monkeypatch, tmp_path):
    dashboard = {
        "dashboard": {
            "uid": "ip-quality-dashboard",
            "panels": [{
                "title": "Profile Status",
                "targets": [{
                    "url": "/api/provider-profiles/readiness/?profile_id=$profile_id",
                    "metricsContract": {"shape": "profile_readiness_summary"},
                }],
            }, {
                "title": "Component Bugs by Area",
                "targets": [{
                    "url": "/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=component_bug&chart_version=1",
                    "metricsContract": {"shape": "wide_bucket_series"},
                }],
            }, {
                "title": "Open Bug Trend",
                "targets": [{
                    "url": "/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=open_bug_trend&chart_version=1",
                    "metricsContract": {"shape": "wide_bucket_series"},
                }],
            }, {
                "title": "Quality Chart Health",
                "targets": [{
                    "url": "/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=open_bug_trend&chart_version=1",
                    "metricsContract": {"shape": "provider_series_state", "providerBinding": "selected_provider_state"},
                }],
            }, {
                "title": "Execution Metrics Not Mapped Yet",
                "targets": [{
                    "url": "/api/provider-charts/data/?profile_id=$profile_id&begin_ww=$begin_ww&end_ww=$end_ww&chart_id=execution_statistics&chart_version=1",
                    "metricsContract": {"shape": "provider_series_state", "providerBinding": "first_wave_deferred"},
                }],
            }],
        }
    }

    def fake_request_json(method, url, payload=None):
        if url.endswith("/api/dashboards/uid/ip-quality-dashboard"):
            return dashboard
        if "api/provider-profiles/readiness/" in url:
            return {
                "profile_status_rows": [{
                    "provider_id": "hsdes",
                    "profile_id": "nvu-ttl-hsdes",
                    "status": "seeded_preview",
                    "data_status": "seeded_preview",
                    "data_status_reason": "HSD-ES seed facts can render supported preview charts",
                }],
            }
        if "api/provider-charts/data/" in url:
            if e2e_provider_parity.query_value(url, "chart_id") == "execution_statistics":
                return {
                    "status": "deferred",
                    "grafana_rows": [],
                    "provider_series_state": [{"status": "deferred", "reason": "Execution mappings deferred"}],
                }
            if e2e_provider_parity.query_value(url, "chart_id") == "component_bug":
                return {
                    "status": "supported",
                    "grafana_rows": [{"provider_id": "hsdes", "profile_id": "nvu-ttl-hsdes", "component_bug_count": 3}],
                    "provider_series_state": [{"status": "supported", "reason": ""}],
                }
            return {
                "status": "configuration_required",
                "grafana_rows": [],
                "provider_series_state": [{"status": "configuration_required", "reason": "HSD-ES bindings required"}],
            }
        return {}

    monkeypatch.setattr(e2e_provider_parity, "request_json", fake_request_json)
    monkeypatch.setattr(e2e_provider_parity, "assert_http_ok", lambda url, auth=False: None)
    monkeypatch.setattr(e2e_provider_parity, "validate_visible_dashboard", lambda *args, **kwargs: None)

    e2e_provider_parity.validate_runtime(
        tmp_path,
        3999,
        8999,
        e2e_provider_parity.ProviderParitySettings(provider_id="hsdes", profile_id="nvu-ttl-hsdes", begin_ww="26WW32", end_ww="26WW32"),
    )


def test_supported_payload_rejects_provider_prefixed_grafana_row_fields():
    try:
        e2e_provider_parity.validate_supported_payload(
            "Component Bugs by Area",
            {"shape": "wide_bucket_series"},
            {
                "status": "supported",
                "grafana_rows": [{
                    "provider_id": "hsdes",
                    "profile_id": "nvu-ttl-hsdes",
                    "hsdes_component_bug_count": 3,
                }],
            },
        )
    except RuntimeError as error:
        assert "provider-prefixed Grafana row fields" in str(error)
    else:
        raise AssertionError("provider-prefixed Grafana row fields were accepted")


def test_provider_parity_visible_text_accepts_virtualized_state_tables_when_panel_titles_render():
    body_text = """
    IP Quality Dashboard
    QUALITY
    Profile Status
    Open Bug Trend
    Quality Chart Health
    EXECUTION
    Execution Metrics Not Mapped Yet
    EFFICIENCY
    Open Bug Aging
    Efficiency Metrics Not Mapped Yet
    """

    e2e_provider_parity.assert_visible_dashboard_text(body_text)
