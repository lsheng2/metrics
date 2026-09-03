param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [ValidateSet('grafana', 'workbench', 'none')]
    [string]$OpenEntrypoint = 'grafana',
    [switch]$ForceByPort
)

$ErrorActionPreference = 'Stop'

$python = Join-Path $Workspace '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

$arguments = @(
    (Join-Path $Workspace 'scripts\e2e_bug_trend.py'),
    'start',
    '--workspace',
    $Workspace,
    '--open-entrypoint',
    $OpenEntrypoint
)
if ($ForceByPort) {
    $arguments += '--force-by-port'
}

& $python @arguments
