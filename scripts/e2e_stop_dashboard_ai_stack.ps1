param(
    [string]$DashboardWorkspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$AiBaseWorkspace = 'D:\AIGC\Report_creater_agent',
    [switch]$ForceByPort
)

$arguments = @(
    '-Action', 'stop',
    '-DashboardWorkspace', $DashboardWorkspace,
    '-AiBaseWorkspace', $AiBaseWorkspace
)
if ($ForceByPort) { $arguments += '-ForceByPort' }

& (Join-Path $PSScriptRoot 'e2e_dashboard_ai_stack.ps1') @arguments
