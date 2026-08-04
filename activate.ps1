# activate.ps1 - Kich hoat Node portable cho workspace nay
$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $wsRoot ".tools\node"
if (-not (Test-Path (Join-Path $nodeDir "node.exe"))) { Write-Host "LOI: Khong tim thay Node portable" -ForegroundColor Red; return }
$global:_OldPath = $env:PATH
$env:PATH = "$nodeDir;$env:PATH"
$env:NODE_PATH = Join-Path $wsRoot "node_modules"
function global:deactivate { if ($global:_OldPath) { $env:PATH = $global:_OldPath; Remove-Variable -Name _OldPath -Scope Global -EA SilentlyContinue } }
$v = & (Join-Path $nodeDir "node.exe") --version
Write-Host "Node portable: $v" -ForegroundColor Green
