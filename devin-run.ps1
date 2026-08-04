# devin-run.ps1 — Chạy Devin CLI với Node 22 portable + ruflo MCP
# Model mac dinh: glm-5-2 (FREE, khong ton quota Pro)
# Dung: .\devin-run.ps1              -> glm-5-2 (FREE)
#       .\devin-run.ps1 -Model swe-1-7  -> SWE-1.7 (FREE beta, tot cho coding)
#       .\devin-run.ps1 -Model claude-sonnet-5  -> Claude Sonnet 5 (Pro quota)
#       .\devin-run.ps1 -Model opus    -> Claude Opus 5 (Pro quota)

param(
    [string]$Model = "glm-5-2"
)

$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $wsRoot '.tools\node'
if (Test-Path $nodeDir) { $env:PATH = "$nodeDir;$env:PATH" }
$env:NODE_PATH = Join-Path $wsRoot 'node_modules'
$env:DEVIN_MODEL = $Model

$label = switch ($Model) {
    "glm-5-2"         { "GLM-5.2 High (FREE, 200K ctx)" }
    "swe-1-7"         { "SWE-1.7 Max (FREE beta, 262K ctx, coding-tuned)" }
    "swe-1-7-medium"  { "SWE-1.7 Medium (FREE beta, 262K ctx)" }
    "swe-1-6"         { "SWE-1.6 (FREE, 200K ctx)" }
    "claude-sonnet-5" { "Claude Sonnet 5 (Pro quota)" }
    "claude-opus-5"   { "Claude Opus 5 (Pro quota)" }
    "gpt-5-6-luna-medium" { "GPT-5.6 Luna Medium (Pro quota)" }
    default           { $Model }
}

Write-Host "Devin CLI + Ruflo Autopilot" -ForegroundColor Cyan
Write-Host "Node: $(node --version)" -ForegroundColor DarkGray
Write-Host "Model: $label" -ForegroundColor Green
Write-Host ""
devin @args
