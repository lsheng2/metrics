from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import e2e_bug_trend
from port_lifecycle import ServiceSpec, ServiceState


def test_bug_trend_load_specs_uses_json_ports_unless_cli_overrides(tmp_path):
    config = tmp_path / "services.json"
    config.write_text(
        json.dumps(
            {
                "project_name": "sample-project",
                "services": [
                    {"name": "django", "preferred_ports": [9100], "command": ["{python}", "server.py"]},
                    {"name": "grafana", "preferred_ports": [9200], "command": ["{grafana_bin}", "server"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    args = type(
        "Args",
        (),
        {
            "service_config": str(config),
            "django_ports": "",
            "grafana_ports": "9300,9400",
        },
    )()

    specs = e2e_bug_trend.load_specs(args, tmp_path, sys.executable, "grafana", tmp_path)

    assert specs["django"].preferred_ports == (9100,)
    assert specs["grafana"].preferred_ports == (9300, 9400)


def test_bug_trend_start_runtime_uses_joint_port_plan(monkeypatch, tmp_path):
    django_spec = ServiceSpec.from_values("django", [9100], [sys.executable, "--version"])
    grafana_spec = ServiceSpec.from_values("grafana", [9100, 9200], [sys.executable, "--version"])
    calls = []

    class FakeLifecycle:
        def profile_step(self, label, callback, run_id=None, prefix="PortLifecycle timing"):
            calls.append(("profile_step", label, run_id, prefix))
            return callback()

        def restart_services(self, service_specs, graceful_timeout_seconds=5.0, force_by_port=False, run_id=None, after_prepare=None, before_start=None):
            calls.append(("restart_services", tuple(spec.name for spec in service_specs), graceful_timeout_seconds, force_by_port, run_id))
            after_prepare([])
            port_plan = {"django": 9100, "grafana": 9200}
            runtime_specs = tuple(before_start(port_plan, service_specs))
            calls.append(("runtime_specs", tuple(spec.name for spec in runtime_specs)))
            return type(
                "RestartResult",
                (),
                {
                    "port_plan": port_plan,
                    "service_states": (
                        ServiceState("django", "127.0.0.1", 9100, 1, (), "now", "out", "err", "authority", (), None, None, None, 0.0),
                        ServiceState("grafana", "127.0.0.1", 9200, 2, (), "now", "out", "err", "authority", (), None, None, None, 0.0),
                    ),
                },
            )()

    args = type(
        "Args",
        (),
        {
            "grafana_bin": "grafana",
            "grafana_homepath": str(tmp_path),
            "service_config": str(tmp_path / "services.json"),
            "django_ports": "",
            "grafana_ports": "",
            "force_by_port": True,
            "scope_id": "7",
            "begin": "2026-01-01",
            "end": "2026-02-01",
            "open_entrypoint": "none",
        },
    )()

    monkeypatch.setattr(e2e_bug_trend, "resolve_grafana_bin", lambda configured: "grafana")
    monkeypatch.setattr(e2e_bug_trend, "resolve_grafana_homepath", lambda configured, grafana_bin: str(tmp_path))
    monkeypatch.setattr(e2e_bug_trend, "load_specs", lambda *values, **kwargs: {"django": django_spec, "grafana": grafana_spec})
    monkeypatch.setattr(e2e_bug_trend, "run", lambda command, workspace: calls.append(("run", tuple(command))))
    monkeypatch.setattr(e2e_bug_trend, "write_runtime_grafana_config", lambda workspace, grafana_port: tmp_path / f"grafana-{grafana_port}.ini")
    monkeypatch.setattr(e2e_bug_trend, "configure_grafana_datasource", lambda grafana_port, django_port: calls.append(("datasource", grafana_port, django_port)))
    monkeypatch.setattr(e2e_bug_trend, "import_grafana_dashboard", lambda workspace, grafana_port, django_port, scope_id, begin, end: None)
    monkeypatch.setattr(e2e_bug_trend, "validate_runtime", lambda workspace, grafana_port, django_port, scope_id, begin, end: calls.append(("validate", grafana_port, django_port)))
    monkeypatch.setattr(e2e_bug_trend, "write_e2e_summary", lambda workspace, django_port, grafana_port, dashboard_url, workbench_url: calls.append(("summary", django_port, grafana_port, dashboard_url, workbench_url)))
    monkeypatch.setattr(e2e_bug_trend, "open_browser", lambda url: None)

    e2e_bug_trend.start_runtime(args, tmp_path, FakeLifecycle(), run_id="run-1")

    assert calls[0] == ("restart_services", ("django", "grafana"), 5.0, True, "run-1")
    assert ("profile_step", "migrate", "run-1", "E2E timing") in calls
    assert ("profile_step", "seed_bug_trend_sample", "run-1", "E2E timing") in calls
    assert ("profile_step", "write_grafana_config", "run-1", "E2E timing") in calls
    assert ("runtime_specs", ("django", "grafana")) in calls
    assert ("datasource", 9200, 9100) in calls


def test_bug_trend_selected_ports_propagate_to_runtime_outputs(monkeypatch, tmp_path):
    django_port = 8999
    grafana_port = 3999
    scope_id = "7"
    begin = "2026-01-01"
    end = "2026-02-01"
    config_source = tmp_path / "state" / "grafana" / "grafana.ini"
    config_source.parent.mkdir(parents=True)
    config_source.write_text("[server]\nhttp_port = 3000\nroot_url = http://127.0.0.1:3000/\n", encoding="utf-8")
    http_checks = []
    json_requests = []

    def fake_assert_http_ok(url, auth=False):
        http_checks.append((url, auth))

    def fake_request_json(method, url, payload=None):
        json_requests.append((method, url, payload))
        if method == "GET":
            return {
                "dashboard": {
                    "panels": [
                        {
                            "targets": [{"url": "/api/charts/data/?chart_id=default_bug_trend"}],
                            "fieldConfig": {"defaults": {"links": [{"url": f"http://127.0.0.1:{django_port}/workbench/grafana-selection/?chart_id=default_bug_trend"}]}}
                        }
                    ]
                }
            }
        return {}

    monkeypatch.setattr(e2e_bug_trend, "assert_http_ok", fake_assert_http_ok)
    monkeypatch.setattr(e2e_bug_trend, "request_json", fake_request_json)

    runtime_config = e2e_bug_trend.write_runtime_grafana_config(tmp_path, grafana_port)
    e2e_bug_trend.configure_grafana_datasource(grafana_port, django_port)
    e2e_bug_trend.validate_runtime(tmp_path, grafana_port, django_port, scope_id, begin, end)
    dashboard_url = e2e_bug_trend.grafana_dashboard_url(grafana_port, scope_id, begin, end)
    workbench_url = e2e_bug_trend.workbench_url_for(django_port, scope_id, begin, end)
    e2e_bug_trend.write_e2e_summary(tmp_path, django_port, grafana_port, dashboard_url, workbench_url)

    runtime_content = runtime_config.read_text(encoding="utf-8")
    assert f"http_port = {grafana_port}" in runtime_content
    assert f"root_url = http://127.0.0.1:{grafana_port}/" in runtime_content
    assert "org_role = Viewer" in runtime_content
    assert "check_for_updates = false" in runtime_content
    assert "check_for_plugin_updates = false" in runtime_content
    assert "[unified_alerting]" in runtime_content
    assert "execute_alerts = false" in runtime_content
    assert "[unified_alerting.state_history]" in runtime_content
    assert "disable_plugins = " in runtime_content
    assert "elasticsearch" in runtime_content
    assert "prometheus" not in runtime_content
    assert "tempo" in runtime_content
    assert "preinstall_disabled = true" in runtime_content
    assert "preinstall_auto_update = false" in runtime_content
    assert (tmp_path / "state" / "grafana" / "conf" / "provisioning" / "alerting").is_dir()
    assert (tmp_path / "state" / "grafana" / "conf" / "provisioning" / "dashboards").is_dir()
    assert (tmp_path / "state" / "grafana" / "conf" / "provisioning" / "plugins").is_dir()
    datasource_payload = json_requests[0][2]
    assert json_requests[0][1] == f"http://127.0.0.1:{grafana_port}/api/datasources/uid/metrics-bug-trend-api"
    assert datasource_payload["url"] == f"http://127.0.0.1:{django_port}"
    assert any(f"127.0.0.1:{django_port}/api/charts/data/" in url for url, auth in http_checks)
    assert any(f"127.0.0.1:{grafana_port}/api/datasources/proxy/" in url for url, auth in http_checks)
    assert dashboard_url.startswith(f"http://127.0.0.1:{grafana_port}/")
    summary = json.loads((tmp_path / "state" / "e2e" / "bug_trend_ports.json").read_text(encoding="utf-8"))
    assert summary == {"dashboard_url": dashboard_url, "django_port": django_port, "grafana_port": grafana_port, "workbench_url": workbench_url}


def test_grafana_datasource_is_created_when_uid_update_returns_not_found(monkeypatch):
    calls = []

    def fake_request_json(method, url, payload=None):
        calls.append((method, url, payload))
        if method == "PUT":
            raise urllib.error.HTTPError(url, 404, "not found", None, None)
        return {}

    monkeypatch.setattr(e2e_bug_trend, "request_json", fake_request_json)

    e2e_bug_trend.configure_grafana_datasource(3999, 8999)

    assert calls[0][0] == "PUT"
    assert calls[1][0] == "POST"
    assert calls[1][1] == "http://127.0.0.1:3999/api/datasources"
    assert calls[1][2]["uid"] == "metrics-bug-trend-api"
