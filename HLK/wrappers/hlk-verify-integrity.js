/**
 * HLK Integrity Verifier
 * Run after upstream merge to confirm HLK layer is intact.
 *
 * Usage:
 *   node HLK/wrappers/hlk-verify-integrity.js
 *
 * Exit codes:
 *   0 = All checks passed
 *   1 = One or more checks failed
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HLK_ROOT = path.resolve(__dirname, '..');

const REQUIRED_FILES = [
  'config/hlk.config.json',
  'wrappers/hlk-loader.js',
  'wrappers/git-upstream-sync.sh',
  'wrappers/git-upstream-sync.ps1',
  'security/sanitizer.js',
  'security/vault-bridge.js',
  'README.md',
];

let failures = 0;

function check(label, condition) {
  if (condition) {
    console.log(`  ✅ ${label}`);
  } else {
    console.log(`  ❌ ${label}`);
    failures++;
  }
}

console.log('\n[HLK Integrity Check] Verifying HLK layer...\n');

// 1. Check required files exist
console.log('📂 Required files:');
for (const rel of REQUIRED_FILES) {
  const full = path.join(HLK_ROOT, rel);
  check(rel, fs.existsSync(full));
}

// 2. Validate config JSON
console.log('\n⚙️ Config validation:');
const configPath = path.join(HLK_ROOT, 'config/hlk.config.json');
let config = null;
try {
  const raw = fs.readFileSync(configPath, 'utf8');
  config = JSON.parse(raw);
  check('hlk.config.json is valid JSON', true);
  check('hlk_enabled field exists', 'hlk_enabled' in config);
  check('version field exists', 'version' in config);
  check('security_rules.redact_patterns present',
    Array.isArray(config?.security_rules?.redact_patterns));
  check('upstream config present',
    config?.upstream?.repository && config?.upstream?.remote_name);
} catch (err) {
  check(`hlk.config.json parse error: ${err.message}`, false);
}

// 3. Check .gitignore has HLK protection
console.log('\n🔒 Gitignore protection:');
const gitignorePath = path.resolve(HLK_ROOT, '../.gitignore');
try {
  const gitignore = fs.readFileSync(gitignorePath, 'utf8');
  check('HLK/config/secrets.* in .gitignore', gitignore.includes('HLK/config/secrets.'));
  check('HLK/logs/ in .gitignore', gitignore.includes('HLK/logs/'));
} catch {
  check('.gitignore readable', false);
}

// 4. Check prompts directory
console.log('\n📝 Prompts:');
const promptsDir = path.join(HLK_ROOT, 'prompts');
try {
  const prompts = fs.readdirSync(promptsDir).filter(f => f.endsWith('.md'));
  check(`${prompts.length} prompt files found`, prompts.length >= 4);
} catch {
  check('prompts directory readable', false);
}

// 5. Summary
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
