<#
.SYNOPSIS
  Deploy harness template vào dự án mới — resolve placeholders, git init, verify.
.DESCRIPTION
  1. Giải nén template zip vào target directory (safe extraction, chống path traversal)
  2. Phát hiện aide-memory global path, node.exe path
  3. Resolve placeholders trong config.json + mcp_config.json
  4. Xóa TEMPLATE_MANIFEST.json (metadata đóng gói, không cần ở target)
  5. Tạo .aide/memories subdirs rỗng và docs/plans
  6. (Optional) Clean runtime nếu target đã có dữ liệu cũ
  7. Git init + initial commit
  8. Chạy verify-workspace.ps1
.PARAMETER TemplatePath
  Đường dẫn template zip (từ package-template.ps1).
.PARAMETER TargetPath
  Đường dẫn dự án mới (tạo nếu chưa tồn tại).
.PARAMETER ProjectName
  Tên dự án (cho git + package.json). Mặc định: tên thư mục TargetPath.
.PARAMETER SkipGitInit
  Bỏ qua git init (nếu target đã có git repo).
.PARAMETER CleanRuntime
  Chạy clean-runtime.ps1 sau khi extract để xóa runtime data cũ trong target.
.PARAMETER DryRun
  Không tạo target, chỉ in báo cáo các bước sẽ làm.
.EXAMPLE
  .\tools\deploy-template.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-app
  .\tools\deploy-template.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-app -ProjectName "My App" -CleanRuntime
  .\tools\deploy-template.ps1 -TemplatePath .\harness-template.zip -TargetPath D:\projects\my-app -DryRun
#>
param(
  [Parameter(Mandatory)][string]$TemplatePath,
  [Parameter(Mandatory)][string]$TargetPath,
  [string]$ProjectName,
  [switch]$SkipGitInit,
  [switch]$CleanRuntime,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

Write-Host "`n=== Deploy Template ===" -ForegroundColor Cyan
Write-Host "Template: $TemplatePath" -ForegroundColor Gray
Write-Host "Target:   $TargetPath" -ForegroundColor Gray
if ($DryRun) { Write-Host "Mode:     DRY-RUN (no files written)" -ForegroundColor Yellow } else { Write-Host "Mode:     deploy" -ForegroundColor Gray }
Write-Host ""

# --- 1. Validate template ---
if (-not (Test-Path $TemplatePath)) {
  throw "Template not found: $TemplatePath"
}
$templateItem = Get-Item $TemplatePath
if ($templateItem.Length -eq 0) { throw "Template file is empty: $TemplatePath" }

# --- 2. Resolve target path and validate ---
$target = [System.IO.Path]::GetFullPath($TargetPath)
if (-not (Test-Path $target) -and -not $DryRun) {
  New-Item -ItemType Directory -Path $target -Force | Out-Null
}
if (-not $ProjectName) { $ProjectName = (Split-Path $target -Leaf) }

# T4.13: Validate target path against shared path_zones (single source of truth).
# Đã bỏ regex `\.\.` cũ ở đây vì path_zones.py xử lý path traversal, dangerous roots, blocked zones đầy đủ hơn.
# Đối với deploy target, target thường nằm ngoài workspace nên dùng check-absolute:
# chỉ chặn blocked zones và path traversal, không bắt buộc safe zone.
$rolloutGates = Join-Path $PSScriptRoot 'RolloutGates.ps1'
if (Test-Path $rolloutGates) { . $rolloutGates }

$placeholderUtils = Join-Path $PSScriptRoot 'PlaceholderUtils.ps1'
if (Test-Path $placeholderUtils) { . $placeholderUtils }

$pathZonesScript = Join-Path $PSScriptRoot '..\.devin\scripts\path_zones.py'
if (Test-Path $pathZonesScript) {
  if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "python không có trong PATH, không thể chạy path_zones validation"
  }
  try {
    $pathZonesResult = Invoke-ExternalCommand -FilePath 'python' -ArgumentList @($pathZonesScript, 'check-absolute', $target) -WorkingDirectory $PSScriptRoot -TimeoutSeconds 30
  } catch {
    # path_zones.py trả exit code 2 khi path bị block.
    if ($_ -match 'FAILED \(exit 2\)') {
      throw "Target path blocked by path_zones: $_"
    } else {
      throw $_
    }
  }
}

# --- 3. Kiểm tra target rỗng (hoặc chỉ có .git) ---
if (Test-Path $target) {
  $existing = Get-ChildItem $target -Force -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.git' }
  if ($existing) {
    if ($DryRun) {
      Write-Host "  [dry-run] Target exists with files; would merge (or clean with -CleanRuntime)" -ForegroundColor Yellow
    } else {
      Write-Host "  [warn] Target không rỗng — files hiện có sẽ được merge`n" -ForegroundColor Yellow
    }
  }
}

# --- 4. Giải nén template ---
if ($DryRun) {
  # Liệt kê nội dung zip mà không extract
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [System.IO.Compression.ZipFile]::OpenRead($TemplatePath)
  Write-Host "  [dry-run] Zip contains $($zip.Entries.Count) entries" -ForegroundColor Gray
  $topDirs = $zip.Entries | ForEach-Object { ($_.FullName -split '/')[0] } | Select-Object -Unique
  Write-Host "  [dry-run] Top-level entries: $($topDirs -join ', ')" -ForegroundColor Gray
  $zip.Dispose()

  Write-Host "  [dry-run] Would resolve placeholders:" -ForegroundColor Gray
  Write-Host "    WORKSPACE_ROOT       = $target" -ForegroundColor DarkGray
  $npmRoot = (npm root -g 2>$null)
  if ($npmRoot) { $npmRoot = $npmRoot.Trim() }
  $node = (Get-Command node -ErrorAction SilentlyContinue).Source
  Write-Host "    AIDE_MEMORY_GLOBAL   = $(if ($npmRoot) { Join-Path $npmRoot 'aide-memory' } else { '(unknown)' })" -ForegroundColor DarkGray
  Write-Host "    AIDE_MEMORY_CLI      = $(if ($npmRoot) { Join-Path $npmRoot 'aide-memory\dist\memory\cli.js' } else { '(unknown)' })" -ForegroundColor DarkGray
  Write-Host "    NODE_EXE             = $(if ($node) { $node } else { '(unknown)' })" -ForegroundColor DarkGray

  Write-Host "`n[DryRun] Deploy would complete at: $target" -ForegroundColor Yellow
  return
}

$tempExtract = Join-Path $env:TEMP "harness-extract-$(Get-Date -Format 'yyyyMMddHHmmss')"
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem
$tempExtractFull = [System.IO.Path]::GetFullPath($tempExtract)
$zip = [System.IO.Compression.ZipFile]::OpenRead($TemplatePath)
foreach ($entry in $zip.Entries) {
  $targetEntryPath = [System.IO.Path]::GetFullPath(
    [System.IO.Path]::Combine($tempExtractFull, $entry.FullName)
  )
  if (-not $targetEntryPath.StartsWith($tempExtractFull, [System.StringComparison]::OrdinalIgnoreCase)) {
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
    if (-not (Test-Path $dest)) {
      Copy-Item $item.FullName $dest -Recurse -Force
    } else {
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
Write-Host "  [done] Extracted to target`n" -ForegroundColor Green

# --- 5. Xóa TEMPLATE_MANIFEST.json khỏi target ---
$manifestPath = Join-Path $target 'TEMPLATE_MANIFEST.json'
if (Test-Path $manifestPath) {
  Remove-Item $manifestPath -Force
  Write-Host "  [removed] TEMPLATE_MANIFEST.json (packaging metadata)" -ForegroundColor Green
}

# --- 6. Clean runtime nếu được yêu cầu ---
if ($CleanRuntime) {
  $cleanScript = Join-Path $PSScriptRoot 'clean-runtime.ps1'
  if (Test-Path $cleanScript) {
    Write-Host "  [clean] Running clean-runtime.ps1..." -ForegroundColor Cyan
    & $cleanScript -WorkspaceRoot $target
  } else {
    Write-Host "  [warn] clean-runtime.ps1 not found — skipping" -ForegroundColor Yellow
  }
}

# --- 7. Phát hiện paths ---
Write-Host "  [detect] Resolving placeholders..." -ForegroundColor Gray

# 7a. Node.exe path
$nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $nodeExe) {
  $toolsNode = Join-Path $target '.tools\node\node.exe'
  if (Test-Path $toolsNode) { $nodeExe = $toolsNode }
  else { throw "node.exe not found. Install Node.js hoặc đặt vào .tools\node\" }
}
Write-Host "    NODE_EXE = $nodeExe" -ForegroundColor DarkGray

# 7b. Aide-memory global path
$npmRoot = (npm root -g 2>$null)
if ($npmRoot) { $npmRoot = $npmRoot.Trim() }
if (-not $npmRoot) {
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

# 7c. Workspace root
$workspaceRoot = $target
Write-Host "    WORKSPACE_ROOT = $workspaceRoot`n" -ForegroundColor DarkGray

# --- 8. Resolve placeholders trong config.json + mcp_config.json ---
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

function Resolve-ConfigPlaceholders($path, $replacements) {
  if (-not (Test-Path $path)) { return }

  $json = Get-Content $path -Raw | ConvertFrom-Json
  $json = Replace-StringsRecursively $json $replacements

  # Check unresolved placeholders
  $strings = @()
  Find-Strings $json ([ref]$strings)
  $unresolved = $strings | Where-Object { $_ -match '\{\{.*?\}\}' }
  if ($unresolved) {
    Write-Host "  [WARN] Unresolved placeholders in $([System.IO.Path]::GetFileName($path)): $($unresolved.Count)" -ForegroundColor Yellow
    $unresolved | ForEach-Object { Write-Host "    $_" -ForegroundColor Yellow }
  }

  # Quote paths with spaces in HLK hook launcher command
  if (([System.IO.Path]::GetFileName($path)) -eq 'config.json') {
    Set-BashCommandSlashes $json
    foreach ($entry in $json.hooks.PreToolUse) {
      foreach ($hook in $entry.hooks) {
        if ($hook.command -and $hook.command -match 'hlk-hook-launcher\.mjs') {
          if ($hook.command -match '^(.+?)\s+([A-Za-z]:\\.+hlk-hook-launcher\.mjs)$') {
            $node = $matches[1].Trim()
            $script = $matches[2].Trim()
            if ($node -match '^[A-Za-z]:\\') { $node = '"' + $node + '"' }
            if ($script -match '^[A-Za-z]:\\') { $script = '"' + $script + '"' }
            $hook.command = "$node $script"
          }
        }
      }
    }
  }

  $content = $json | ConvertTo-Json -Depth 100
  [System.IO.File]::WriteAllText($path, $content, $utf8NoBom)

  Write-Host "  [resolved] $([System.IO.Path]::GetFileName($path))" -ForegroundColor Green
}

$allReplacements = [ordered]@{
  '{{WORKSPACE_ROOT}}'       = $workspaceRoot
  '{{AIDE_MEMORY_GLOBAL}}'   = $aideMemoryGlobal
  '{{AIDE_MEMORY_CLI}}'      = $aideMemoryCli
  '{{NODE_EXE}}'             = $nodeExe
  '${USER_HOME}'             = $env:USERPROFILE
}

Resolve-ConfigPlaceholders (Join-Path $target '.devin\config.json') $allReplacements
Resolve-ConfigPlaceholders (Join-Path $target '.devin\mcp_config.json') $allReplacements

# --- 9. Ensure .aide/memories + docs/plans subdirs ---
$memBase = Join-Path $target '.aide\memories'
foreach ($sub in @('area_context', 'guidelines', 'preferences', 'technical')) {
  New-Item -ItemType Directory -Path (Join-Path $memBase $sub) -Force | Out-Null
}
foreach ($sub in @('personal', 'shared')) {
  New-Item -ItemType Directory -Path (Join-Path $memBase "preferences\$sub") -Force | Out-Null
}
Write-Host "  [ensured] .aide/memories/ subdirs" -ForegroundColor Green

$docsPlans = Join-Path $target 'docs\plans'
New-Item -ItemType Directory -Path $docsPlans -Force | Out-Null
Write-Host "  [ensured] docs/plans/" -ForegroundColor Green

# --- 10. Update package.json name ---
$pkgPath = Join-Path $target 'package.json'
if (Test-Path $pkgPath) {
  $pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json
  $pkg.name = $ProjectName.ToLower() -replace '\s+', '-'
  $pkgJson = $pkg | ConvertTo-Json -Depth 5
  [System.IO.File]::WriteAllText($pkgPath, $pkgJson, $utf8NoBom)
  Write-Host "  [updated] package.json name → $($pkg.name)" -ForegroundColor Green
}

# --- 11. Git init ---
if (-not $SkipGitInit) {
  $gitDir = Join-Path $target '.git'
  if (-not (Test-Path $gitDir)) {
    Write-Host "`n  [git] Initializing git repo..." -ForegroundColor Gray
    git -C $target init 2>$null | Out-Null
    git -C $target -c core.autocrlf=false add -A 2>$null | Out-Null
    $commitMsg = "feat: init project with Agent Harness Deploy template`n`nDeployed from harness template. See REPOS.md for full source attributions.`n`nGenerated with [Devin](https://devin.ai)`n`nCo-Authored-By: Devin"
    git -C $target commit -m $commitMsg 2>$null | Out-Null
    Write-Host "  [git] Initial commit created`n" -ForegroundColor Green
  } else {
    Write-Host "  [git] Repo đã tồn tại, skip init`n" -ForegroundColor DarkGray
  }
}

# --- 12. Verify ---
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
