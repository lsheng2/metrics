param(
    [switch]$UpdateBaseline,
    [string]$BaselineDir = ".github/skills/lsheng2-ui-design/visual-regression/baselines",
    [string]$DiffOutputDir = "tmp_ui_validation/visual-diffs",
    [double]$MaxDiffRatio = 0.001
)

$ErrorActionPreference = "Stop"

$Python = ".venv\Scripts\python.exe"
$UiSkillRoot = Join-Path $env:USERPROFILE ".agents\skills\lsheng2-ui-design"
$Manifest = ".github/skills/lsheng2-ui-design/visual-regression/synthetic-baseline-manifest.json"

$VisualArgs = @(
    (Join-Path $UiSkillRoot "scripts\run_visual_state_scenarios.py"),
    "--project-root", ".",
    "--manifest", $Manifest,
    "--include-hooked",
    "--hook-module", "scripts\ui_design_fixture_hooks.py",
    "--baseline-dir", $BaselineDir,
    "--diff-output-dir", $DiffOutputDir,
    "--max-diff-ratio", $MaxDiffRatio.ToString([Globalization.CultureInfo]::InvariantCulture)
)

if ($UpdateBaseline) {
    $VisualArgs += "--update-baseline"
}

& $Python @VisualArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
