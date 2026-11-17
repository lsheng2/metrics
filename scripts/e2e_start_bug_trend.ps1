[CmdletBinding()]
param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [ValidateSet('grafana', 'workbench', 'none')]
    [string]$OpenEntrypoint = 'workbench',
    [int]$DjangoPort = 0,
    [int]$GrafanaPort = 0
)

$ErrorActionPreference = 'Stop'

$python = if ($env:METRICS_DASHBOARD_PYTHON) { $env:METRICS_DASHBOARD_PYTHON } else { Join-Path $Workspace '.venv-embedded\Scripts\python.exe' }
if (-not (Test-Path $python)) { throw "Validated dashboard Python not found. Set METRICS_DASHBOARD_PYTHON or create .venv-embedded." }

$arguments = @(
    (Join-Path $Workspace 'scripts\e2e_bug_trend.py'),
    'start',
    '--workspace',
    $Workspace,
    '--open-entrypoint',
    $OpenEntrypoint
)
if ($DjangoPort -gt 0) {
    $arguments += @('--django-ports', ([string]$DjangoPort))
}
if ($GrafanaPort -gt 0) {
    $arguments += @('--grafana-ports', ([string]$GrafanaPort))
}

& $python @arguments
exit $LASTEXITCODE
