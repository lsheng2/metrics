from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "metrics.settings.production")

import django

django.setup()

from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.test import RequestFactory
from forecast.app.domain.model.enums import TaskScope
from sd_metrics_lib.utils.enums import HealthStatus
from ui_web.data.member_data import MemberGroupData
from ui_web.data.pull_request_data import ApprovalData, LinkedTaskData, PersonActivitySummaryData, PullRequestData
from ui_web.data.task_data import AssigneeData, AssignmentData, ForecastData, LinkedPullRequestData, ReleaseData, SystemMetadataData, TimeTrackingData
from ui_web.data.task_forecast_data import TaskForecastBreakdownItem, TaskForecastParamsData, TaskForecastSummaryData
from ui_web.data.velocity_task_detail_data import DeveloperVelocitySummary, TaskVelocityData
from ui_web.data.bug_trend_data import BugTrendEvidenceData


def provider_profile_test_success(context: dict) -> dict:
    return _html_fixture(
        "provider-profile-test-success",
        _render_provider_profile_editor(
            provider_id="jira",
            connection_test={
                "status": "success",
                "summary": "Jira connection succeeded.",
                "details": {"server": "Mock Jira", "version": "10.0"},
            },
        ),
    )


def provider_profile_test_failure(context: dict) -> dict:
    return _html_fixture(
        "provider-profile-test-failure",
        _render_provider_profile_editor(
            provider_id="jira",
            connection_test={
                "status": "failure",
                "summary": "Jira connection failed. Check the base URL and token.",
                "details": {"error": "401 unauthorized"},
            },
        ),
    )


def pull_request_filter_applied(context: dict) -> dict:
    pull_requests = [_pull_request_data()]
    fragment = (
        render_to_string("partials/pull_request_summary_table.html", {
            "activity_summary": [
                PersonActivitySummaryData("Monkey User", created_count=1, approved_count=0, changes_requested_count=0),
                PersonActivitySummaryData("Lead Reviewer", created_count=0, approved_count=1, changes_requested_count=0),
            ],
        }, request=_fixture_request())
        + render_to_string("partials/pull_request_filters.html", {
            "selected_member_group_id": "core",
            "author_options": ["Monkey User", "Lead Reviewer"],
            "iteration_options": ["Sprint 12"],
            "release_options": [("rel-1", "2026.015")],
            "selected_author": "Monkey User",
            "selected_iteration": "",
            "selected_release": "",
        }, request=_fixture_request())
        + '<span data-filter-active="author">Monkey User</span>'
        + render_to_string("partials/pull_requests_table.html", {"pull_requests": pull_requests}, request=_fixture_request())
    )
    return _html_fixture("pull-request-filter-applied", fragment)


def current_tasks_fake_data(context: dict) -> dict:
    fragment = render_to_string("partials/task_table.html", {
        "tasks": [_current_task_data()],
        "show_header": True,
        "pr_gateway_column_enabled": True,
        "release_column_enabled": True,
        "task_table_colspan": 11,
    }, request=_fixture_request())
    return _html_fixture("current-tasks-fake-data", fragment)


def task_forecast_fake_data(context: dict) -> dict:
    fragment = render_to_string("partials/task_forecast_content.html", {
        "success": True,
        "task_forecast": _task_forecast_summary_data(),
        "chart_data": "",
        "include_done_tasks": True,
        "time_unit": "days",
        "forecast_params": TaskForecastParamsData(task_id="TASK-101", task_scope=TaskScope.ALL),
    }, request=_fixture_request())
    return _html_fixture("task-forecast-fake-data", fragment)


def team_velocity_fake_data(context: dict) -> dict:
    return _html_fixture("team-velocity-fake-data", _velocity_fragment("Team Velocity", "team"))


def dev_velocity_fake_data(context: dict) -> dict:
    return _html_fixture("dev-velocity-fake-data", _velocity_fragment("Developer Velocity", "dev"))


def bug_trend_evidence_fake_data(context: dict) -> dict:
    fragment = render_to_string("partials/bug_trend_evidence.html", {
        "evidence": BugTrendEvidenceData(
            rows=[_evidence_row()],
            total_count=1,
            shown_count=1,
            selection_title="Fixture Evidence Tickets",
            display_fields=[],
            scope_id=1,
            calculation_run_id="fixture-run",
            begin="2026-09-01",
            end="2026-09-07",
            has_selection=True,
            bucket_id="fixture-bucket",
            series_name="new_critical_high",
            active_chart_id="default_bug_trend",
        ),
    }, request=_fixture_request())
    return _html_fixture("bug-trend-evidence-fake-data", fragment)


def _html_fixture(fixture_name: str, fragment: str) -> dict:
    return {
        "fixture": fixture_name,
        "html": _browser_html(fragment),
    }


def _render_provider_profile_editor(provider_id: str, connection_test: dict) -> str:
    profile = SimpleNamespace(
        id="",
        profile_id="monkey-jira-profile",
        provider_id=provider_id,
        display_name="Monkey Jira Profile",
        lifecycle_state="draft",
        mapping_version=1,
        mapping_version_hash="fixture-mapping-hash",
        source_version_hash="fixture-source-hash",
        connection_settings={
            "base_url": "https://provider.example.test",
            "auth_mode": "server_pat",
            "credential_ref": "profile:local",
            "credentials": {"api_token": "********"},
        },
        source_population={},
    )
    editor = SimpleNamespace(
        profile=profile,
        provider_options=[
            SimpleNamespace(
                provider_id="jira",
                label="Jira",
                summary="Jira issue provider",
                color="green",
                selected=True,
                enabled=True,
                profile_count=1,
                metadata_supported=True,
                metadata_summary="Jira metadata fields",
            ),
            SimpleNamespace(
                provider_id="hsdes",
                label="HSD-ES",
                summary="HSD-ES issue provider",
                color="blue",
                selected=False,
                enabled=True,
                profile_count=1,
                metadata_supported=True,
                metadata_summary="HSD-ES metadata fields",
            ),
            SimpleNamespace(
                provider_id="github",
                label="GitHub",
                summary="GitHub issue provider",
                color="purple",
                selected=False,
                enabled=False,
                profile_count=0,
                metadata_supported=False,
                metadata_summary="Template reserved",
            ),
        ],
        selected_provider_id=provider_id,
        provider_label="Jira",
        provider_color="green",
        provider_summary="Jira issue provider",
        source_query_label="JQL",
        source_query_help="Jira query language",
        metadata_supported=True,
        metadata_summary="Jira metadata fields are available after connection.",
        detail_rows=[
            SimpleNamespace(label="Auth", value="API token / PAT", help_text=""),
            SimpleNamespace(label="Probe", value="Server info", help_text=""),
        ],
        json_fields=[
            {"name": "source_population", "label": "Source population", "value": json.dumps({"native_query_text": "project = SAMPLE"})},
            {"name": "scope_labels", "label": "Scope labels", "value": json.dumps({"ip": "SAMPLE"})},
            {"name": "field_bindings", "label": "Field bindings", "value": json.dumps({"severity": {"native_field": "priority"}})},
            {"name": "value_mappings", "label": "Value mappings", "value": json.dumps({"bug_type_values": ["Bug"]})},
            {"name": "chart_bindings", "label": "Chart bindings", "value": json.dumps({"open_bug_trend": {"support_status": "supported"}})},
            {"name": "sync_policy", "label": "Sync policy", "value": json.dumps({"live_sync": "supported"})},
            {"name": "readiness_policy", "label": "Readiness policy", "value": json.dumps({"ready_status": "ready"})},
        ],
        connection_settings_json=json.dumps(profile.connection_settings),
        connection_status_label="Ready to test",
    )
    return render_to_string("partials/provider_profile_editor.html", {
        "provider_setup_editor": editor,
        "provider_connection_test": connection_test,
    }, request=_fixture_request())


def _fixture_request():
    request = RequestFactory().get("/")
    get_token(request)
    return request


def _velocity_fragment(title: str, variant: str) -> str:
    return (
        f'<section class="box"><h2 class="title is-3">{title}</h2>'
        '<p class="subtitle is-6">Fixture chart drilldown selected.</p>'
        '<div class="notification is-info is-light">September 2026 selected</div>'
        '</section>'
        + render_to_string("partials/velocity_task_table.html", {
            "tasks": [_velocity_task_data()],
            "summary": _velocity_summary(),
        }, request=_fixture_request())
        + f'<span data-filter-active="{variant}-velocity">September 2026</span>'
    )


def _current_task_data():
    task = _velocity_task_data()
    task.linked_pull_request = LinkedPullRequestData(
        id="101",
        repository_id="repo-1",
        project_id="project-1",
        project_name="Metrics",
        url="https://provider.example.test/pr/101",
    )
    return task


def _pull_request_data() -> PullRequestData:
    release = ReleaseData("rel-1", "2026.015")
    return PullRequestData(
        id="101",
        title="Align dense table action controls",
        author_name="Monkey User",
        status="active",
        internal_gate=True,
        url="https://provider.example.test/pr/101",
        repository="metrics",
        repository_id="repo-1",
        project_id="project-1",
        project_name="Metrics",
        approvals=[
            ApprovalData("Lead Reviewer", "approved", "main", True),
            ApprovalData("Dev Reviewer", "waiting", "additional", False),
        ],
        linked_task=LinkedTaskData(
            id="TASK-101",
            url="https://provider.example.test/TASK-101",
            status="Code Review",
            iteration="Sprint 12",
            releases=[release],
        ),
    )


def _evidence_row():
    return SimpleNamespace(
        issue_key="TASK-101",
        source_url="https://provider.example.test/TASK-101",
        summary="Fixture evidence ticket",
        series_name="new_critical_high",
        status="Open",
        severity="P1-Critical",
        owner="Monkey User",
        component="ui",
        created_at="2026-09-02",
        updated_at="2026-09-03",
        extra_field_values=[],
    )


def _task_forecast_summary_data() -> TaskForecastSummaryData:
    return TaskForecastSummaryData(
        task_title="Fixture Forecast Root",
        total_estimation_days=9.0,
        forecasted_start_date=datetime(2026, 9, 9, tzinfo=timezone.utc),
        forecasted_end_date=datetime(2026, 9, 18, tzinfo=timezone.utc),
        average_team_velocity=1.2,
        task_forecasts=[
            TaskForecastBreakdownItem("TASK-101", "Forecast root task", 5.0, 0, True, False, "In Progress"),
            TaskForecastBreakdownItem("TASK-102", "Child implementation task", 3.0, 1, False, False, "Development"),
            TaskForecastBreakdownItem("TASK-103", "Completed verification task", 1.0, 1, False, True, "Done"),
        ],
        completed_estimation_days=1.0,
        remaining_estimation_days=8.0,
    )


def _velocity_task_data() -> TaskVelocityData:
    return TaskVelocityData(
        id="TASK-101",
        title="Tighten dense dashboard table behavior",
        assignment=AssignmentData(AssigneeData("user-1", "Monkey User"), MemberGroupData("core", "Core Team")),
        time_tracking=TimeTrackingData(total_spent_time_days=1.5, current_assignee_spent_time_days=0.8),
        system_metadata=SystemMetadataData("In Progress", "https://provider.example.test/TASK-101"),
        story_points=5,
        child_tasks_count=2,
        stage="Development",
        iteration="Sprint 12",
        forecast=ForecastData(HealthStatus.GREEN, estimation_time_days=2.5),
        releases=[ReleaseData("rel-1", "2026.015")],
        developer_story_points=3.0,
        developer_time_days=1.0,
        total_estimated_days=2.0,
        estimated_days=1.2,
        deviation_percent=0.0,
    )


def _velocity_summary() -> DeveloperVelocitySummary:
    return DeveloperVelocitySummary(
        total_story_points=3.0,
        total_time_days=1.0,
        velocity=3.0,
        total_task_story_points=5.0,
        total_estimated_days=2.0,
        average_deviation_percent=0.0,
        working_days=1.0,
        working_days_in_month=22,
        workload_percent=4.5,
    )


def _browser_html(fragment: str) -> str:
    static_dir = Path(__file__).resolve().parents[1] / "ui_web" / "static"
    vendor_css = (static_dir / "css" / "vendor_fallbacks.css").read_text(encoding="utf-8")
    main_css = (static_dir / "css" / "main.css").read_text(encoding="utf-8")
    main_js = (static_dir / "js" / "main.js").read_text(encoding="utf-8")
    return (
        '<!doctype html><html lang="en" data-theme="dark" class="has-navbar-fixed-top">'
        f"<head><style>{vendor_css}\n{main_css}</style></head>"
        '<body class="is-flex is-flex-direction-column is-fullheight">'
        '<div class="columns is-gapless is-flex-grow-1 dashboard-app-layout">'
        '<main class="column is-flex is-flex-direction-column dashboard-main-column">'
        '<section class="section is-flex-grow-1"><div class="container"><div id="main-content">'
        f"{fragment}"
        f"</div></div></section></main></div><script>{main_js}</script></body></html>"
    )
