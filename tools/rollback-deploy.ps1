<#
.SYNOPSIS
  Rollback a deploy — restore workspace to pre-deploy state using backup.
.DESCRIPTION
  1. Find the most recent backup before the deploy timestamp
  2. Verify SHA256 hash
  3. Restore workspace files (protected: src/, tests/, node_modules/, .git/)
  4. Optionally revert the last git commit (if deploy created one)
  5. Run verify-workspace.ps1 post-rollback
.PARAMETER WorkspaceRoot
  Workspace root path. Default: current directory.
.PARAMETER BeforeTimestamp
  Only consider backups created before this timestamp (format: yyyy-MM-dd HH:mm:ss).
  If not specified, uses the most recent backup.
.PARAMETER RevertGitCommit
  Also revert the last git commit (git revert, not reset --hard).
.PARAMETER DryRun
  Show what would be rolled back without making changes.
.EXAMPLE
  .\tools\rollback-deploy.ps1
  .\tools\rollback-deploy.ps1 -BeforeTimestamp "2026-07-07 14:00:00"
  .\tools\rollback-deploy.ps1 -RevertGitCommit -DryRun
#>
param(
  [string]$WorkspaceRoot = (Get-Location).Path,
  [string]$BeforeTimestamp,
  [switch]$RevertGitCommit,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

Write-Host "`n=== Rollback Deploy ===" -ForegroundColor Cyan
Write-Host "Workspace: $WorkspaceRoot`n" -ForegroundColor Gray

if ($DryRun) {
  Write-Host "[DryRun] No changes will be made.`n" -ForegroundColor Yellow
}

# --- 1. Find backup to restore from ---
$backupDir = Join-Path $WorkspaceRoot 'backups'
if (-not (Test-Path $backupDir)) {
  throw "No backups directory found at $backupDir - cannot rollback without a backup"
}

$backups = Get-ChildItem $backupDir -Filter 'harness-backup-*.zip' | Sort-Object LastWriteTime -Descending
if ($backups.Count -eq 0) {
  throw "No backups found in $backupDir - cannot rollback without a backup"
}

# Filter by timestamp if specified
$selectedBackup = $null
if ($BeforeTimestamp) {
  $cutoff = [datetime]::Parse($BeforeTimestamp)
  $backupsBefore = $backups | Where-Object { $_.LastWriteTime -lt $cutoff } | Sort-Object LastWriteTime -Descending
  if ($backupsBefore.Count -eq 0) {
    throw "No backups found before $BeforeTimestamp"
  }
  $selectedBackup = $backupsBefore[0]
  Write-Host "  [selected] $($selectedBackup.Name) (before $BeforeTimestamp)" -ForegroundColor Gray
} else {
  $selectedBackup = $backups[0]
  Write-Host "  [selected] $($selectedBackup.Name) (most recent)" -ForegroundColor Gray
}

# --- 2. Verify SHA256 ---
$backupName = $selectedBackup.Name
$hashesFile = Join-Path $backupDir 'hashes.txt'
if (Test-Path $hashesFile) {
  $expectedHash = $null
  foreach ($line in Get-Content $hashesFile) {
    if ($line -match "^\s*([A-Fa-f0-9]{64})\s+$([regex]::Escape($backupName))") {
      $expectedHash = $Matches[1]
      break
    }
  }
  if ($expectedHash) {
    $actualHash = (Get-FileHash $selectedBackup.FullName -Algorithm SHA256).Hash
    if ($actualHash -ne $expectedHash) {
      throw "SHA256 mismatch! Expected: $expectedHash, Actual: $actualHash - backup corrupted, refusing rollback"
    }
    Write-Host "  [verified] SHA256 match" -ForegroundColor Green
  } else {
    Write-Host "  [warn] No hash entry for $backupName - proceeding without verification" -ForegroundColor Yellow
  }
}

# --- 3. Show what will be restored ---
Write-Host "`n  Restoring from: $backupName" -ForegroundColor Gray
Write-Host "  Protected (not overwritten): src/, tests/, node_modules/, .git/" -ForegroundColor Gray

if ($RevertGitCommit) {
  Write-Host "  Will also: git revert HEAD (revert last commit)" -ForegroundColor Gray
}

if ($DryRun) {
  Write-Host "`n[DryRun] Would restore from: $($selectedBackup.FullName)" -ForegroundColor Yellow
  if ($RevertGitCommit) {
    Write-Host "[DryRun] Would run: git revert HEAD --no-edit" -ForegroundColor Yellow
  }
  Write-Host "[DryRun] Would run: verify-workspace.ps1" -ForegroundColor Yellow
  return
}

# --- 4. Restore from backup (reuse restore-workspace.ps1) ---
$restoreScript = Join-Path $PSScriptRoot 'restore-workspace.ps1'
if (Test-Path $restoreScript) {
  Write-Host "`n  [restore] Running restore-workspace.ps1...`n" -ForegroundColor Gray
  & $restoreScript -BackupPath $selectedBackup.FullName -WorkspaceRoot $WorkspaceRoot
} else {
  throw "restore-workspace.ps1 not found at $restoreScript"
}

# --- 5. Optionally revert last git commit ---
if ($RevertGitCommit) {
  Write-Host "`n  [git] Reverting last commit..." -ForegroundColor Gray
  $gitDir = Join-Path $WorkspaceRoot '.git'
  if (Test-Path $gitDir) {
    git -C $WorkspaceRoot revert HEAD --no-edit 2>&1 | ForEach-Object {
      Write-Host "    $_" -ForegroundColor DarkGray
    }
    if ($LASTEXITCODE -eq 0) {
      Write-Host "  [git] Last commit reverted" -ForegroundColor Green
    } else {
      Write-Host "  [git] Revert failed (exit $LASTEXITCODE) - check for conflicts" -ForegroundColor Yellow
    }
  } else {
    Write-Host "  [skip] No .git directory - skipping git revert" -ForegroundColor DarkGray
  }
}

# --- 6. Post-rollback verification ---
$verifyScript = Join-Path $PSScriptRoot 'verify-workspace.ps1'
if (Test-Path $verifyScript) {
  Write-Host "`n  [verify] Running integrity check...`n" -ForegroundColor Gray
  & $verifyScript -WorkspaceRoot $WorkspaceRoot
}

Write-Host "`n=== Rollback complete ===" -ForegroundColor Cyan
Write-Host "Restored from: $backupName" -ForegroundColor Green
if ($RevertGitCommit) {
  Write-Host "Git: last commit reverted" -ForegroundColor Green
}
Write-Host "`nNext steps:" -ForegroundColor Gray
Write-Host "  1. Review changes: git diff" -ForegroundColor White
Write-Host "  2. If satisfied: git push (if needed)" -ForegroundColor White
Write-Host "  3. If not satisfied: use restore-workspace.ps1 with a different backup" -ForegroundColor White
