from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_ai_stack_smoke_checks_unified_workbench():
    script = (ROOT / "scripts" / "e2e_dashboard_ai_stack.ps1").read_text(encoding="utf-8")

    assert "'-OpenEntrypoint', 'none'" in script
    assert "METRICS_AI_BASE_FRONTEND_URL = $AiBaseFrontendUrl" in script
    assert "Update-DashboardRuntimeUrls" in script
    assert 'state\\e2e\\bug_trend_ports.json' in script
    assert '"$DashboardBaseUrl/workbench/"' in script
    assert "Start-Process $workbenchUrl" in script
    assert "Clear-StaleDemoProcesses" in script
    assert "sample_agent" in script
    assert "grafana-e2e-" in script
    assert "-NoCapture" in script
    assert "bug_trend_ports.json" in script
    assert "workbench_url" in script
    assert "'-Headless'" in script
    assert "'-RequireGateway'" in script
    assert "if ($FullAiChatSmoke)" in script
    assert "LOGFIRE_IGNORE_NO_CONFIG = '1'" in script
    assert "FullAiChatSmoke" in script
    assert "Skipping deep AI chat publish smoke" in script
    assert "$exitCode -ne 0" in script
    assert "$($exitCode)" in script
    assert "Invoke-WithStackRetry" in script
    assert "Invoke-BootLogAudit -Phase 'dashboard-start' -RequireDashboardState" in script
    assert "Test-JiraProfileSyncRunning" in script
    assert "E2E_JIRA_PROFILE_ID" in script
    assert "-Label 'jira-profile-sync'" in script
    assert "A sync is already running for this scope" in script
    assert "Set-Content -Path $logPath -Value 'Jira profile sync already active; continuing with the existing sync state.'" in script
    assert "Write-Host 'Jira profile sync already active; continuing with the existing sync state.'" in script
    assert "Write-Warning 'Jira profile sync is already running for this scope" not in script
    assert "Invoke-BootLogAudit -Phase 'ai-base-start' -RequireDashboardState -RequireAiBaseState" in script
    assert "Invoke-BootLogAudit -Phase 'final' -RequireDashboardState -RequireAiBaseState" in script
    assert "workbench-ai-context" in script
    assert "Metrics Workbench" in script


def test_bug_trend_launcher_can_defer_browser_to_unified_stack():
    script = (ROOT / "scripts" / "e2e_start_bug_trend.ps1").read_text(encoding="utf-8")
    runtime = (ROOT / "scripts" / "e2e_bug_trend.py").read_text(encoding="utf-8")

    assert "[ValidateSet('grafana', 'workbench', 'none')]" in script
    assert "'--open-entrypoint'" in script
    assert 'choices=("grafana", "workbench", "none")' in runtime
    assert "workbench_url_for" in runtime


def test_bug_trend_service_config_avoids_observed_forbidden_grafana_port():
    config = (ROOT / "scripts" / "e2e_bug_trend.services.json").read_text(encoding="utf-8")

    assert '"grafana"' in config
    assert "3011" not in config
    assert "3051" in config
