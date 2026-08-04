# devin-swe.ps1 — Shortcut chay Devin CLI voi SWE-1.7 (FREE beta, tot cho coding)
# Dung: .\devin-swe.ps1
#       .\devin-swe.ps1 -p -- "mieu ta cong viec"

$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $wsRoot '.tools\node'
if (Test-Path $nodeDir) { $env:PATH = "$nodeDir;$env:PATH" }
$env:NODE_PATH = Join-Path $wsRoot 'node_modules'
$env:DEVIN_MODEL = "swe-1-7"

Write-Host "Devin CLI + Ruflo Autopilot" -ForegroundColor Cyan
Write-Host "Node: $(node --version)" -ForegroundColor DarkGray
Write-Host "Model: SWE-1.7 Max (FREE beta, 262K ctx, coding-tuned)" -ForegroundColor Green
Write-Host ""
devin @args
