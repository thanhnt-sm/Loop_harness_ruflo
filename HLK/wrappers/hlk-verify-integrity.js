/**
 * HLK Integrity Verifier
 * ======================
 * Mục đích tổng thể:
 *   Kiểm tra tính toàn vẹn của lớp HLK sau khi merge upstream.
 *
 * Usage:
 *   node HLK/wrappers/hlk-verify-integrity.js
 *
 * Exit codes:
 *   0 = tất cả kiểm tra PASS
 *   1 = có ít nhất một kiểm tra FAIL
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const HLK_ROOT = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(HLK_ROOT, '..');

// Các file/thư mục bắt buộc phải tồn tại
const REQUIRED_FILES = [
  'config/hlk.config.json',
  'config/secrets.env.example',
  'wrappers/hlk-loader.js',
  'wrappers/hlk-hook-bridge.mjs',
  'wrappers/hlk-verify-integrity.js',
  'wrappers/git-upstream-sync.sh',
  'wrappers/git-upstream-sync.ps1',
  'wrappers/ruflo-hlk.mjs',
  'wrappers/ruflo-hlk.cmd',
  'wrappers/ruflo-hlk.ps1',
  'security/sanitizer.js',
  'security/vault-bridge.js',
  'custom-hooks/README.md',
  'README.md',
];

let failures = 0;

// ---------------------------------------------------------------------------
// Tiện ích
// ---------------------------------------------------------------------------

function check(label, condition) {
  if (condition) {
    console.log(`  ✅ ${label}`);
  } else {
    console.log(`  ❌ ${label}`);
    failures++;
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra 1: Các file bắt buộc
// ---------------------------------------------------------------------------

console.log('\n[HLK Integrity Check] Verifying HLK layer...\n');
console.log('📂 Required files:');

for (const rel of REQUIRED_FILES) {
  const full = path.join(HLK_ROOT, rel);
  check(rel, fs.existsSync(full));
}

// ---------------------------------------------------------------------------
// Kiểm tra 2: Cấu hình JSON hợp lệ
// ---------------------------------------------------------------------------

console.log('\n⚙️ Config validation:');

const configPath = path.join(HLK_ROOT, 'config/hlk.config.json');
let config = null;

try {
  const raw = fs.readFileSync(configPath, 'utf8');
  config = JSON.parse(raw);
  check('hlk.config.json là JSON hợp lệ', true);
  check('Trường hlk_enabled tồn tại', 'hlk_enabled' in config);
  check('Trường version tồn tại', 'version' in config);
  check('security_rules.redact_patterns là mảng', Array.isArray(config?.security_rules?.redact_patterns));
  check('upstream.repository và upstream.remote_name có giá trị',
    !!(config?.upstream?.repository && config?.upstream?.remote_name));
} catch (err) {
  check(`hlk.config.json lỗi parse: ${err.message}`, false);
}

// ---------------------------------------------------------------------------
// Kiểm tra 3: .gitignore bảo vệ HLK
// ---------------------------------------------------------------------------

console.log('\n🔒 Gitignore protection:');

const gitignorePath = path.resolve(REPO_ROOT, '.gitignore');

try {
  const gitignore = fs.readFileSync(gitignorePath, 'utf8');
  check('HLK/config/secrets.* trong .gitignore', gitignore.includes('HLK/config/secrets.'));
  check('HLK/logs/ trong .gitignore', gitignore.includes('HLK/logs/'));
  check('*.rvf trong .gitignore', gitignore.includes('.rvf') || gitignore.includes('*.rvf'));
  check('*.rvf.lock trong .gitignore', gitignore.includes('.rvf.lock') || gitignore.includes('*.rvf.lock'));
} catch {
  check('.gitignore đọc được', false);
}

// ---------------------------------------------------------------------------
// Kiểm tra 4: Thư mục prompts
// ---------------------------------------------------------------------------

console.log('\n📝 Prompts:');

const promptsDir = path.join(HLK_ROOT, 'prompts');
try {
  const prompts = fs.readdirSync(promptsDir).filter((f) => f.endsWith('.md'));
  check(`${prompts.length} prompt files found`, prompts.length >= 4);
} catch {
  check('Thư mục prompts đọc được', false);
}

// ---------------------------------------------------------------------------
// Kiểm tra 5: Không có file .rvf bị git track
// ---------------------------------------------------------------------------

console.log('\n🛡️ Git tracking safety:');

/**
 * Kiểm tra một file có đang bị git track không.
 */
function checkTracked(file) {
  const result = spawnSync('git', ['ls-files', '--', file], {
    cwd: REPO_ROOT,
    encoding: 'utf8',
  });
  const tracked = result.stdout.trim().length > 0;
  check(`${file} KHÔNG bị git track`, !tracked);
}

checkTracked('agentdb.rvf');
checkTracked('agentdb.rvf.lock');

// ---------------------------------------------------------------------------
// Tổng kết
// ---------------------------------------------------------------------------

console.log('\n' + '─'.repeat(50));

if (failures === 0) {
  console.log('🎉 All HLK integrity checks PASSED!\n');
  if (config) {
    console.log(`   HLK Version:  ${config.version || '?'}`);
    console.log(`   HLK Enabled:  ${config.hlk_enabled}`);
    console.log(`   Ruflo Tested: ${config.ruflo_version_tested || '?'}`);
  }
} else {
  console.log(`⚠️ ${failures} check(s) FAILED — review HLK layer\n`);
}

process.exit(failures > 0 ? 1 : 0);
