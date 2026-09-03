from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.parse
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Mapping, Sequence, TypeVar

import e2e_bug_trend
from e2e_provider_parity_validation import (
    assert_visible_dashboard_text,
    grafana_dashboard_url,
    query_value,
    url_query_values,
    validate_runtime,
    validate_supported_payload,
    validate_visible_dashboard,
)
from service_lifecycle_engine import ServiceLifecycleEngine, ServiceSpec, load_project_name

T = TypeVar("T")

PROVIDER_ID_BY_PROFILE = {
    "chiplet-2a-jira": "jira",
    "nvu-ttl-hsdes": "hsdes",
}


@dataclass(frozen=True, slots=True)
class ProviderParitySettings:
    provider_id: str = ""
    profile_id: str = "chiplet-2a-jira"
    range_mode: str = "ww"
    space_id: str = "chiplet_ip"
    release_target: str = "chiplet"
    milestone: str = "2a"
    begin_ww: str = "26WW32"
    end_ww: str = "26WW32"
    begin_date: str = "2026-08-03"
    end_date: str = "2026-08-09"
    skip_browser: bool = False

    def variables(self) -> dict[str, str]:
        return {
            "profile_id": self.profile_id,
            "range_mode": self.range_mode,
            "begin_ww": self.begin_ww,
            "end_ww": self.end_ww,
        }

    def target_variables(self) -> dict[str, str]:
        variables = self.variables()
        begin_date, end_date = self.date_range()
        variables["{__from:date:YYYY-MM-DD}"] = begin_date.isoformat()
        variables["{__to:date:YYYY-MM-DD}"] = end_date.isoformat()
        return variables

    def date_range(self) -> tuple[date, date]:
        if self.range_mode.strip().lower() == "date":
            return iso_date(self.begin_date), iso_date(self.end_date)
        return ww_range_to_dates(self.begin_ww, self.end_ww)

    def grafana_time_range(self) -> dict[str, str]:
        begin_date, end_date = self.date_range()
        return {
            "from": f"{begin_date.isoformat()}T00:00:00",
            "to": f"{end_date.isoformat()}T23:59:59",
        }

    def resolved_provider_id(self) -> str:
        profile_provider_id = PROVIDER_ID_BY_PROFILE.get(self.profile_id, "")
        if self.provider_id and profile_provider_id and self.provider_id != profile_provider_id:
            raise ValueError(f"Provider {self.provider_id} does not match selected profile {self.profile_id}.")
        return self.provider_id or profile_provider_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Start/stop the IP Quality Grafana E2E runtime.")
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
    parser.add_argument("--range-mode", default="ww")
    parser.add_argument("--space-id", default="chiplet_ip")
    parser.add_argument("--release-target", default="chiplet")
    parser.add_argument("--milestone", default="2a")
    parser.add_argument("--begin-ww", default="26WW32")
    parser.add_argument("--end-ww", default="26WW32")
    parser.add_argument("--begin-date", default="2026-08-03")
    parser.add_argument("--end-date", default="2026-08-09")
    parser.add_argument("--skip-browser", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    lifecycle = ServiceLifecycleEngine(
        project_name=load_project_name(Path(args.service_config), "metrics-provider-parity"),
        workspace=workspace,
        instance_name=args.instance,
        state_directory=workspace / "state" / "e2e" / "service-lifecycle-engine",
    )
    run_id = f"provider-parity-{int(time.time())}"
    settings = ProviderParitySettings(
        provider_id=args.provider_id,
        profile_id=args.profile_id,
        range_mode=args.range_mode,
        space_id=args.space_id,
        release_target=args.release_target,
        milestone=args.milestone,
        begin_ww=args.begin_ww,
        end_ww=args.end_ww,
        begin_date=args.begin_date,
        end_date=args.end_date,
        skip_browser=args.skip_browser,
    )

    if args.action == "stop":
        e2e_bug_trend.stop_runtime(lifecycle, args, run_id)
        return
    start_runtime(args, workspace, lifecycle, settings, run_id)


def start_runtime(args: argparse.Namespace, workspace: Path, lifecycle: ServiceLifecycleEngine, settings: ProviderParitySettings, run_id: str | None = None) -> None:
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
    print(f"E2E IP Quality Dashboard is ready: {dashboard_url}")


def profile_step(lifecycle: object, label: str, callback: Callable[[], T], run_id: str | None = None) -> T:
    if hasattr(lifecycle, "profile_step"):
        return lifecycle.profile_step(label, callback, run_id=run_id, prefix="E2E timing")
    return e2e_bug_trend.timed_step(label, callback)


def import_grafana_dashboard(workspace: Path, grafana_port: int, settings: ProviderParitySettings) -> None:
    artifact = workspace / "ops" / "grafana" / "provider_parity_dashboard.json"
    dashboard = json.loads(artifact.read_text(encoding="utf-8"))
    dashboard["time"] = settings.grafana_time_range()
    dashboard["timezone"] = "browser"
    variables = settings.variables()
    for variable in dashboard["templating"]["list"]:
        value = variables.get(variable["name"])
        if value is None:
            continue
        if variable.get("type") != "custom":
            variable["query"] = value
        current_text = variable_option_text(variable, value)
        variable["current"] = {"text": current_text, "value": value}
        for option in variable.get("options", []):
            if isinstance(option, dict):
                option["selected"] = option.get("value") == value
    request_json(
        "POST",
        f"http://127.0.0.1:{grafana_port}/api/dashboards/db",
        {"dashboard": dashboard, "overwrite": True, "message": "Import IP Quality dashboard"},
    )


def variable_option_text(variable: dict[str, object], value: str) -> str:
    for option in variable.get("options", []):
        if isinstance(option, dict) and option.get("value") == value:
            return str(option.get("text") or value)
    return value


def ww_range_to_dates(begin_ww: str, end_ww: str) -> tuple[date, date]:
    begin = ww_to_monday(begin_ww)
    end = ww_to_monday(end_ww) + timedelta(days=6)
    if begin > end:
        raise ValueError("begin_ww must be earlier than or equal to end_ww.")
    return begin, end


def ww_to_monday(value: str) -> date:
    normalized = value.strip()
    if len(normalized) != 6 or normalized[2:4].upper() != "WW":
        raise ValueError("WW values must use YYWWNN format.")
    year = 2000 + int(normalized[:2])
    week = int(normalized[4:])
    return date.fromisocalendar(year, week, 1)


def iso_date(value: str) -> date:
    return date.fromisoformat(value[:10])


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
