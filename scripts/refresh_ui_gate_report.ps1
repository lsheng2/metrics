param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [switch]$IncludeHooked,
    [switch]$SkipBrowser,
    [switch]$Screenshots,
    [string]$BaselineDir = "",
    [string]$DiffOutputDir = "tmp_ui_validation\visual-diffs",
    [double]$MaxDiffRatio = 0.001,
    [switch]$UpdateBaseline
)

$ErrorActionPreference = "Stop"

$Python = ".venv\Scripts\python.exe"
$UiSkillRoot = Join-Path $env:USERPROFILE ".agents\skills\lsheng2-ui-design"
$ReportScript = Join-Path $UiSkillRoot "scripts\create_ui_gate_report.py"

$ReportArgs = @(
    $ReportScript,
    "--project-root", ".",
    "--python", $Python,
    "--write"
)

if ($SkipBrowser) {
    $ReportArgs += "--skip-browser"
} elseif ($BaseUrl) {
    $ReportArgs += @("--base-url", $BaseUrl)
}

if ($IncludeHooked) {
    $ReportArgs += "--include-hooked"
    $ReportArgs += @("--hook-module", "scripts\ui_design_fixture_hooks.py")
}

if ($Screenshots) {
    $ReportArgs += "--screenshots"
}

if ($BaselineDir) {
    $ReportArgs += @("--baseline-dir", $BaselineDir)
}

if ($DiffOutputDir) {
    $ReportArgs += @("--diff-output-dir", $DiffOutputDir)
}

if ($UpdateBaseline) {
    $ReportArgs += "--update-baseline"
}

$ReportArgs += @("--max-diff-ratio", $MaxDiffRatio.ToString([Globalization.CultureInfo]::InvariantCulture))

& $Python @ReportArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
