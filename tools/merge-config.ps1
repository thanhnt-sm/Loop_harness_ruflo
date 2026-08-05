#!/usr/bin/env pwsh
<#
.SYNOPSIS
  U36: Automated config merge with conflict resolution.

.DESCRIPTION
  Merges two .devin/config.json files. Auto-merges non-conflicting sections,
  prompts human for conflicts.

.PARAMETER Base
  Base config file path (current/destination).

.PARAMETER Source
  Source config file path (incoming/new).

.PARAMETER Output
  Output file path. Defaults to Base path (in-place merge).

.EXAMPLE
  pwsh tools/merge-config.ps1 -Base .devin/config.json -Source .devin/config.new.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$Base,

    [Parameter(Mandatory)]
    [string]$Source,

    [string]$Output
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Base)) { Write-Error "Base config not found: $Base"; exit 1 }
if (-not (Test-Path $Source)) { Write-Error "Source config not found: $Source"; exit 1 }

if (-not $Output) { $Output = $Base }

$baseCfg = Get-Content $Base -Raw | ConvertFrom-Json -AsHashtable
$srcCfg = Get-Content $Source -Raw | ConvertFrom-Json -AsHashtable

$conflicts = @()
$merged = @{}

# U36: Auto-merge non-conflicting sections
foreach ($key in $srcCfg.Keys) {
    if (-not $baseCfg.ContainsKey($key)) {
        # Key only in source — add it
        $merged[$key] = $srcCfg[$key]
        Write-Host "[ADD] $key — new key from source" -ForegroundColor Green
    }
    elseif ($baseCfg[$key] -eq $srcCfg[$key]) {
        # Same value — keep
        $merged[$key] = $baseCfg[$key]
    }
    else {
        # Conflict — check type
        $baseVal = $baseCfg[$key]
        $srcVal = $srcCfg[$key]

        if ($baseVal -is [array] -and $srcVal -is [array]) {
            # Arrays: merge unique items
            $combined = @()
            $combined += $baseVal
            foreach ($item in $srcVal) {
                if ($item -notin $combined) {
                    $combined += $item
                    Write-Host "[MERGE] $key + item: $item" -ForegroundColor Cyan
                }
            }
            $merged[$key] = $combined
        }
        elseif ($baseVal -is [hashtable] -and $srcVal -is [hashtable]) {
            # Nested objects: recursive merge
            $nestedMerged = @{}
            $nestedConflicts = @()
            foreach ($nk in $srcVal.Keys) {
                if (-not $baseVal.ContainsKey($nk)) {
                    $nestedMerged[$nk] = $srcVal[$nk]
                }
                elseif ($baseVal[$nk] -eq $srcVal[$nk]) {
                    $nestedMerged[$nk] = $baseVal[$nk]
                }
                else {
                    $nestedConflicts += [PSCustomObject]@{
                        Path = "$key.$nk"
                        Base = $baseVal[$nk]
                        Source = $srcVal[$nk]
                    }
                }
            }
            # Add base-only nested keys
            foreach ($nk in $baseVal.Keys) {
                if (-not $nestedMerged.ContainsKey($nk)) {
                    $nestedMerged[$nk] = $baseVal[$nk]
                }
            }
            $merged[$key] = $nestedMerged
            $conflicts += $nestedConflicts
        }
        else {
            # Scalar conflict
            $conflicts += [PSCustomObject]@{
                Path = $key
                Base = $baseVal
                Source = $srcVal
            }
        }
    }
}

# Add base-only keys
foreach ($key in $baseCfg.Keys) {
    if (-not $merged.ContainsKey($key)) {
        $merged[$key] = $baseCfg[$key]
    }
}

# U36: Conflict detection → human prompt
if ($conflicts.Count -gt 0) {
    Write-Host ""
    Write-Host "[CONFLICT] $($conflicts.Count) conflict(s) detected:" -ForegroundColor Yellow
    $i = 0
    foreach ($c in $conflicts) {
        $i++
        Write-Host ""
        Write-Host "  Conflict $i : $($c.Path)" -ForegroundColor Yellow
        Write-Host "    Base  : $($c.Base)" -ForegroundColor White
        Write-Host "    Source: $($c.Source)" -ForegroundColor White
    }

    Write-Host ""
    $choice = Read-Host "Resolve conflicts: (b)ase, (s)ource, (m)anual, (a)bort? [b/s/m/a]"

    switch ($choice.ToLower()) {
        'b' {
            foreach ($c in $conflicts) {
                $parts = $c.Path -split '\.'
                if ($parts.Count -eq 1) {
                    $merged[$c.Path] = $c.Base
                }
                Write-Host "[RESOLVE] $($c.Path) → base value" -ForegroundColor Green
            }
        }
        's' {
            foreach ($c in $conflicts) {
                $parts = $c.Path -split '\.'
                if ($parts.Count -eq 1) {
                    $merged[$c.Path] = $c.Source
                }
                Write-Host "[RESOLVE] $($c.Path) → source value" -ForegroundColor Green
            }
        }
        'm' {
            Write-Host "Manual mode: edit $Output manually after merge." -ForegroundColor Yellow
            Write-Host "Conflicts will be kept as base values. Edit after." -ForegroundColor Yellow
        }
        'a' {
            Write-Host "Merge aborted." -ForegroundColor Red
            exit 1
        }
        default {
            Write-Host "Invalid choice. Aborting." -ForegroundColor Red
            exit 1
        }
    }
}

# Write merged config
$mergedJson = $merged | ConvertTo-Json -Depth 10
Set-Content -Path $Output -Value $mergedJson -Encoding UTF8

Write-Host ""
Write-Host "[DONE] Merged config written to: $Output" -ForegroundColor Green
Write-Host "  Keys: $($merged.Count)" -ForegroundColor Green
if ($conflicts.Count -gt 0) {
    Write-Host "  Conflicts resolved: $($conflicts.Count)" -ForegroundColor Green
}
exit 0
