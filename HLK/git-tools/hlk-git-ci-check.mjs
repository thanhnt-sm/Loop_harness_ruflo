#!/usr/bin/env node
/**
 * hlk-git-ci-check.mjs
 * ====================
 * Kiểm tra CI/CD readiness trước khi push:
 * 1. .githooks/ — cấu trúc, core.hooksPath, chạy pre-commit trực tiếp
 * 2. .github/workflows/ — file tồn tại, YAML hợp lệ
 * 3. Local CI equivalents — pytest, governance, hook integrity, bandit (nếu có)
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-ci-check.mjs [--no-tests] [--no-bash-hooks]
 *
 * Options:
 *   --no-tests       Bỏ qua bước chạy pytest
 *   --no-bash-hooks  Bỏ qua việc chạy .githooks/pre-commit trực tiếp
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import {
  log,
  runGit,
  getRepoRoot,
} from './lib/hlk-git-lib.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CWD = process.cwd();

const args = process.argv.slice(2);
const SKIP_TESTS = args.includes('--no-tests');
const SKIP_BASH_HOOKS = args.includes('--no-bash-hooks');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function runCmd(cmd, cmdArgs, cwd = CWD, inherit = false) {
  const result = spawnSync(cmd, cmdArgs, {
    cwd,
    encoding: 'utf8',
    stdio: inherit ? 'inherit' : ['pipe', 'pipe', 'pipe'],
  });
  return {
    status: result.status ?? 1,
    stdout: result.stdout?.toString() ?? '',
    stderr: result.stderr?.toString() ?? '',
  };
}

function findPython() {
  try {
    const r = runCmd('python', ['--version']);
    if (r.status === 0) return 'python';
  } catch { /* */ }
  try {
    const r = runCmd('python3', ['--version']);
    if (r.status === 0) return 'python3';
  } catch { /* */ }
  return null;
}

// ---------------------------------------------------------------------------
// Check 1: .githooks structure + core.hooksPath
// ---------------------------------------------------------------------------

function checkGithooks() {
  const errors = [];
  const warnings = [];

  const hooksDir = path.join(CWD, '.githooks');
  if (!fs.existsSync(hooksDir)) {
    errors.push('Thư mục .githooks/ không tồn tại');
    return { errors, warnings, checked: false };
  }

  // Kiểm tra hook files
  const expectedHooks = ['pre-commit', 'post-merge'];
  const actualHooks = fs.readdirSync(hooksDir, { withFileTypes: true })
    .filter(e => e.isFile())
    .map(e => e.name);

  for (const h of expectedHooks) {
    if (!actualHooks.includes(h)) {
      errors.push(`Hook ${h} trong .githooks/ không tìm thấy`);
    } else {
      log('info', `  ✅ .githooks/${h} tồn tại`);
    }
  }

  // Kiểm tra core.hooksPath
  const r = runGit(['config', 'core.hooksPath']);
  if (r.status !== 0 || r.stdout.trim() !== '.githooks') {
    warnings.push('core.hooksPath chưa được cấu hình đến .githooks/');
    log('warn', '  core.hooksPath chưa config → chạy: git config core.hooksPath .githooks');
    // Tự động cố định
    const fix = runGit(['config', 'core.hooksPath', '.githooks']);
    if (fix.status === 0) {
      log('success', '  ✅ Đã tự động cấu hình core.hooksPath = .githooks');
    }
  } else {
    log('success', '  ✅ core.hooksPath = .githooks');
  }

  return { errors, warnings, checked: true };
}

// ---------------------------------------------------------------------------
// Check 2: .github/workflows YAML
// ---------------------------------------------------------------------------

async function checkGithubWorkflows() {
  const errors = [];
  const warnings = [];

  const workflowsDir = path.join(CWD, '.github', 'workflows');
  if (!fs.existsSync(workflowsDir)) {
    errors.push('Thư mục .github/workflows/ không tồn tại');
    return { errors, warnings, checked: false };
  }

  const ymlFiles = fs.readdirSync(workflowsDir)
    .filter(f => f.endsWith('.yml') || f.endsWith('.yaml'));

  if (ymlFiles.length === 0) {
    warnings.push('Không có workflow nào trong .github/workflows/');
    return { errors, warnings, checked: false };
  }

  const yamlModule = await loadYamlModule();
  for (const f of ymlFiles) {
    const fpath = path.join(workflowsDir, f);
    const content = fs.readFileSync(fpath, 'utf8');

    // Kiểm tra YAML hợp lệ
    if (yamlModule) {
      try {
        const parsed = yamlModule.parse(content);
        const name = parsed.name || f;
        const jobs = Object.keys(parsed.jobs || {});
        log('info', `  ✅ ${f} (${name}) — jobs: ${jobs.join(', ')}`);

        // Kiểm tra job names có trùng lặp không
        for (const [jobName, job] of Object.entries(parsed.jobs)) {
          if (typeof job === 'object' && job !== null) {
            const runsOn = job['runs-on'] || job['runs-on'] === false ? job['runs-on'] : '?';
            log('info', `    → ${jobName}: runs-on ${runsOn}`);
          }
        }
      } catch (e) {
        errors.push(`Workflow ${f} không parse được YAML: ${e.message}`);
      }
    } else {
      // Fallback: check for basic structure
      if (content.includes('name:') && content.includes('jobs:')) {
        log('info', `  ✅ ${f} — cấu trúc cơ bản OK (không có yaml module để parse sâu)`);
      } else {
        warnings.push(`Workflow ${f} có thể thiếu 'name:' hoặc 'jobs:'`);
      }
    }
  }

  return { errors, warnings, checked: true };
}

async function loadYamlModule() {
  try {
    const mod = await import('yaml');
    return mod;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Check 3: Local CI equivalents
// ---------------------------------------------------------------------------

function checkHookIntegrity(py) {
  const errors = [];
  const warnings = [];

  const f = '.devin/scripts/hook_integrity.py';
  if (!fs.existsSync(path.join(CWD, f))) {
    warnings.push(`Không tìm thấy ${f} — bỏ qua hook integrity check`);
    return errors;
  }

  log('info', `  Chạy: ${py} ${f} --verify`);
  const r1 = runCmd(py, [f, '--verify']);
  if (r1.status !== 0) {
    errors.push(`Hook integrity --verify thất bại: ${r1.stderr.trim().slice(0, 200)}`);
  } else {
    log('success', '  ✅ Hook integrity --verify OK');
  }

  log('info', `  Chạy: ${py} ${f} --verify-order`);
  const r2 = runCmd(py, [f, '--verify-order']);
  if (r2.status !== 0) {
    errors.push(`Hook integrity --verify-order thất bại: ${r2.stderr.trim().slice(0, 200)}`);
  } else {
    log('success', '  ✅ Hook integrity --verify-order OK');
  }

  return errors;
}

function checkGovernance(py) {
  const errors = [];
  const warnings = [];

  const f = 'tools/check_governance.py';
  if (!fs.existsSync(path.join(CWD, f))) {
    warnings.push(`Không tìm thấy ${f} — bỏ qua governance check`);
    return errors;
  }

  log('info', `  Chạy: ${py} ${f}`);
  const r = runCmd(py, [f]);
  if (r.status !== 0) {
    errors.push(`Governance check thất bại: ${r.stdout.trim().slice(0, 200)}`);
  } else {
    log('success', `  ✅ ${r.stdout.trim() || 'Governance OK'}`);
  }

  return errors;
}

function checkPytest(py) {
  const errors = [];
  const warnings = [];

  log('info', `  Chạy: ${py} -m pytest tests/ -q --tb=short --override-ini="addopts=-ra"`);
  const r = runCmd(py, ['-m', 'pytest', 'tests/', '-q', '--tb=short', '--override-ini=addopts=-ra'], CWD, false);
  const output = (r.stdout + r.stderr).slice(-500);
  if (r.status !== 0) {
    errors.push(`pytest thất bại (exit ${r.status}). Output:\n${output}`);
  } else {
    log('success', '  ✅ pytest PASSED');
    log('info', `    ${output.split('\n').filter(l => l.trim()).slice(-3).join('\n    ')}`);
  }

  return errors;
}

function checkBandit(py) {
  const errors = [];
  const warnings = [];

  const r = runCmd(py, ['-c', 'import bandit']);
  if (r.status !== 0) {
    warnings.push('bandit chưa cài đặt locally (CI sẽ cài đặt tự động)');
    log('warn', '  [SKIP] bandit không có sẵn locally (CI sẽ cài đặt)');
    return errors;
  }

  log('info', `  Chạy: ${py} -m bandit -r .devin/scripts .devin/hooks tools`);
  const r2 = runCmd(py, ['-m', 'bandit', '-q', '-r', '.devin/scripts', '.devin/hooks', 'tools']);
  if (r2.status !== 0) {
    // bandit trả về non-zero nếu tìm thấy issues — chỉ báo cáo, không block
    const out = r2.stdout.trim();
    if (out) log('warn', `  [WARN] bandit tìm thấy issues:\n${out.slice(0, 300)}`);
  }
  log('success', '  ✅ bandit scan hoàn thành');

  return errors;
}

function checkHlkChainImport(py) {
  const errors = [];
  const warnings = [];

  log('info', '  Kiểm tra HLK chain imports...');
  const r = runCmd(py, ['-c', 'import sys; sys.path.insert(0, "HLK"); import chain; print("OK")'], CWD, false);
  if (r.status !== 0) {
    errors.push(`HLK chain import thất bại: ${r.stderr.trim().slice(0, 200)}`);
  } else {
    log('success', `  ✅ ${r.stdout.trim()}`);
  }

  return errors;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Git CI Check ===');
  log('info', `Workspace: ${CWD}`);

  const repoRoot = getRepoRoot(CWD);
  if (!repoRoot) {
    log('error', 'Không phải git repo.');
    process.exit(1);
  }

  let hasErrors = false;
  let totalWarnings = 0;

  // --- .githooks ---
  log('info', '');
  log('info', '--- Check 1: .githooks ---');
  const hooksResult = checkGithooks();
  if (hooksResult.errors.length > 0) {
    for (const e of hooksResult.errors) log('error', `  ❌ ${e}`);
    hasErrors = true;
  }
  if (hooksResult.warnings.length > 0) {
    for (const w of hooksResult.warnings) log('warn', `  ⚠️  ${w}`);
    totalWarnings += hooksResult.warnings.length;
  }

  // Chạy pre-commit hook trực tiếp (nếu có bash hooks)
  if (!SKIP_BASH_HOOKS && hooksResult.checked) {
    const preCommitPath = path.join(CWD, '.githooks', 'pre-commit');
    if (fs.existsSync(preCommitPath)) {
      log('info', '  Chạy .githooks/pre-commit trực tiếp...');
      // Thử tìm shell có sẵn: bash (Linux/macOS, Git-Bash Windows), sau đó sh
      let shell = null;
      for (const candidate of ['bash', 'sh']) {
        const probe = runCmd(candidate, ['--version']);
        if (probe.status === 0) { shell = candidate; break; }
      }
      if (!shell) {
        log('warn', '  [SKIP] Không tìm thấy bash/sh — bỏ qua chạy pre-commit trực tiếp');
        log('info', '  (Git sẽ tự chạy pre-commit qua core.hooksPath khi commit)');
      } else {
        const r = runCmd(shell, [preCommitPath], CWD, true);
        if (r.status !== 0) {
          log('error', '  ❌ pre-commit hook chạy thất bại');
          hasErrors = true;
        } else {
          log('success', '  ✅ pre-commit hook PASSED');
        }
      }
    }
  }

  // --- .github/workflows ---
  log('info', '');
  log('info', '--- Check 2: .github/workflows ---');
  const wfResult = await checkGithubWorkflows();
  if (wfResult.errors.length > 0) {
    for (const e of wfResult.errors) log('error', `  ❌ ${e}`);
    hasErrors = true;
  }
  if (wfResult.warnings.length > 0) {
    for (const w of wfResult.warnings) log('warn', `  ⚠️  ${w}`);
    totalWarnings += wfResult.warnings.length;
  }

  // --- Local CI equivalents ---
  const py = findPython();
  if (py) {
    log('info', '');
    log('info', `--- Check 3: Local CI equivalents (Python: ${py}) ---`);

    const ciErrors = [];

    log('info', '  [A] Hook integrity...');
    ciErrors.push(...checkHookIntegrity(py));

    log('info', '  [B] Governance check...');
    ciErrors.push(...checkGovernance(py));

    if (!SKIP_TESTS) {
      log('info', '  [C] pytest...');
      ciErrors.push(...checkPytest(py));

      log('info', '  [D] HLK chain import...');
      ciErrors.push(...checkHlkChainImport(py));
    } else {
      log('info', '  [C/D] Bỏ qua pytest và HLK chain import (--no-tests)');
    }

    log('info', '  [E] Bandit SAST...');
    ciErrors.push(...checkBandit(py));

    if (ciErrors.length > 0) {
      for (const e of ciErrors) log('error', `  ❌ ${e}`);
      hasErrors = true;
    }
  } else {
    log('warn', '  Python không tìm thấy — bỏ qua local CI checks');
    totalWarnings++;
  }

  // --- Summary ---
  log('info', '');
  log('info', '=== Tổng kết CI Check ===');
  if (hasErrors) {
    log('error', '❌ Có lỗi — CI sẽ thất bại trên GitHub Actions.');
    process.exit(1);
  } else if (totalWarnings > 0) {
    log('warn', `⚠️  ${totalWarnings} cảnh báo — CI có thể bị fail tùy cấu hình.`);
    log('success', '✅ CI check hoàn thành (có cảnh báo nhẹ).');
  } else {
    log('success', '✅ Tất cả CI checks đạt — sẵn sàng push lên GitHub.');
  }
  process.exit(0);
}

main();
