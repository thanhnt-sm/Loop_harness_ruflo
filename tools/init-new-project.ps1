<#
.SYNOPSIS
  One-shot orchestrator: package template → deploy to new project → git init → verify → print first prompt.
.DESCRIPTION
  Script tiện lợi nhất — chạy 1 lệnh, có ngay dự án mới với full harness:
  1. Package workspace hiện tại thành template (nếu chưa có)
  2. Deploy template vào target dir (resolve paths)
  3. Git init + initial commit
  4. Verify integrity
  5. Print hướng dẫn + FULL_POWER_PROMPT

  Nếu template zip đã tồn tại (mặc định ./harness-template.zip), skip packaging.
.PARAMETER TargetPath
  Đường dẫn dự án mới (bắt buộc).
.PARAMETER ProjectName
  Tên dự án. Mặc định: tên thư mục TargetPath.
.PARAMETER TemplatePath
  Đường dẫn template zip. Mặc định: ./harness-template.zip.
.PARAMETER ForceRepackage
  Ép re-package template ngay cả khi đã tồn tại.
.EXAMPLE
  .\tools\init-new-project.ps1 -TargetPath D:\projects\my-new-app
  .\tools\init-new-project.ps1 -TargetPath D:\projects\my-new-app -ProjectName "My App" -ForceRepackage
#>
param(
  [Parameter(Mandatory)][string]$TargetPath,
  [string]$ProjectName,
  [string]$TemplatePath = (Join-Path (Get-Location).Path 'harness-template.zip'),
  [switch]$ForceRepackage
)

$ErrorActionPreference = 'Stop'

Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║   INIT NEW PROJECT — Full Harness Deploy                     ║
║   Package → Deploy → Git Init → Verify → Ready               ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# --- 1. Package (nếu cần) ---
$needPackage = $ForceRepackage -or (-not (Test-Path $TemplatePath))
if ($needPackage) {
  Write-Host "[1/4] Packaging template..." -ForegroundColor Yellow
  & (Join-Path $PSScriptRoot 'package-template.ps1') -OutputPath $TemplatePath -WorkspaceRoot (Get-Location).Path
} else {
  Write-Host "[1/4] Template đã tồn tại: $TemplatePath (skip package)" -ForegroundColor Green
  Write-Host "      Dùng -ForceRepackage để re-package`n" -ForegroundColor DarkGray
}

# --- 2. Deploy ---
Write-Host "`n[2/4] Deploying template..." -ForegroundColor Yellow
$deployArgs = @{
  TemplatePath = $TemplatePath
  TargetPath = $TargetPath
}
if ($ProjectName) { $deployArgs.ProjectName = $ProjectName }
& (Join-Path $PSScriptRoot 'deploy-template.ps1') @deployArgs

# --- 3. Verify (deploy script đã chạy verify, nhưng chạy lại cho chắc) ---
Write-Host "`n[3/4] Final verification..." -ForegroundColor Yellow
& (Join-Path $PSScriptRoot 'verify-workspace.ps1') -WorkspaceRoot $TargetPath

# --- 4. Print ready ---
$target = (Resolve-Path $TargetPath).Path
Write-Host @"

╔══════════════════════════════════════════════════════════════╗
║   [PASS] PROJECT READY                                       ║
╚══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

Write-Host "Project: $target" -ForegroundColor Green
Write-Host ""
Write-Host "Cách dùng:" -ForegroundColor White
Write-Host "  1. cd `"$target`"" -ForegroundColor Gray
Write-Host "  2. devin" -ForegroundColor Gray
Write-Host "  3. Paste nội dung tools/FULL_POWER_PROMPT.md + task của bạn" -ForegroundColor Gray
Write-Host ""
Write-Host "Hoặc one-liner:" -ForegroundColor White
$promptPath = Join-Path $target 'tools\FULL_POWER_PROMPT.md'
Write-Host "  # Đọc prompt:" -ForegroundColor DarkGray
Write-Host "  Get-Content '$promptPath'" -ForegroundColor Gray
Write-Host ""
Write-Host "Harness bao gồm:" -ForegroundColor White
Write-Host "  • 10 canon protocols (BOOT, MEMORY, LOOP, VERIFICATION, v.v.)" -ForegroundColor DarkGray
Write-Host "  • COMMANDER + 7 personas + 5 workers + 2 executors" -ForegroundColor DarkGray
Write-Host "  • 21+ skills (AHD + Devin-native + Nuwa + Chroma + domain-adapters)" -ForegroundColor DarkGray
Write-Host "  • 4 Python hooks (pre/post tool, stop, session)" -ForegroundColor DarkGray
Write-Host "  • 7 runtime scripts (worktree, plan_dispatch, session_manager, v.v.)" -ForegroundColor DarkGray
Write-Host "  • 5 vault templates (anti-link-rot)" -ForegroundColor DarkGray
Write-Host "  • HLK security layer (sanitizer + vault-bridge)" -ForegroundColor DarkGray
Write-Host "  • MCP: aide-memory + spark-memory + deepwiki + devin" -ForegroundColor DarkGray
Write-Host "  • /lightning (SWE-1.7) + /glm (GLM-5.2 free) orchestrators" -ForegroundColor DarkGray
Write-Host ""
