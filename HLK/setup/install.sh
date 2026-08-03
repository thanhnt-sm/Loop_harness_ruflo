#!/usr/bin/env bash
# ============================================================================
# HLK Installer — cài thẳng từ source vào path user chỉ định
# ============================================================================
#
# Cách dùng (từ source đã clone):
#   bash HLK/setup/install.sh
#   # Script sẽ hỏi path cần cài HLK vào, user nhập, mọi việc tự động tiếp
#
# Hoặc truyền path trực tiếp:
#   bash HLK/setup/install.sh /path/to/workspace
#   bash HLK/setup/install.sh --path /path/to/workspace
#
# Script này sẽ:
#   1. Dùng HLK từ source local (đã clone repo) hoặc tải từ GitHub
#   2. Cài Ruflo từ npm registry (npx ruflo@latest init) nếu chưa có
#   3. Copy HLK vào <path>/HLK/ của workspace user chỉ định
#   4. Patch .claude/settings.json (PreToolUse hook, MCP wrapper)
#   5. Patch .gitattributes (merge=ours)
#   6. Patch .gitignore (bảo vệ secrets, *.rvf, .env)
#   7. Copy skills HLK sang .claude/skills/ và .devin/skills/
#   8. Cài .githooks/post-merge (tự verify HLK sau pull/merge)
#   9. Run HLK integrity verify
#
# Options (truyền qua biến môi trường):
#   HLK_REPO=https://github.com/thanhnt-sm/Loop_harness_ruflo.git
#   HLK_BRANCH=main
#   RUFLO_VERSION=latest          # hoặc version cụ thể: 3.34.0
#   SKIP_RUFLO=1                  # bỏ qua cài Ruflo (chỉ cài HLK)
#   SKIP_CLONE=1                  # dùng HLK/setup/ local (đã clone repo)
# ============================================================================

set -euo pipefail

# --- Cấu hình mặc định ---
HLK_REPO="${HLK_REPO:-https://github.com/thanhnt-sm/Loop_harness_ruflo.git}"
HLK_BRANCH="${HLK_BRANCH:-main}"
RUFLO_VERSION="${RUFLO_VERSION:-latest}"
SKIP_RUFLO="${SKIP_RUFLO:-0}"
SKIP_CLONE="${SKIP_CLONE:-0}"

# --- Parse args: install.sh [path] hoặc install.sh --path <path> ---
USER_PATH=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --path)
      USER_PATH="$2"
      shift 2
      ;;
    --yes)
      shift
      ;;
    --*)
      shift
      ;;
    *)
      USER_PATH="$1"
      shift
      ;;
  esac
done

# --- Màu log ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()  { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_ok()    { echo -e "${GREEN}✅ $1${NC}"; }
log_warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# --- Hỏi path cài nếu không truyền qua args ---
if [[ -z "${USER_PATH}" ]]; then
  DEFAULT_PATH="$(pwd)"
  echo -e "${BLUE}ℹ️  Nhập path cần cài HLK vào [mặc định: ${DEFAULT_PATH}]: ${NC}"
  read -r USER_PATH
  USER_PATH="${USER_PATH:-${DEFAULT_PATH}}"
fi

# --- Resolve path tuyệt đối ---
WORKSPACE_ROOT="$(cd "${USER_PATH}" 2>/dev/null && pwd || mkdir -p "${USER_PATH}" && cd "${USER_PATH}" && pwd)"
TEMP_DIR="$(mktemp -d)"
HLK_TARGET_DIR="${WORKSPACE_ROOT}/HLK"

log_info "=== HLK Installer ==="
log_ok "Node $(node --version 2>/dev/null || echo 'không tìm thấy')"
log_info "Workspace: ${WORKSPACE_ROOT}"
log_info "HLK target: ${HLK_TARGET_DIR}"
if [[ "${SKIP_RUFLO}" == "1" ]]; then log_warn "SKIP_RUFLO=1 — bỏ qua cài Ruflo"; fi
if [[ "${SKIP_CLONE}" == "1" ]]; then log_warn "SKIP_CLONE=1 — dùng HLK/setup/ local"; fi

# --- Kiểm tra node ---
if ! command -v node &>/dev/null; then
  log_error "Không tìm thấy Node.js. Cài Node >= 14 trước."
  exit 1
fi
NODE_MAJOR=$(node -e "console.log(process.versions.node.split('.')[0])")
if [[ "${NODE_MAJOR}" -lt 14 ]]; then
  log_error "Node >= 14 yêu cầu. Hiện tại: $(node --version)"
  exit 1
fi
log_ok "Node $(node --version)"

# --- Kiểm tra git ---
if ! command -v git &>/dev/null; then
  log_error "Không tìm thấy git. Cài git trước."
  exit 1
fi

# --- Kiểm tra curl ---
if ! command -v curl &>/dev/null; then
  log_error "Không tìm thấy curl. Cài curl trước."
  exit 1
fi

# ============================================================================
# Bước 1: Tải HLK từ GitHub
# ============================================================================

download_hlk() {
  if [[ "${SKIP_CLONE}" == "1" ]]; then
    # Đã clone repo, dùng HLK/setup/ local
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local repo_root
    repo_root="$(cd "${script_dir}/../.." && pwd)"
    TEMP_DIR="${repo_root}"
    log_info "Bước 1: Dùng HLK từ repo local: ${repo_root}"
    return
  fi

  log_info "Bước 1: Tải HLK từ GitHub..."

  # Thử tải tarball trước (nhanh hơn git clone)
  local tarball_url="https://codeload.github.com/thanhnt-sm/Loop_harness_ruflo/tar.gz/refs/heads/${HLK_BRANCH}"

  if curl -fsSL -o "${TEMP_DIR}/hlk.tar.gz" "${tarball_url}" 2>/dev/null; then
    log_info "Đã tải tarball, giải nén..."
    tar -xzf "${TEMP_DIR}/hlk.tar.gz" -C "${TEMP_DIR}"
    # Tarball giải nén thành thư mục Loop_harness_ruflo-<branch>
    local extracted_dir
    extracted_dir="$(find "${TEMP_DIR}" -maxdepth 1 -type d -name "Loop_harness_ruflo-*" | head -1)"
    if [[ -z "${extracted_dir}" ]]; then
      log_error "Không tìm thấy thư mục sau giải nén tarball."
      exit 1
    fi
    TEMP_DIR="${extracted_dir}"
    log_ok "Đã giải nén HLK vào ${TEMP_DIR}"
  else
    # Fallback: git clone
    log_warn "Tải tarball thất bại, fallback sang git clone..."
    git clone --depth 1 --branch "${HLK_BRANCH}" "${HLK_REPO}" "${TEMP_DIR}/hlk-clone"
    TEMP_DIR="${TEMP_DIR}/hlk-clone"
    log_ok "Đã clone HLK vào ${TEMP_DIR}"
  fi
}

# ============================================================================
# Bước 2: Cài Ruflo nếu chưa có
# ============================================================================

install_ruflo() {
  if [[ "${SKIP_RUFLO}" == "1" ]]; then
    log_info "Bước 2: Bỏ qua cài Ruflo (SKIP_RUFLO=1)"
    return
  fi

  # Kiểm tra Ruflo đã có chưa
  if [[ -d "${WORKSPACE_ROOT}/.claude" ]] || [[ -f "${WORKSPACE_ROOT}/package.json" ]]; then
    log_info "Bước 2: Ruflo đã có trong workspace — bỏ qua init."
    return
  fi

  log_info "Bước 2: Cài Ruflo ${RUFLO_VERSION} qua npm..."

  if ! command -v npx &>/dev/null; then
    log_error "Không tìm thấy npx. Cài Node + npm trước."
    exit 1
  fi

  if [[ "${RUFLO_VERSION}" == "latest" ]]; then
    npx -y ruflo@latest init
  else
    npx -y "ruflo@${RUFLO_VERSION}" init
  fi

  if [[ ! -d "${WORKSPACE_ROOT}/.claude" ]] && [[ ! -f "${WORKSPACE_ROOT}/package.json" ]]; then
    log_error "Ruflo init thất bại — không tìm thấy .claude/ hoặc package.json sau init."
    exit 1
  fi

  log_ok "Ruflo đã cài xong."
}

# ============================================================================
# Bước 3: Copy HLK vào workspace
# ============================================================================

copy_hlk() {
  log_info "Bước 3: Copy HLK vào ${HLK_TARGET_DIR}..."

  local hlk_src="${TEMP_DIR}/HLK"
  if [[ ! -d "${hlk_src}" ]]; then
    log_error "Không tìm thấy HLK/ trong repo tải về: ${hlk_src}"
    exit 1
  fi

  # Backup HLK cũ nếu có
  if [[ -d "${HLK_TARGET_DIR}" ]]; then
    local backup_dir="${WORKSPACE_ROOT}/HLK.backup.$(date +%s)"
    cp -r "${HLK_TARGET_DIR}" "${backup_dir}"
    log_info "Đã backup HLK cũ sang: ${backup_dir}"
  fi

  mkdir -p "${HLK_TARGET_DIR}"

  # Copy các thư mục cần thiết
  local dirs=(config wrappers security custom-hooks docs prompts reports loop git-tools upstream skills bin setup)
  for dir in "${dirs[@]}"; do
    if [[ -d "${hlk_src}/${dir}" ]]; then
      cp -r "${hlk_src}/${dir}" "${HLK_TARGET_DIR}/${dir}"
      log_info "  Đã copy ${dir}/"
    fi
  done

  # Copy các file riêng lẻ
  local files=(README.md INSTALL.md package.json)
  for file in "${files[@]}"; do
    if [[ -f "${hlk_src}/${file}" ]]; then
      cp "${hlk_src}/${file}" "${HLK_TARGET_DIR}/${file}"
    fi
  done

  log_ok "Đã copy HLK vào ${HLK_TARGET_DIR}"
}

# ============================================================================
# Bước 4: Patch .claude/settings.json
# ============================================================================

patch_settings() {
  log_info "Bước 4: Patch .claude/settings.json..."

  local settings_path="${WORKSPACE_ROOT}/.claude/settings.json"
  if [[ ! -f "${settings_path}" ]]; then
    log_warn "Không tìm thấy .claude/settings.json — bỏ qua patch."
    return
  fi

  # Dùng node để patch JSON an toàn
  node -e "
    const fs = require('fs');
    const path = '${settings_path}'.replace(/\\\\/g, '/');
    let s;
    try { s = JSON.parse(fs.readFileSync(path, 'utf8')); }
    catch (e) { console.error('❌ Lỗi parse settings.json:', e.message); process.exit(1); }

    // 1. Thêm HLK PreToolUse hook nếu chưa có
    if (!s.hooks) s.hooks = {};
    if (!Array.isArray(s.hooks.PreToolUse)) s.hooks.PreToolUse = [];
    const hasHlk = s.hooks.PreToolUse.some(e =>
      e.hooks?.some(h => h.command?.includes('hlk-hook-bridge.mjs'))
    );
    if (!hasHlk) {
      s.hooks.PreToolUse.unshift({
        hooks: [{
          type: 'command',
          command: 'node \"\$CLAUDE_PROJECT_DIR/HLK/wrappers/hlk-hook-bridge.mjs\"',
          timeout: 5000
        }]
      });
      console.log('✅ Đã thêm HLK PreToolUse hook');
    } else {
      console.log('ℹ️  HLK PreToolUse hook đã có');
    }

    // 2. Cập nhật MCP server dùng HLK wrapper
    if (!s.mcpServers) s.mcpServers = {};
    const cur = s.mcpServers['claude-flow'];
    const usesHlk = cur?.args?.some(a => typeof a === 'string' && a.includes('ruflo-hlk-mcp'));
    if (!usesHlk) {
      s.mcpServers['claude-flow'] = {
        command: 'node',
        args: ['HLK/wrappers/ruflo-hlk-mcp.mjs', 'mcp', 'start']
      };
      console.log('✅ Đã cập nhật MCP wrapper dùng HLK');
    } else {
      console.log('ℹ️  MCP server đã dùng HLK wrapper');
    }

    fs.writeFileSync(path, JSON.stringify(s, null, 2) + '\n', 'utf8');
    console.log('✅ Đã ghi .claude/settings.json');
  "
}

# ============================================================================
# Bước 5: Patch .gitattributes
# ============================================================================

patch_gitattributes() {
  log_info "Bước 5: Patch .gitattributes..."

  local gitattr_path="${WORKSPACE_ROOT}/.gitattributes"
  local content=""
  if [[ -f "${gitattr_path}" ]]; then
    content="$(cat "${gitattr_path}")"
  fi

  local lines=(
    "# HLK config — always keep our version on merge conflicts"
    "HLK/config/hlk.config.json merge=ours"
    ""
    "# HLK wrappers — keep ours"
    "HLK/wrappers/** merge=ours"
    ""
    "# HLK security — keep ours"
    "HLK/security/** merge=ours"
    ""
    "# HLK docs — keep ours"
    "HLK/docs/** merge=ours"
    ""
    "# .claude settings — keep ours"
    ".claude/settings.json merge=ours"
  )

  local modified=0
  for line in "${lines[@]}"; do
    if ! echo "${content}" | grep -qF "${line}"; then
      content="${content}"$'\n'"${line}"
      modified=1
    fi
  done

  if [[ "${modified}" == "1" ]]; then
    echo "${content}" > "${gitattr_path}"
    log_ok "Đã cập nhật .gitattributes với merge=ours"
  else
    log_info ".gitattributes đã chứa HLK merge rules"
  fi
}

# ============================================================================
# Bước 6: Patch .gitignore
# ============================================================================

patch_gitignore() {
  log_info "Bước 6: Patch .gitignore..."

  local gitignore_path="${WORKSPACE_ROOT}/.gitignore"
  local content=""
  if [[ -f "${gitignore_path}" ]]; then
    content="$(cat "${gitignore_path}")"
  fi

  local patterns=(
    "HLK/config/secrets.*"
    "HLK/config/*.local.json"
    "HLK/logs/"
    "*.rvf"
    "*.rvf.lock"
    "agentdb.rvf"
    "agentdb.rvf.lock"
    ".env"
    ".env.*"
    "!.env.example"
    "!.env.*.example"
    "example.env"
    "HLK/dist/*.tgz"
    "HLK/dist/"
  )

  local modified=0
  for pattern in "${patterns[@]}"; do
    if ! echo "${content}" | grep -qxF "${pattern}"; then
      content="${content}"$'\n'"${pattern}"
      modified=1
    fi
  done

  if [[ "${modified}" == "1" ]]; then
    echo "${content}" > "${gitignore_path}"
    log_ok "Đã cập nhật .gitignore bảo vệ secrets"
  else
    log_info ".gitignore đã bảo vệ đầy đủ"
  fi
}

# ============================================================================
# Bước 7: Copy skills HLK
# ============================================================================

copy_skills() {
  log_info "Bước 7: Copy skills HLK..."

  local skills_src="${HLK_TARGET_DIR}/skills"
  if [[ ! -d "${skills_src}" ]]; then
    log_warn "Không tìm thấy HLK/skills/ — bỏ qua"
    return
  fi

  # Copy sang .claude/skills/
  local claude_skills="${WORKSPACE_ROOT}/.claude/skills"
  mkdir -p "${claude_skills}"

  # Copy sang .devin/skills/
  local devin_skills="${WORKSPACE_ROOT}/.devin/skills"
  mkdir -p "${devin_skills}"

  for skill_dir in "${skills_src}"/hlk-*; do
    [[ -d "${skill_dir}" ]] || continue
    local name
    name="$(basename "${skill_dir}")"

    cp -r "${skill_dir}" "${claude_skills}/${name}"
    cp -r "${skill_dir}" "${devin_skills}/${name}"
    log_info "  Đã copy skill ${name}"
  done

  log_ok "Đã copy skills sang .claude/skills/ và .devin/skills/"
}

# ============================================================================
# Bước 8: Cài .githooks/post-merge
# ============================================================================

install_githooks() {
  log_info "Bước 8: Cài .githooks/post-merge..."

  local template="${HLK_TARGET_DIR}/skills/post-merge.template"
  if [[ ! -f "${template}" ]]; then
    log_warn "Không tìm thấy post-merge.template — bỏ qua"
    return
  fi

  local githooks_dir="${WORKSPACE_ROOT}/.githooks"
  mkdir -p "${githooks_dir}"

  cp "${template}" "${githooks_dir}/post-merge"
  chmod +x "${githooks_dir}/post-merge"
  log_ok "Đã cài .githooks/post-merge"

  # Kích hoạt core.hooksPath nếu chưa
  local current_hooks_path
  current_hooks_path="$(git config core.hooksPath 2>/dev/null || echo "")"
  if [[ -z "${current_hooks_path}" ]]; then
    git config core.hooksPath .githooks
    log_ok "Đã kích hoạt git config core.hooksPath .githooks"
  elif [[ "${current_hooks_path}" != ".githooks" ]]; then
    log_warn "core.hooksPath hiện tại = \"${current_hooks_path}\" (không phải .githooks)"
    log_warn "Chạy: git config core.hooksPath .githooks"
  fi
}

# ============================================================================
# Bước 9: Tạo secrets.env nếu chưa có
# ============================================================================

create_secrets() {
  local secrets_path="${HLK_TARGET_DIR}/config/secrets.env"
  if [[ -f "${secrets_path}" ]]; then
    log_info "HLK/config/secrets.env đã có — giữ nguyên"
    return
  fi

  local example_path="${HLK_TARGET_DIR}/config/secrets.env.example"
  if [[ -f "${example_path}" ]]; then
    cp "${example_path}" "${secrets_path}"
    log_ok "Đã tạo HLK/config/secrets.env từ example"
  else
    log_warn "Không tìm thấy secrets.env.example — bỏ qua"
  fi
}

# ============================================================================
# Bước 10: Run HLK integrity verify
# ============================================================================

run_verify() {
  log_info "Bước 9: HLK integrity verify..."

  local verify="${HLK_TARGET_DIR}/wrappers/hlk-verify-integrity.js"
  if [[ ! -f "${verify}" ]]; then
    log_warn "Không tìm thấy hlk-verify-integrity.js — bỏ qua"
    return
  fi

  if ! node "${verify}"; then
    log_error "HLK integrity verify FAILED"
    exit 1
  fi

  log_ok "HLK integrity verify PASSED"
}

# ============================================================================
# Cleanup
# ============================================================================

cleanup() {
  if [[ "${SKIP_CLONE}" == "1" ]]; then
    return
  fi
  if [[ -n "${TEMP_DIR}" ]] && [[ "${TEMP_DIR}" != "$(pwd)" ]]; then
    rm -rf "${TEMP_DIR}" 2>/dev/null || true
  fi
}

# ============================================================================
# Main
# ============================================================================

trap cleanup EXIT

download_hlk
install_ruflo
copy_hlk
patch_settings
patch_gitattributes
patch_gitignore
copy_skills
install_githooks
create_secrets
run_verify

echo ""
log_ok "HLK đã cài đặt xong."
echo ""
log_info "Các bước tiếp theo:"
log_info "  1. Mở HLK/config/secrets.env và điền API keys / tokens thật."
log_info "  2. Khởi động lại Claude Code để MCP server dùng HLK wrapper."
log_info "  3. Test: node HLK/wrappers/hlk-hook-bridge.mjs < test-secret.json"
log_info "  4. Đọc HLK/docs/01-tong-quan-va-kien-truc.md để tìm hiểu thêm."
echo ""
log_info "Pull update từ upstream ruflo + reinstall HLK:"
log_info "  node HLK/upstream/hlk-upstream-pull.mjs --yes"
