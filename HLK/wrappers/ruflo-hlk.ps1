#requires -Version 5.1
<#
.SYNOPSIS
    Ruflo HLK Launcher — Windows PowerShell

.DESCRIPTION
    Tự động set NODE_OPTIONS trỏ đến HLK loader rồi chạy bin/cli.js.

.EXAMPLE
    .\HLK\wrappers\ruflo-hlk.ps1 memory store -k demo -v "sk-abc..."
#>

$ErrorActionPreference = "Stop"

# Xác định đường dẫn
$WrapperDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $WrapperDir "..\..")
$LoaderUrl = "file://$($RepoRoot.Path)/HLK/wrappers/hlk-loader.js"
$CliPath = Join-Path $RepoRoot "bin/cli.js"

# Chuẩn bị NODE_OPTIONS
$nodeOpts = $env:NODE_OPTIONS
if (-not $nodeOpts) {
    $env:NODE_OPTIONS = "--import=$LoaderUrl"
} elseif ($nodeOpts -notlike "*--import=*") {
    $env:NODE_OPTIONS = "$nodeOpts --import=$LoaderUrl"
}

# Chạy Node với bin/cli.js và các args còn lại
& node $CliPath @args
