param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'

$python = Join-Path $Workspace '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $python = 'python'
}

& $python (Join-Path $Workspace 'scripts\e2e_bug_trend.py') start --workspace $Workspace
