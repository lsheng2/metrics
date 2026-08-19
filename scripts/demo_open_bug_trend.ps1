param(
    [int]$Port = 8002
)

$url = 'http://127.0.0.1:' + $Port + '/bug-trend/?begin=2025-04-07&end=2026-08-09'
Start-Process $url