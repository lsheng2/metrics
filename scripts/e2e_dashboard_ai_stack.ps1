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
    [switch]$FullAiChatSmoke,
    [switch]$ForceByPort
)

$ErrorActionPreference = 'Stop'

function Invoke-StackScript {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [string[]]$Arguments = @(),
        [string]$Label = 'stack-script',
        [switch]$NoCapture
    )

    $commandArguments = @('-ExecutionPolicy', 'Bypass', '-File', $ScriptPath)
    $commandArguments += $Arguments
    Invoke-StackCommand -FilePath 'powershell' -Arguments $commandArguments -Label $Label -NoCapture:($NoCapture.IsPresent)
}

function Invoke-StackCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [string[]]$Arguments = @(),
        [string]$Label = 'stack-command',
        [switch]$NoCapture
    )

    if ($NoCapture.IsPresent) {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Stack command failed with exit code $($LASTEXITCODE): $FilePath"
        }
        return
    }

    $logPath = New-StackLogPath -Label $Label
    $script:LastStackLogPath = $logPath
    $script:LastStackErrorLogPath = $logPath
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

function Invoke-BootLogAudit {
    param(
        [string]$Phase = '',
        [switch]$RequireDashboardState,
        [switch]$RequireAiBaseState
    )

    $python = Join-Path $DashboardWorkspace '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        $python = 'python'
    }

    $auditArgs = @(
        (Join-Path $DashboardWorkspace 'scripts\audit_stack_boot_logs.py'),
        '--dashboard-workspace',
        $DashboardWorkspace,
        '--ai-base-workspace',
        $AiBaseWorkspace,
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
    if ($RequireAiBaseState) {
        $auditArgs += '--require-ai-base-state'
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

    $python = Join-Path $DashboardWorkspace '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        $python = 'python'
    }

    $auditArgs = @(
        (Join-Path $DashboardWorkspace 'scripts\audit_stack_process_inventory.py'),
        '--dashboard-workspace',
        $DashboardWorkspace,
        '--ai-base-workspace',
        $AiBaseWorkspace,
        '--phase',
        $Phase
    )

    Write-Host "Running process inventory audit: $Phase"
    & $python @auditArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Process inventory audit failed during $Phase."
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

function Invoke-JsonPost {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [Parameter(Mandatory = $true)]
    [object]$Body
    )

    $json = $Body | ConvertTo-Json -Depth 10
    Invoke-WithStackRetry -ScriptBlock {
        Invoke-RestMethod -Uri $Url -Method Post -Body $json -ContentType 'application/json' -TimeoutSec 20
    }
}

function Invoke-JsonPostStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [Parameter(Mandatory = $true)]
        [object]$Body
    )

    $json = $Body | ConvertTo-Json -Depth 10
    $webRequestCommand = Get-Command Invoke-WebRequest
    if ($webRequestCommand.Parameters.ContainsKey('SkipHttpErrorCheck')) {
        $response = Invoke-WithStackRetry -ScriptBlock {
            Invoke-WebRequest -Uri $Url -Method Post -Body $json -ContentType 'application/json' -TimeoutSec 20 -UseBasicParsing -SkipHttpErrorCheck
        }
        return @{
            StatusCode = [int]$response.StatusCode
            Body = $response.Content | ConvertFrom-Json
        }
    }

    try {
        $response = Invoke-WithStackRetry -ScriptBlock {
            Invoke-WebRequest -Uri $Url -Method Post -Body $json -ContentType 'application/json' -TimeoutSec 20 -UseBasicParsing
        }
        return @{
            StatusCode = [int]$response.StatusCode
            Body = $response.Content | ConvertFrom-Json
        }
    }
    catch {
        $webResponse = $_.Exception.Response
        if (-not $webResponse) {
            throw
        }
        if ($_.ErrorDetails.Message) {
            return @{
                StatusCode = [int]$webResponse.StatusCode
                Body = $_.ErrorDetails.Message | ConvertFrom-Json
            }
        }
        $stream = $webResponse.GetResponseStream()
        $reader = [System.IO.StreamReader]::new($stream)
        try {
            $content = $reader.ReadToEnd()
        }
        finally {
            $reader.Dispose()
        }
        return @{
            StatusCode = [int]$webResponse.StatusCode
            Body = $content | ConvertFrom-Json
        }
    }
}

function Stop-DashboardAiStack {
    $dashboardStop = Join-Path $DashboardWorkspace 'scripts\e2e_stop_bug_trend.ps1'
    $aiBaseStop = Join-Path $AiBaseWorkspace 'scripts\stop-minimal-chat-dev.ps1'

    $dashboardArgs = @('-Workspace', $DashboardWorkspace)
    if ($ForceByPort) {
        $dashboardArgs += '-ForceByPort'
    }
    Invoke-StackScript -ScriptPath $dashboardStop -Arguments $dashboardArgs -Label 'dashboard-stop'

    $aiBaseArgs = @('-Profile', 'dashboard_query_agent')
    if ($ForceByPort) {
        $aiBaseArgs += '-ForceByPort'
    }
    Invoke-StackScript -ScriptPath $aiBaseStop -Arguments $aiBaseArgs -Label 'ai-base-stop' -NoCapture
}

function Start-DashboardStack {
    $dashboardStart = Join-Path $DashboardWorkspace 'scripts\e2e_start_bug_trend.ps1'
    $dashboardArgs = @('-Workspace', $DashboardWorkspace)
    if ($ForceByPort) {
        $dashboardArgs += '-ForceByPort'
    }
    $dashboardArgs += @('-OpenEntrypoint', 'none')

    Invoke-WithTemporaryEnv -Values @{
        METRICS_AI_SIDECAR_ENABLED = 'true'
        METRICS_AI_BASE_URL = $AiBaseBackendUrl
        METRICS_AI_BASE_FRONTEND_URL = $AiBaseFrontendUrl
    } -ScriptBlock {
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

function Start-AiBaseStack {
    $aiBaseStart = Join-Path $AiBaseWorkspace 'scripts\start-minimal-chat-dev.ps1'
    $aiBaseArgs = @('-Profile', 'dashboard_query_agent', '-Headless')
    if ($FullAiChatSmoke) {
        $aiBaseArgs += '-RequireGateway'
    }
    Invoke-WithTemporaryEnv -Values @{
        RCA_DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
        DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
        LOGFIRE_IGNORE_NO_CONFIG = '1'
    } -ScriptBlock {
        Invoke-StackScript -ScriptPath $aiBaseStart -Arguments $aiBaseArgs -Label 'ai-base-start' -NoCapture
    }
}

function Restart-AiBaseStack {
    $aiBaseRestart = Join-Path $AiBaseWorkspace 'scripts\restart-minimal-chat-dev.ps1'
    $aiBaseArgs = @('-Profile', 'dashboard_query_agent')
    $aiBaseArgs += '-Headless'
    if ($FullAiChatSmoke) {
        $aiBaseArgs += '-RequireGateway'
    }
    if ($ForceByPort) {
        $aiBaseArgs += '-ForceByPort'
    }

    Invoke-WithTemporaryEnv -Values @{
        RCA_DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
        DASHBOARD_METRICS_BASE_URL = $DashboardBaseUrl
        LOGFIRE_IGNORE_NO_CONFIG = '1'
    } -ScriptBlock {
        Invoke-StackScript -ScriptPath $aiBaseRestart -Arguments $aiBaseArgs -Label 'ai-base-restart' -NoCapture
    }
}

function Get-ProcessTreeIds {
    param(
        [int[]]$RootProcessIds
    )

    $allProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $childrenByParent = @{}
    foreach ($process in $allProcesses) {
        $parentId = [int]$process.ParentProcessId
        if (-not $childrenByParent.ContainsKey($parentId)) {
            $childrenByParent[$parentId] = @()
        }
        $childrenByParent[$parentId] += [int]$process.ProcessId
    }

    $seen = @{}
    $stack = New-Object System.Collections.Stack
    foreach ($rootId in @($RootProcessIds | Where-Object { $_ -gt 0 } | Sort-Object -Unique)) {
        $stack.Push([int]$rootId)
    }
    while ($stack.Count -gt 0) {
        $currentId = [int]$stack.Pop()
        if ($seen.ContainsKey($currentId)) {
            continue
        }
        $seen[$currentId] = $true
        if ($childrenByParent.ContainsKey($currentId)) {
            foreach ($childId in $childrenByParent[$currentId]) {
                if (-not $seen.ContainsKey([int]$childId)) {
                    $stack.Push([int]$childId)
                }
            }
        }
    }
    return @($seen.Keys | Sort-Object -Descending)
}

function Stop-ProcessTrees {
    param(
        [int[]]$RootProcessIds,
        [string]$Reason
    )

    $processIds = @(Get-ProcessTreeIds -RootProcessIds $RootProcessIds)
    if (-not $processIds -or $processIds.Count -eq 0) {
        return
    }
    foreach ($processId in $processIds) {
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
        }
        catch {
        }
    }
    Write-Host "Stopped stale $Reason process tree PID(s): $($processIds -join ', ')"
}

function Get-CurrentDashboardServiceRootIds {
    $statePath = Join-Path $DashboardWorkspace 'state\e2e\port-lifecycle\metrics-bug-trend-default.json'
    if (-not (Test-Path $statePath)) {
        return @()
    }
    try {
        $state = Get-Content -Path $statePath -Raw | ConvertFrom-Json
    }
    catch {
        return @()
    }
    $ids = @()
    foreach ($serviceName in @('django', 'grafana')) {
        $service = $state.services.$serviceName
        if ($service -and $service.pid) {
            $ids += [int]$service.pid
        }
    }
    return @($ids | Where-Object { $_ -gt 0 } | Sort-Object -Unique)
}

function Stop-StaleDashboardDemoProcesses {
    $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $runningProcessIds = @{}
    foreach ($process in $processes) {
        $runningProcessIds[[int]$process.ProcessId] = $true
    }
    $protectedProcessIds = @{}
    foreach ($processId in @(Get-ProcessTreeIds -RootProcessIds (Get-CurrentDashboardServiceRootIds))) {
        $protectedProcessIds[[int]$processId] = $true
    }
    $rootPids = @(
        $processes |
            Where-Object {
                if ($protectedProcessIds.ContainsKey([int]$_.ProcessId)) {
                    return $false
                }
                $commandLine = [string]$_.CommandLine
                if ([string]::IsNullOrWhiteSpace($commandLine)) {
                    $false
                }
                else {
                    $normalized = $commandLine.ToLowerInvariant()
                    $isDashboardPath = $normalized.Contains('\scrum_dashboard\') -or $normalized.Contains('/scrum_dashboard/')
                    $isE2eGrafana = $normalized.Contains('grafana.exe') -and $normalized.Contains('grafana-e2e-')
                    $isE2eDjango = $normalized.Contains('manage.py') -and $normalized.Contains('runserver 127.0.0.1:80')
                    $isOrphanGrafanaPlugin = $_.Name.StartsWith('gpx_') -and -not $runningProcessIds.ContainsKey([int]$_.ParentProcessId)
                    ($isDashboardPath -and ($isE2eGrafana -or $isE2eDjango)) -or $isOrphanGrafanaPlugin
                }
            } |
            ForEach-Object { [int]$_.ProcessId }
    )
    Stop-ProcessTrees -RootProcessIds $rootPids -Reason 'Dashboard E2E'
}

function Stop-StaleAiBaseProfiles {
    $aiBaseStop = Join-Path $AiBaseWorkspace 'scripts\stop-minimal-chat-dev.ps1'
    if (-not (Test-Path $aiBaseStop)) {
        return
    }
    foreach ($profile in @('sample_agent')) {
        try {
            Invoke-StackScript -ScriptPath $aiBaseStop -Arguments @('-Profile', $profile, '-ForceByPort') -Label "ai-base-stop-$profile" -NoCapture
        }
        catch {
            Write-Warning "Could not stop stale AI Base profile ${profile}: $($_.Exception.Message)"
        }
    }
}

function Clear-StaleDemoProcesses {
    Stop-StaleDashboardDemoProcesses
    Stop-StaleAiBaseProfiles
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

    $python = Join-Path $DashboardWorkspace '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) {
        $python = 'python'
    }

    if (Test-JiraProfileSyncRunning -Python $python) {
        Write-Host 'Jira profile sync is already running for this scope; continuing with the existing sync state.'
        return
    }

    $logPath = New-StackLogPath -Label 'jira-profile-sync'
    $script:LastStackLogPath = $logPath
    $script:LastStackErrorLogPath = $logPath
    Write-Host "Stack script log: $logPath"
    if (Test-Path $logPath) {
        Remove-Item -Path $logPath -Force
    }
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $python `
            (Join-Path $DashboardWorkspace 'manage.py') `
            sync_provider_profile `
            --profile-id $JiraProfileId `
            --begin-ww $BeginWw `
            --end-ww $EndWw `
            --force-refresh *> $logPath
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

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

function Test-DashboardAiStack {
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
    if ($workflowPage.StatusCode -ne 200 -or -not $workflowPage.Content.Contains('/api/ai-dashboard/workflow/')) {
        throw 'Dashboard AI workflow page did not expose the expected workflow endpoint.'
    }

    Write-Host 'Smoke check: Dashboard workflow API.'
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

    Write-Host 'Smoke check: AI Base diagnostics.'
    $diagnostics = Invoke-WithStackRetry -ScriptBlock {
        Invoke-RestMethod -Uri "$AiBaseBackendUrl/api/runtime/diagnostics/summary" -TimeoutSec 20
    }
    $connector = @($diagnostics.security.connectors | Where-Object { $_.connectorId -eq 'metrics-dashboard' } | Select-Object -First 1)
    if (-not $connector) {
        throw 'AI Base diagnostics did not report the metrics-dashboard connector.'
    }
    if (-not $connector.executable) {
        throw "AI Base metrics-dashboard connector is not executable: $($connector.blockedReason)"
    }
    if (@($connector.modelVisibleOperations) -contains 'workflow.run') {
        throw 'AI Base metrics-dashboard connector exposes workflow.run as model-visible.'
    }
    if (@($connector.modelVisibleOperations) -contains 'artifact.validate') {
        throw 'AI Base metrics-dashboard connector exposes artifact.validate as model-visible.'
    }

    Write-Host 'Smoke check: Workspace context and artifact validation.'
    $contextBundle = Invoke-WithStackRetry -ScriptBlock {
        Invoke-RestMethod -Uri "$DashboardBaseUrl/api/ai-dashboard/workspace-context/?profile_id=$JiraProfileId" -TimeoutSec 20
    }
    $workspaceSync = Invoke-JsonPost -Url "$AiBaseBackendUrl/api/app-workspace-context-bundles/sync" -Body $contextBundle
    if (-not $workspaceSync.workspace.workspaceId) {
        throw 'AI Base workspace context sync did not return a workspace id.'
    }

    $artifactContent = @{
        profile_id = $JiraProfileId
        dashboard_uid = 'ip-quality-dashboard'
        chart_id = 'open_bug_trend'
        requested_series = @('new_critical_high')
        range_mode = 'ww'
        range_start = $BeginWw
        range_end = $EndWw
        output_type = 'render_config_draft'
        visualization = 'timeseries'
    }
    $artifact = Invoke-JsonPost -Url "$AiBaseBackendUrl/api/workspace-artifacts" -Body @{
        workspaceId = $workspaceSync.workspace.workspaceId
        sourceAppId = 'metrics-dashboard'
        workspaceKey = $contextBundle.workspace_key
        artifactKind = 'dashboard.chart.renderConfigDraft'
        title = 'E2E Weekly Open Bug Trend'
        correlationId = 'e2e-dashboard-ai-stack'
        content = $artifactContent
    }
    $artifactRef = "ai-base-artifact://workspace/$($artifact.artifactId)/v$($artifact.version)"
    $artifactValidation = Invoke-JsonPost -Url "$DashboardBaseUrl/api/ai-dashboard/artifacts/validate/" -Body @{
        artifact_ref = $artifactRef
        artifact_version = $artifact.version
        workspace_key = $contextBundle.workspace_key
        correlation_id = 'e2e-dashboard-ai-stack'
        artifact = $artifact.content
    }
    if ($artifactValidation.status -ne 'draft_validated') {
        throw "Dashboard artifact validation was $($artifactValidation.status)."
    }
    $publicValidationWrite = Invoke-JsonPostStatus -Url "$AiBaseBackendUrl/api/workspace-artifacts/$($artifact.artifactId)/revisions" -Body @{
        title = $artifact.title
        content = $artifact.content
        validationStatus = $artifactValidation.status
        validationResult = $artifactValidation
    }
    $publicValidationWriteDetail = [string]$publicValidationWrite.Body.detail
    if ($publicValidationWrite.StatusCode -ne 400 -or -not $publicValidationWriteDetail.Contains('owning validator')) {
        throw "AI Base public artifact revision did not reject owning-validator state write: status=$($publicValidationWrite.StatusCode)"
    }
    $forgedPublish = Invoke-JsonPost -Url "$DashboardBaseUrl/api/ai-dashboard/publish-demo/" -Body @{
        profile_id = $JiraProfileId
        dashboard_uid = 'ai-open-bug-trend-demo'
        chart_id = 'open_bug_trend'
        requested_series = @('new_critical_high')
        range_mode = 'ww'
        range_start = $BeginWw
        range_end = $EndWw
        operation = 'grafana_import'
        actor = 'e2e_dashboard_ai_stack'
        approval_id = 'approval_chat_demo_forged'
        dry_run_proof_id = 'dryrun_forged'
        artifact_ref = $artifactRef
        artifact_version = $artifact.version
        artifact_hash = $artifact.contentHash
    }
    if ($forgedPublish.status -ne 'blocked' -or $forgedPublish.reason -ne 'approval_not_granted') {
        throw "Dashboard accepted forged publish authority: status=$($forgedPublish.status) reason=$($forgedPublish.reason)"
    }

    if (-not $FullAiChatSmoke) {
        Write-Host 'Skipping deep AI chat publish smoke. Re-run with -FullAiChatSmoke to exercise model-backed chat approval and publish.'
        Write-Host 'Smoke checks passed.'
        return
    }

    $session = Invoke-JsonPost -Url "$AiBaseBackendUrl/api/chat/sessions" -Body @{
        title = 'E2E Dashboard publish demo'
        workspaceId = $workspaceSync.workspace.workspaceId
    }
    $firstTurn = Invoke-JsonPost -Url "$AiBaseBackendUrl/api/chat/sessions/$($session.sessionId)/messages" -Body @{
        content = "Approve and publish a weekly open bug trend chart for chiplet Jira from $BeginWw to $EndWw, only new critical/high."
    }
    $firstContent = [string]$firstTurn.assistantMessage.content
    if (-not $firstContent.Contains('Approval request:')) {
        throw 'AI Base chat did not produce a Dashboard publish approval request.'
    }
    $approvalLine = @($firstContent -split "`n" | Where-Object { $_.StartsWith('- Approval request:') } | Select-Object -First 1)
    if (-not $approvalLine) {
        throw 'AI Base chat approval request id line was missing.'
    }
    $approvalId = $approvalLine.Split(':', 2)[1].Trim()
    if (-not $approvalId.StartsWith('approval_dashboard_publish_')) {
        throw "AI Base chat produced unexpected approval id: $approvalId"
    }
    $approvalMatch = [regex]::Match($approvalId, '^approval_dashboard_publish_(art_[a-z0-9]+)_v([0-9]+)_(dryrun_[a-z0-9_]+)$')
    if (-not $approvalMatch.Success) {
        throw "AI Base chat approval id was not bound to artifact/version/dry-run proof: $approvalId"
    }
    $chatArtifactId = $approvalMatch.Groups[1].Value
    $chatArtifactVersion = [int]$approvalMatch.Groups[2].Value
    $dryRunProofId = $approvalMatch.Groups[3].Value
    $chatArtifact = Invoke-WithStackRetry -ScriptBlock {
        Invoke-RestMethod -Uri "$AiBaseBackendUrl/api/workspace-artifacts/$chatArtifactId/revisions/$chatArtifactVersion" -TimeoutSec 20
    }
    if ($chatArtifact.artifact.validationResult.dry_run.dryRunProofId -ne $dryRunProofId) {
        throw 'AI Base owning-validator path did not record the dry-run proof on the artifact revision.'
    }
    $approvalDecision = Invoke-JsonPost -Url "$AiBaseBackendUrl/api/chat/permission-requests/$approvalId/decision" -Body @{
        decision = 'approved'
    }
    if ($approvalDecision.status -ne 'approved') {
        throw "AI Base approval decision was $($approvalDecision.status)."
    }
    $publishTurn = Invoke-JsonPost -Url "$AiBaseBackendUrl/api/chat/sessions/$($session.sessionId)/messages" -Body @{
        content = "Publish approved $approvalId weekly open bug trend chart for chiplet Jira from $BeginWw to $EndWw, only new critical/high."
    }
    $publishContent = [string]$publishTurn.assistantMessage.content
    if (-not $publishContent.Contains('Dashboard chart published to Grafana.')) {
        throw "AI Base chat publish did not report Grafana publication. Response: $publishContent"
    }
    $publishedArtifact = Invoke-WithStackRetry -ScriptBlock {
        Invoke-RestMethod -Uri "$AiBaseBackendUrl/api/workspace-artifacts/$chatArtifactId/revisions/$chatArtifactVersion" -TimeoutSec 20
    }
    if ($publishedArtifact.artifact.validationResult.status -ne 'published') {
        throw "AI Base artifact publish result was $($publishedArtifact.artifact.validationResult.status)."
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
if (-not (Test-Path $AiBaseWorkspace)) {
    throw "AI Base workspace not found: $AiBaseWorkspace"
}

$script:StackRunStartedAtUtc = (Get-Date).ToUniversalTime().ToString('o')
$script:StackLogDirectory = Join-Path $DashboardWorkspace 'state\e2e\dashboard-ai-stack\logs'

if ($Action -eq 'stop') {
    Stop-DashboardAiStack
    Clear-StaleDemoProcesses
    Write-Host 'Dashboard + AI Base E2E stack stopped.'
    return
}

try {
    if ($Action -eq 'restart') {
        Stop-DashboardAiStack
    }
    Clear-StaleDemoProcesses

    Start-DashboardStack
    Update-DashboardRuntimeUrls
    Invoke-BootLogAudit -Phase 'dashboard-start' -RequireDashboardState

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
    Invoke-BootLogAudit -Phase 'ai-base-start' -RequireDashboardState -RequireAiBaseState
    Write-Host 'Running stack smoke checks.'
    Test-DashboardAiStack
    Write-Host 'Stack smoke checks completed.'
    Invoke-BootLogAudit -Phase 'final' -RequireDashboardState -RequireAiBaseState
    Clear-StaleDemoProcesses
    Invoke-ProcessInventoryAudit -Phase 'final'

    $workbenchUrl = Get-WorkbenchUrl
    Start-Process $workbenchUrl

    Write-Host ''
    Write-Host 'Dashboard + AI Base E2E stack is ready.'
    Write-Host "Metrics Workbench    : $workbenchUrl"
    Write-Host "Dashboard AI Workflow: $DashboardBaseUrl/ai-dashboard/workflow/"
    Write-Host "AI Base frontend     : $AiBaseFrontendUrl/"
    Write-Host "AI Base backend      : $AiBaseBackendUrl/"
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
