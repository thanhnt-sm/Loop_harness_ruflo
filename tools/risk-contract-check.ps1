#!/usr/bin/env pwsh
<#
.SYNOPSIS
  U28: Pre-commit hook — validate risk contracts before commit.

.DESCRIPTION
  Checks .devin/risk_contract.json for critical file modifications.
  Blocks commit if forbidden changes detected.

.EXAMPLE
  pwsh tools/risk-contract-check.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$contractPath = Join-Path $repoRoot ".devin\risk_contract.json"

if (-not (Test-Path $contractPath)) {
    Write-Host "[OK] No risk contract found. Skipping." -ForegroundColor Green
    exit 0
}

$contract = Get-Content $contractPath -Raw | ConvertFrom-Json
$stagedFiles = git diff --cached --name-only 2>$null

if (-not $stagedFiles) {
    Write-Host "[OK] No staged files. Skipping." -ForegroundColor Green
    exit 0
}

$violations = @()

foreach ($file in $stagedFiles) {
    $normalizedFile = $file -replace '/', '\'

    # Check if file is in critical_files
    $criticalFile = $null
    foreach ($key in $contract.critical_files.PSObject.Properties.Name) {
        if ($normalizedFile -like $key) {
            $criticalFile = $contract.critical_files.$key
            break
        }
    }

    if ($criticalFile) {
        Write-Host "[CHECK] Critical file staged: $file (risk: $($criticalFile.risk))" -ForegroundColor Yellow

        # Check forbidden changes via diff
        $diff = git diff --cached -- "$file" 2>$null

        foreach ($forbidden in $criticalFile.forbidden_changes) {
            # Simple heuristic: check if diff contains removal of patterns
            # that match forbidden changes
            if ($diff -match "^\-.*$forbidden" -or $diff -match "^\+.*$forbidden") {
                $violations += [PSCustomObject]@{
                    File = $file
                    Violation = "Forbidden change detected: $forbidden"
                    Risk = $criticalFile.risk
                }
            }
        }

        # Warn about critical file modification
        if ($criticalFile.required_review -eq "human") {
            Write-Host "[WARN] $file requires human review (risk: $($criticalFile.risk))" -ForegroundColor Yellow
        }
    }
}

if ($violations.Count -gt 0) {
    Write-Host ""
    Write-Host "[BLOCK] Risk contract violations detected:" -ForegroundColor Red
    $violations | Format-Table File, Violation, Risk -AutoSize
    Write-Host ""
    Write-Host "Commit blocked. Review violations and fix before committing." -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Risk contract check passed. No violations." -ForegroundColor Green
exit 0
