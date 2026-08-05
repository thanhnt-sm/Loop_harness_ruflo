#!/usr/bin/env pwsh
<#
.SYNOPSIS
  U22: Cleanup orphaned session_state files not in registry.

.DESCRIPTION
  Scans .devin/session_state/ for .json files, checks each against
  .devin/loop_state.md registry. Files not in registry AND older than
  7 days are deleted. Outputs a cleanup report.

.PARAMETER DryRun
  If set, report what would be cleaned without deleting.

.PARAMETER MaxAge
  Maximum age in days before orphan is deleted. Default: 7.

.EXAMPLE
  pwsh tools/cleanup-orphan-sessions.ps1
  pwsh tools/cleanup-orphan-sessions.ps1 -DryRun
  pwsh tools/cleanup-orphan-sessions.ps1 -MaxAge 14
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [int]$MaxAge = 7
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$sessionStateDir = Join-Path $repoRoot ".devin\session_state"
$registryPath = Join-Path $repoRoot ".devin\loop_state.md"
$archiveDir = Join-Path $repoRoot ".devin\loop_state_archive"

# --- Parse registry to get known session IDs ---
$knownSessions = @{}
if (Test-Path $registryPath) {
    $registryContent = Get-Content $registryPath -Encoding UTF8
    foreach ($line in $registryContent) {
        # Match table rows: | session_id | ... |
        if ($line -match '^\|\s*([a-zA-Z0-9_-]+)\s*\|') {
            $sid = $matches[1]
            if ($sid -notin @("session_id", "---", "Active", "Completed", "Recent")) {
                $knownSessions[$sid] = $true
            }
        }
    }
}

Write-Host "== U22: Orphan Session Cleanup ==" -ForegroundColor Cyan
Write-Host ""
Write-Host "Session state dir: $sessionStateDir"
Write-Host "Registry:          $registryPath"
Write-Host "Known sessions:    $($knownSessions.Count)"
Write-Host "Max age:           $MaxAge days"
if ($DryRun) {
    Write-Host "Mode:              DRY RUN (no deletion)" -ForegroundColor Yellow
} else {
    Write-Host "Mode:              DELETE" -ForegroundColor Red
}
Write-Host ""

# --- Scan session_state directory ---
if (-not (Test-Path $sessionStateDir)) {
    Write-Host "[OK] Session state directory does not exist. Nothing to clean." -ForegroundColor Green
    exit 0
}

$sessionFiles = Get-ChildItem -Path $sessionStateDir -Filter "*.json" -File
Write-Host "Found $($sessionFiles.Count) session_state files."

$orphans = @()
$kept = @()
$now = Get-Date

foreach ($file in $sessionFiles) {
    $sid = $file.BaseName  # session ID = filename without .json

    # Check if in registry
    if ($knownSessions.ContainsKey($sid)) {
        $kept += [PSCustomObject]@{
            SessionId = $sid
            File = $file.Name
            Age = ((($now - $file.LastWriteTime).TotalDays).ToString("F1") + " days")
            Status = "in_registry"
        }
        continue
    }

    # Check age
    $ageDays = ($now - $file.LastWriteTime).TotalDays
    if ($ageDays -gt $MaxAge) {
        $orphans += [PSCustomObject]@{
            SessionId = $sid
            File = $file.Name
            Age = ("{0:F1} days" -f $ageDays)
            Status = "orphan_expired"
            Path = $file.FullName
            Size = $file.Length
        }
    } else {
        $kept += [PSCustomObject]@{
            SessionId = $sid
            File = $file.Name
            Age = ("{0:F1} days" -f $ageDays)
            Status = "orphan_recent"
        }
    }
}

# --- Also scan session_state subdirectories (per-session dirs) ---
$sessionDirs = Get-ChildItem -Path $sessionStateDir -Directory -ErrorAction SilentlyContinue
foreach ($dir in $sessionDirs) {
    $sid = $dir.Name
    if ($knownSessions.ContainsKey($sid)) {
        continue
    }
    $ageDays = ($now - $dir.LastWriteTime).TotalDays
    if ($ageDays -gt $MaxAge) {
        $orphans += [PSCustomObject]@{
            SessionId = $sid
            File = "$sid/ (directory)"
            Age = ("{0:F1} days" -f $ageDays)
            Status = "orphan_dir_expired"
            Path = $dir.FullName
            Size = (Get-ChildItem $dir.FullName -Recurse -File | Measure-Object -Property Length -Sum).Sum
        }
    }
}

# --- Report ---
Write-Host ""
Write-Host "== Cleanup Report ==" -ForegroundColor Cyan
Write-Host ""

if ($orphans.Count -eq 0) {
    Write-Host "[OK] No orphaned sessions found." -ForegroundColor Green
} else {
    Write-Host "[!] Found $($orphans.Count) orphaned session(s):" -ForegroundColor Yellow
    $orphans | Format-Table SessionId, Age, Status, Size -AutoSize

    if (-not $DryRun) {
        # Create archive directory if it doesn't exist
        if (-not (Test-Path $archiveDir)) {
            New-Item -ItemType Directory -Path $archiveDir -Force | Out-Null
        }

        $deleted = 0
        $archived = 0
        foreach ($orphan in $orphans) {
            try {
                if ($orphan.Status -eq "orphan_dir_expired") {
                    # Archive directory then delete
                    $archivePath = Join-Path $archiveDir "$($orphan.SessionId).zip"
                    if (Test-Path $orphan.Path) {
                        Compress-Archive -Path "$($orphan.Path)\*" -DestinationPath $archivePath -Force
                        Remove-Item $orphan.Path -Recurse -Force
                        $archived++
                    }
                } else {
                    # Archive file then delete
                    $archivePath = Join-Path $archiveDir "$($orphan.SessionId).json"
                    if (Test-Path $orphan.Path) {
                        Copy-Item $orphan.Path $archivePath -Force
                        Remove-Item $orphan.Path -Force
                        $archived++
                    }
                }
                $deleted++
            } catch {
                Write-Host "[ERROR] Failed to clean $($orphan.SessionId): $_" -ForegroundColor Red
            }
        }
        Write-Host ""
        Write-Host "[DONE] Deleted: $deleted, Archived: $archived" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "[DRY RUN] Would delete $($orphans.Count) orphan(s)." -ForegroundColor Yellow
    }
}

if ($kept.Count -gt 0) {
    Write-Host ""
    Write-Host "Kept sessions ($($kept.Count)):" -ForegroundColor Gray
    $kept | Format-Table SessionId, Age, Status -AutoSize
}

Write-Host ""
Write-Host "== Cleanup Complete ==" -ForegroundColor Cyan
