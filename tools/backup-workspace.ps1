<#
.SYNOPSIS
  Backup harness workspace - snapshot .devin/, .agents/, HLK/, root config files.
.DESCRIPTION
  1. Snapshot critical harness directories + files
  2. Create zip with timestamp: backups/harness-backup-YYYYMMDD-HHMMSS.zip
  3. Compute SHA256 hash, store in backups/hashes.txt
  4. Rotate old backups (keep max 10)
.PARAMETER WorkspaceRoot
  Workspace root path. Default: current directory.
.EXAMPLE
  .\tools\backup-workspace.ps1
  .\tools\backup-workspace.ps1 -WorkspaceRoot D:\projects\my-app
#>
param(
  [string]$WorkspaceRoot = (Get-Location).Path
)

$ErrorActionPreference = 'Stop'

Write-Host "`n=== Backup Workspace ===" -ForegroundColor Cyan
Write-Host "Workspace: $WorkspaceRoot`n" -ForegroundColor Gray

# --- 1. Validate workspace ---
if (-not (Test-Path (Join-Path $WorkspaceRoot '.devin'))) {
  throw "Not a harness workspace: .devin/ not found at $WorkspaceRoot"
}

# --- 2. Create backup directory ---
$backupDir = Join-Path $WorkspaceRoot 'backups'
if (-not (Test-Path $backupDir)) {
  New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
}

# --- 3. Create temp staging directory ---
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$tempStage = Join-Path $env:TEMP "harness-backup-stage-$timestamp"
if (Test-Path $tempStage) { Remove-Item $tempStage -Recurse -Force }
New-Item -ItemType Directory -Path $tempStage -Force | Out-Null

# --- 4. Copy critical files/dirs to staging ---
$criticalPaths = @(
  '.devin',
  '.agents',
  'HLK',
  'AGENTS.md',
  'CLAUDE.md',
  'REPOS.md'
)

foreach ($relPath in $criticalPaths) {
  $src = Join-Path $WorkspaceRoot $relPath
  if (Test-Path $src) {
    $dest = Join-Path $tempStage $relPath
    $parent = Split-Path $dest -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Copy-Item $src $dest -Recurse -Force
    Write-Host "  [copied] $relPath" -ForegroundColor DarkGray
  } else {
    Write-Host "  [skip] $relPath (not found)" -ForegroundColor DarkGray
  }
}

# --- 5. Create zip ---
$zipPath = Join-Path $backupDir "harness-backup-$timestamp.zip"
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($tempStage, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)
Write-Host "`n  [created] $zipPath" -ForegroundColor Green

# --- 6. Compute SHA256 ---
$hash = (Get-FileHash $zipPath -Algorithm SHA256).Hash
$hashLine = "$hash  harness-backup-$timestamp.zip"
$hashesFile = Join-Path $backupDir 'hashes.txt'
Add-Content -Path $hashesFile -Value $hashLine -Encoding UTF8
Write-Host "  [sha256] $hash" -ForegroundColor DarkGray

# --- 7. Rotate old backups (keep max 10) ---
$backups = Get-ChildItem $backupDir -Filter 'harness-backup-*.zip' | Sort-Object LastWriteTime -Descending
if ($backups.Count -gt 10) {
  $old = $backups | Select-Object -Skip 10
  foreach ($oldBackup in $old) {
    Remove-Item $oldBackup.FullName -Force
    Write-Host "  [rotated] $($oldBackup.Name)" -ForegroundColor Yellow
  }
}

# --- 8. Cleanup staging ---
Remove-Item $tempStage -Recurse -Force -ErrorAction SilentlyContinue

$zipSize = [math]::Round((Get-Item $zipPath).Length / 1KB, 1)
Write-Host "`n=== Backup complete ===" -ForegroundColor Cyan
Write-Host "File: $zipPath ($zipSize KB)" -ForegroundColor Green
Write-Host "SHA256: $hash" -ForegroundColor Green
Write-Host "Backups retained: $((Get-ChildItem $backupDir -Filter 'harness-backup-*.zip').Count)/10" -ForegroundColor Gray
