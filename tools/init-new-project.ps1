<#
.SYNOPSIS
  Deploy toàn bộ loop-harness (AHD + HLK) sang một dự án mới trong một lệnh duy nhất.
.DESCRIPTION
  Script này kết hợp 4 bước:
    1. (Tùy chọn) Package source workspace thành template zip tạm.
    2. Deploy template sang thư mục target (resolve placeholders, tạo memory, git init, verify).
    3. Cài HLK layer cho CLI đã chọn từ source, không làm thay đổi source.
    4. Kiểm tra toàn vẹn HLK và AHD workspace.
  Không làm thay đổi workspace gốc. Mọi thao tác ghi chỉ diễn ra trong target.
.PARAMETER TemplatePath
  Đường dẫn template zip. Nếu không có, script tự package source ra zip tạm trong $env:TEMP.
.PARAMETER TargetPath
  Thư mục đích cho dự án mới (bắt buộc).
.PARAMETER ProjectName
  Tên dự án (dùng cho package.json). Mặc định: tên thư mục target.
.PARAMETER Cli
  CLI cần cấu hình HLK: claude | devin | agy | all. Mặc định: devin.
.PARAMETER DryRun
  Chỉ in kế hoạch, không thực hiện.
.PARAMETER SkipHlk
  Bỏ qua bước cài HLK.
.PARAMETER NoVerify
  Bỏ qua bước verify HLK và AHD.
.PARAMETER SkipGitInit
  Truyền sang deploy-template.ps1: không tạo git repo ở target.
.PARAMETER RolloutStage
  T5.10: Cổng rollout P1 Canary / P2 Pilot / P3 GA. Mặc định Skip (không chặn).
  - P1: pytest 100% + bench >=25% + red-team 0 critical.
  - P2: E2E pass + user approval (interactive).
  - P3: CI green 7 ngay + 0 P0/P1 bug (manual sign-off).
  Gate chạy trên SOURCE workspace trước khi deploy sang target.
.EXAMPLE
  .\tools\init-new-project.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-app -Cli devin
  .\tools\init-new-project.ps1 -TargetPath D:\projects\my-app -Cli all
  .\tools\init-new-project.ps1 -TargetPath D:\projects\my-app -RolloutStage P1
#>
param(
  [string]$TemplatePath,
  [Parameter(Mandatory)][string]$TargetPath,
  [string]$ProjectName,
  [ValidateSet('claude','devin','agy','all')][string]$Cli = 'devin',
  [switch]$DryRun,
  [switch]$SkipHlk,
  [switch]$NoVerify,
  [switch]$SkipGitInit,
  [ValidateSet('P1','P2','P3','Skip')][string]$RolloutStage = 'Skip'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ---------------------------------------------------------------------------
# Bước 0: Xác định source workspace và in thông tin
# ---------------------------------------------------------------------------
$toolsDir = $PSScriptRoot
$sourceRoot = (Resolve-Path (Join-Path $toolsDir '..')).Path

Write-Host "`n=== Init New Loop-Harness Project ===" -ForegroundColor Cyan
Write-Host "Source workspace: $sourceRoot" -ForegroundColor Gray
Write-Host "Target path:      $TargetPath" -ForegroundColor Gray
Write-Host "CLI:              $Cli" -ForegroundColor Gray
if ($DryRun) { Write-Host "Mode:             DRY-RUN" -ForegroundColor Yellow }
if ($RolloutStage -ne 'Skip') { Write-Host "Rollout:          $RolloutStage (Canary=P1, Pilot=P2, GA=P3)" -ForegroundColor Magenta }

# ---------------------------------------------------------------------------
# T5.10: Rollout gate — chạy trên SOURCE workspace trước khi deploy.
# P1 (Canary): P0 100% + bench >=25% + 0 critical exploit.
# P2 (Pilot) : E2E pass + user approval (interactive).
# P3 (GA)    : CI green 7 ngay + 0 P0/P1 bug (manual sign-off).
# Sử dụng RolloutGates.ps1 để tránh duplicate logic giữa package-template và init-new-project.
# ---------------------------------------------------------------------------
$rolloutGates = Join-Path $toolsDir 'RolloutGates.ps1'
if (-not (Test-Path $rolloutGates)) {
  throw "Không tìm thấy $rolloutGates"
}
. $rolloutGates

if ($RolloutStage -ne 'Skip') {
  $null = Invoke-RolloutGate -Stage $RolloutStage -SourceRoot $sourceRoot
}

# ---------------------------------------------------------------------------
# Bước 1: Validate các file/thư mục cần thiết trong source
# ---------------------------------------------------------------------------
$requiredFiles = @(
  (Join-Path $sourceRoot 'tools/package-template.ps1'),
  (Join-Path $sourceRoot 'tools/deploy-template.ps1'),
  (Join-Path $sourceRoot 'tools/RolloutGates.ps1'),
  (Join-Path $sourceRoot 'tools/verify-workspace.ps1'),
  (Join-Path $sourceRoot 'HLK/bin/hlk-install.mjs')
)

foreach ($file in $requiredFiles) {
  if (-not (Test-Path $file)) { throw "Thiếu file cần thiết trong source workspace: $file" }
}

# ---------------------------------------------------------------------------
# Bước 2: Resolve đường dẫn tuyệt đối và bảo vệ source khỏi ghi đè
# ---------------------------------------------------------------------------
$target = [System.IO.Path]::GetFullPath($TargetPath)
$source = [System.IO.Path]::GetFullPath($sourceRoot)

if ($target -eq $source) { throw "Target không được trùng với source workspace" }
if ($target.StartsWith($source + [System.IO.Path]::DirectorySeparatorChar)) { throw "Target không được nằm bên trong source workspace" }
if ($source.StartsWith($target + [System.IO.Path]::DirectorySeparatorChar)) { throw "Source workspace không được nằm bên trong target" }

# ---------------------------------------------------------------------------
# Bước 3: Chuẩn bị target directory và project name
# ---------------------------------------------------------------------------
if (-not $ProjectName) { $ProjectName = (Split-Path $target -Leaf) }

if (-not $DryRun) {
  if (-not (Test-Path $target)) {
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    Write-Host "  [created] target directory" -ForegroundColor DarkGray
  } else {
    Write-Host "  [info] target directory already exists" -ForegroundColor DarkGray
  }
}

# ---------------------------------------------------------------------------
# Bước 4: Chuẩn bị template zip
# ---------------------------------------------------------------------------
$tempZip = $null
$usedTemplate = $null

if ($TemplatePath) {
  $usedTemplate = [System.IO.Path]::GetFullPath($TemplatePath)
  if (-not (Test-Path $usedTemplate)) { throw "Không tìm thấy template: $usedTemplate" }
} else {
  if ($DryRun) {
    $usedTemplate = '<auto-generated-temp-zip>'
  } else {
    $tempZip = Join-Path $env:TEMP ("harness-template-" + [Guid]::NewGuid().ToString() + ".zip")
    $packageScript = Join-Path $sourceRoot 'tools/package-template.ps1'
    Write-Host "`n[1/5] Packaging source to temp template zip..." -ForegroundColor Cyan
    & $packageScript -OutputPath $tempZip
    if ($LASTEXITCODE -ne 0) { throw "package-template.ps1 failed with exit code $LASTEXITCODE" }
    $usedTemplate = $tempZip
    Write-Host "  [ok] Template: $usedTemplate" -ForegroundColor Green
  }
}

# ---------------------------------------------------------------------------
# Bước 5: Tìm node.exe trong PATH hoặc source .tools
# ---------------------------------------------------------------------------
$nodeExe = $null
$nodeCmd = Get-Command 'node' -ErrorAction SilentlyContinue
if ($nodeCmd) {
  $nodeExe = $nodeCmd.Source
} elseif (Test-Path (Join-Path $sourceRoot '.tools/node/node.exe')) {
  $nodeExe = Join-Path $sourceRoot '.tools/node/node.exe'
} else {
  throw "Không tìm thấy node.exe trong PATH hoặc $sourceRoot\.tools\node\node.exe"
}

# ---------------------------------------------------------------------------
# Bước 6: Dry-run summary
# ---------------------------------------------------------------------------
if ($DryRun) {
  Write-Host "`n=== Dry-run plan ===" -ForegroundColor Cyan
  if ($TemplatePath) {
    Write-Host "1. Use provided template: $usedTemplate" -ForegroundColor Gray
  } else {
    Write-Host "1. Package source to temp zip in `$env:TEMP" -ForegroundColor Gray
  }
  Write-Host "2. Deploy AHD: deploy-template.ps1 -TemplatePath '$usedTemplate' -TargetPath '$target' -ProjectName '$ProjectName'" -ForegroundColor Gray
  if (-not $SkipHlk) {
    Write-Host "3. HLK install (cwd=$target): node '$sourceRoot\HLK\bin\hlk-install.mjs' (HLK_CLI=$Cli)" -ForegroundColor Gray
    Write-Host "4. HLK verify (cwd=$target): node HLK\wrappers\hlk-verify-integrity.js" -ForegroundColor Gray
  }
  if (-not $NoVerify) {
    Write-Host "5. AHD verify: verify-workspace.ps1 -WorkspaceRoot '$target'" -ForegroundColor Gray
  }
  Write-Host "`nDry-run complete. No files were written." -ForegroundColor Yellow
  return
}

# ---------------------------------------------------------------------------
# Bước 7: Deploy AHD template
# ---------------------------------------------------------------------------
$deployScript = Join-Path $sourceRoot 'tools/deploy-template.ps1'
Write-Host "`n[1/5] Deploying AHD template to target..." -ForegroundColor Cyan
& $deployScript -TemplatePath $usedTemplate -TargetPath $target -ProjectName $ProjectName -CleanRuntime -SkipGitInit:$SkipGitInit
if ($LASTEXITCODE -ne 0) { throw "deploy-template.ps1 failed with exit code $LASTEXITCODE" }
Write-Host "  [ok] AHD deployed" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Bước 8: Install HLK layer
# ---------------------------------------------------------------------------
if (-not $SkipHlk) {
  $hlkInstallMjs = Join-Path $sourceRoot 'HLK/bin/hlk-install.mjs'
  Write-Host "`n[2/5] Installing HLK layer for CLI: $Cli..." -ForegroundColor Cyan

  # Dùng $env:HLK_CLI để tránh prompt; chạy với working directory = target
  $env:HLK_CLI = $Cli
  Invoke-ExternalCommand -FilePath $nodeExe -ArgumentList @($hlkInstallMjs) -WorkingDirectory $target -TimeoutSeconds 300
  Write-Host "  [ok] HLK installed" -ForegroundColor Green

  # ---------------------------------------------------------------------------
  # Bước 9: HLK integrity verify
  # ---------------------------------------------------------------------------
  if (-not $NoVerify) {
    $hlkVerify = 'HLK/wrappers/hlk-verify-integrity.js'
    Write-Host "`n[3/5] Verifying HLK layer..." -ForegroundColor Cyan
    Invoke-ExternalCommand -FilePath $nodeExe -ArgumentList @($hlkVerify) -WorkingDirectory $target -TimeoutSeconds 180
    Write-Host "  [ok] HLK verify passed" -ForegroundColor Green
  }
}

# ---------------------------------------------------------------------------
# Bước 10: AHD workspace verify
# ---------------------------------------------------------------------------
if (-not $NoVerify) {
  $verifyScript = Join-Path $sourceRoot 'tools/verify-workspace.ps1'
  Write-Host "`n[4/5] Verifying AHD workspace..." -ForegroundColor Cyan
  & $verifyScript -WorkspaceRoot $target
  if ($LASTEXITCODE -ne 0) { throw "verify-workspace.ps1 failed with exit code $LASTEXITCODE" }
  Write-Host "  [ok] AHD verify passed" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Bước 11: Kiểm tra source workspace không bị thay đổi
# ---------------------------------------------------------------------------
Write-Host "`n[5/5] Checking source workspace integrity..." -ForegroundColor Cyan
$status = & git -C $sourceRoot status --short
if ($status) {
  Write-Host "  [WARN] Source workspace has uncommitted changes after init:" -ForegroundColor Yellow
  $status | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
  Write-Host "  Script did NOT write to source; existing changes were already there." -ForegroundColor Yellow
} else {
  Write-Host "  [ok] Source workspace unchanged" -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Bước 12: Cleanup temp zip nếu script tự sinh
# ---------------------------------------------------------------------------
if ($tempZip -and (Test-Path $tempZip)) {
  Remove-Item $tempZip -Force
  Write-Host "  [cleaned] temp template zip" -ForegroundColor DarkGray
}

Write-Host "`n=== Init complete ===" -ForegroundColor Cyan
Write-Host "Project ready at: $target" -ForegroundColor Green
Write-Host "Next: open the target workspace in Devin CLI" -ForegroundColor Gray
