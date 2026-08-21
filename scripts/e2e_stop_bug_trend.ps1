param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$ForceByPort
)

$ErrorActionPreference = 'Stop'

$python = Join-Path $Workspace '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

$arguments = @((Join-Path $Workspace 'scripts\e2e_bug_trend.py'), 'stop', '--workspace', $Workspace)
if ($ForceByPort) {
    $arguments += '--force-by-port'
}

& $python @arguments
