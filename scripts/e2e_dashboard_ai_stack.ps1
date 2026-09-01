param(
    [ValidateSet('start', 'stop', 'restart')]
    [string]$Action = 'start',
    [string]$DashboardWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$AiBaseWorkspace = 'D:\AIGC\Report_creater_agent',
    [string]$DashboardBaseUrl = 'http://127.0.0.1:8002',
    [string]$AiBaseBackendUrl = 'http://127.0.0.1:48300',
    [string]$AiBaseFrontendUrl = 'http://127.0.0.1:48310',
    [string]$JiraProfileId = 'chiplet-2a-jira',
    [string]$BeginWw = '26WW32',
    [string]$EndWw = '26WW35',
    [switch]$SkipJiraSync,
    [switch]$SkipSmoke,
    [switch]$ForceByPort
)

$ErrorActionPreference = 'Stop'

function Invoke-StackScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [string[]]$Arguments = @()
    )

    & powershell -ExecutionPolicy Bypass -File $ScriptPath @Arguments
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

function Invoke-JsonPost {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [Parameter(Mandatory = $true)]
        [hashtable]$Body
    )

    $json = $Body | ConvertTo-Json -Depth 10
    Invoke-RestMethod -Uri $Url -Method Post -Body $json -ContentType 'application/json' -TimeoutSec 20
}

function Stop-DashboardAiStack {
    $dashboardStop = Join-Path $DashboardWorkspace 'scripts\e2e_stop_bug_trend.ps1'
    $aiBaseStop = Join-Path $AiBaseWorkspace 'scripts\stop-minimal-chat-dev.ps1'

    $dashboardArgs = @('-Workspace', $DashboardWorkspace)
    if ($ForceByPort) {
        $dashboardArgs += '-ForceByPort'
    }
    Invoke-StackScript -ScriptPath $dashboardStop -Arguments $dashboardArgs

    $aiBaseArgs = @('-Profile', 'dashboard_query_agent')
    if ($ForceByPort) {
        $aiBaseArgs += '-ForceByPort'
    }
    Invoke-StackScript -ScriptPath $aiBaseStop -Arguments $aiBaseArgs
}

function Start-DashboardStack {
    $dashboardStart = Join-Path $DashboardWorkspace 'scripts\e2e_start_bug_trend.ps1'
    $dashboardArgs = @('-Workspace', $DashboardWorkspace)
    if ($ForceByPort) {
        $dashboardArgs += '-ForceByPort'
    }

    Invoke-WithTemporaryEnv -Values @{
        METRICS_AI_SIDECAR_ENABLED = 'true'
        METRICS_AI_BASE_URL = $AiBaseBackendUrl
    } -ScriptBlock {
        Invoke-StackScript -ScriptPath $dashboardStart -Arguments $dashboardArgs
    }
}

function Start-AiBaseStack {
    $aiBaseStart = Join-Path $AiBaseWorkspace 'scripts\start-minimal-chat-dev.ps1'
    Invoke-WithTemporaryEnv -Values @{
        RCA_DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
        DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
    } -ScriptBlock {
        Invoke-StackScript -ScriptPath $aiBaseStart -Arguments @('-Profile', 'dashboard_query_agent')
    }
}

function Restart-AiBaseStack {
    $aiBaseRestart = Join-Path $AiBaseWorkspace 'scripts\restart-minimal-chat-dev.ps1'
    $aiBaseArgs = @('-Profile', 'dashboard_query_agent')
    if ($ForceByPort) {
        $aiBaseArgs += '-ForceByPort'
    }

    Invoke-WithTemporaryEnv -Values @{
        RCA_DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
        DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
    } -ScriptBlock {
        Invoke-StackScript -ScriptPath $aiBaseRestart -Arguments $aiBaseArgs
    }
}

function Sync-JiraProfile {
    if ($SkipJiraSync) {
        Write-Host 'Skipping Jira profile sync.'
        return
    }

    $python = Join-Path $DashboardWorkspace '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        $python = 'python'
    }

    & $python (Join-Path $DashboardWorkspace 'manage.py') sync_provider_profile `
        --profile-id $JiraProfileId `
        --begin-ww $BeginWw `
        --end-ww $EndWw `
        --force-refresh
}

function Test-DashboardAiStack {
    if ($SkipSmoke) {
        Write-Host 'Skipping smoke checks.'
        return
    }

    $workflowPage = Invoke-WebRequest -Uri "$DashboardBaseUrl/ai-dashboard/workflow/" -TimeoutSec 20 -UseBasicParsing
    if ($workflowPage.StatusCode -ne 200 -or -not $workflowPage.Content.Contains('/api/ai-dashboard/workflow/')) {
        throw 'Dashboard AI workflow page did not expose the expected workflow endpoint.'
    }

    $workflowResult = Invoke-JsonPost -Url "$DashboardBaseUrl/api/ai-dashboard/workflow/" -Body @{
        profile_id = $JiraProfileId
        dashboard_uid = 'ip-quality-dashboard'
        chart_id = 'open_bug_trend'
        requested_series = @('new_critical_high')
        range_mode = 'ww'
        range_start = $BeginWw
        range_end = $EndWw
        operation = 'grafana_import'
        actor = 'e2e_dashboard_ai_stack'
    }
    if ($workflowResult.intent_validation.status -ne 'draft_validated') {
        throw "Dashboard workflow intent validation was $($workflowResult.intent_validation.status)."
    }
    if ($workflowResult.gcx_precondition.status -ne 'precondition_passed') {
        throw "Dashboard workflow gcx precondition was $($workflowResult.gcx_precondition.status)."
    }

    $diagnostics = Invoke-RestMethod -Uri "$AiBaseBackendUrl/api/runtime/diagnostics/summary" -TimeoutSec 20
    $connector = @($diagnostics.security.connectors | Where-Object { $_.connectorId -eq 'metrics-dashboard' } | Select-Object -First 1)
    if (-not $connector) {
        throw 'AI Base diagnostics did not report the metrics-dashboard connector.'
    }
    if (-not $connector.executable) {
        throw "AI Base metrics-dashboard connector is not executable: $($connector.blockedReason)"
    }
    if (-not (@($connector.modelVisibleOperations) -contains 'workflow.run')) {
        throw 'AI Base metrics-dashboard connector does not expose workflow.run.'
    }

    Write-Host 'Smoke checks passed.'
}

if (-not (Test-Path $DashboardWorkspace)) {
    throw "Dashboard workspace not found: $DashboardWorkspace"
}
if (-not (Test-Path $AiBaseWorkspace)) {
    throw "AI Base workspace not found: $AiBaseWorkspace"
}

if ($Action -eq 'stop') {
    Stop-DashboardAiStack
    Write-Host 'Dashboard + AI Base E2E stack stopped.'
    return
}

if ($Action -eq 'restart') {
    Stop-DashboardAiStack
}

Start-DashboardStack
Sync-JiraProfile
if ($Action -eq 'restart') {
    Restart-AiBaseStack
}
else {
    try {
        Start-AiBaseStack
    }
    catch {
        Write-Warning "AI Base start failed, attempting restart instead. Original error: $($_.Exception.Message)"
        Restart-AiBaseStack
    }
}
Test-DashboardAiStack

Write-Host ''
Write-Host 'Dashboard + AI Base E2E stack is ready.'
Write-Host "Dashboard AI Workflow: $DashboardBaseUrl/ai-dashboard/workflow/"
Write-Host "AI Base frontend     : $AiBaseFrontendUrl/"
Write-Host "AI Base backend      : $AiBaseBackendUrl/"
Write-Host "Jira profile         : $JiraProfileId ($BeginWw to $EndWw)"
