param(
    [int]$Port = 8002
)

$pidFile = Join-Path $env:TEMP 'metrics-django-demo-8002.pid'
$processIds = @()

if (Test-Path $pidFile) {
    $processIds += Get-Content $pidFile -ErrorAction SilentlyContinue
}

$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @('127.0.0.1', '0.0.0.0', '::1', '::') }

$processIds += $connections | Select-Object -ExpandProperty OwningProcess -Unique
$processIds = $processIds | Where-Object { $_ } | Select-Object -Unique

if ($processIds) {
    $processIds | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
    Write-Host ('Stopped Django backend on 127.0.0.1:{0}' -f $Port)
} else {
    Write-Host ('No Django backend listening on 127.0.0.1:{0}' -f $Port)
}