param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$Json
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
        elseif ($current -and $line.StartsWith('HEAD ')) {
            $current.Head = $line.Substring('HEAD '.Length)
        }
    }
    if ($current) {
        $rows += $current
    }
    return @($rows | Where-Object { Test-Path -LiteralPath (Join-Path $_.Path 'scripts\e2e_bug_trend.py') })
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }
    try {
        return Get-Content -Path $Path -Raw | ConvertFrom-Json
    }
    catch {
        return $null
    }
}

function Get-ListenerPids {
    param([int]$Port)
    try {
        return @(
            Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop |
                Select-Object -ExpandProperty OwningProcess -Unique |
                Sort-Object
        )
    }
    catch {
        return @()
    }
}

function Add-PortRow {
    param(
        [System.Collections.Generic.List[object]]$Rows,
        [object]$Worktree,
        [string]$InstanceId,
        [string]$Service,
        [int]$Port,
        [string]$Source
    )
    if ($Port -le 0) {
        return
    }
    $pids = @(Get-ListenerPids -Port $Port)
    $Rows.Add([PSCustomObject]@{
        Worktree = $Worktree.Path
        Branch = [string]$Worktree.Branch
        Instance = $InstanceId
        Service = $Service
        Port = $Port
        Source = $Source
        Live = ($pids.Count -gt 0)
        Pids = ($pids -join ',')
    }) | Out-Null
}

$inventory = [System.Collections.Generic.List[object]]::new()
foreach ($worktree in Get-DashboardWorktrees) {
    $profilePath = Join-Path $worktree.Path 'state\local\runtime-instance.json'
    $profile = Read-JsonFile -Path $profilePath
    $instanceId = ''
    if ($profile -and $profile.identity -and $profile.identity.instance_id) {
        $instanceId = [string]$profile.identity.instance_id
    }
    if ($profile -and $profile.service_ports) {
        Add-PortRow -Rows $inventory -Worktree $worktree -InstanceId $instanceId -Service 'django' -Port ([int]$profile.service_ports.django) -Source 'runtime-profile'
        Add-PortRow -Rows $inventory -Worktree $worktree -InstanceId $instanceId -Service 'grafana' -Port ([int]$profile.service_ports.grafana) -Source 'runtime-profile'
    }

    $summary = Read-JsonFile -Path (Join-Path $worktree.Path 'state\e2e\bug_trend_ports.json')
    if ($summary) {
        Add-PortRow -Rows $inventory -Worktree $worktree -InstanceId $instanceId -Service 'django' -Port ([int]$summary.django_port) -Source 'e2e-summary'
        Add-PortRow -Rows $inventory -Worktree $worktree -InstanceId $instanceId -Service 'grafana' -Port ([int]$summary.grafana_port) -Source 'e2e-summary'
    }

    $stateFiles = @()
    $stateFiles += Get-ChildItem -LiteralPath (Join-Path $worktree.Path 'state\local\instances') -Filter 'metrics-bug-trend-*.json' -Recurse -ErrorAction SilentlyContinue
    $legacyState = Join-Path $worktree.Path 'state\e2e\service-lifecycle-engine\metrics-bug-trend-default.json'
    if (Test-Path -LiteralPath $legacyState) {
        $stateFiles += Get-Item -LiteralPath $legacyState
    }
    foreach ($stateFile in $stateFiles) {
        $state = Read-JsonFile -Path $stateFile.FullName
        if (-not $state -or -not $state.services) {
            continue
        }
        foreach ($serviceName in @('django', 'grafana')) {
            $service = $state.services.$serviceName
            if ($service -and $service.port) {
                Add-PortRow -Rows $inventory -Worktree $worktree -InstanceId ([string]$state.instance) -Service $serviceName -Port ([int]$service.port) -Source 'lifecycle-state'
            }
        }
    }
}

$uniqueRows = @(
    $inventory |
        Sort-Object Worktree, Instance, Service, Port, Source -Unique
)

if ($Json) {
    $uniqueRows | ConvertTo-Json -Depth 4
}
else {
    $uniqueRows | Format-Table -AutoSize
}
