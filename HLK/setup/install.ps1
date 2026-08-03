# ============================================================================
# HLK Installer — cài thẳng từ source vào path user chỉ định (PowerShell)
# ============================================================================
#
# Cách dùng (từ source đã clone):
#   powershell -ExecutionPolicy Bypass -File HLK/setup/install.ps1
#   # Script sẽ hỏi path cần cài HLK vào, user nhập, mọi việc tự động tiếp
#
# Hoặc truyền path trực tiếp:
#   powershell -ExecutionPolicy Bypass -File HLK/setup/install.ps1 -Path "C:\target"
#   powershell -ExecutionPolicy Bypass -File HLK/setup/install.ps1 "C:\target"
#
# Script này sẽ:
#   1. Dùng HLK từ source local (đã clone repo) hoặc tải từ GitHub
#   2. Cài Ruflo từ npm registry (npx ruflo@latest init) nếu chưa có
#   3. Copy HLK vào <path>\HLK\ của workspace user chỉ định
#   4. Patch .claude\settings.json (PreToolUse hook, MCP wrapper)
#   5. Patch .gitattributes (merge=ours)
#   6. Patch .gitignore (bảo vệ secrets, *.rvf, .env)
#   7. Copy skills HLK sang .claude\skills\ và .devin\skills\
#   8. Cài .githooks\post-merge (tự verify HLK sau pull/merge)
#   9. Run HLK integrity verify
#
# Options (truyền qua biến môi trường):
#   $env:HLK_REPO, $env:HLK_BRANCH, $env:RUFLO_VERSION, $env:SKIP_RUFLO, $env:SKIP_CLONE
# ============================================================================

param(
    [string]$Path = "",
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

# --- Cấu hình mặc định ---
$HLK_REPO       = if ($env:HLK_REPO)       { $env:HLK_REPO }       else { "https://github.com/thanhnt-sm/Loop_harness_ruflo.git" }
$HLK_BRANCH     = if ($env:HLK_BRANCH)     { $env:HLK_BRANCH }     else { "main" }
$RUFLO_VERSION  = if ($env:RUFLO_VERSION)  { $env:RUFLO_VERSION }  else { "latest" }
$SKIP_RUFLO     = if ($env:SKIP_RUFLO)     { $env:SKIP_RUFLO }     else { "0" }
$SKIP_CLONE     = if ($env:SKIP_CLONE)     { $env:SKIP_CLONE }     else { "0" }

# --- Hỏi path cài nếu không truyền qua args ---
if ([string]::IsNullOrWhiteSpace($Path)) {
    $defaultPath = (Get-Location).Path
    $Path = Read-Host "Nhập path cần cài HLK vào [mặc định: $defaultPath]"
    if ([string]::IsNullOrWhiteSpace($Path)) { $Path = $defaultPath }
}

$WORKSPACE_ROOT = (Resolve-Path -Path $Path -ErrorAction SilentlyContinue)?.Path
if (-not $WORKSPACE_ROOT) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
    $WORKSPACE_ROOT = (Resolve-Path -Path $Path).Path
}

$TEMP_DIR       = Join-Path $env:TEMP "hlk-install-$(Get-Date -Format 'yyyyMMddHHmmss')"
$HLK_TARGET_DIR = Join-Path $WORKSPACE_ROOT "HLK"

# --- Log helper ---
function Log-Info  { param([string]$m) Write-Host "ℹ️  $m" -ForegroundColor Blue }
function Log-Ok    { param([string]$m) Write-Host "✅ $m" -ForegroundColor Green }
function Log-Warn  { param([string]$m) Write-Host "⚠️  $m" -ForegroundColor Yellow }
function Log-Error { param([string]$m) Write-Host "❌ $m" -ForegroundColor Red }

Log-Info "=== HLK Installer ==="
Log-Ok "Node $(node --version 2>$null)"
Log-Info "Workspace: $WORKSPACE_ROOT"
Log-Info "HLK target: $HLK_TARGET_DIR"
if ($SKIP_RUFLO -eq "1") { Log-Warn "SKIP_RUFLO=1 — bỏ qua cài Ruflo" }
if ($SKIP_CLONE -eq "1") { Log-Warn "SKIP_CLONE=1 — dùng HLK\setup\ local" }

# --- Kiểm tra node ---
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Log-Error "Không tìm thấy Node.js. Cài Node >= 14 trước."
    exit 1
}
$nodeVersion = (node --version) -replace 'v(\d+).*', '$1'
if ([int]$nodeVersion -lt 14) {
    Log-Error "Node >= 14 yêu cầu. Hiện tại: $(node --version)"
    exit 1
}
Log-Ok "Node $(node --version)"

# --- Kiểm tra git ---
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if (-not $gitCmd) {
    Log-Error "Không tìm thấy git. Cài git trước."
    exit 1
}

# ============================================================================
# Bước 1: Tải HLK từ GitHub
# ============================================================================

function Download-Hlk {
    if ($SKIP_CLONE -eq "1") {
        $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
        if (-not $scriptDir) { $scriptDir = $PSScriptRoot }
        if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
        $repoRoot = (Resolve-Path (Join-Path $scriptDir "..\..")).Path
        $script:TEMP_DIR = $repoRoot
        Log-Info "Bước 1: Dùng HLK từ repo local: $repoRoot"
        return
    }

    Log-Info "Bước 1: Tải HLK từ GitHub..."

    # Tải tarball
    $tarballUrl = "https://codeload.github.com/thanhnt-sm/Loop_harness_ruflo/tar.gz/refs/heads/$HLK_BRANCH"
    $tarballPath = Join-Path $TEMP_DIR "hlk.tar.gz"

    try {
        New-Item -ItemType Directory -Force -Path $TEMP_DIR | Out-Null
        Invoke-WebRequest -Uri $tarballUrl -OutFile $tarballPath -UseBasicParsing
        Log-Info "Đã tải tarball, giải nén..."

        # Giải nén tarball (cần tar.exe — có sẵn trên Windows 10+)
        & tar -xzf $tarballPath -C $TEMP_DIR
        if ($LASTEXITCODE -ne 0) { throw "tar extract failed" }

        $extractedDir = Get-ChildItem -Path $TEMP_DIR -Directory -Filter "Loop_harness_ruflo-*" | Select-Object -First 1
        if (-not $extractedDir) {
            throw "Không tìm thấy thư mục sau giải nén"
        }
        $script:TEMP_DIR = $extractedDir.FullName
        Log-Ok "Đã giải nén HLK vào $($script:TEMP_DIR)"
    }
    catch {
        Log-Warn "Tải tarball thất bại, fallback sang git clone..."
        $cloneDir = Join-Path $TEMP_DIR "hlk-clone"
        & git clone --depth 1 --branch $HLK_BRANCH $HLK_REPO $cloneDir
        if ($LASTEXITCODE -ne 0) {
            Log-Error "Git clone thất bại"
            exit 1
        }
        $script:TEMP_DIR = $cloneDir
        Log-Ok "Đã clone HLK vào $($script:TEMP_DIR)"
    }
}

# ============================================================================
# Bước 2: Cài Ruflo nếu chưa có
# ============================================================================

function Install-Ruflo {
    if ($SKIP_RUFLO -eq "1") {
        Log-Info "Bước 2: Bỏ qua cài Ruflo (SKIP_RUFLO=1)"
        return
    }

    $hasRuflo = (Test-Path (Join-Path $WORKSPACE_ROOT ".claude")) -or (Test-Path (Join-Path $WORKSPACE_ROOT "package.json"))
    if ($hasRuflo) {
        Log-Info "Bước 2: Ruflo đã có trong workspace — bỏ qua init."
        return
    }

    Log-Info "Bước 2: Cài Ruflo $RUFLO_VERSION qua npm..."

    $npxCmd = Get-Command npx -ErrorAction SilentlyContinue
    if (-not $npxCmd) {
        Log-Error "Không tìm thấy npx. Cài Node + npm trước."
        exit 1
    }

    if ($RUFLO_VERSION -eq "latest") {
        & npx -y ruflo@latest init
    } else {
        & npx -y "ruflo@$RUFLO_VERSION" init
    }

    if ($LASTEXITCODE -ne 0) {
        Log-Error "Ruflo init thất bại"
        exit 1
    }

    Log-Ok "Ruflo đã cài xong."
}

# ============================================================================
# Bước 3: Copy HLK vào workspace
# ============================================================================

function Copy-Hlk {
    Log-Info "Bước 3: Copy HLK vào $HLK_TARGET_DIR..."

    $hlkSrc = Join-Path $TEMP_DIR "HLK"
    if (-not (Test-Path $hlkSrc)) {
        Log-Error "Không tìm thấy HLK\ trong repo tải về: $hlkSrc"
        exit 1
    }

    # Backup HLK cũ nếu có
    if (Test-Path $HLK_TARGET_DIR) {
        $backupDir = Join-Path $WORKSPACE_ROOT "HLK.backup.$(Get-Date -Format 'yyyyMMddHHmmss')"
        Copy-Item -Recurse -Force $HLK_TARGET_DIR $backupDir
        Log-Info "Đã backup HLK cũ sang: $backupDir"
    }

    New-Item -ItemType Directory -Force -Path $HLK_TARGET_DIR | Out-Null

    # Copy các thư mục cần thiết
    $dirs = @("config", "wrappers", "security", "custom-hooks", "docs", "prompts", "reports", "loop", "git-tools", "upstream", "skills", "bin", "setup")
    foreach ($dir in $dirs) {
        $src = Join-Path $hlkSrc $dir
        if (Test-Path $src) {
            Copy-Item -Recurse -Force $src (Join-Path $HLK_TARGET_DIR $dir)
            Log-Info "  Đã copy $dir\"
        }
    }

    # Copy các file riêng lẻ
    $files = @("README.md", "INSTALL.md", "package.json")
    foreach ($file in $files) {
        $src = Join-Path $hlkSrc $file
        if (Test-Path $src) {
            Copy-Item -Force $src (Join-Path $HLK_TARGET_DIR $file)
        }
    }

    Log-Ok "Đã copy HLK vào $HLK_TARGET_DIR"
}

# ============================================================================
# Bước 4: Patch .claude\settings.json
# ============================================================================

function Patch-Settings {
    Log-Info "Bước 4: Patch .claude\settings.json..."

    $settingsPath = Join-Path $WORKSPACE_ROOT ".claude\settings.json"
    if (-not (Test-Path $settingsPath)) {
        Log-Warn "Không tìm thấy .claude\settings.json — bỏ qua patch."
        return
    }

    $settingsJson = $settingsPath -replace '\\', '/'
    $hlkTargetJson = $HLK_TARGET_DIR -replace '\\', '/'

    $nodeScript = @"
const fs = require('fs');
const path = '$settingsJson';
let s;
try { s = JSON.parse(fs.readFileSync(path, 'utf8')); }
catch (e) { console.error('Lỗi parse settings.json:', e.message); process.exit(1); }

if (!s.hooks) s.hooks = {};
if (!Array.isArray(s.hooks.PreToolUse)) s.hooks.PreToolUse = [];
const hasHlk = s.hooks.PreToolUse.some(e =>
  e.hooks?.some(h => h.command?.includes('hlk-hook-bridge.mjs'))
);
if (!hasHlk) {
  s.hooks.PreToolUse.unshift({
    hooks: [{
      type: 'command',
      command: 'node "\$CLAUDE_PROJECT_DIR/HLK/wrappers/hlk-hook-bridge.mjs"',
      timeout: 5000
    }]
  });
  console.log('Da them HLK PreToolUse hook');
} else {
  console.log('HLK PreToolUse hook da co');
}

if (!s.mcpServers) s.mcpServers = {};
const cur = s.mcpServers['claude-flow'];
const usesHlk = cur?.args?.some(a => typeof a === 'string' && a.includes('ruflo-hlk-mcp'));
if (!usesHlk) {
  s.mcpServers['claude-flow'] = {
    command: 'node',
    args: ['HLK/wrappers/ruflo-hlk-mcp.mjs', 'mcp', 'start']
  };
  console.log('Da cap nhat MCP wrapper dung HLK');
} else {
  console.log('MCP server da dung HLK wrapper');
}

fs.writeFileSync(path, JSON.stringify(s, null, 2) + '\n', 'utf8');
console.log('Da ghi .claude/settings.json');
"@

    $result = & node -e $nodeScript 2>&1
    Write-Host $result

    Log-Ok "Đã patch .claude\settings.json"
}

# ============================================================================
# Bước 5: Patch .gitattributes
# ============================================================================

function Patch-GitAttributes {
    Log-Info "Bước 5: Patch .gitattributes..."

    $gitattrPath = Join-Path $WORKSPACE_ROOT ".gitattributes"
    $content = ""
    if (Test-Path $gitattrPath) {
        $content = Get-Content $gitattrPath -Raw
    }

    $lines = @(
        "# HLK config — always keep our version on merge conflicts",
        "HLK/config/hlk.config.json merge=ours",
        "",
        "# HLK wrappers — keep ours",
        "HLK/wrappers/** merge=ours",
        "",
        "# HLK security — keep ours",
        "HLK/security/** merge=ours",
        "",
        "# HLK docs — keep ours",
        "HLK/docs/** merge=ours",
        "",
        "# .claude settings — keep ours",
        ".claude/settings.json merge=ours"
    )

    $modified = $false
    foreach ($line in $lines) {
        if ($content -notlike "*$line*") {
            $content += "`n$line"
            $modified = $true
        }
    }

    if ($modified) {
        Set-Content -Path $gitattrPath -Value $content -NoNewline
        Log-Ok "Đã cập nhật .gitattributes với merge=ours"
    } else {
        Log-Info ".gitattributes đã chứa HLK merge rules"
    }
}

# ============================================================================
# Bước 6: Patch .gitignore
# ============================================================================

function Patch-GitIgnore {
    Log-Info "Bước 6: Patch .gitignore..."

    $gitignorePath = Join-Path $WORKSPACE_ROOT ".gitignore"
    $content = ""
    if (Test-Path $gitignorePath) {
        $content = Get-Content $gitignorePath -Raw
    }

    $patterns = @(
        "HLK/config/secrets.*",
        "HLK/config/*.local.json",
        "HLK/logs/",
        "*.rvf",
        "*.rvf.lock",
        "agentdb.rvf",
        "agentdb.rvf.lock",
        ".env",
        ".env.*",
        "!.env.example",
        "!.env.*.example",
        "example.env",
        "HLK/dist/*.tgz",
        "HLK/dist/"
    )

    $modified = $false
    foreach ($pattern in $patterns) {
        $lines = $content -split "`n"
        $found = $lines | Where-Object { $_.Trim() -eq $pattern }
        if (-not $found) {
            $content += "`n$pattern"
            $modified = $true
        }
    }

    if ($modified) {
        Set-Content -Path $gitignorePath -Value $content -NoNewline
        Log-Ok "Đã cập nhật .gitignore bảo vệ secrets"
    } else {
        Log-Info ".gitignore đã bảo vệ đầy đủ"
    }
}

# ============================================================================
# Bước 7: Copy skills HLK
# ============================================================================

function Copy-Skills {
    Log-Info "Bước 7: Copy skills HLK..."

    $skillsSrc = Join-Path $HLK_TARGET_DIR "skills"
    if (-not (Test-Path $skillsSrc)) {
        Log-Warn "Không tìm thấy HLK\skills\ — bỏ qua"
        return
    }

    $claudeSkills = Join-Path $WORKSPACE_ROOT ".claude\skills"
    New-Item -ItemType Directory -Force -Path $claudeSkills | Out-Null

    $devinSkills = Join-Path $WORKSPACE_ROOT ".devin\skills"
    New-Item -ItemType Directory -Force -Path $devinSkills | Out-Null

    Get-ChildItem -Path $skillsSrc -Directory -Filter "hlk-*" | ForEach-Object {
        Copy-Item -Recurse -Force $_.FullName (Join-Path $claudeSkills $_.Name)
        Copy-Item -Recurse -Force $_.FullName (Join-Path $devinSkills $_.Name)
        Log-Info "  Đã copy skill $($_.Name)"
    }

    Log-Ok "Đã copy skills sang .claude\skills\ và .devin\skills\"
}

# ============================================================================
# Bước 8: Cài .githooks\post-merge
# ============================================================================

function Install-GitHooks {
    Log-Info "Bước 8: Cài .githooks\post-merge..."

    $template = Join-Path $HLK_TARGET_DIR "skills\post-merge.template"
    if (-not (Test-Path $template)) {
        Log-Warn "Không tìm thấy post-merge.template — bỏ qua"
        return
    }

    $githooksDir = Join-Path $WORKSPACE_ROOT ".githooks"
    New-Item -ItemType Directory -Force -Path $githooksDir | Out-Null

    Copy-Item -Force $template (Join-Path $githooksDir "post-merge")
    Log-Ok "Đã cài .githooks\post-merge"

    # Kích hoạt core.hooksPath nếu chưa
    $currentHooksPath = & git config core.hooksPath 2>$null
    if (-not $currentHooksPath) {
        & git config core.hooksPath .githooks
        Log-Ok "Đã kích hoạt git config core.hooksPath .githooks"
    } elseif ($currentHooksPath -ne ".githooks") {
        Log-Warn "core.hooksPath hiện tại = `"$currentHooksPath`" (không phải .githooks)"
        Log-Warn "Chạy: git config core.hooksPath .githooks"
    }
}

# ============================================================================
# Bước 9: Tạo secrets.env nếu chưa có
# ============================================================================

function Create-Secrets {
    $secretsPath = Join-Path $HLK_TARGET_DIR "config\secrets.env"
    if (Test-Path $secretsPath) {
        Log-Info "HLK\config\secrets.env đã có — giữ nguyên"
        return
    }

    $examplePath = Join-Path $HLK_TARGET_DIR "config\secrets.env.example"
    if (Test-Path $examplePath) {
        Copy-Item $examplePath $secretsPath
        Log-Ok "Đã tạo HLK\config\secrets.env từ example"
    } else {
        Log-Warn "Không tìm thấy secrets.env.example — bỏ qua"
    }
}

# ============================================================================
# Bước 10: Run HLK integrity verify
# ============================================================================

function Run-Verify {
    Log-Info "Bước 9: HLK integrity verify..."

    $verify = Join-Path $HLK_TARGET_DIR "wrappers\hlk-verify-integrity.js"
    if (-not (Test-Path $verify)) {
        Log-Warn "Không tìm thấy hlk-verify-integrity.js — bỏ qua"
        return
    }

    & node $verify
    if ($LASTEXITCODE -ne 0) {
        Log-Error "HLK integrity verify FAILED"
        exit 1
    }

    Log-Ok "HLK integrity verify PASSED"
}

# ============================================================================
# Cleanup
# ============================================================================

function Cleanup {
    if ($SKIP_CLONE -eq "1") { return }
    if ($TEMP_DIR -and (Test-Path $TEMP_DIR) -and ($TEMP_DIR -ne $WORKSPACE_ROOT)) {
        Remove-Item -Recurse -Force $TEMP_DIR -ErrorAction SilentlyContinue
    }
}

# ============================================================================
# Main
# ============================================================================

try {
    Download-Hlk
    Install-Ruflo
    Copy-Hlk
    Patch-Settings
    Patch-GitAttributes
    Patch-GitIgnore
    Copy-Skills
    Install-GitHooks
    Create-Secrets
    Run-Verify

    Write-Host ""
    Log-Ok "HLK đã cài đặt xong."
    Write-Host ""
    Log-Info "Các bước tiếp theo:"
    Log-Info "  1. Mở HLK\config\secrets.env và điền API keys / tokens thật."
    Log-Info "  2. Khởi động lại Claude Code để MCP server dùng HLK wrapper."
    Log-Info "  3. Test: node HLK\wrappers\hlk-hook-bridge.mjs < test-secret.json"
    Log-Info "  4. Đọc HLK\docs\01-tong-quan-va-kien-truc.md để tìm hiểu thêm."
    Write-Host ""
    Log-Info "Pull update từ upstream ruflo + reinstall HLK:"
    Log-Info "  node HLK\upstream\hlk-upstream-pull.mjs --yes"
} finally {
    Cleanup
}
