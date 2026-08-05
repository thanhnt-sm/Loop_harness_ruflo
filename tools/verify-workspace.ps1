<#
.SYNOPSIS
  Verify workspace integrity — kiểm tra đủ canon, skills, agents, hooks, scripts, config.
.DESCRIPTION
  Kiểm tra đầy đủ cấu trúc AHD workspace:
  - 10 canon files trong .devin/canon/
  - COMMANDER + personas + workers trong .devin/agents/
  - Skills trong .devin/skills/
  - 4 hooks trong .devin/hooks/
  - 7 scripts trong .devin/scripts/
  - 5 vault templates trong .devin/skills/assets/vault/
  - config.json + mcp_config.json valid JSON
  - .agents/ shared state files
  - HLK security layer
  - Root docs (AGENTS.md, CLAUDE.md, REPOS.md)
.PARAMETER WorkspaceRoot
  Workspace cần verify. Mặc định: thư mục hiện tại.
.EXAMPLE
  .\tools\verify-workspace.ps1
  .\tools\verify-workspace.ps1 -WorkspaceRoot D:\projects\my-app
#>
param(
  [string]$WorkspaceRoot = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path $WorkspaceRoot).Path

Write-Host "`n=== Verify Workspace Integrity ===" -ForegroundColor Cyan
Write-Host "Workspace: $root`n" -ForegroundColor Gray

$errors = @()
$warnings = @()
$passed = 0

function Check-File($rel, $label) {
  $full = Join-Path $root $rel
  if (Test-Path $full) {
    Write-Host "  [OK]   $rel" -ForegroundColor Green
    $script:passed++
  } else {
    Write-Host "  [FAIL] $rel — $label" -ForegroundColor Red
    $script:errors += "$rel — $label"
  }
}

function Check-Dir($rel, $label) {
  $full = Join-Path $root $rel
  if ((Test-Path $full) -and (Get-ChildItem $full -ErrorAction SilentlyContinue)) {
    $count = (Get-ChildItem $full -Recurse -File -ErrorAction SilentlyContinue).Count
    Write-Host "  [OK]   $rel ($count files)" -ForegroundColor Green
    $script:passed++
  } else {
    Write-Host "  [FAIL] $rel — $label" -ForegroundColor Red
    $script:errors += "$rel — $label"
  }
}

# --- 1. Canon (10 files) ---
Write-Host "`n[1/8] Canon protocols (.devin/canon/)" -ForegroundColor Yellow
$canonFiles = @(
  'CORE_CANON.md', 'BOOT_PROTOCOL.md', 'MEMORY_PROTOCOL.md',
  'LOOP_PROTOCOL.md', 'VERIFICATION_PROTOCOL.md', 'CAVEMAN_PROTOCOL.md',
  'HARNESS_ENGINEERING.md', 'JUDGMENT_RUBRICS.md', 'HANDOFF_LETTER.md',
  'REDLINES.md'
)
foreach ($f in $canonFiles) { Check-File ".devin/canon/$f" "canon protocol missing" }

# --- 2. Agents ---
Write-Host "`n[2/8] Orchestrator (.devin/agents/)" -ForegroundColor Yellow
Check-File '.devin/agents/COMMANDER.md' 'Commander persona'
Check-File '.devin/agents/DISPATCH_TEMPLATES.md' 'Dispatch templates'
Check-File '.devin/agents/MODEL_TIERS.md' 'Model tiers (case-insensitive check)'
Check-File '.devin/agents/model_tiers.md' 'Model tiers'
Check-File '.devin/agents/PERSONA_TEMPLATE.md' 'Persona template'
Check-Dir '.devin/agents/personas' '3 persona files (U26: via negativa)'
Check-Dir '.devin/agents/workers' '5 worker files'
Check-File '.devin/agents/lightning-executor/AGENT.md' 'Lightning executor'
Check-File '.devin/agents/glm-executor/AGENT.md' 'GLM executor'

# --- 3. Skills ---
Write-Host "`n[3/8] Skills (.devin/skills/)" -ForegroundColor Yellow
# U26: Reduced from 16 AHD skills to 5 core (via negativa)
$ahdSkills = @(
  'comment_checker.md', 'fable-judge.md', 'harness-sensor.md',
  'slop-detector.md', 'using-skills.md'
)
foreach ($s in $ahdSkills) { Check-File ".devin/skills/$s" "AHD skill missing" }

Check-Dir '.devin/skills/nuwa-skill' 'Nuwa skill (vendored)'
Check-File '.devin/skills/lightning/SKILL.md' 'Lightning skill'
Check-File '.devin/skills/glm/SKILL.md' 'GLM skill'
Check-File '.devin/skills/aide-memory/SKILL.md' 'aide-memory skill'
Check-File '.devin/skills/hlk-git-tools/SKILL.md' 'HLK git tools skill'
Check-File '.devin/skills/hlk-integrity-check/SKILL.md' 'HLK integrity check skill'

# --- 4. Hooks (4 files) ---
Write-Host "`n[4/8] Hooks (.devin/hooks/)" -ForegroundColor Yellow
$hooks = @('pre_tool_use.py', 'post_tool_use.py', 'stop.py', 'ahd_session.py')
foreach ($h in $hooks) { Check-File ".devin/hooks/$h" "hook missing" }

# --- 5. Scripts (7 files) ---
Write-Host "`n[5/8] Scripts (.devin/scripts/)" -ForegroundColor Yellow
$scripts = @(
  'worktree.py', 'plan_dispatch.py', 'session_manager.py',
  'loop_memory_sync.py', 'memory_audit.py', 'pre_task_audit.py'
)
foreach ($s in $scripts) { Check-File ".devin/scripts/$s" "script missing" }

# --- 6. Vault (5 templates) ---
Write-Host "`n[6/8] Vault templates (.devin/skills/assets/vault/)" -ForegroundColor Yellow
$vault = @(
  'caveman_template.json', 'agency_framework.toml',
  'memory_mcp_schema.json', 'strix_security_rules.json',
  'graphify_knowledge_spec.json'
)
foreach ($v in $vault) { Check-File ".devin/skills/assets/vault/$v" "vault template missing" }

# --- 7. Config + shared state ---
Write-Host "`n[7/8] Config + shared state" -ForegroundColor Yellow
Check-File '.devin/config.json' 'Devin config'
Check-File '.devin/mcp_config.json' 'MCP config'
Check-File '.devin/AGENTS.md' 'Auto-generated harness entry'
Check-File '.agents/user_profile.md' 'User profile'
Check-File '.agents/loop_state.md' 'Loop state registry'
Check-File '.agents/knowledge_distill.md' 'Knowledge distill'

# Validate JSON
try {
  Get-Content (Join-Path $root '.devin/config.json') -Raw | ConvertFrom-Json | Out-Null
  Write-Host "  [OK]   config.json valid JSON" -ForegroundColor Green
  $passed++
} catch {
  Write-Host "  [FAIL] config.json invalid JSON: $_" -ForegroundColor Red
  $errors += "config.json invalid JSON"
}
try {
  Get-Content (Join-Path $root '.devin/mcp_config.json') -Raw | ConvertFrom-Json | Out-Null
  Write-Host "  [OK]   mcp_config.json valid JSON" -ForegroundColor Green
  $passed++
} catch {
  Write-Host "  [FAIL] mcp_config.json invalid JSON: $_" -ForegroundColor Red
  $errors += "mcp_config.json invalid JSON"
}

# Check unresolved placeholders
$configContent = Get-Content (Join-Path $root '.devin/config.json') -Raw
if ($configContent -match '\{\{.*\}\}') {
  Write-Host "  [WARN] config.json có unresolved placeholders" -ForegroundColor Yellow
  $warnings += "config.json has unresolved {{...}} placeholders"
}

# --- 8. HLK + root docs ---
Write-Host "`n[8/8] HLK + root docs" -ForegroundColor Yellow
Check-Dir 'HLK' 'HLK security layer'
Check-File 'HLK/security/sanitizer.js' 'HLK sanitizer'
Check-File 'HLK/security/vault-bridge.js' 'HLK vault-bridge'
Check-File 'HLK/wrappers/hlk-hook-launcher.mjs' 'HLK hook launcher'
Check-File 'AGENTS.md' 'Root AGENTS.md'
Check-File 'CLAUDE.md' 'Root CLAUDE.md'
Check-File 'REPOS.md' 'REPOS.md reference list'

# --- Summary ---
Write-Host "`n=== Summary ===" -ForegroundColor Cyan
Write-Host "  Passed:   $passed" -ForegroundColor Green
Write-Host "  Warnings: $($warnings.Count)" -ForegroundColor Yellow
Write-Host "  Errors:   $($errors.Count)" -ForegroundColor $(if ($errors.Count) {'Red'} else {'Green'})

if ($warnings.Count -gt 0) {
  Write-Host "`nWarnings:" -ForegroundColor Yellow
  foreach ($w in $warnings) { Write-Host "  - $w" -ForegroundColor Yellow }
}

if ($errors.Count -gt 0) {
  Write-Host "`nErrors:" -ForegroundColor Red
  foreach ($e in $errors) { Write-Host "  - $e" -ForegroundColor Red }
  Write-Host "`n  [FAIL] Workspace KHÔNG đầy đủ — cần fix trước khi dùng.`n" -ForegroundColor Red
  exit 1
} else {
  Write-Host "`n  [PASS] Workspace đầy đủ — sẵn sàng full power.`n" -ForegroundColor Green
  exit 0
}
