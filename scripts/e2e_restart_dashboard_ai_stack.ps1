param(
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

$arguments = @(
    '-Action', 'restart',
    '-DashboardWorkspace', $DashboardWorkspace,
    '-AiBaseWorkspace', $AiBaseWorkspace,
    '-DashboardBaseUrl', $DashboardBaseUrl,
    '-AiBaseBackendUrl', $AiBaseBackendUrl,
    '-AiBaseFrontendUrl', $AiBaseFrontendUrl,
    '-JiraProfileId', $JiraProfileId,
    '-BeginWw', $BeginWw,
    '-EndWw', $EndWw
)
if ($SkipJiraSync) { $arguments += '-SkipJiraSync' }
if ($SkipSmoke) { $arguments += '-SkipSmoke' }
if ($ForceByPort) { $arguments += '-ForceByPort' }

& (Join-Path $PSScriptRoot 'e2e_dashboard_ai_stack.ps1') @arguments
