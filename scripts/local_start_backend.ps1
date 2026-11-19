[CmdletBinding()]
param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [int]$Port = 8002
)

$ErrorActionPreference = 'Stop'

$python = if ($env:METRICS_DASHBOARD_PYTHON) { $env:METRICS_DASHBOARD_PYTHON } else { Join-Path $Workspace '.venv-embedded\Scripts\python.exe' }
if (-not (Test-Path $python)) { throw "Validated dashboard Python not found. Set METRICS_DASHBOARD_PYTHON or create .venv-embedded." }

$arguments = @(
    (Join-Path $Workspace 'scripts\e2e_bug_trend.py'),
    'start-backend',
    '--workspace',
    $Workspace,
    '--django-ports',
    ([string]$Port),
    '--open-entrypoint',
    'none'
)

& $python @arguments
exit $LASTEXITCODE
