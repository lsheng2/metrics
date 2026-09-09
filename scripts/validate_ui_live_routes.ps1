param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$IncludeHooked,
    [switch]$NoScreenshots,
    [switch]$AllManifestRoutes
)

$ErrorActionPreference = "Stop"

$Python = ".venv\Scripts\python.exe"
$UiSkillRoot = Join-Path $env:USERPROFILE ".agents\skills\lsheng2-ui-design"
$Manifest = ".github/skills/lsheng2-ui-design/visual-regression/manifest.json"

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

$RouteArgs = @()
$LayoutTargetArgs = @()
$ViewportArgs = @("--viewport", "desktop:1440x900", "--viewport", "tablet:768x1024", "--viewport", "phone:390x900")
if ($AllManifestRoutes) {
    $LayoutTargetArgs += @("--manifest", $Manifest)
} else {
    $RouteArgs += @("--route", "/provider-setup/")
    $RouteArgs += @("--route", "/bug-trend/scope-config/")
    $LayoutTargetArgs += @("--url", "$BaseUrl/provider-setup/")
    $LayoutTargetArgs += @("--url", "$BaseUrl/bug-trend/scope-config/?mode=new&provider_id=jira")
}

$ScenarioArgs = @()
if ($IncludeHooked) {
    $ScenarioArgs += "--include-hooked"
}
if ($NoScreenshots) {
    $ScenarioArgs += "--no-screenshots"
}

Invoke-Checked {
    & $Python (Join-Path $UiSkillRoot "scripts\audit_layout_metrics.py") `
        --project-root . `
        --base-url $BaseUrl `
        --checks overflow,tables,buttons,forms `
        @ViewportArgs `
        @LayoutTargetArgs
}

Invoke-Checked {
    & $Python (Join-Path $UiSkillRoot "scripts\run_visual_state_scenarios.py") `
        --manifest $Manifest `
        --base-url $BaseUrl `
        @RouteArgs `
        @ScenarioArgs
}
