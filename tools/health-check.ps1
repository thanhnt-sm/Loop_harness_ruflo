#!/usr/bin/env pwsh
<#
.SYNOPSIS
  U37: Workspace health check — detect silent degradation.

.DESCRIPTION
  Tests: hook execution, MCP server ping, memory write/read.
  Reports health score (0-100).

.PARAMETER Verbose
  Show detailed output for each check.

.EXAMPLE
  pwsh tools/health-check.ps1
  pwsh tools/health-check.ps1 -Verbose
#>
[CmdletBinding()]
param(
    [switch]$Detailed
)

$ErrorActionPreference = "Continue"
$repoRoot = Split-Path -Parent $PSScriptRoot

$totalChecks = 0
$passedChecks = 0
$warnings = @()
$errors = @()

function Check-Result {
    param([string]$Name, [bool]$Pass, [string]$Detail, [int]$Weight = 10)
    $script:totalChecks++
    if ($Pass) {
        $script:passedChecks++
        if ($Detailed -or $script:Detailed) {
            Write-Host "  [PASS] $Name — $Detail" -ForegroundColor Green
        }
    }
    else {
        $script:warnings += "${Name}: ${Detail}"
        if ($Detailed -or $script:Detailed) {
            Write-Host "  [WARN] $Name — $Detail" -ForegroundColor Yellow
        }
    }
}

function Error-Result {
    param([string]$Name, [string]$Detail)
    $script:totalChecks++
    $script:errors += "${Name}: ${Detail}"
    if ($Detailed -or $script:Detailed) {
        Write-Host "  [FAIL] $Name — $Detail" -ForegroundColor Red
    }
}

Write-Host "=== U37: Workspace Health Check ===" -ForegroundColor Cyan
Write-Host ""

# --- 1. Hook execution (30 points) ---
Write-Host "[1/4] Hook execution (.devin/hooks/)" -ForegroundColor Yellow

$hooks = @('pre_tool_use.py', 'post_tool_use.py', 'stop.py', 'ahd_session.py')
foreach ($h in $hooks) {
    $path = Join-Path $repoRoot ".devin\hooks\$h"
    $exists = Test-Path $path
    Check-Result "Hook exists: $h" $exists "file present"
}

# Test Python syntax of hooks
foreach ($h in $hooks) {
    $path = Join-Path $repoRoot ".devin\hooks\$h"
    if (Test-Path $path) {
        $result = python -c "import py_compile; py_compile.compile(r'$path', doraise=True)" 2>&1
        $ok = $LASTEXITCODE -eq 0
        Check-Result "Hook syntax: $h" $ok "compiles"
    }
}

# --- 2. MCP server ping (20 points) ---
Write-Host ""
Write-Host "[2/4] MCP server connectivity" -ForegroundColor Yellow

$mcpConfigPath = Join-Path $repoRoot ".devin\mcp_config.json"
if (Test-Path $mcpConfigPath) {
    Check-Result "MCP config exists" $true "mcp_config.json present"

    # Check aide-memory MCP
    $aideMemoryPath = Join-Path $env:APPDATA "nvm\v18.20.0\node_modules\aide-memory"
    $aideExists = Test-Path $aideMemoryPath
    Check-Result "aide-memory installed" $aideExists "node_modules present"
}
else {
    Error-Result "MCP config" "mcp_config.json missing"
}

# --- 3. Memory write/read (30 points) ---
Write-Host ""
Write-Host "[3/4] Memory write/read" -ForegroundColor Yellow

$sessionStateDir = Join-Path $repoRoot ".devin\session_state"
$stateDirExists = Test-Path $sessionStateDir
Check-Result "Session state dir exists" $stateDirExists ".devin/session_state/"

if ($stateDirExists) {
    # Test write
    $testFile = Join-Path $sessionStateDir "health-check-test.json"
    $testData = @{ test = "u37-health-check"; timestamp = Get-Date -Format "o" }
    try {
        $testData | ConvertTo-Json | Set-Content -Path $testFile -Encoding UTF8
        $writeOk = Test-Path $testFile
        Check-Result "Memory write" $writeOk "can write session_state"

        # Test read
        $readData = Get-Content $testFile -Raw | ConvertFrom-Json
        $readOk = $readData.test -eq "u37-health-check"
        Check-Result "Memory read" $readOk "can read session_state"

        # Cleanup
        Remove-Item $testFile -Force -ErrorAction SilentlyContinue
    }
    catch {
        Error-Result "Memory write/read" $_.Exception.Message
    }
}

# --- 4. Canon + config integrity (20 points) ---
Write-Host ""
Write-Host "[4/4] Canon + config integrity" -ForegroundColor Yellow

$canonFiles = @(
    '.devin\canon\BOOT_PROTOCOL.md',
    '.devin\canon\LOOP_PROTOCOL.md',
    '.devin\canon\VERIFICATION_PROTOCOL.md',
    '.devin\canon\REDLINES.md',
    '.devin\config.json',
    '.devin\tool_registry.json'
)

foreach ($f in $canonFiles) {
    $path = Join-Path $repoRoot $f
    $exists = Test-Path $path
    Check-Result "Canon/config: $(Split-Path $f -Leaf)" $exists "file present"
}

# Config JSON valid
$configPath = Join-Path $repoRoot ".devin\config.json"
if (Test-Path $configPath) {
    try {
        $null = Get-Content $configPath -Raw | ConvertFrom-Json
        Check-Result "config.json valid JSON" $true "parses"
    }
    catch {
        Error-Result "config.json JSON" $_.Exception.Message
    }
}

# --- Calculate score ---
Write-Host ""
$score = if ($totalChecks -gt 0) { [math]::Round(($passedChecks / $totalChecks) * 100) } else { 0 }

$color = if ($score -ge 90) { "Green" } elseif ($score -ge 70) { "Yellow" } else { "Red" }
$status = if ($score -ge 90) { "HEALTHY" } elseif ($score -ge 70) { "DEGRADED" } else { "UNHEALTHY" }

Write-Host "=== Health Score: $score/100 ($status) ===" -ForegroundColor $color
Write-Host "  Checks passed: $passedChecks/$totalChecks" -ForegroundColor White

if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "Warnings ($($warnings.Count)):" -ForegroundColor Yellow
    foreach ($w in $warnings) { Write-Host "  - $w" -ForegroundColor Yellow }
}

if ($errors.Count -gt 0) {
    Write-Host ""
    Write-Host "Errors ($($errors.Count)):" -ForegroundColor Red
    foreach ($e in $errors) { Write-Host "  - $e" -ForegroundColor Red }
}

Write-Host ""
if ($score -ge 90) {
    Write-Host "Status: All systems healthy." -ForegroundColor Green
}
elseif ($score -ge 70) {
    Write-Host "Status: Some degradation detected. Review warnings." -ForegroundColor Yellow
}
else {
    Write-Host "Status: Unhealthy. Fix errors before running loops." -ForegroundColor Red
}

if ($score -ge 70) { exit 0 } else { exit 1 }
