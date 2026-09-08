param(
    [switch]$Broad
)

$ErrorActionPreference = "Stop"

$Python = ".venv\Scripts\python.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Step
    )

    & $Step
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Invoke-Checked { & $Python manage.py test `
    ui_web.tests.test_dashboard_ui_design_system `
    ui_web.tests.test_ui_design_baseline_gate }

if ($Broad) {
    Invoke-Checked { & $Python manage.py test `
        ui_web.tests.test_dashboard_ui_design_system `
        ui_web.tests.test_provider_setup_views `
        ui_web.tests.test_bug_trend_scope_config_views `
        ui_web.tests.test_data_health_views `
        ui_web.tests.test_workbench_views `
        ui_web.tests.test_workbench_ai_host_actions `
        ui_web.tests.test_ai_dashboard_api_surface `
        ui_web.tests.test_ui_design_baseline_gate }

    Invoke-Checked { & $Python manage.py check }
    Invoke-Checked { & $Python manage.py makemigrations --check --dry-run }
    Invoke-Checked { openspec validate standardize-dashboard-ui-design-system --strict }
    Invoke-Checked { openspec validate consolidate-provider-onboarding-profile --strict }
}

Invoke-Checked { git diff --check }
