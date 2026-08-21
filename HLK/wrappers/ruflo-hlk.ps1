# PowerShell launcher for ruflo with HLK preload
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir | Split-Path -Parent
& node "$repoRoot\HLK\wrappers\ruflo-hlk.mjs" @args
