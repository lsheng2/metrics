param()

$ErrorActionPreference = "Stop"

$Python = ".venv\Scripts\python.exe"

& $Python manage.py test `
    ui_web.tests.test_ui_design_baseline_gate.TestUiDesignBaselineGate.test_shouldRunVisualRegressionManifestAgainstCoreRoutes

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
