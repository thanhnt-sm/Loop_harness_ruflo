<#
.SYNOPSIS
  Restore harness workspace from backup zip.
.DESCRIPTION
  1. Verify SHA256 hash before restore
  2. Restore .devin/, .agents/, HLK/, root config files
  3. Do NOT overwrite src/, tests/ (user source code)
  4. Post-restore: run verify-workspace.ps1
.PARAMETER BackupPath
  Path to backup zip. If not specified, use -Latest.
.PARAMETER Latest
  Restore most recent backup.
.PARAMETER WorkspaceRoot
  Workspace root path. Default: current directory.
.PARAMETER DryRun
  Show what would be restored without making changes.
.EXAMPLE
  .\tools\restore-workspace.ps1 -Latest
  .\tools\restore-workspace.ps1 -BackupPath .\backups\harness-backup-20260707-120000.zip
  .\tools\restore-workspace.ps1 -Latest -DryRun
#>
param(
  [string]$BackupPath,
  [switch]$Latest,
  [string]$WorkspaceRoot = (Get-Location).Path,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

Write-Host "`n=== Restore Workspace ===" -ForegroundColor Cyan

# --- 1. Determine backup path ---
if ($Latest -and -not $BackupPath) {
  $backupDir = Join-Path $WorkspaceRoot 'backups'
  if (-not (Test-Path $backupDir)) {
    throw "No backups directory found at $backupDir"
  }
  $latestBackup = Get-ChildItem $backupDir -Filter 'harness-backup-*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if (-not $latestBackup) {
    throw "No backups found in $backupDir"
  }
  $BackupPath = $latestBackup.FullName
  Write-Host "Using latest backup: $($latestBackup.Name)`n" -ForegroundColor Gray
} elseif (-not $BackupPath) {
  throw "Specify either -BackupPath <path> or -Latest"
}

if (-not (Test-Path $BackupPath)) {
  throw "Backup not found: $BackupPath"
}

Write-Host "Backup: $BackupPath" -ForegroundColor Gray
Write-Host "Target: $WorkspaceRoot`n" -ForegroundColor Gray

if ($DryRun) {
  Write-Host "[DryRun] No changes will be made.`n" -ForegroundColor Yellow
}

# --- 2. Verify SHA256 hash ---
$backupName = Split-Path $BackupPath -Leaf
$hashesFile = Join-Path $WorkspaceRoot 'backups\hashes.txt'
if (Test-Path $hashesFile) {
  $expectedHash = $null
  foreach ($line in Get-Content $hashesFile) {
    if ($line -match "^\s*([A-Fa-f0-9]{64})\s+$([regex]::Escape($backupName))") {
      $expectedHash = $Matches[1]
      break
    }
  }
  if ($expectedHash) {
    $actualHash = (Get-FileHash $BackupPath -Algorithm SHA256).Hash
    if ($actualHash -ne $expectedHash) {
      throw "SHA256 mismatch! Expected: $expectedHash, Actual: $actualHash - backup may be corrupted"
    }
    Write-Host "  [verified] SHA256 match: $actualHash" -ForegroundColor Green
  } else {
    Write-Host "  [warn] No hash entry for $backupName - skipping verification" -ForegroundColor Yellow
  }
} else {
  Write-Host "  [warn] hashes.txt not found - skipping verification" -ForegroundColor Yellow
}

if ($DryRun) {
  Write-Host "`n[DryRun] Would restore from: $BackupPath" -ForegroundColor Yellow
  Write-Host "[DryRun] Would extract to: $WorkspaceRoot" -ForegroundColor Yellow
  Write-Host "[DryRun] Would NOT overwrite: src/, tests/" -ForegroundColor Yellow
  return
}

# --- 3. Extract to temp ---
$tempExtract = Join-Path $env:TEMP "harness-restore-$(Get-Date -Format 'yyyyMMddHHmmss')"
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
New-Item -ItemType Directory -Path $tempExtract -Force | Out-Null

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($BackupPath, $tempExtract)
Write-Host "  [extracted] to temp" -ForegroundColor DarkGray

# --- 4. Restore files (do NOT overwrite src/, tests/) ---
$protectedDirs = @('src', 'tests', 'node_modules', '.git')
$restoredCount = 0

$items = Get-ChildItem $tempExtract -Force
foreach ($item in $items) {
  # Skip protected directories
  if ($item.PSIsContainer -and $protectedDirs -contains $item.Name) {
    Write-Host "  [protected] $($item.Name) - skipped" -ForegroundColor Yellow
    continue
  }

  $dest = Join-Path $WorkspaceRoot $item.Name
  if ($item.PSIsContainer) {
    # Merge directory
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
  $restoredCount++
  Write-Host "  [restored] $($item.Name)" -ForegroundColor DarkGray
}

# --- 5. Cleanup temp ---
Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "`n  [done] Restored $restoredCount items" -ForegroundColor Green

# --- 6. Post-restore verification ---
$verifyScript = Join-Path $PSScriptRoot 'verify-workspace.ps1'
if (Test-Path $verifyScript) {
  Write-Host "`n  [verify] Running integrity check...`n" -ForegroundColor Gray
  & $verifyScript -WorkspaceRoot $WorkspaceRoot
}

Write-Host "`n=== Restore complete ===" -ForegroundColor Cyan
Write-Host "Restored from: $BackupPath" -ForegroundColor Green
Write-Host "Protected dirs (not overwritten): $($protectedDirs -join ', ')" -ForegroundColor Gray
