<#
.SYNOPSIS
  HLK Upstream Sync — Safely merge ruflo updates without breaking HLK Layer.
.DESCRIPTION
  Fetches from upstream (ruvnet/ruflo), merges into current branch with --no-ff,
  then verifies HLK layer integrity after merge.
.NOTES
  Cross-platform equivalent of git-upstream-sync.sh for Windows.
#>

param(
  [string]$UpstreamUrl = "https://github.com/ruvnet/ruflo.git",
  [string]$UpstreamRemote = "upstream",
  [string]$TargetBranch = "main",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Write-HLK { param([string]$msg) Write-Host "[HLK UPSTREAM SYNC] $msg" }

# ── Pre-flight checks ──────────────────────────────────────────────────────

$hlkConfigPath = Join-Path $PSScriptRoot "..\config\hlk.config.json"
if (-not (Test-Path $hlkConfigPath)) {
  Write-Warning "HLK config not found at $hlkConfigPath — aborting"
  exit 1
}

# Read current config for backup
$configBackup = Get-Content $hlkConfigPath -Raw

# ── Ensure upstream remote ──────────────────────────────────────────────────

Write-HLK "🔄 Checking Git remotes..."
$remotes = git remote 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Warning "Not a git repository. Run 'git init' first."
  exit 1
}

if ($remotes -notcontains $UpstreamRemote) {
  Write-HLK "➕ Adding remote '$UpstreamRemote': $UpstreamUrl"
  git remote add $UpstreamRemote $UpstreamUrl
}

# ── Fetch upstream ──────────────────────────────────────────────────────────

Write-HLK "📥 Fetching from $UpstreamRemote ($TargetBranch)..."
git fetch $UpstreamRemote

if ($DryRun) {
  Write-HLK "🔍 DRY RUN — showing what would change:"
  git log --oneline "HEAD..$UpstreamRemote/$TargetBranch" -- ':!HLK/'
  Write-HLK "✅ Dry run complete. HLK/ directory is excluded from diff."
  exit 0
}

# ── Check for uncommitted changes ──────────────────────────────────────────

$status = git status --porcelain 2>&1
if ($status) {
  Write-Warning "You have uncommitted changes. Commit or stash them first."
  Write-Host $status
  exit 1
}

# ── Backup HLK config ──────────────────────────────────────────────────────

$backupDir = Join-Path $PSScriptRoot "..\logs"
if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupFile = Join-Path $backupDir "hlk.config.backup-$timestamp.json"
$configBackup | Set-Content $backupFile -NoNewline
Write-HLK "💾 Config backed up to $backupFile"

# ── Merge upstream ──────────────────────────────────────────────────────────

Write-HLK "🔀 Merging $UpstreamRemote/$TargetBranch into current branch..."
git merge "$UpstreamRemote/$TargetBranch" --no-ff -m "chore: merge updates from upstream ruflo"

if ($LASTEXITCODE -ne 0) {
  Write-Warning "Merge failed or has conflicts. Resolve manually, then run hlk-verify-integrity.js"
  exit 1
}

# ── Post-merge HLK verification ────────────────────────────────────────────

Write-HLK "🔍 Verifying HLK integrity..."

# Check config still exists and is valid JSON
if (-not (Test-Path $hlkConfigPath)) {
  Write-Warning "⚠️ HLK config MISSING after merge! Restoring from backup..."
  $configBackup | Set-Content $hlkConfigPath -NoNewline
  Write-HLK "✅ Config restored from backup."
} else {
  try {
    $cfg = Get-Content $hlkConfigPath -Raw | ConvertFrom-Json
    if ($cfg.hlk_enabled -eq $true) {
      Write-HLK "✅ HLK enabled and config valid (v$($cfg.version))"
    } else {
      Write-HLK "⚠️ HLK is disabled in config — toggle hlk_enabled=true to re-activate"
    }
  } catch {
    Write-Warning "⚠️ HLK config is invalid JSON after merge! Restoring from backup..."
    $configBackup | Set-Content $hlkConfigPath -NoNewline
    Write-HLK "✅ Config restored from backup."
  }
}

# Check security modules still exist
$securityFiles = @(
  (Join-Path $PSScriptRoot "..\security\sanitizer.js"),
  (Join-Path $PSScriptRoot "..\security\vault-bridge.js")
)
$missing = $securityFiles | Where-Object { -not (Test-Path $_) }
if ($missing) {
  Write-Warning "⚠️ Missing HLK security modules: $($missing -join ', ')"
} else {
  Write-HLK "✅ All security modules intact"
}

Write-HLK "🎉 Upstream sync complete!"
