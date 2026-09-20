#!/usr/bin/env node
// ============================================================================
// HLK/chain/hlk_wrappers/verify-first-wrapper.mjs
// ----------------------------------------------------------------------------
// CLI wrapper cho verify-first chain. Thêm HLK loader + audit log + rotation.
//
// Cách dùng:
//   node HLK/chain/hlk_wrappers/verify-first-wrapper.mjs <BRD.md> [options]
// ============================================================================

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, appendFileSync, statSync, renameSync, readdirSync, unlinkSync } from 'node:fs';
import { resolve, dirname, basename, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// === Detect platform ===
const isWindows = process.platform === 'win32';
const pythonCmd = isWindows ? 'py' : 'python3';

// === Audit log ===
const AUDIT_LOG = resolve(
  process.env.AHD_AUDIT_LOG || '.devin/state/verify_first_audit.jsonl'
);

const AUDIT_MAX_SIZE_MB = parseFloat(process.env.AHD_AUDIT_MAX_SIZE_MB || '10.0');

/**
 * Rotate audit log nếu file vượt threshold.
 * Pattern: verify-first_audit_2026-08-27.jsonl
 */
function rotateAuditLog() {
  if (!existsSync(AUDIT_LOG)) return;
  const sizeMB = statSync(AUDIT_LOG).size / (1024 * 1024);
  if (sizeMB < AUDIT_MAX_SIZE_MB) return;
  // Date suffix (UTC)
  const today = new Date().toISOString().slice(0, 10);
  const ext = '.jsonl';
  const base = basename(AUDIT_LOG, ext);
  const parent = dirname(AUDIT_LOG);
  const archive = join(parent, `${base}_${today}_${Date.now()}${ext}`);
  try {
    renameSync(AUDIT_LOG, archive);
  } catch (e) {
    process.stderr.write(`[wrapper] rotate failed: ${e.message}\n`);
  }
}

/**
 * Ghi 1 entry audit (sau khi rotate nếu cần).
 */
function writeAudit(entry) {
  try {
    rotateAuditLog();
    mkdirSync(dirname(AUDIT_LOG), { recursive: true });
    appendFileSync(AUDIT_LOG, JSON.stringify({
      ...entry,
      timestamp: new Date().toISOString(),
    }) + '\n', 'utf-8');
  } catch (e) {
    process.stderr.write(`[wrapper] audit write failed: ${e.message}\n`);
  }
}

// === Resolve CLI path ===
const CLI_PATH = resolve(__dirname, '../../../chain/verify_first_cli.py');

if (!existsSync(CLI_PATH)) {
  process.stderr.write(`[wrapper] CLI not found: ${CLI_PATH}\n`);
  process.exit(2);
}

// === Parse args ===
const args = process.argv.slice(2);
if (args.length === 0) {
  process.stderr.write('Usage: node HLK/chain/hlk_wrappers/verify-first-wrapper.mjs <BRD.md> [options]\n');
  process.exit(2);
}

// === Spawn CLI ===
writeAudit({ event: 'wrapper_start', args, python_cmd: pythonCmd });

const child = spawn(pythonCmd, [CLI_PATH, ...args], {
  stdio: 'inherit',
  env: process.env,
});

child.on('exit', (code) => {
  writeAudit({ event: 'wrapper_end', args, exit_code: code });
  process.exit(code ?? 1);
});

child.on('error', (err) => {
  process.stderr.write(`[wrapper] spawn error: ${err.message}\n`);
  writeAudit({ event: 'wrapper_error', args, error: err.message });
  process.exit(1);
});
