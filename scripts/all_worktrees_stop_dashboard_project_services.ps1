param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$ForceByPort
)

$ErrorActionPreference = 'Stop'

function Get-DashboardWorktrees {
    $rows = @()
    $current = $null
    foreach ($line in @(git -C $Workspace worktree list --porcelain)) {
        if ($line.StartsWith('worktree ')) {
            if ($current) {
                $rows += $current
            }
            $current = [ordered]@{ Path = $line.Substring('worktree '.Length) }
        }
        elseif ($current -and $line.StartsWith('branch ')) {
            $current.Branch = $line.Substring('branch '.Length)
        }
        elseif ($current -and $line.StartsWith('detached')) {
            $current.Branch = 'detached'
        }
    }
    if ($current) {
        $rows += $current
    }
    return @($rows | Where-Object { Test-Path -LiteralPath (Join-Path $_.Path 'scripts\e2e_stop_bug_trend.ps1') })
}

$worktrees = @(Get-DashboardWorktrees)
if ($worktrees.Count -eq 0) {
    Write-Host 'No Dashboard worktrees found.'
    exit 0
}

foreach ($worktree in $worktrees) {
    $script = Join-Path $worktree.Path 'scripts\e2e_stop_bug_trend.ps1'
    $arguments = @('-ExecutionPolicy', 'Bypass', '-File', $script, '-Workspace', $worktree.Path)
    if ($ForceByPort) {
        $arguments += '-ForceByPort'
    }
    Write-Host "Stopping Dashboard project services in $($worktree.Path)"
    & powershell @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Stop failed for Dashboard worktree: $($worktree.Path)"
    }
}
