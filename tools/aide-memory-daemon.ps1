#!/usr/bin/env pwsh
<#
.SYNOPSIS
  U38: Manage aide-memory MCP daemon lifecycle.

.DESCRIPTION
  Start, stop, status check for aide-memory daemon.
  Interim wrapper approach — spawns aide-memory as persistent process.

.PARAMETER Action
  start | stop | status | restart

.EXAMPLE
  pwsh tools/aide-memory-daemon.ps1 start
  pwsh tools/aide-memory-daemon.ps1 status
  pwsh tools/aide-memory-daemon.ps1 stop
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('start', 'stop', 'status', 'restart')]
    [string]$Action
)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $repoRoot ".devin\tmp\aide-memory-daemon.pid"
$logFile = Join-Path $repoRoot ".devin\tmp\aide-memory-daemon.log"

# Phát hiện aide-memory path động thay vì hardcode version nvm.
$npmRoot = (npm root -g 2>$null)
if ($npmRoot) { $npmRoot = $npmRoot.Trim() }
if (-not $npmRoot) {
  $nodeExe = (Get-Command node -ErrorAction SilentlyContinue).Source
  if ($nodeExe) {
    $nodeDir = Split-Path $nodeExe -Parent
    $npmRoot = Join-Path (Split-Path $nodeDir -Parent) 'node_modules'
  }
}
$aideMemoryPath = Join-Path $npmRoot 'aide-memory'

function Get-DaemonPid {
    if (Test-Path $pidFile) {
        $pid_val = Get-Content $pidFile -Raw
        $proc = Get-Process -Id $pid_val -ErrorAction SilentlyContinue
        if ($proc) { return [int]$pid_val }
        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
    return $null
}

switch ($Action) {
    'start' {
        if (Get-DaemonPid) {
            Write-Host "[OK] Daemon already running (PID $(Get-DaemonPid))" -ForegroundColor Green
            exit 0
        }

        if (-not (Test-Path $aideMemoryPath)) {
            Write-Host "[ERROR] aide-memory not found at: $aideMemoryPath" -ForegroundColor Red
            exit 1
        }

        Write-Host "[START] Launching aide-memory daemon..." -ForegroundColor Cyan

        # U38: Interim approach — spawn aide-memory MCP server as background process
        # Full daemon mode requires upstream support (see DAEMON_PROTOCOL.md)
        $daemonScript = Join-Path $aideMemoryPath "src\mcp-server.js"
        if (-not (Test-Path $daemonScript)) {
            $daemonScript = Join-Path $aideMemoryPath "index.js"
        }

        if (Test-Path $daemonScript) {
            $proc = Start-Process -FilePath "node" -ArgumentList $daemonScript `
                -WindowStyle Hidden -PassThru `
                -RedirectStandardOutput $logFile `
                -RedirectStandardError "$logFile.err"

            $proc.Id | Set-Content -Path $pidFile -Encoding UTF8
            Write-Host "[OK] Daemon started (PID $($proc.Id))" -ForegroundColor Green
            Write-Host "  Log: $logFile" -ForegroundColor White
        }
        else {
            Write-Host "[WARN] Daemon script not found. Documented in DAEMON_PROTOCOL.md" -ForegroundColor Yellow
            Write-Host "  aide-memory daemon mode requires upstream support." -ForegroundColor Yellow
            Write-Host "  Architecture documented in .devin/canon/DAEMON_PROTOCOL.md" -ForegroundColor Yellow
        }
    }

    'stop' {
        $pid_val = Get-DaemonPid
        if ($pid_val) {
            Stop-Process -Id $pid_val -Force -ErrorAction SilentlyContinue
            Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
            Write-Host "[OK] Daemon stopped (PID $pid_val)" -ForegroundColor Green
        }
        else {
            Write-Host "[WARN] Daemon not running" -ForegroundColor Yellow
        }
    }

    'status' {
        $pid_val = Get-DaemonPid
        if ($pid_val) {
            $proc = Get-Process -Id $pid_val -ErrorAction SilentlyContinue
            if ($proc) {
                $uptime = (Get-Date) - $proc.StartTime
                Write-Host "[OK] Daemon running" -ForegroundColor Green
                Write-Host "  PID: $pid_val" -ForegroundColor White
                Write-Host "  Uptime: $($uptime.ToString('hh\:mm\:ss'))" -ForegroundColor White
                Write-Host "  Memory: $([math]::Round($proc.WorkingSet64 / 1MB, 1)) MB" -ForegroundColor White
            }
            else {
                Write-Host "[WARN] PID file exists but process dead" -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "[INFO] Daemon not running" -ForegroundColor Cyan
            Write-Host "  Start with: pwsh tools/aide-memory-daemon.ps1 start" -ForegroundColor White
        }
    }

    'restart' {
        & $PSCommandPath -Action stop
        Start-Sleep -Seconds 1
        & $PSCommandPath -Action start
    }
}
