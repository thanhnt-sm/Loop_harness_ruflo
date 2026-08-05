<#
.SYNOPSIS
  Deploy harness template vào dự án mới — resolve placeholders, git init, verify.
.DESCRIPTION
  1. Giải nén template zip vào target directory
  2. Phát hiện aide-memory global path, node.exe path
  3. Resolve placeholders trong config.json + mcp_config.json
  4. Tạo .aide/memories subdirs rỗng
  5. Git init + initial commit
  6. Chạy verify-workspace.ps1
.PARAMETER TemplatePath
  Đường dẫn template zip (từ package-template.ps1).
.PARAMETER TargetPath
  Đường dẫn dự án mới (tạo nếu chưa tồn tại).
.PARAMETER ProjectName
  Tên dự án (cho git + package.json). Mặc định: tên thư mục TargetPath.
.PARAMETER SkipGitInit
  Bỏ qua git init (nếu target đã có git repo).
.EXAMPLE
  .\tools\deploy-template.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-app
  .\tools\deploy-template.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-app -ProjectName "My App"
#>
param(
  [Parameter(Mandatory)][string]$TemplatePath,
  [Parameter(Mandatory)][string]$TargetPath,
  [string]$ProjectName,
  [switch]$SkipGitInit
)

$ErrorActionPreference = 'Continue'

Write-Host "`n=== Deploy Template ===" -ForegroundColor Cyan
Write-Host "Template: $TemplatePath" -ForegroundColor Gray
Write-Host "Target:   $TargetPath`n" -ForegroundColor Gray

# --- 1. Validate template ---
if (-not (Test-Path $TemplatePath)) {
  throw "Template not found: $TemplatePath"
}

# --- 2. Tạo target dir ---
if (-not (Test-Path $TargetPath)) {
  New-Item -ItemType Directory -Path $TargetPath -Force | Out-Null
}
$target = (Resolve-Path $TargetPath).Path
if (-not $ProjectName) { $ProjectName = (Split-Path $target -Leaf) }

# --- 3. Kiểm tra target rỗng (hoặc chỉ có .git) ---
$existing = Get-ChildItem $target -Force | Where-Object { $_.Name -ne '.git' }
if ($existing) {
  Write-Host "  [warn] Target không rỗng — files hiện có sẽ được merge`n" -ForegroundColor Yellow
}

# --- 4. Giải nén template ---
Write-Host "  [extract] Template → target..." -ForegroundColor Gray
$tempExtract = Join-Path $env:TEMP "harness-extract-$(Get-Date -Format 'yyyyMMddHHmmss')"
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null

# Dùng .NET ZipFile để extract (tránh Expand-Archive bug)
Add-Type -AssemblyName System.IO.Compression.FileSystem

# U09: Safe zip extraction — validate entry paths to prevent path traversal
$tempExtractFull = [System.IO.Path]::GetFullPath($tempExtract)
$zip = [System.IO.Compression.ZipFile]::OpenRead($TemplatePath)
foreach ($entry in $zip.Entries) {
  $targetPath = [System.IO.Path]::GetFullPath(
    [System.IO.Path]::Combine($tempExtractFull, $entry.FullName)
  )
  if (-not $targetPath.StartsWith($tempExtractFull, [System.StringComparison]::OrdinalIgnoreCase)) {
    Write-Host "  [BLOCKED] Path traversal detected in zip entry: $($entry.FullName)" -ForegroundColor Red
    $zip.Dispose()
    throw "Path traversal detected in zip entry: $($entry.FullName) — refusing to extract"
  }
}
$zip.Dispose()
Write-Host "  [security] Zip entry paths validated (no traversal)" -ForegroundColor DarkGray
[System.IO.Compression.ZipFile]::ExtractToDirectory($TemplatePath, $tempExtract)

# Copy tất cả vào target (merge, không overwrite files hiện có của user)
$items = Get-ChildItem $tempExtract -Force
foreach ($item in $items) {
  $dest = Join-Path $target $item.Name
  if ($item.PSIsContainer) {
    # Copy dir (merge) — dùng Copy-Item -Recurse cho tin cậy
    if (-not (Test-Path $dest)) {
      Copy-Item $item.FullName $dest -Recurse -Force
    } else {
      # Merge: copy từng file/dir con
      Get-ChildItem $item.FullName -Recurse -Force | ForEach-Object {
        $rel = $_.FullName.Substring($item.FullName.Length + 1)
        $d = Join-Path $dest $rel
        if ($_.PSIsContainer) {
          New-Item -ItemType Directory -Path $d -Force -ErrorAction SilentlyContinue | Out-Null
        } else {
          $dd = Split-Path $d -Parent
          if (-not (Test-Path $dd)) { New-Item -ItemType Directory -Path $dd -Force | Out-Null }
          Copy-Item $_.FullName $d -Force -ErrorAction SilentlyContinue
        }
      }
    }
  } else {
    Copy-Item $item.FullName $dest -Force -ErrorAction SilentlyContinue
  }
}
Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  [done] Extracted`n" -ForegroundColor Green

# --- 5. Phát hiện paths ---
Write-Host "  [detect] Resolving placeholders..." -ForegroundColor Gray

# 5a. Node.exe path
$nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $nodeExe) {
  # Fallback: tìm trong .tools\node
  $toolsNode = Join-Path $target '.tools\node\node.exe'
  if (Test-Path $toolsNode) { $nodeExe = $toolsNode }
  else { throw "node.exe not found. Install Node.js hoặc đặt vào .tools\node\" }
}
Write-Host "    NODE_EXE = $nodeExe" -ForegroundColor DarkGray

# 5b. Aide-memory global path
$npmRoot = (npm root -g 2>$null).Trim()
if (-not $npmRoot) {
  # Fallback: đoán từ node path
  $npmRoot = Split-Path (Split-Path $nodeExe -Parent) -Parent
  $npmRoot = Join-Path $npmRoot 'node_modules'
}
$aideMemoryGlobal = Join-Path $npmRoot 'aide-memory'
$aideMemoryCli = Join-Path $aideMemoryGlobal 'dist\memory\cli.js'

if (-not (Test-Path $aideMemoryCli)) {
  Write-Host "    [warn] aide-memory không tìm thấy tại $aideMemoryGlobal" -ForegroundColor Yellow
  Write-Host "    [hint] Cài: npm install -g aide-memory" -ForegroundColor Yellow
  Write-Host "    [hint] Sau khi cài, chạy lại script hoặc manually edit config.json + mcp_config.json" -ForegroundColor Yellow
} else {
  Write-Host "    AIDE_MEMORY_GLOBAL = $aideMemoryGlobal" -ForegroundColor DarkGray
  Write-Host "    AIDE_MEMORY_CLI = $aideMemoryCli" -ForegroundColor DarkGray
}

# 5c. Workspace root
$workspaceRoot = $target
# U09: Validate workspaceRoot for path traversal
if ($workspaceRoot -match '\.\.') {
  throw "WORKSPACE_ROOT contains path traversal characters: $workspaceRoot — refusing to deploy"
}
$workspaceRoot = [System.IO.Path]::GetFullPath($workspaceRoot)
Write-Host "    WORKSPACE_ROOT = $workspaceRoot`n" -ForegroundColor DarkGray

# --- 6. Resolve placeholders trong config.json + mcp_config.json ---
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
$configPath = Join-Path $target '.devin\config.json'
if (Test-Path $configPath) {
  $content = Get-Content $configPath -Raw
  $content = $content -replace '\{\{WORKSPACE_ROOT\}\}', ($workspaceRoot -replace '\\', '\\')
  $content = $content -replace '\{\{AIDE_MEMORY_GLOBAL\}\}', ($aideMemoryGlobal -replace '\\', '\\')
  $content = $content -replace '\{\{AIDE_MEMORY_CLI\}\}', ($aideMemoryCli -replace '\\', '\\')
  $content = $content -replace '\{\{NODE_EXE\}\}', ($nodeExe -replace '\\', '\\')
  [System.IO.File]::WriteAllText($configPath, $content, $utf8NoBom)
  # U09: Check for unresolved placeholders
  $unresolved = [regex]::Matches($content, '\{\{.*?\}\}')
  if ($unresolved.Count -gt 0) {
    Write-Host "  [WARN] Unresolved placeholders in config.json: $($unresolved.Count)" -ForegroundColor Yellow
    $unresolved | ForEach-Object { Write-Host "    $($_.Value)" -ForegroundColor Yellow }
  }
  Write-Host "  [resolved] .devin/config.json" -ForegroundColor Green
}

$mcpPath = Join-Path $target '.devin\mcp_config.json'
if (Test-Path $mcpPath) {
  $content = Get-Content $mcpPath -Raw
  $content = $content -replace '\{\{WORKSPACE_ROOT\}\}', ($workspaceRoot -replace '\\', '\\')
  $content = $content -replace '\{\{AIDE_MEMORY_CLI\}\}', ($aideMemoryCli -replace '\\', '\\')
  [System.IO.File]::WriteAllText($mcpPath, $content, $utf8NoBom)
  # U09: Check for unresolved placeholders
  $unresolvedMcp = [regex]::Matches($content, '\{\{.*?\}\}')
  if ($unresolvedMcp.Count -gt 0) {
    Write-Host "  [WARN] Unresolved placeholders in mcp_config.json: $($unresolvedMcp.Count)" -ForegroundColor Yellow
    $unresolvedMcp | ForEach-Object { Write-Host "    $($_.Value)" -ForegroundColor Yellow }
  }
  Write-Host "  [resolved] .devin/mcp_config.json" -ForegroundColor Green
}

# --- 7. Tạo .aide/memories subdirs rỗng ---
$memBase = Join-Path $target '.aide\memories'
foreach ($sub in @('area_context', 'guidelines', 'preferences', 'technical')) {
  New-Item -ItemType Directory -Path (Join-Path $memBase $sub) -Force | Out-Null
}
foreach ($sub in @('personal', 'shared')) {
  New-Item -ItemType Directory -Path (Join-Path $memBase "preferences\$sub") -Force | Out-Null
}
Write-Host "  [ensured] .aide/memories/ subdirs" -ForegroundColor Green

# --- 8. Update package.json name ---
$pkgPath = Join-Path $target 'package.json'
if (Test-Path $pkgPath) {
  $pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json
  $pkg.name = $ProjectName.ToLower() -replace '\s+', '-'
  $pkgJson = $pkg | ConvertTo-Json -Depth 5
  [System.IO.File]::WriteAllText($pkgPath, $pkgJson, $utf8NoBom)
  Write-Host "  [updated] package.json name → $($pkg.name)" -ForegroundColor Green
}

# --- 9. Git init ---
if (-not $SkipGitInit) {
  $gitDir = Join-Path $target '.git'
  if (-not (Test-Path $gitDir)) {
    Write-Host "`n  [git] Initializing git repo..." -ForegroundColor Gray
    $gitEnv = @{ GIT_TERMINAL_PROMPT = '0'; GIT_QUIET = '1' }
    git -C $target init 2>$null | Out-Null
    git -C $target -c core.autocrlf=false add -A 2>$null | Out-Null
    $commitMsg = "feat: init project with Agent Harness Deploy template`n`nDeployed from harness template. See REPOS.md for full source attributions.`n`nGenerated with [Devin](https://devin.ai)`n`nCo-Authored-By: Devin <158243242+devin-ai-integration[bot]@users.noreply.github.com>"
    git -C $target commit -m $commitMsg 2>$null | Out-Null
    Write-Host "  [git] Initial commit created`n" -ForegroundColor Green
  } else {
    Write-Host "  [git] Repo đã tồn tại, skip init`n" -ForegroundColor DarkGray
  }
}

# --- 10. Verify ---
Write-Host "  [verify] Running integrity check...`n" -ForegroundColor Gray
& (Join-Path $PSScriptRoot 'verify-workspace.ps1') -WorkspaceRoot $target

Write-Host "`n=== Deploy complete ===" -ForegroundColor Cyan
Write-Host "Project: $target" -ForegroundColor Green
Write-Host "`nBước tiếp theo:" -ForegroundColor Gray
Write-Host "  1. cd $target" -ForegroundColor White
Write-Host "  2. devin" -ForegroundColor White
Write-Host "  3. Paste nội dung tools/FULL_POWER_PROMPT.md + task của bạn" -ForegroundColor White
Write-Host "`nHoặc chạy nhanh:" -ForegroundColor Gray
Write-Host "  devin -p -- `"<paste FULL_POWER_PROMPT content> <your-task>`"" -ForegroundColor White
