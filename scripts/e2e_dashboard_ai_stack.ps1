[CmdletBinding()]
param(
    [ValidateSet('start', 'stop', 'restart')]
    [string]$Action = 'start',
    [string]$DashboardWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$DashboardBaseUrl = 'http://127.0.0.1:8002',
    [string]$ModelBaseUrl = '',
    [string]$JiraProfileId = 'chiplet-2a-jira',
    [string]$BeginWw = '26WW32',
    [string]$EndWw = '26WW35',
    [int]$DjangoPort = 0,
    [int]$GrafanaPort = 0,
    [switch]$SkipJiraSync,
    [switch]$SkipSmoke,
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
function Resolve-DashboardPython {
    if ($env:METRICS_DASHBOARD_PYTHON) {
        return $env:METRICS_DASHBOARD_PYTHON
    }
    $python = Join-Path $DashboardWorkspace '.venv-embedded\Scripts\python.exe'
    if (Test-Path $python) {
        return $python
    }
    throw "Validated dashboard Python not found. Set METRICS_DASHBOARD_PYTHON or create .venv-embedded."
}
function Invoke-StackScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [string[]]$Arguments = @(),
        [string]$Label = 'stack-script'
    )
    $commandArguments = @('-ExecutionPolicy', 'Bypass', '-File', $ScriptPath)
    $commandArguments += $Arguments
    Invoke-StackCommand -FilePath 'powershell' -Arguments $commandArguments -Label $Label
}
function Invoke-StackCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$Label = 'stack-command'
    )
    $logPath = New-StackLogPath -Label $Label
    Write-Host "Stack script log: $logPath"
    if (Test-Path $logPath) {
        Remove-Item -Path $logPath -Force
    }
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $FilePath @Arguments *> $logPath
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if (Test-Path $logPath) {
        Get-Content -Path $logPath
    }
    if ($exitCode -ne 0) {
        throw "Stack command failed with exit code $($exitCode): $FilePath"
    }
}
function New-StackLogPath {
    param(
        [string]$Label = 'stack-script'
    )
    if (-not $script:StackLogDirectory) {
        $script:StackLogDirectory = Join-Path $DashboardWorkspace 'state\e2e\dashboard-ai-stack\logs'
    }
    if (-not (Test-Path $script:StackLogDirectory)) {
        New-Item -ItemType Directory -Path $script:StackLogDirectory -Force | Out-Null
    }
    $safeLabel = $Label -replace '[^A-Za-z0-9_.-]', '-'
    $timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    return Join-Path $script:StackLogDirectory "$timestamp-$safeLabel.log"
}
function Invoke-WithStackRetry {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock,
        [int]$Attempts = 3,
        [int]$DelaySeconds = 1
    )
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            return & $ScriptBlock
        }
        catch {
            if ($attempt -ge $Attempts) {
                throw
            }
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}
function Invoke-WithTemporaryEnv {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Values,
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock
    )
    $previousValues = @{}
    foreach ($name in $Values.Keys) {
        $previousValues[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, [string]$Values[$name], 'Process')
    }
    try {
        & $ScriptBlock
    }
    finally {
        foreach ($name in $Values.Keys) {
            [Environment]::SetEnvironmentVariable($name, $previousValues[$name], 'Process')
        }
    }
}
function Invoke-WithDashboardRuntimeEnv {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$ScriptBlock
    )
    $values = @{
        LOGFIRE_IGNORE_NO_CONFIG = '1'
    }
    if (-not [string]::IsNullOrWhiteSpace($ModelBaseUrl)) {
        $values['METRICS_AI_MODEL_BASE_URL'] = $ModelBaseUrl
    }
    Invoke-WithTemporaryEnv -Values $values -ScriptBlock $ScriptBlock
}
function Invoke-BootLogAudit {
    param(
        [string]$Phase = '',
        [switch]$RequireDashboardState
    )
    $python = Resolve-DashboardPython
    $auditArgs = @(
        (Join-Path $DashboardWorkspace 'scripts\audit_stack_boot_logs.py'),
        '--dashboard-workspace',
        $DashboardWorkspace,
        '--dashboard-state',
        (Get-DashboardLifecycleStatePath),
        '--stack-log-directory',
        $script:StackLogDirectory,
        '--since-utc',
        $script:StackRunStartedAtUtc,
        '--phase',
        $Phase
    )
    if ($RequireDashboardState) {
        $auditArgs += '--require-dashboard-state'
    }
    Write-Host "Running boot log audit: $Phase"
    & $python @auditArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Boot log audit failed during $Phase."
    }
}
function Invoke-ProcessInventoryAudit {
    param(
        [string]$Phase = ''
    )
    $python = Resolve-DashboardPython
    $auditArgs = @(
        (Join-Path $DashboardWorkspace 'scripts\audit_stack_process_inventory.py'),
        '--dashboard-workspace',
        $DashboardWorkspace,
        '--dashboard-state',
        (Get-DashboardLifecycleStatePath),
        '--phase',
        $Phase
    )
    Write-Host "Running process inventory audit: $Phase"
    & $python @auditArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Process inventory audit failed during $Phase."
    }
}
function Stop-DashboardStack {
    $dashboardStop = Join-Path $DashboardWorkspace 'scripts\e2e_stop_bug_trend.ps1'
    $dashboardArgs = @('-Workspace', $DashboardWorkspace)
    if ($DjangoPort -gt 0) {
        $dashboardArgs += @('-DjangoPort', ([string]$DjangoPort))
    }
    if ($GrafanaPort -gt 0) {
        $dashboardArgs += @('-GrafanaPort', ([string]$GrafanaPort))
    }
    Invoke-StackScript -ScriptPath $dashboardStop -Arguments $dashboardArgs -Label 'dashboard-stop'
}
function Start-DashboardStack {
    $dashboardStart = Join-Path $DashboardWorkspace 'scripts\e2e_start_bug_trend.ps1'
    $dashboardArgs = @('-Workspace', $DashboardWorkspace, '-OpenEntrypoint', 'none')
    if ($DjangoPort -gt 0) {
        $dashboardArgs += @('-DjangoPort', ([string]$DjangoPort))
    }
    if ($GrafanaPort -gt 0) {
        $dashboardArgs += @('-GrafanaPort', ([string]$GrafanaPort))
    }
    Invoke-WithDashboardRuntimeEnv -ScriptBlock {
        Invoke-StackScript -ScriptPath $dashboardStart -Arguments $dashboardArgs -Label 'dashboard-start'
    }
}
function Update-DashboardRuntimeUrls {
    $summaryPath = Join-Path $DashboardWorkspace 'state\e2e\bug_trend_ports.json'
    if (-not (Test-Path $summaryPath)) {
        return
    }
    try {
        $summary = Get-Content -Path $summaryPath -Raw | ConvertFrom-Json
    }
    catch {
        Write-Warning "Could not read E2E runtime ports from ${summaryPath}: $($_.Exception.Message)"
        return
    }
    if ($summary.django_port) {
        $runtimeDashboardBaseUrl = "http://127.0.0.1:$([int]$summary.django_port)"
        if ($DashboardBaseUrl -ne $runtimeDashboardBaseUrl) {
            Write-Host "E2E runtime Dashboard URL: $runtimeDashboardBaseUrl"
            Set-Variable -Name DashboardBaseUrl -Scope Script -Value $runtimeDashboardBaseUrl
        }
    }
}
function Get-DashboardLifecycleStatePath {
    $profilePath = Join-Path $DashboardWorkspace 'state\local\runtime-instance.json'
    if (Test-Path $profilePath) {
        try {
            $profile = Get-Content -Path $profilePath -Raw | ConvertFrom-Json
            $instanceId = [string]$profile.identity.instance_id
            if (-not [string]::IsNullOrWhiteSpace($instanceId)) {
                return (Join-Path $DashboardWorkspace "state\local\instances\$instanceId\service-lifecycle-engine\metrics-bug-trend-$instanceId.json")
            }
        }
        catch {
        }
    }
    return (Join-Path $DashboardWorkspace 'state\e2e\service-lifecycle-engine\metrics-bug-trend-default.json')
}
function Test-JiraProfileSyncRunning {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Python
    )
    $query = 'import os; from bug_metrics.models import JiraScopeConfig; from jira_sync.models import JiraSyncCursor; profile_id = os.environ.get("E2E_JIRA_PROFILE_ID", ""); scope = JiraScopeConfig.objects.filter(enabled=True, name=profile_id).first(); print(JiraSyncCursor.objects.filter(scope=scope).values_list("status", flat=True).first() if scope else "")'
    $previousProfileId = [Environment]::GetEnvironmentVariable('E2E_JIRA_PROFILE_ID', 'Process')
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        [Environment]::SetEnvironmentVariable('E2E_JIRA_PROFILE_ID', $JiraProfileId, 'Process')
        $statusOutput = @(& $Python (Join-Path $DashboardWorkspace 'manage.py') shell -c $query 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $statusOutput) {
            return $false
        }
        $status = [string](@($statusOutput)[-1])
        return ($status.Trim().ToLowerInvariant() -eq 'running')
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        [Environment]::SetEnvironmentVariable('E2E_JIRA_PROFILE_ID', $previousProfileId, 'Process')
    }
}
function Sync-JiraProfile {
    if ($SkipJiraSync) {
        Write-Host 'Skipping Jira profile sync.'
        return
    }
    $python = Resolve-DashboardPython
    if (Test-JiraProfileSyncRunning -Python $python) {
        Write-Host 'Jira profile sync is already running for this scope; continuing with the existing sync state.'
        return
    }
    $logPath = New-StackLogPath -Label 'jira-profile-sync'
    Write-Host "Stack script log: $logPath"
    if (Test-Path $logPath) {
        Remove-Item -Path $logPath -Force
    }
    $previousErrorActionPreference = $ErrorActionPreference
    Invoke-WithDashboardRuntimeEnv -ScriptBlock {
        try {
            $ErrorActionPreference = 'Continue'
            & $python `
                (Join-Path $DashboardWorkspace 'manage.py') `
                sync_provider_profile `
                --profile-id $JiraProfileId `
                --begin-ww $BeginWw `
                --end-ww $EndWw `
                --force-refresh *> $logPath
            $script:LastJiraProfileSyncExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
    }
    $exitCode = $script:LastJiraProfileSyncExitCode
    $script:LastJiraProfileSyncExitCode = $null
    if ($exitCode -eq 0) {
        Get-Content -Path $logPath
        return
    }
    $syncAlreadyRunning = (
        (Test-Path $logPath) -and
        (Select-String -Path $logPath -Pattern 'A sync is already running for this scope' -Quiet)
    )
    if ($syncAlreadyRunning) {
        Set-Content -Path $logPath -Value 'Jira profile sync already active; continuing with the existing sync state.' -Encoding utf8
        Write-Host 'Jira profile sync already active; continuing with the existing sync state.'
        return
    }
    if (Test-Path $logPath) {
        Get-Content -Path $logPath
    }
    throw "Stack command failed with exit code $($exitCode): $python"
}
function Test-DashboardStack {
    if ($SkipSmoke) {
        Write-Host 'Skipping smoke checks.'
        return
    }
    Write-Host 'Smoke check: Dashboard workbench.'
    $workbenchPage = Invoke-WithStackRetry -ScriptBlock {
        Invoke-WebRequest -Uri "$DashboardBaseUrl/workbench/" -TimeoutSec 20 -UseBasicParsing
    }
    if ($workbenchPage.StatusCode -ne 200 -or -not $workbenchPage.Content.Contains('workbench-ai-context')) {
        throw 'Dashboard workbench page did not expose the expected unified UI context.'
    }
    Write-Host 'Smoke check: Dashboard AI workflow.'
    $workflowPage = Invoke-WithStackRetry -ScriptBlock {
        Invoke-WebRequest -Uri "$DashboardBaseUrl/ai-dashboard/workflow/" -TimeoutSec 20 -UseBasicParsing
    }
    if ($workflowPage.StatusCode -ne 200 -or -not $workflowPage.Content.Contains('ai-workflow-form') -or -not $workflowPage.Content.Contains('method="post"')) {
        throw 'Dashboard AI workflow page did not expose the current workflow form.'
    }
    Write-Host 'Smoke checks passed.'
}
function Get-WorkbenchUrl {
    $defaultUrl = "$DashboardBaseUrl/workbench/"
    $summaryPath = Join-Path $DashboardWorkspace 'state\e2e\bug_trend_ports.json'
    if (-not (Test-Path $summaryPath)) {
        return $defaultUrl
    }
    try {
        $summary = Get-Content -Path $summaryPath -Raw | ConvertFrom-Json
        if ($summary.workbench_url) {
            return [string]$summary.workbench_url
        }
    }
    catch {
        Write-Warning "Could not read E2E workbench URL from ${summaryPath}: $($_.Exception.Message)"
    }
    return $defaultUrl
}
if (-not (Test-Path $DashboardWorkspace)) {
    throw "Dashboard workspace not found: $DashboardWorkspace"
}
$script:StackRunStartedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
$script:StackLogDirectory = Join-Path $DashboardWorkspace 'state\e2e\dashboard-ai-stack\logs'
if ($Action -eq 'stop') {
    Stop-DashboardStack
    Write-Host 'Dashboard E2E stack stopped.'
    return
}
try {
    if ($Action -eq 'restart') {
        Stop-DashboardStack
    }
    Start-DashboardStack
    Update-DashboardRuntimeUrls
    Invoke-BootLogAudit -Phase 'dashboard-start' -RequireDashboardState
    Sync-JiraProfile
    Write-Host 'Running stack smoke checks.'
    Test-DashboardStack
    Write-Host 'Stack smoke checks completed.'
    Invoke-BootLogAudit -Phase 'final' -RequireDashboardState
    Invoke-ProcessInventoryAudit -Phase 'final'
    $workbenchUrl = Get-WorkbenchUrl
    if (-not $NoOpen) {
        Start-Process $workbenchUrl
    }
    Write-Host ''
    Write-Host 'Dashboard E2E stack is ready.'
    Write-Host "Metrics Workbench    : $workbenchUrl"
    Write-Host "Dashboard AI Workflow: $DashboardBaseUrl/ai-dashboard/workflow/"
    Write-Host "Jira profile         : $JiraProfileId ($BeginWw to $EndWw)"
}
catch {
    try {
        Invoke-BootLogAudit -Phase 'failure'
    }
    catch {
        Write-Warning "Boot log audit also failed while handling the launch failure: $($_.Exception.Message)"
    }
    throw
}
