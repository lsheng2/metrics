param(
    [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [int]$Port = 8002
)

$ErrorActionPreference = 'Stop'

$python = Join-Path $Workspace '.venv\Scripts\python.exe'
$pidFile = Join-Path $env:TEMP 'metrics-django-local-8002.pid'
$outLog = Join-Path $env:TEMP 'metrics-django-local-8002.out.log'
$errLog = Join-Path $env:TEMP 'metrics-django-local-8002.err.log'
$url = 'http://127.0.0.1:' + $Port + '/bug-trend/?begin=2025-04-07&end=2026-08-09'

if (-not (Test-Path $python)) {
    throw "Python executable not found: $python"
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::1', '::') } |
    Select-Object -First 1

if ($listener) {
    Write-Host ('Django backend already listening on http://127.0.0.1:{0}/' -f $Port)
    $listener.OwningProcess | Set-Content -Path $pidFile
    exit 0
}

Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue

$process = Start-Process `
    -FilePath $python `
    -ArgumentList @('manage.py', 'runserver', ('127.0.0.1:' + $Port), '--noreload') `
    -WorkingDirectory $Workspace `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru `
    -WindowStyle Hidden

$process.Id | Set-Content -Path $pidFile

for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Milliseconds 500
    $status = & curl.exe --noproxy 127.0.0.1 -s -o NUL -w '%{http_code}' $url
    if ($status -eq '200') {
        Write-Host ('Django backend started on http://127.0.0.1:{0}/' -f $Port)
        exit 0
    }
    $process.Refresh()
    if ($process.HasExited) {
        Write-Error "Django backend exited early. See $errLog"
        exit 1
    }
}

Write-Error "Django backend did not become ready. See $errLog"
exit 1