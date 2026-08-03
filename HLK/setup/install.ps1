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
#   4. Hỏi CLI đang dùng, patch cấu hình MCP + hook cho CLI đó
#   5. Patch .gitattributes (merge=ours)
#   6. Patch .gitignore (bảo vệ secrets, *.rvf, .env)
#   7. Copy skills HLK sang thư mục skills của CLI đã chọn
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
# Bước 3.5: Hỏi human đang dùng CLI nào
# ============================================================================

function Ask-CliChoice {
    Write-Host ""
    Write-Host "═══ Bạn đang dùng CLI nào? ═══"
    Write-Host "  1. Claude Code        (.claude\)"
    Write-Host "  2. Devin CLI          (.devin\)"
    Write-Host "  3. Antigravity CLI    (.agents\)"
    Write-Host "  4. Tất cả (cả 3 CLI)  ← khuyến nghị nếu dùng nhiều CLI"
    $answer = Read-Host "Nhập số (1-4) [mặc định: 4]"
    if ([string]::IsNullOrWhiteSpace($answer)) { $answer = "4" }

    $trimmed = $answer.Trim().ToLower()
    switch ($trimmed) {
        { $_ -in @("1", "claude", "c") }    { $script:CLI_CHOICE = "claude" }
        { $_ -in @("2", "devin", "d") }     { $script:CLI_CHOICE = "devin" }
        { $_ -in @("3", "agy", "a") }       { $script:CLI_CHOICE = "agy" }
        { $_ -in @("4", "all") }            { $script:CLI_CHOICE = "all" }
        default                             { $script:CLI_CHOICE = "all" }
    }

    Log-Info "Đã chọn CLI: $($script:CLI_CHOICE)"
}

# ============================================================================
# Bước 4: Patch cấu hình MCP + hook cho CLI đã chọn
# ----------------------------------------------------------------------------
# Lặp qua từng CLI (claude/devin/agy) và ghi file cấu hình tương ứng:
#   - claude: .claude\settings.json (hooks + mcpServers cùng file)
#   - devin:  .devin\mcp_config.json (MCP) + .devin\hooks.v1.json (hooks)
#   - agy:    .agents\mcp_config.json (chỉ MCP, không hooks)
# Hook command dùng hlk-hook-launcher.mjs (path tương đối, trung tính CLI)
# ============================================================================

function Patch-CliSettings {
    Log-Info "Bước 4: Patch cấu hình CLI ($CLI_CHOICE)..."

    $hlkSelect = Join-Path $HLK_TARGET_DIR "wrappers\hlk-cli-select.mjs"

    # Truyền path qua env var để tránh escape phức tạp trong PowerShell
    $env:WS = $WORKSPACE_ROOT
    $env:HLK_SELECT = $hlkSelect
    $env:CLI_CHOICE = $CLI_CHOICE

    # Dùng single-quoted here-string để tránh PowerShell interpolate
    $nodeScript = @'
import { pathToFileURL } from "node:url";
import fs from "node:fs";

const ws = process.env.WS;
const selectPath = process.env.HLK_SELECT;
const choice = process.env.CLI_CHOICE;

// Import module dùng chung hlk-cli-select.mjs
const mod = await import(pathToFileURL(selectPath).href);
const { cliTargets, cliMcpConfigPath, cliHooksPath, ensureCliDirs, hookCommand, CLI_INFO } = mod;

const targets = cliTargets(choice);

// Hook command trung tính — dùng hlk-hook-launcher.mjs (path tương đối)
const hookCmd = hookCommand(5000);

// MCP server config dùng HLK wrapper
const mcpConfig = {
  command: "node",
  args: ["HLK/wrappers/ruflo-hlk-mcp.mjs", "mcp", "start"]
};

for (const cli of targets) {
  console.log("--- Patching " + CLI_INFO[cli].displayName + " ---");
  ensureCliDirs(ws, cli);

  const mcpPath = cliMcpConfigPath(ws, cli);
  const hooksPath = cliHooksPath(ws, cli);

  if (cli === "claude") {
    // Claude Code: cả hooks + mcpServers trong cùng settings.json
    let s = {};
    try { s = JSON.parse(fs.readFileSync(mcpPath, "utf8")); } catch { s = {}; }

    // Thêm PreToolUse hook (dùng launcher trung tính)
    if (!s.hooks) s.hooks = {};
    if (!Array.isArray(s.hooks.PreToolUse)) s.hooks.PreToolUse = [];
    const hasHlk = s.hooks.PreToolUse.some(e =>
      e.hooks?.some(h => h.command?.includes("hlk-hook"))
    );
    if (!hasHlk) {
      s.hooks.PreToolUse.unshift({ hooks: [hookCmd] });
      console.log("  ✅ Đã thêm HLK PreToolUse hook");
    } else {
      // Cập nhật hook command cũ sang launcher trung tính
      for (const entry of s.hooks.PreToolUse) {
        if (entry.hooks) for (const h of entry.hooks) {
          if (h.command?.includes("hlk-hook-bridge")) h.command = hookCmd.command;
        }
      }
      console.log("  ℹ️  Đã cập nhật HLK hook sang launcher trung tính");
    }

    // Cập nhật MCP server
    if (!s.mcpServers) s.mcpServers = {};
    s.mcpServers["claude-flow"] = mcpConfig;

    fs.writeFileSync(mcpPath, JSON.stringify(s, null, 2) + "\n", "utf8");
    console.log("  ✅ Đã ghi " + mcpPath);

  } else if (cli === "devin") {
    // Devin CLI: MCP riêng (mcp_config.json) + hooks riêng (hooks.v1.json)
    let mcp = {};
    try { mcp = JSON.parse(fs.readFileSync(mcpPath, "utf8")); } catch { mcp = {}; }
    if (!mcp.mcpServers) mcp.mcpServers = {};
    mcp.mcpServers["claude-flow"] = mcpConfig;
    fs.writeFileSync(mcpPath, JSON.stringify(mcp, null, 2) + "\n", "utf8");
    console.log("  ✅ Đã ghi " + mcpPath);

    if (hooksPath) {
      let hooks = {};
      try { hooks = JSON.parse(fs.readFileSync(hooksPath, "utf8")); } catch { hooks = {}; }
      if (!Array.isArray(hooks.PreToolUse)) hooks.PreToolUse = [];
      const hasHlk = hooks.PreToolUse.some(e =>
        e.hooks?.some(h => h.command?.includes("hlk-hook"))
      );
      if (!hasHlk) {
        hooks.PreToolUse.unshift({ hooks: [hookCmd] });
      } else {
        for (const entry of hooks.PreToolUse) {
          if (entry.hooks) for (const h of entry.hooks) {
            if (h.command?.includes("hlk-hook-bridge")) h.command = hookCmd.command;
          }
        }
      }
      fs.writeFileSync(hooksPath, JSON.stringify(hooks, null, 2) + "\n", "utf8");
      console.log("  ✅ Đã ghi " + hooksPath);
    }

  } else if (cli === "agy") {
    // Antigravity: chỉ MCP (mcp_config.json), không có hooks riêng
    let mcp = {};
    try { mcp = JSON.parse(fs.readFileSync(mcpPath, "utf8")); } catch { mcp = {}; }
    if (!mcp.mcpServers) mcp.mcpServers = {};
    mcp.mcpServers["claude-flow"] = mcpConfig;
    fs.writeFileSync(mcpPath, JSON.stringify(mcp, null, 2) + "\n", "utf8");
    console.log("  ✅ Đã ghi " + mcpPath);
  }
}
console.log("✅ Đã patch cấu hình cho " + targets.length + " CLI");
'@

    $result = & node --input-type=module -e $nodeScript 2>&1
    Write-Host $result

    Log-Ok "Đã patch cấu hình CLI"
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

    # Copy sang .agents\skills\ nếu chọn agy hoặc all
    $agySkills = $null
    if ($CLI_CHOICE -eq "agy" -or $CLI_CHOICE -eq "all") {
        $agySkills = Join-Path $WORKSPACE_ROOT ".agents\skills"
        New-Item -ItemType Directory -Force -Path $agySkills | Out-Null
    }

    Get-ChildItem -Path $skillsSrc -Directory -Filter "hlk-*" | ForEach-Object {
        Copy-Item -Recurse -Force $_.FullName (Join-Path $claudeSkills $_.Name)
        Copy-Item -Recurse -Force $_.FullName (Join-Path $devinSkills $_.Name)
        if ($agySkills) {
            Copy-Item -Recurse -Force $_.FullName (Join-Path $agySkills $_.Name)
        }
        Log-Info "  Đã copy skill $($_.Name)"
    }

    Log-Ok "Đã copy skills sang thư mục CLI đã chọn"
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
    Ask-CliChoice
    Copy-Hlk
    Patch-CliSettings
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
    Log-Info "  3. Test: node HLK\wrappers\hlk-hook-launcher.mjs < test-secret.json"
    Log-Info "  4. Đọc HLK\docs\01-tong-quan-va-kien-truc.md để tìm hiểu thêm."
    Write-Host ""
    Log-Info "Pull update từ upstream ruflo + reinstall HLK:"
    Log-Info "  node HLK\upstream\hlk-upstream-pull.mjs --yes"
} finally {
    Cleanup
}
