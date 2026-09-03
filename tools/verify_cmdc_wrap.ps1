$ErrorActionPreference = 'Stop'

# Validate JSON
foreach ($f in @('.commandcode/settings.json', '.mcp.json')) {
    try {
        Get-Content $f -Raw | ConvertFrom-Json | Out-Null
        Write-Host "$f OK"
    } catch {
        Write-Host "$f INVALID: $_"
    }
}

# Count cmdc files
$cmdcCount = (Get-ChildItem -Recurse .commandcode -File | Where-Object { $_.Name -ne 'taste.md' }).Count
Write-Host ""
Write-Host "=== cmdc files (excluding taste): $cmdcCount ==="

# List docs
Write-Host ""
Write-Host "=== New docs ==="
foreach ($f in @('docs/reports/CMDC_FULL_GUIDE.md', 'docs/CMDC_QUICKREF.md', 'docs/reports/CMDC_WRAP_REPORT.md', 'docs/reports/HARNESS_UPGRADE_REPORT.md', '.mcp.json')) {
    if (Test-Path $f) {
        $rel = (Resolve-Path $f).Path.Substring($PWD.Path.Length + 1)
        $len = (Get-Content $f -Raw).Length
        Write-Host ("  {0,-50} {1,8} bytes" -f $rel, $len)
    }
}
