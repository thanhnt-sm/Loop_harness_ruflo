<#
.SYNOPSIS
  Xóa runtime state — biến workspace về trạng thái "sạch" như mới deploy.
.DESCRIPTION
  Wipe các thư mục/file runtime (session state, memories, loop state, context flags, plan state, reports, telemetry, tmp)
  và reset registry files về trạng thái rỗng. Giữ nguyên tất cả config, canon, skills,
  agents, hooks, scripts, vault — chỉ xóa dữ liệu sinh ra trong quá trình chạy.
.PARAMETER WorkspaceRoot
  Đường dẫn workspace cần clean. Mặc định: thư mục hiện tại.
.EXAMPLE
  .\tools\clean-runtime.ps1
  .\tools\clean-runtime.ps1 -WorkspaceRoot D:\projects\my-new-project
#>
param(
  [string]$WorkspaceRoot = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $WorkspaceRoot).Path

Write-Host "`n=== Clean Runtime State ===" -ForegroundColor Cyan
Write-Host "Workspace: $root`n" -ForegroundColor Gray

# --- 1. Wipe runtime directories (toàn bộ nội dung, giữ thư mục rỗng) ---
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

foreach ($dir in $runtimeDirs) {
  $full = Join-Path $root $dir
  if (Test-Path $full) {
    Get-ChildItem $full -Recurse -Force | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [cleaned] $dir" -ForegroundColor Yellow
  } else {
    New-Item -ItemType Directory -Path $full -Force | Out-Null
    Write-Host "  [created] $dir (empty)" -ForegroundColor DarkGray
  }
}

# --- 2. Wipe runtime files ---
$runtimeFiles = @(
  '.aide/recall-log.jsonl'
)

foreach ($file in $runtimeFiles) {
  $full = Join-Path $root $file
  if (Test-Path $full) {
    Remove-Item $full -Force
    Write-Host "  [removed] $file" -ForegroundColor Yellow
  }
}

# --- 3. Reset registry files về template rỗng ---
$loopState = Join-Path $root '.agents/loop_state.md'
if (Test-Path $loopState) {
  Set-Content -Path $loopState -Value "---`nactive_sessions: []`nactive_session: null`n---" -Encoding UTF8
  Write-Host "  [reset]   .agents/loop_state.md" -ForegroundColor Green
}

$knowledgeDistill = Join-Path $root '.agents/knowledge_distill.md'
if (Test-Path $knowledgeDistill) {
  Set-Content -Path $knowledgeDistill -Value "# Knowledge Distill`n`nAnti-patterns and reusable lessons. Grows by distillation only.`n" -Encoding UTF8
  Write-Host "  [reset]   .agents/knowledge_distill.md" -ForegroundColor Green
}

# --- 4. Wipe .claude/ + .cursor/ (gitignored, recreated by hooks) ---
foreach ($dir in @('.claude', '.cursor')) {
  $full = Join-Path $root $dir
  if (Test-Path $full) {
    Remove-Item $full -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  [removed] $dir (will recreate on next session)" -ForegroundColor Yellow
  }
}

# --- 5. Tạo lại memory subdirs rỗng (aide-memory cần cấu trúc này) ---
$memBase = Join-Path $root '.aide/memories'
foreach ($sub in @('area_context', 'guidelines', 'preferences', 'technical')) {
  $full = Join-Path $memBase $sub
  if (-not (Test-Path $full)) {
    New-Item -ItemType Directory -Path $full -Force | Out-Null
  }
}
# preferences/personal + preferences/shared
foreach ($sub in @('personal', 'shared')) {
  $full = Join-Path $memBase "preferences/$sub"
  if (-not (Test-Path $full)) {
    New-Item -ItemType Directory -Path $full -Force | Out-Null
  }
}
Write-Host "  [ensured] .aide/memories/ subdirs" -ForegroundColor DarkGray

Write-Host "`n=== Clean complete ===`n" -ForegroundColor Cyan
Write-Host "Workspace đã sạch runtime state. Sẵn sàng đóng gói hoặc bắt đầu session mới." -ForegroundColor Green
