<# tools/cline-toggle-rules.ps1
.Bật / tắt toàn bộ rules layer (.clinerules/) của workspace cho Cline.
.Dùng:  pwsh tools/cline-toggle-rules.ps1 [on|off|status|toggle]   (mặc định status)
.Exit: 0 = ok, 1 = lỗi.
#>
param([ValidateSet('on','off','status','toggle')][string]$Action = 'status')

$Root   = Split-Path $PSScriptRoot -Parent
$Rules  = Join-Path $Root '.clinerules'
$Off    = Join-Path $Root '.clinerules.off'

function Get-State { if (Test-Path $Rules) { 'on' } else { 'off' } }

switch ($Action) {
  'on' {
    if (Test-Path $Rules)       { 'OK: Cline rules ON (.clinerules/)' }
    elseif (Test-Path $Off)     { Rename-Item $Off $Rules -ErrorAction Stop; 'OK: Cline rules ON — đã khôi phục .clinerules/' }
    else                        { 'ERR: không tìm thấy .clinerules/ hay .clinerules.off/'; exit 1 }
  }
  'off' {
    if (Test-Path $Off)         { 'OK: Cline rules OFF (.clinerules.off/)' }
    elseif (Test-Path $Rules)   { Rename-Item $Rules $Off -ErrorAction Stop; 'OK: Cline rules OFF — đã đổi .clinerules/ -> .clinerules.off/' }
    else                        { 'ERR: không tìm thấy .clinerules/'; exit 1 }
  }
  'toggle' {
    $p = Join-Path $Root 'tools/cline-toggle-rules.ps1'
    if ((Get-State) -eq 'on') { & $p off } else { & $p on }
  }
  'status' {
    $s = Get-State
    $t = if ($s -eq 'on') { $Rules } else { $Off }
    "Cline rules: $s ($t)"
  }
}
