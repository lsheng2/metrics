param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$NoScreenshots,
    [switch]$WithScreenshotDiff,
    [switch]$UpdateBaseline,
    [string]$BaselineDir = "tmp_ui_validation\visual-baselines",
    [string]$DiffOutputDir = "tmp_ui_validation\visual-diffs",
    [double]$MaxDiffRatio = 0.001,
    [switch]$SkipReportRefresh
)

$ErrorActionPreference = "Stop"

$Python = ".venv\Scripts\python.exe"
$UiSkillRoot = Join-Path $env:USERPROFILE ".agents\skills\lsheng2-ui-design"
$Manifest = ".github/skills/lsheng2-ui-design/visual-regression/manifest.json"

$LiveRouteGate = Join-Path $PSScriptRoot "validate_ui_live_routes.ps1"
if ($WithScreenshotDiff -or $UpdateBaseline) {
    & $LiveRouteGate `
        -BaseUrl $BaseUrl `
        -IncludeHooked `
        -NoScreenshots:$($NoScreenshots.IsPresent) `
        -BaselineDir $BaselineDir `
        -DiffOutputDir $DiffOutputDir `
        -MaxDiffRatio $MaxDiffRatio `
        -UpdateBaseline:$($UpdateBaseline.IsPresent)
} else {
    & $LiveRouteGate `
        -BaseUrl $BaseUrl `
        -IncludeHooked `
        -NoScreenshots:$($NoScreenshots.IsPresent)
}
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$VisualArgs = @(
    (Join-Path $UiSkillRoot "scripts\run_visual_state_scenarios.py"),
    "--project-root", ".",
    "--manifest", $Manifest,
    "--base-url", $BaseUrl,
    "--include-hooked",
    "--hook-module", "scripts\ui_design_fixture_hooks.py"
)

if ($NoScreenshots) {
    $VisualArgs += "--no-screenshots"
}

if ($WithScreenshotDiff -or $UpdateBaseline) {
    $VisualArgs += @("--baseline-dir", $BaselineDir)
    $VisualArgs += @("--diff-output-dir", $DiffOutputDir)
    $VisualArgs += @("--max-diff-ratio", $MaxDiffRatio.ToString([Globalization.CultureInfo]::InvariantCulture))
}

if ($UpdateBaseline) {
    $VisualArgs += "--update-baseline"
}

& $Python @VisualArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not $SkipReportRefresh) {
    $ReportRefresh = Join-Path $PSScriptRoot "refresh_ui_gate_report.ps1"
    if ($WithScreenshotDiff -or $UpdateBaseline) {
        & $ReportRefresh `
            -BaseUrl $BaseUrl `
            -IncludeHooked `
            -Screenshots `
            -BaselineDir $BaselineDir `
            -DiffOutputDir $DiffOutputDir `
            -MaxDiffRatio $MaxDiffRatio `
            -UpdateBaseline:$($UpdateBaseline.IsPresent)
    } else {
        & $ReportRefresh `
            -BaseUrl $BaseUrl `
            -IncludeHooked
    }
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
