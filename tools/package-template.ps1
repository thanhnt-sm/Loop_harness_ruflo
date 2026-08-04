<#
.SYNOPSIS
  Đóng gói workspace hiện tại thành template zip — sạch, sẵn sàng deploy sang dự án mới.
.DESCRIPTION
  1. Chạy clean-runtime.ps1 để wipe runtime state
  2. Tạo template config.json + mcp_config.json với placeholders (thay hardcoded paths)
  3. Copy các file/thư mục reusable vào staging dir
  4. Loại bỏ: .git, .tools, node_modules, HLK/reports, .github/issues, v.v.
  5. Nén thành zip
.PARAMETER OutputPath
  Đường dẫn output zip. Mặc định: ./harness-template.zip
.PARAMETER WorkspaceRoot
  Workspace cần đóng gói. Mặc định: thư mục hiện tại.
.EXAMPLE
  .\tools\package-template.ps1
  .\tools\package-template.ps1 -OutputPath D:\templates\my-harness.zip
#>
param(
  [string]$OutputPath = (Join-Path (Get-Location).Path 'harness-template.zip'),
  [string]$WorkspaceRoot = (Get-Location).Path
)

$ErrorActionPreference = 'Continue'
$root = (Resolve-Path $WorkspaceRoot).Path
$staging = Join-Path $env:TEMP "harness-staging-$(Get-Date -Format 'yyyyMMddHHmmss')"

Write-Host "`n=== Package Template ===" -ForegroundColor Cyan
Write-Host "Source:      $root" -ForegroundColor Gray
Write-Host "Staging:     $staging" -ForegroundColor Gray
Write-Host "Output:      $OutputPath`n" -ForegroundColor Gray

# --- 1. Clean runtime (inline để tránh scope propagation issues) ---
Write-Host "`n=== Clean Runtime State ===" -ForegroundColor Cyan
$runtimeDirs = @('.devin/session_state', '.devin/loop_state', '.devin/loop_state_archive', '.devin/context_flags', '.aide/memories', '.aide/cache')
foreach ($dir in $runtimeDirs) {
  $full = Join-Path $root $dir
  if (Test-Path $full) {
    Get-ChildItem $full -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [cleaned] $dir" -ForegroundColor Yellow
  } else {
    New-Item -ItemType Directory -Path $full -Force -ErrorAction SilentlyContinue | Out-Null
  }
}
$loopStateFile = Join-Path $root '.agents/loop_state.md'
if (Test-Path $loopStateFile) {
  Set-Content -Path $loopStateFile -Value "---`nactive_sessions: []`nactive_session: null`n---" -Encoding UTF8 -ErrorAction SilentlyContinue
  Write-Host "  [reset]   .agents/loop_state.md" -ForegroundColor Green
}
$kdFile = Join-Path $root '.agents/knowledge_distill.md'
if (Test-Path $kdFile) {
  Set-Content -Path $kdFile -Value "# Knowledge Distill`n`nAnti-patterns and reusable lessons. Grows by distillation only.`n" -Encoding UTF8 -ErrorAction SilentlyContinue
  Write-Host "  [reset]   .agents/knowledge_distill.md" -ForegroundColor Green
}
foreach ($dir in @('.claude', '.cursor')) {
  $full = Join-Path $root $dir
  if (Test-Path $full) {
    Remove-Item $full -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [removed] $dir" -ForegroundColor Yellow
  }
}
$memBase = Join-Path $root '.aide/memories'
foreach ($sub in @('area_context', 'guidelines', 'preferences', 'technical')) {
  $full = Join-Path $memBase $sub
  if (-not (Test-Path $full)) { New-Item -ItemType Directory -Path $full -Force -ErrorAction SilentlyContinue | Out-Null }
}
foreach ($sub in @('personal', 'shared')) {
  $full = Join-Path $memBase "preferences/$sub"
  if (-not (Test-Path $full)) { New-Item -ItemType Directory -Path $full -Force -ErrorAction SilentlyContinue | Out-Null }
}
Write-Host "  [ensured] .aide/memories/ subdirs" -ForegroundColor DarkGray
Write-Host "=== Clean complete ===`n" -ForegroundColor Cyan

# --- 2. Tạo staging dir ---
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue }
New-Item -ItemType Directory -Path $staging -Force | Out-Null
Write-Host "  [debug] staging dir created: $staging" -ForegroundColor Magenta

# --- 3. Danh sách thư mục reusable (copy nguyên cây) ---
$includeDirs = @(
  '.devin',
  '.agents',
  '.aide',
  '.github',
  'HLK',
  'tools'
)

# --- 4. Danh sách file root reusable ---
$includeFiles = @(
  'AGENTS.md',
  'CLAUDE.md',
  'REPOS.md',
  '.gitignore',
  'package.json'
)

# --- 5. Danh sách loại bỏ (exclude patterns) — không mang sang dự án mới ---
# Dùng -like wildcard matching (không phải regex) để tránh lỗi backslash
$excludePatterns = @(
  '*HLK\reports*',
  '*HLK\logs*',
  '*.github\issues*',
  '*.github\supply-chain*',
  '*\node_modules\*',
  '*\.git\*',
  '*\.tools\*',
  '*\.claude\*',
  '*\.cursor\*'
)

function Test-Excluded($path) {
  $normalized = $path -replace '/', '\'
  foreach ($pattern in $excludePatterns) {
    if ($normalized -like $pattern) { return $true }
  }
  return $false
}

# --- 6. Copy dirs ---
foreach ($dir in $includeDirs) {
  $src = Join-Path $root $dir
  if (-not (Test-Path $src)) {
    Write-Host "  [skip] $dir (not found)" -ForegroundColor DarkGray
    continue
  }
  try {
    $items = Get-ChildItem $src -Recurse -Force -ErrorAction SilentlyContinue
    foreach ($item in $items) {
      $rel = $item.FullName.Substring($root.Length + 1)
      if (Test-Excluded $rel) { continue }
      $dest = Join-Path $staging $rel
      if ($item.PSIsContainer) {
        New-Item -ItemType Directory -Path $dest -Force | Out-Null
      } else {
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        Copy-Item $item.FullName $dest -Force -ErrorAction SilentlyContinue
      }
    }
    Write-Host "  [copied] $dir" -ForegroundColor Green
  } catch {
    Write-Host "  [ERROR] Copy $dir failed: $_" -ForegroundColor Red
    throw $_
  }
}

# --- 7. Copy root files ---
foreach ($file in $includeFiles) {
  $src = Join-Path $root $file
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $staging $file) -Force
    Write-Host "  [copied] $file" -ForegroundColor Green
  } else {
    Write-Host "  [skip] $file (not found)" -ForegroundColor DarkGray
  }
}

# --- 8. Tạo templated config.json (thay hardcoded paths → placeholders) ---
$configSrc = Join-Path $root '.devin/config.json'
$configContent = Get-Content $configSrc -Raw

# Thay workspace path → {{WORKSPACE_ROOT}}
$configContent = $configContent -replace [regex]::Escape('D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo'), '{{WORKSPACE_ROOT}}'
# Thay aide-memory global path → {{AIDE_MEMORY_GLOBAL}}
$configContent = $configContent -replace [regex]::Escape('C:\Users\thant\AppData\Roaming\nvm\v18.20.0\node_modules\aide-memory'), '{{AIDE_MEMORY_GLOBAL}}'
# Thay .tools\node path → {{NODE_EXE}}
$configContent = $configContent -replace [regex]::Escape('D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\.tools\node\node.exe'), '{{NODE_EXE}}'

$configDest = Join-Path $staging '.devin\config.json'
$configDestDir = Split-Path $configDest -Parent
if (-not (Test-Path $configDestDir)) { New-Item -ItemType Directory -Path $configDestDir -Force | Out-Null }
[System.IO.File]::WriteAllText($configDest, $configContent, (New-Object System.Text.UTF8Encoding $false))
Write-Host "  [templated] .devin/config.json (placeholders: WORKSPACE_ROOT, AIDE_MEMORY_GLOBAL, NODE_EXE)" -ForegroundColor Cyan

# --- 9. Tạo templated mcp_config.json ---
$mcpSrc = Join-Path $root '.devin/mcp_config.json'
$mcpContent = Get-Content $mcpSrc -Raw
$mcpContent = $mcpContent -replace [regex]::Escape('C:\Users\thant\AppData\Roaming\nvm\v18.20.0\node_modules\aide-memory\dist\memory\cli.js'), '{{AIDE_MEMORY_CLI}}'
$mcpContent = $mcpContent -replace [regex]::Escape('D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo'), '{{WORKSPACE_ROOT}}'

$mcpDest = Join-Path $staging '.devin\mcp_config.json'
$mcpDestDir = Split-Path $mcpDest -Parent
if (-not (Test-Path $mcpDestDir)) { New-Item -ItemType Directory -Path $mcpDestDir -Force | Out-Null }
[System.IO.File]::WriteAllText($mcpDest, $mcpContent, (New-Object System.Text.UTF8Encoding $false))
Write-Host "  [templated] .devin/mcp_config.json (placeholders: AIDE_MEMORY_CLI, WORKSPACE_ROOT)" -ForegroundColor Cyan

# --- 10. Tạo template manifest ---
$manifest = @{
  packaged_at = (Get-Date -Format 'o')
  source_workspace = $root.Path
  git_commit = (git -C $root rev-parse HEAD 2>$null)
  contents = @{
    canon = 10
    skills_ahd = 16
    skills_devin_native = 5
    skills_vendored = 'nuwa-skill + chroma-hybrid-search + domain-adapters(9)'
    agents = 'COMMANDER + 7 personas + 5 workers + lightning-executor + glm-executor'
    hooks = 4
    scripts = 7
    vault_templates = 5
  }
  placeholders = @(
    '{{WORKSPACE_ROOT}} — absolute path to new project root',
    '{{AIDE_MEMORY_GLOBAL}} — global node_modules/aide-memory path',
    '{{AIDE_MEMORY_CLI}} — aide-memory dist/cli.js path',
    '{{NODE_EXE}} — node.exe path for HLK hook launcher'
  )
}
$manifestDest = Join-Path $staging 'TEMPLATE_MANIFEST.json'
$manifest | ConvertTo-Json -Depth 5 | Out-File -FilePath $manifestDest -Encoding UTF8 -Force
Write-Host "  [created] TEMPLATE_MANIFEST.json" -ForegroundColor Cyan

# --- 11. Zip (dùng .NET ZipFile để tránh Compress-Archive bug giữ full path) ---
$outputDir = Split-Path $OutputPath -Parent
if (-not (Test-Path $outputDir)) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
if (Test-Path $OutputPath) { Remove-Item $OutputPath -Force }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($staging, $OutputPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

# --- 12. Cleanup staging ---
Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue

$size = (Get-Item $OutputPath).Length / 1KB
Write-Host "`n=== Package complete ===" -ForegroundColor Cyan
Write-Host "Output: $OutputPath ($([math]::Round($size, 1)) KB)`n" -ForegroundColor Green
Write-Host "Deploy với: .\tools\deploy-template.ps1 -TemplatePath '$OutputPath' -TargetPath '<new-project-dir>'" -ForegroundColor Gray
