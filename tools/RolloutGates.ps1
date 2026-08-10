<#
.SYNOPSIS
Rollout gates chung cho package-template.ps1 và init-new-project.ps1.

.DESCRIPTION
Tập trung hóa logic P1/P2/P3 để tránh duplicate code và drift.
- P1 Canary: pytest 100% + bench >=25% + red-team 0 critical.
- P2 Pilot  : E2E pass + user approval (interactive).
- P3 GA     : 7 ngày CI xanh + 0 P0/P1 bug (manual sign-off).

Trả về [PSCustomObject] với stage, passed, details để ghi vào manifest.
#>

function Invoke-RolloutGate {
  param(
    [Parameter(Mandatory)]
    [ValidateSet('P1','P2','P3')]
    [string]$Stage,

    [Parameter(Mandatory)]
    [string]$SourceRoot
  )

  Write-Host "`n=== Rollout Gate: $Stage ===" -ForegroundColor Magenta
  $gateOk = $true
  $gateDetails = [System.Collections.Generic.List[string]]::new()

  Push-Location $SourceRoot
  try {
    switch ($Stage) {
      'P1' {
        # pytest toàn bộ (P0 100%).
        Write-Host "  [P1] Running pytest (P0 must be 100%)..." -ForegroundColor Gray
        $pytestOut = & python -m pytest -q --no-header 2>&1 | Out-String
        $pytestExit = $LASTEXITCODE
        if ($pytestExit -ne 0) {
          Write-Host "  [P1] FAIL: pytest exited $pytestExit" -ForegroundColor Red
          $gateOk = $false
        } else {
          if ($pytestOut -match '(\d+) passed') {
            $passed = [int]$Matches[1]
            Write-Host "  [P1] OK: $passed tests passed" -ForegroundColor Green
            $gateDetails.Add("pytest: $passed passed")
          } else {
            Write-Host "  [P1] OK: pytest passed" -ForegroundColor Green
            $gateDetails.Add("pytest: pass")
          }
        }

        # Bench: token reduction >=25%.
        Write-Host "  [P1] Running bench (token reduction >=25%)..." -ForegroundColor Gray
        $benchOut = & python tests/bench_upgrade_success.py 2>&1 | Out-String
        $benchExit = $LASTEXITCODE
        if ($benchExit -ne 0) {
          Write-Host "  [P1] FAIL: bench exited $benchExit" -ForegroundColor Red
          $gateOk = $false
        } else {
          Write-Host "  [P1] OK: bench all metrics pass" -ForegroundColor Green
          $gateDetails.Add("bench: all pass")
        }

        # Red-team: 0 critical exploit.
        # Dùng --no-cov vì chỉ chạy 1 file; pytest.ini có cov-fail-under=80 sẽ fail khi coverage thấp.
        Write-Host "  [P1] Running red-team suite (0 critical exploit)..." -ForegroundColor Gray
        $rtOut = & python -m pytest tests/test_red_team_suite.py -q --no-header --no-cov 2>&1 | Out-String
        $rtExit = $LASTEXITCODE
        if ($rtExit -ne 0) {
          Write-Host "  [P1] FAIL: red-team suite exited $rtExit" -ForegroundColor Red
          $gateOk = $false
        } else {
          Write-Host "  [P1] OK: 0 critical exploit" -ForegroundColor Green
          $gateDetails.Add("red-team: 0 critical")
        }
      }

      'P2' {
        Write-Host "  [P2] Running E2E full-power test..." -ForegroundColor Gray
        $e2eOut = & python -m pytest tests/test_e2e_full_power.py -q --no-header --no-cov 2>&1 | Out-String
        $e2eExit = $LASTEXITCODE
        if ($e2eExit -ne 0) {
          Write-Host "  [P2] FAIL: E2E exited $e2eExit" -ForegroundColor Red
          $gateOk = $false
        } else {
          Write-Host "  [P2] OK: E2E pass" -ForegroundColor Green
          $gateDetails.Add("e2e: pass")
        }

        Write-Host "  [P2] User approval required for Pilot rollout." -ForegroundColor Yellow
        $resp = Read-Host "  [P2] Approve Pilot rollout? (y/N)"
        if ($resp -ne 'y' -and $resp -ne 'Y') {
          Write-Host "  [P2] FAIL: user did not approve" -ForegroundColor Red
          $gateOk = $false
        } else {
          Write-Host "  [P2] OK: user approved" -ForegroundColor Green
          $gateDetails.Add("user_approval: yes")
        }
      }

      'P3' {
        Write-Host "  [P3] GA requires: CI green for 7 consecutive days + 0 P0/P1 bugs." -ForegroundColor Yellow
        $resp = Read-Host "  [P3] Confirm CI green 7 days + 0 P0/P1 bugs? (y/N)"
        if ($resp -ne 'y' -and $resp -ne 'Y') {
          Write-Host "  [P3] FAIL: manual sign-off denied" -ForegroundColor Red
          $gateOk = $false
        } else {
          Write-Host "  [P3] OK: GA sign-off confirmed" -ForegroundColor Green
          $gateDetails.Add("ga_signoff: yes")
        }
      }
    }
  } finally {
    Pop-Location
  }

  if (-not $gateOk) {
    Write-Host "`n  [Rollout] Gate $Stage FAILED - abort." -ForegroundColor Red
    throw "Rollout gate $Stage failed. Fix issues before retry."
  }

  Write-Host "  [Rollout] Gate $Stage PASSED." -ForegroundColor Green
  return [PSCustomObject]@{
    stage   = $Stage
    passed  = $true
    details = $gateDetails -join '; '
  }
}
