[CmdletBinding()]
param([string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path)

$ErrorActionPreference = 'Stop'

function Get-DashboardWorktrees {
    $output = @(& git -C $Workspace worktree list --porcelain -z)
    if ($LASTEXITCODE -ne 0) {
        throw "Dashboard worktree enumeration failed with exit code $LASTEXITCODE"
    }
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($field in ([string]::Join("`n", $output)).Split([char]0)) {
        if ($field.StartsWith('worktree ')) {
            $path = $field.Substring('worktree '.Length)
            if (-not [IO.Path]::IsPathRooted($path)) { throw 'Worktree path is not absolute.' }
            $path = [IO.Path]::GetFullPath($path)
            if (-not $seen.Add($path)) { continue }
            $profile = Join-Path $path 'state\local\runtime-instance.json'
            if ((Test-Path -LiteralPath (Join-Path $path 'scripts\e2e_stop_bug_trend.ps1')) -and
                (Test-Path -LiteralPath $profile -PathType Leaf)) {
                $path
            }
        }
    }
}

$worktrees = @(Get-DashboardWorktrees)
if ($worktrees.Count -eq 0) {
    Write-Host 'No Dashboard worktrees found.'
    exit 0
}

$codeRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = if ($env:METRICS_DASHBOARD_PYTHON) { $env:METRICS_DASHBOARD_PYTHON } else { Join-Path $codeRoot '.venv-embedded\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Selected runtime Python is missing.' }
$launcher = Join-Path $PSScriptRoot 'e2e_bug_trend.py'
$failures = @()
foreach ($worktree in $worktrees) {
    Write-Host "Stopping registered Dashboard services in $worktree"
    & $python $launcher stop --workspace $worktree
    if ($LASTEXITCODE -ne 0) {
        $failures += $worktree
    }
}
if ($failures.Count) { throw "Stop failed for Dashboard worktree(s): $($failures -join ', ')" }
exit 0
