#requires -Version 5.1
<#
.SYNOPSIS
    HLK Upstream Sync — Windows PowerShell v2.1.0

.DESCRIPTION
    Đồng bộ từ upstream Ruflo mà KHÔNG làm mất lớp HLK.

.EXAMPLE
    .\HLK\wrappers\git-upstream-sync.ps1
    .\HLK\wrappers\git-upstream-sync.ps1 -DryRun
#>

$ErrorActionPreference = "Stop"

$UpstreamUrl = "https://github.com/ruvnet/ruflo.git"
$UpstreamRemote = "upstream"
$TargetBranch = "main"
$DryRun = $args -contains "-DryRun" -or $args -contains "--dry-run"

# ---------------------------------------------------------------------------
# Bước 1: Kiểm tra / thêm remote upstream
# ---------------------------------------------------------------------------

Write-Host "[HLK UPSTREAM SYNC] 🔄 Kiểm tra Git remote..."
$remotes = git remote
if (-not ($remotes -contains $UpstreamRemote)) {
    Write-Host "[HLK UPSTREAM SYNC] ➕ Thêm remote upstream: $UpstreamUrl"
    git remote add $UpstreamRemote $UpstreamUrl
} else {
    git remote set-url $UpstreamRemote $UpstreamUrl
}

# ---------------------------------------------------------------------------
# Bước 2: Fetch upstream
# ---------------------------------------------------------------------------

Write-Host "[HLK UPSTREAM SYNC] 📥 Fetching từ upstream..."
git fetch $UpstreamRemote

# ---------------------------------------------------------------------------
# Bước 3: Dry-run
# ---------------------------------------------------------------------------

if ($DryRun) {
    Write-Host "[HLK UPSTREAM SYNC] 🧪 DRY-RUN — thống kê thay đổi:"
    git diff --stat HEAD.."$UpstreamRemote/$TargetBranch"
    exit 0
}

# ---------------------------------------------------------------------------
# Bước 4: Backup HLK config
# ---------------------------------------------------------------------------

$backupDir = "HLK/logs"
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$backupFile = "$backupDir/hlk.config.json.backup.$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
Copy-Item HLK/config/hlk.config.json $backupFile
Write-Host "[HLK UPSTREAM SYNC] 💾 Backup config → $backupFile"

# ---------------------------------------------------------------------------
# Bước 5: Merge
# ---------------------------------------------------------------------------

git merge "$UpstreamRemote/$TargetBranch" --no-ff -m "chore: merge updates from upstream ruflo"

# ---------------------------------------------------------------------------
# Bước 6: Kiểm tra tính toàn vẹn HLK
# ---------------------------------------------------------------------------

Write-Host "[HLK UPSTREAM SYNC] 🔍 Kiểm tra tính toàn vẹn HLK..."
node HLK/wrappers/hlk-verify-integrity.js

# ---------------------------------------------------------------------------
# Bước 7: Ghi log
# ---------------------------------------------------------------------------

$logFile = "$backupDir/upstream-sync.$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
@(
    "Upstream sync completed at $(Get-Date -Format 'o')"
    "Upstream commit: $(git rev-parse "$UpstreamRemote/$TargetBranch")"
    "Backup config: $backupFile"
) | Out-File -FilePath $logFile -Encoding utf8

Write-Host "[HLK UPSTREAM SYNC] ✅ Hoàn tất! Log: $logFile"
