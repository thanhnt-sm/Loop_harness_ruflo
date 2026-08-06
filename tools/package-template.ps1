<#
.SYNOPSIS
  Đóng gói workspace hiện tại thành template zip — sạch, sẵn sàng deploy sang dự án mới.
.DESCRIPTION
  1. Tạo staging dir, copy chỉ các thư mục/file reusable.
  2. KHÔNG sửa source workspace — mọi dọn dẹp xảy ra trên staging.
  3. Loại bỏ runtime data, pycache, secrets, workflow cũ, v.v.
  4. Resolve placeholders trong .devin/config.json và .devin/mcp_config.json tự động.
  5. Nén thành zip.
.PARAMETER OutputPath
  Đường dẫn output zip. Mặc định: ./harness-template.zip
.PARAMETER WorkspaceRoot
  Workspace cần đóng gói. Mặc định: thư mục hiện tại.
.PARAMETER DryRun
  Không tạo zip, chỉ in báo cáo những gì sẽ làm.
.EXAMPLE
  .\tools\package-template.ps1
  .\tools\package-template.ps1 -OutputPath D:\templates\my-harness.zip
  .\tools\package-template.ps1 -DryRun
#>
param(
  [string]$OutputPath = (Join-Path (Get-Location).Path 'harness-template.zip'),
  [string]$WorkspaceRoot = (Get-Location).Path,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $WorkspaceRoot).Path
$timestamp = Get-Date -Format 'yyyyMMddHHmmss'
$staging = Join-Path $env:TEMP "harness-staging-$timestamp"

Write-Host "`n=== Package Template ===" -ForegroundColor Cyan
Write-Host "Source:      $root" -ForegroundColor Gray
Write-Host "Staging:     $staging" -ForegroundColor Gray
Write-Host "Output:      $OutputPath" -ForegroundColor Gray
if ($DryRun) { Write-Host "Mode:        DRY-RUN (no zip created)" -ForegroundColor Yellow } else { Write-Host "Mode:        package" -ForegroundColor Gray }
Write-Host ""

# --- 1. Thư mục/file cần copy ---
$includeDirs = @('.devin', '.agents', '.aide', 'HLK', 'tools')
$includeFiles = @('AGENTS.md', 'CLAUDE.md', 'REPOS.md', '.gitignore', 'package.json')

# --- 2. Danh sách loại bỏ (glob-style) ---
# Applied to relative path (backslash). Match if any segment equals excluded.
$excludePatterns = @(
  '*.git\*',
  '*.tools\*',
  '*node_modules\*',
  '*__pycache__*',
  '*.pyc',
  '*.pyo',
  '*.pytest_cache*',
  '*.mypy_cache*',
  '*.ruff_cache*',
  '*.coverage',
  '*htmlcov*',
  '*.log',
  '*.tmp',
  '*.bak',
  '*.orig',
  '*.DS_Store*',
  '*Thumbs.db*',
  '*HLK\logs\*',
  '*HLK\reports\*',
  '*HLK\dist\*',
  '*HLK\config\secrets.env*',
  '*HLK\config\*.local.json*',
  '*.aide\config*.json*',
  '*.aide\*.md*',
  '*.aide\memories\*',
  '*.aide\cache\*',
  '*.aide\recall-log.jsonl*',
  '*.devin\config.*.json*',
  '*.devin\session_state\*',
  '*.devin\loop_state\*',
  '*.devin\loop_state_archive\*',
  '*.devin\context_flags\*',
  '*.devin\plan_state\*',
  '*.devin\reports\*',
  '*.devin\telemetry\*',
  '*.devin\tmp\*',
  '*.devin\upgrade\*',
  '*.devin\session_state',
  '*.devin\loop_state',
  '*.devin\loop_state_archive',
  '*.devin\context_flags',
  '*.devin\plan_state',
  '*.devin\reports',
  '*.devin\telemetry',
  '*.devin\tmp',
  '*.devin\upgrade',
  '*.github\*',
  '*.claude\*',
  '*.cursor\*'
)

# Runtime dir names (will be recreated empty)
$runtimeDirs = @(
  '.devin/session_state',
  '.devin/loop_state',
  '.devin/loop_state_archive',
  '.devin/context_flags',
  '.devin/plan_state',
  '.devin/reports',
  '.devin/telemetry',
  '.devin/tmp',
  '.aide/memories',
  '.aide/cache'
)

function Test-Excluded($relPath) {
  $norm = $relPath -replace '/', '\'
  foreach ($p in $excludePatterns) {
    if ($norm -like $p) { return $true }
  }
  return $false
}

# --- 3. Clean staging if exists ---
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $staging -Force | Out-Null

# --- 4. Copy included dirs to staging ---
$copied = @()
foreach ($dir in $includeDirs) {
  $src = Join-Path $root $dir
  if (-not (Test-Path $src)) {
    Write-Host "  [skip] $dir (not found)" -ForegroundColor DarkGray
    continue
  }
  $items = Get-ChildItem $src -Recurse -Force -ErrorAction SilentlyContinue
  foreach ($item in $items) {
    $rel = $item.FullName.Substring($root.Length + 1)
    if (Test-Excluded $rel) { continue }
    $dest = Join-Path $staging $rel
    if ($item.PSIsContainer) {
      if (-not (Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -Force | Out-Null }
    } else {
      $destDir = Split-Path $dest -Parent
      if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
      Copy-Item $item.FullName $dest -Force -ErrorAction Stop
    }
  }
  $copied += $dir
  Write-Host "  [copied] $dir" -ForegroundColor Green
}

# --- 5. Copy root files ---
foreach ($file in $includeFiles) {
  $src = Join-Path $root $file
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $staging $file) -Force
    Write-Host "  [copied] $file" -ForegroundColor Green
  } else {
    Write-Host "  [skip] $file (not found)" -ForegroundColor DarkGray
  }
}

# --- 6. Wipe runtime dirs in staging and recreate empty ---
Write-Host "`n=== Clean runtime data in staging ===" -ForegroundColor Cyan
foreach ($dir in $runtimeDirs) {
  $full = Join-Path $staging $dir
  if (Test-Path $full) {
    Remove-Item $full -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $full -Force | Out-Null
    Write-Host "  [cleaned] $dir" -ForegroundColor Yellow
  } else {
    New-Item -ItemType Directory -Path $full -Force | Out-Null
    Write-Host "  [created] $dir (empty)" -ForegroundColor DarkGray
  }
}

# --- 7. Reset registry files in staging ---
$loopState = Join-Path $staging '.agents/loop_state.md'
if (Test-Path $loopState) {
  Set-Content -Path $loopState -Value "---`nactive_sessions: []`nactive_session: null`n---" -Encoding UTF8 -ErrorAction SilentlyContinue
  Write-Host "  [reset]   .agents/loop_state.md" -ForegroundColor Green
}
$kdFile = Join-Path $staging '.agents/knowledge_distill.md'
if (Test-Path $kdFile) {
  Set-Content -Path $kdFile -Value "# Knowledge Distill`n`nAnti-patterns and reusable lessons. Grows by distillation only.`n" -Encoding UTF8 -ErrorAction SilentlyContinue
  Write-Host "  [reset]   .agents/knowledge_distill.md" -ForegroundColor Green
}

# --- 8. Ensure .aide/memories subdirs ---
$memBase = Join-Path $staging '.aide/memories'
foreach ($sub in @('area_context', 'guidelines', 'preferences', 'technical')) {
  New-Item -ItemType Directory -Path (Join-Path $memBase $sub) -Force | Out-Null
}
foreach ($sub in @('personal', 'shared')) {
  New-Item -ItemType Directory -Path (Join-Path $memBase "preferences/$sub") -Force | Out-Null
}
Write-Host "  [ensured] .aide/memories/ subdirs" -ForegroundColor DarkGray

# --- 9. Placeholder resolution helpers ---
function Find-AbsolutePaths($node, [ref]$paths) {
  if ($node -is [string]) {
    $matches = [regex]::Matches($node, '[A-Za-z]:\\[^<>"|\r\n\s]+')
    foreach ($m in $matches) {
      $val = $m.Value
      if ($val -match '^[A-Za-z]:\\' -and -not $paths.Value.Contains($val)) {
        $paths.Value.Add($val) | Out-Null
      }
    }
  } elseif ($node -is [array]) {
    foreach ($el in $node) { Find-AbsolutePaths $el $paths }
  } elseif ($node -is [PSCustomObject]) {
    foreach ($prop in $node.PSObject.Properties) { Find-AbsolutePaths $prop.Value $paths }
  }
}

function Replace-PathsRecursively($node, $map) {
  if ($node -is [string]) {
    $s = $node
    foreach ($kv in $map.GetEnumerator()) {
      $s = $s -replace [regex]::Escape($kv.Key), $kv.Value
    }
    return $s
  } elseif ($node -is [array]) {
    return @($node | ForEach-Object { Replace-PathsRecursively $_ $map })
  } elseif ($node -is [PSCustomObject]) {
    $clone = [PSCustomObject]@{}
    foreach ($prop in $node.PSObject.Properties) {
      $clone | Add-Member -NotePropertyName $prop.Name -NotePropertyValue (Replace-PathsRecursively $prop.Value $map) -Force
    }
    return $clone
  }
  return $node
}

function Resolve-Placeholders($configPath, $map) {
  $json = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
  $newJson = Replace-PathsRecursively $json $map
  $newJson | ConvertTo-Json -Depth 100 | Set-Content -Path $configPath -Encoding UTF8
}

# --- 10. Build placeholder map from source configs ---
$configSrc = Join-Path $root '.devin/config.json'
$mcpSrc = Join-Path $root '.devin/mcp_config.json'

$map = [ordered]@{ }

# 10a. workspace root
$map['WORKSPACE_ROOT'] = $root

# 10b. aide-memory cli + global from mcp_config
if (Test-Path $mcpSrc) {
  $mcp = Get-Content $mcpSrc -Raw | ConvertFrom-Json
  foreach ($srv in $mcp.mcpServers.PSObject.Properties) {
    $args = $srv.Value.args
    if ($args -and $args.Count -gt 0) {
      foreach ($arg in $args) {
        if ($arg -match 'aide-memory\\dist\\memory\\cli\.js$') {
          $map['AIDE_MEMORY_CLI'] = $arg
          $globalPath = Split-Path (Split-Path (Split-Path $arg -Parent) -Parent) -Parent
          $map['AIDE_MEMORY_GLOBAL'] = $globalPath
          break
        }
      }
    }
  }
}

# 10c. node.exe from config
if (Test-Path $configSrc) {
  $cfg = Get-Content $configSrc -Raw | ConvertFrom-Json
  $pathList = [System.Collections.Generic.HashSet[string]]::new()
  Find-AbsolutePaths $cfg ([ref]$pathList)
  foreach ($p in $pathList) {
    if ($p -match '\\node\.exe$') {
      $map['NODE_EXE'] = $p
      break
    }
  }
}

# Build ordered list: longest first to avoid partial replacement
$orderedKeys = @('NODE_EXE', 'AIDE_MEMORY_CLI', 'AIDE_MEMORY_GLOBAL', 'WORKSPACE_ROOT')
$replaceMap = [ordered]@{ }
foreach ($key in $orderedKeys) {
  if ($map.Contains($key)) { $replaceMap[$map[$key]] = "{{$key}}" }
}

Write-Host "`n=== Placeholders detected ===" -ForegroundColor Cyan
foreach ($key in $orderedKeys) {
  if ($map.Contains($key)) {
    Write-Host "  $key = $($map[$key])" -ForegroundColor DarkGray
  } else {
    Write-Host "  $key = (not found)" -ForegroundColor Yellow
  }
}

# --- 11. Apply templating on staging copies ---
$stagingConfig = Join-Path $staging '.devin/config.json'
$stagingMcp = Join-Path $staging '.devin/mcp_config.json'

if ((Test-Path $stagingConfig) -and $replaceMap.Count -gt 0) {
  Resolve-Placeholders $stagingConfig $replaceMap
  Write-Host "  [templated] .devin/config.json" -ForegroundColor Cyan
} else {
  Write-Host "  [skip] .devin/config.json templating" -ForegroundColor DarkGray
}

if ((Test-Path $stagingMcp) -and $replaceMap.Count -gt 0) {
  Resolve-Placeholders $stagingMcp $replaceMap
  Write-Host "  [templated] .devin/mcp_config.json" -ForegroundColor Cyan
} else {
  Write-Host "  [skip] .devin/mcp_config.json templating" -ForegroundColor DarkGray
}

# --- 12. Check remaining absolute paths in staging config ---
$remaining = @()
$scanFiles = @($stagingConfig, $stagingMcp) | Where-Object { Test-Path $_ }
foreach ($f in $scanFiles) {
  $content = Get-Content $f -Raw
  $m = [regex]::Matches($content, '[A-Za-z]:\\[^<>"|\r\n\s]+')
  if ($m.Count -gt 0) { $remaining += "$f`: $($m[0].Value)" }
}
if ($remaining.Count -gt 0) {
  Write-Host "`n  [WARN] Remaining absolute paths found in config files:" -ForegroundColor Yellow
  foreach ($r in $remaining) { Write-Host "    $r" -ForegroundColor Yellow }
}

# --- 13. Dry-run report ---
if ($DryRun) {
  Write-Host "`n=== Dry-run report ===" -ForegroundColor Cyan
  $allItems = Get-ChildItem $staging -Recurse -Force -ErrorAction SilentlyContinue
  $fileCount = ($allItems | Where-Object { -not $_.PSIsContainer }).Count
  $dirCount = ($allItems | Where-Object { $_.PSIsContainer }).Count
  Write-Host "  Would include: $fileCount files, $dirCount directories" -ForegroundColor Gray
  Write-Host "  Excluded patterns: $($excludePatterns.Count)" -ForegroundColor Gray
  Write-Host "  Placeholders: $($replaceMap.Count)" -ForegroundColor Gray
  if ($remaining.Count -gt 0) {
    Write-Host "  WARN: $($remaining.Count) config still has absolute paths" -ForegroundColor Yellow
  }
  Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
  Write-Host "`n[DryRun] Package would be created at: $OutputPath" -ForegroundColor Yellow
  Write-Host "[DryRun] Staging removed. No zip written." -ForegroundColor Yellow
  return
}

# --- 14. Create manifest ---
$gitCommit = $null
try { $gitCommit = (git -C $root rev-parse HEAD 2>$null) } catch { }
$manifest = @{
  packaged_at = (Get-Date -Format 'o')
  source_workspace = $root
  git_commit = $gitCommit
  contents = @{
    canon = (Get-ChildItem (Join-Path $staging '.devin/canon') -File -ErrorAction SilentlyContinue).Count
    skills = (Get-ChildItem (Join-Path $staging '.devin/skills') -Recurse -File -ErrorAction SilentlyContinue).Count
    agents = (Get-ChildItem (Join-Path $staging '.devin/agents') -Recurse -File -ErrorAction SilentlyContinue).Count
    hooks = (Get-ChildItem (Join-Path $staging '.devin/hooks') -File -ErrorAction SilentlyContinue).Count
    scripts = (Get-ChildItem (Join-Path $staging '.devin/scripts') -File -ErrorAction SilentlyContinue).Count
    hlk = (Get-ChildItem (Join-Path $staging 'HLK') -Recurse -File -ErrorAction SilentlyContinue).Count
    tools = (Get-ChildItem (Join-Path $staging 'tools') -Recurse -File -ErrorAction SilentlyContinue).Count
  }
  placeholders = @(
    '{{WORKSPACE_ROOT}} — absolute path to new project root',
    '{{AIDE_MEMORY_GLOBAL}} — global node_modules/aide-memory path',
    '{{AIDE_MEMORY_CLI}} — aide-memory dist/memory/cli.js path',
    '{{NODE_EXE}} — node.exe path for HLK hook launcher'
  )
}
$manifestDest = Join-Path $staging 'TEMPLATE_MANIFEST.json'
$manifest | ConvertTo-Json -Depth 5 | Set-Content -Path $manifestDest -Encoding UTF8
Write-Host "  [created] TEMPLATE_MANIFEST.json" -ForegroundColor Cyan

# --- 15. Zip ---
$outputDir = Split-Path $OutputPath -Parent
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
if (Test-Path $OutputPath) { Remove-Item $OutputPath -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($staging, $OutputPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

# --- 16. Post-zip integrity: extract to temp and verify ---
$testExtract = Join-Path $env:TEMP "harness-template-test-$timestamp"
if (Test-Path $testExtract) { Remove-Item $testExtract -Recurse -Force }
New-Item -ItemType Directory -Path $testExtract -Force | Out-Null
[System.IO.Compression.ZipFile]::ExtractToDirectory($OutputPath, $testExtract)
$verifyScript = Join-Path $PSScriptRoot 'verify-workspace.ps1'
if (Test-Path $verifyScript) {
  Write-Host "`n=== Post-package verify ===" -ForegroundColor Cyan
  & $verifyScript -WorkspaceRoot $testExtract
  $verifyExit = $LASTEXITCODE
} else {
  $verifyExit = 0
}

# --- 17. Cleanup staging + test extract ---
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $testExtract -Recurse -Force -ErrorAction SilentlyContinue

$size = (Get-Item $OutputPath).Length / 1KB
if ($verifyExit -eq 0) {
  Write-Host "`n=== Package complete ===" -ForegroundColor Cyan
  Write-Host "Output: $OutputPath ($([math]::Round($size, 1)) KB)" -ForegroundColor Green
  Write-Host "Deploy với: .\tools\deploy-template.ps1 -TemplatePath '$OutputPath' -TargetPath '<new-project-dir>'" -ForegroundColor Gray
} else {
  Write-Host "`n=== Package created but verify FAILED ===" -ForegroundColor Red
  Write-Host "Output: $OutputPath ($([math]::Round($size, 1)) KB)" -ForegroundColor Red
}
