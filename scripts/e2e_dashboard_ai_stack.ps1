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
        [object]$Body
    )

    $json = $Body | ConvertTo-Json -Depth 10
    Invoke-RestMethod -Uri $Url -Method Post -Body $json -ContentType 'application/json' -TimeoutSec 20
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
        $response = Invoke-WebRequest -Uri $Url -Method Post -Body $json -ContentType 'application/json' -TimeoutSec 20 -UseBasicParsing -SkipHttpErrorCheck
        return @{
            StatusCode = [int]$response.StatusCode
            Body = $response.Content | ConvertFrom-Json
        }
    }

    try {
        $response = Invoke-WebRequest -Uri $Url -Method Post -Body $json -ContentType 'application/json' -TimeoutSec 20 -UseBasicParsing
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
    if (@($connector.modelVisibleOperations) -contains 'workflow.run') {
        throw 'AI Base metrics-dashboard connector exposes workflow.run as model-visible.'
    }
    if (@($connector.modelVisibleOperations) -contains 'artifact.validate') {
        throw 'AI Base metrics-dashboard connector exposes artifact.validate as model-visible.'
    }

    $contextBundle = Invoke-RestMethod -Uri "$DashboardBaseUrl/api/ai-dashboard/workspace-context/?profile_id=$JiraProfileId" -TimeoutSec 20
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
    $chatArtifact = Invoke-RestMethod -Uri "$AiBaseBackendUrl/api/workspace-artifacts/$chatArtifactId/revisions/$chatArtifactVersion" -TimeoutSec 20
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
    $publishedArtifact = Invoke-RestMethod -Uri "$AiBaseBackendUrl/api/workspace-artifacts/$chatArtifactId/revisions/$chatArtifactVersion" -TimeoutSec 20
    if ($publishedArtifact.artifact.validationResult.status -ne 'published') {
        throw "AI Base artifact publish result was $($publishedArtifact.artifact.validationResult.status)."
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
