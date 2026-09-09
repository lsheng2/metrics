param(
    [switch]$Broad
)

$ErrorActionPreference = "Stop"

$Python = ".venv\Scripts\python.exe"
$UiSkillRoot = Join-Path $env:USERPROFILE ".agents\skills\lsheng2-ui-design"

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
    Invoke-Checked { & python (Join-Path $UiSkillRoot "scripts\validate_synthetic_fixture.py") }
    Invoke-Checked { & python (Join-Path $UiSkillRoot "scripts\audit_project_ui.py") --project-root . }
    Invoke-Checked { & python (Join-Path $UiSkillRoot "scripts\render_component_catalog.py") --project-root . --output ".github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html" }
    Invoke-Checked { & $Python (Join-Path $UiSkillRoot "scripts\audit_table_metrics.py") --project-root . --html-file ".github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html" }
    Invoke-Checked { & $Python (Join-Path $UiSkillRoot "scripts\audit_layout_metrics.py") --project-root . --html-file ".github/skills/lsheng2-ui-design/component-catalog/dashboard-admin-v1.html" --checks overflow,tables,buttons,forms }
    Invoke-Checked { scripts\validate_ui_visual_diff_gate.ps1 }
    Invoke-Checked { & python (Join-Path $UiSkillRoot "scripts\create_visual_regression_manifest.py") --project-root . --output ".github/skills/lsheng2-ui-design/visual-regression/manifest.json" }
    Invoke-Checked { scripts\refresh_ui_gate_report.ps1 -SkipBrowser }
    Invoke-Checked { scripts\validate_ui_visual_manifest.ps1 }
}

Invoke-Checked { git diff --check }
