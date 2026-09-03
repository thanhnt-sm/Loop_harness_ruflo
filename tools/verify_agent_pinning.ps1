Get-ChildItem -Recurse .commandcode/agents -Filter '*.md' | ForEach-Object {
    $raw = Get-Content $_.FullName -Raw
    $hasModel = $raw -match 'model: '
    $hasMaxTurns = $raw -match 'maxTurns:'
    $hasBg = $raw -match 'background:'
    $hasPerm = $raw -match 'permissionMode:'
    $mark = if ($hasModel -and $hasMaxTurns -and $hasBg -and $hasPerm) { 'OK' } else { 'PARTIAL' }
    Write-Host ("{0,-35} {1}" -f $_.Name, $mark)
}
