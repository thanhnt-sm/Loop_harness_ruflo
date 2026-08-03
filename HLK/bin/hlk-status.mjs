#!/usr/bin/env node
/**
 * hlk-status.mjs
 * ==============
 * Kiểm tra trạng thái HLK trong workspace hoặc package.
 *
 * Cách dùng:
 *   npx hlk-status
 *   npx hlk-status --self-test
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const HLK_PACKAGE_ROOT = path.resolve(__dirname, '..');
const WORKSPACE_ROOT = process.cwd();
const HLK_TARGET_DIR = path.join(WORKSPACE_ROOT, 'HLK');

function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

// ---------------------------------------------------------------------------
// Self-test package
// ---------------------------------------------------------------------------

function selfTestPackage() {
  const pkg = readJson(path.join(HLK_PACKAGE_ROOT, 'package.json'));
  const config = readJson(path.join(HLK_PACKAGE_ROOT, 'config', 'hlk.config.json'));

  log('info', `Package HLK: ${pkg.name}@${pkg.version}`);
  log('info', `HLK config version: ${config.version}`);

  if (pkg.version !== config.version) {
    log('warn', 'package.json version khác hlk.config.json version.');
  } else {
    log('success', 'Version đồng nhất.');
  }

  const required = [
    'bin/hlk-install.mjs',
    'bin/hlk-update.mjs',
    'bin/hlk-pack.mjs',
    'bin/hlk-status.mjs',
    'git-tools/hlk-git-doctor.mjs',
    'git-tools/hlk-git-commit.mjs',
    'git-tools/hlk-git-push.mjs',
    'git-tools/hlk-git-safe-sync.mjs',
    'git-tools/lib/hlk-git-lib.mjs',
    'config/hlk.config.json',
    'wrappers/hlk-hook-bridge.mjs',
    'security/sanitizer.js',
  ];

  for (const f of required) {
    const p = path.join(HLK_PACKAGE_ROOT, f);
    if (!fs.existsSync(p)) {
      log('error', `Thiếu ${f}`);
      process.exit(1);
    }
  }
  log('success', 'Tất cả file bắt buộc tồn tại.');

  // Syntax check
  for (const f of ['bin/hlk-install.mjs', 'bin/hlk-update.mjs', 'bin/hlk-pack.mjs', 'bin/hlk-status.mjs']) {
    const p = path.join(HLK_PACKAGE_ROOT, f);
    const r = spawnSync(process.execPath, ['--check', p], { stdio: 'pipe' });
    if (r.status !== 0) {
      log('error', `Lỗi cú pháp ${f}`);
      process.stderr.write(r.stderr);
      process.exit(1);
    }
  }
  log('success', 'Tất cả scripts pass cú pháp.');
}

// ---------------------------------------------------------------------------
// Check workspace
// ---------------------------------------------------------------------------

function checkWorkspace() {
  if (!fs.existsSync(HLK_TARGET_DIR)) {
    log('error', 'HLK chưa được cài trong workspace.');
    process.exit(1);
  }

  const config = readJson(path.join(HLK_TARGET_DIR, 'config', 'hlk.config.json'));
  log('info', `HLK version: ${config.version}`);
  log('info', `HLK enabled: ${config.hlk_enabled}`);

  const settingsPath = path.join(WORKSPACE_ROOT, '.claude', 'settings.json');
  if (fs.existsSync(settingsPath)) {
    const s = readJson(settingsPath);
    const hasHook = s.hooks?.PreToolUse?.some((h) =>
      h.hooks?.some((x) => x.command?.includes('hlk-hook-bridge'))
    );
    if (hasHook) {
      log('success', 'HLK PreToolUse hook đã cài.');
    } else {
      log('warn', 'Thiếu HLK PreToolUse hook trong .claude/settings.json');
    }

    const hasMcp = s.mcpServers?.['claude-flow']?.args?.some((a) => a.includes('ruflo-hlk-mcp'));
    if (hasMcp) {
      log('success', 'HLK MCP wrapper đã cài.');
    } else {
      log('warn', 'MCP server chưa dùng HLK wrapper.');
    }
  }

  const verifyScript = path.join(HLK_TARGET_DIR, 'wrappers', 'hlk-verify-integrity.js');
  if (fs.existsSync(verifyScript)) {
    const r = spawnSync(process.execPath, [verifyScript], { cwd: WORKSPACE_ROOT, stdio: 'inherit' });
    if (r.status !== 0) {
      log('error', 'HLK integrity verify thất bại.');
      process.exit(1);
    }
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  const args = process.argv.slice(2);
  if (args.includes('--self-test')) {
    log('info', '=== HLK Package Self-Test ===');
    selfTestPackage();
    return;
  }

  log('info', '=== HLK Workspace Status ===');
  checkWorkspace();
}

main();
