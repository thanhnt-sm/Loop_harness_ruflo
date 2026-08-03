#!/usr/bin/env node
/**
 * hlk-git-lib.mjs
 * ================
 * Thư viện chung cho các git-tool scripts.
 * Cung cấp hàm chạy git, kiểm tra trạng thái, quét secrets/sensitive files.
 */

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

// ---------------------------------------------------------------------------
// Log
// ---------------------------------------------------------------------------

export function log(level, msg) {
  const icon = { error: '❌', warn: '⚠️', success: '✅', info: 'ℹ️', prompt: '❓' };
  process.stderr.write(`${icon[level] ?? '•'} ${msg}\n`);
}

// ---------------------------------------------------------------------------
// Chạy git
// ---------------------------------------------------------------------------

export function runGit(args, options = {}) {
  const result = spawnSync('git', args, {
    cwd: options.cwd ?? process.cwd(),
    encoding: 'utf8',
    stdio: options.stdio ?? ['pipe', 'pipe', 'pipe'],
    ...options,
  });

  return {
    status: result.status ?? 1,
    stdout: result.stdout?.toString() ?? '',
    stderr: result.stderr?.toString() ?? '',
  };
}

// ---------------------------------------------------------------------------
// Thông tin repo
// ---------------------------------------------------------------------------

export function getRepoRoot(cwd = process.cwd()) {
  const r = runGit(['rev-parse', '--show-toplevel'], { cwd });
  return r.status === 0 ? r.stdout.trim() : null;
}

export function isGitRepo(cwd = process.cwd()) {
  return getRepoRoot(cwd) !== null;
}

export function getBranch(cwd = process.cwd()) {
  const r = runGit(['branch', '--show-current'], { cwd });
  return r.status === 0 ? r.stdout.trim() : null;
}

export function isDetachedHead(cwd = process.cwd()) {
  const r = runGit(['rev-parse', '--abbrev-ref', 'HEAD'], { cwd });
  return r.status === 0 && r.stdout.trim() === 'HEAD';
}

export function getRemotes(cwd = process.cwd()) {
  const r = runGit(['remote', '-v'], { cwd });
  if (r.status !== 0) return [];

  const remotes = new Set();
  for (const line of r.stdout.split('\n')) {
    const parts = line.trim().split(/\s+/);
    if (parts.length >= 2) remotes.add(parts[0]);
  }
  return [...remotes];
}

export function getTrackingBranch(cwd = process.cwd()) {
  const r = runGit(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}'], { cwd });
  return r.status === 0 ? r.stdout.trim() : null;
}

// ---------------------------------------------------------------------------
// Trạng thái thay đổi
// ---------------------------------------------------------------------------

export function gitStatus(cwd = process.cwd()) {
  const r = runGit(['status', '--porcelain=v1', '-uall'], { cwd });
  if (r.status !== 0) return [];

  const entries = [];
  for (const line of r.stdout.split('\n')) {
    if (!line.trim()) continue;
    const status = line.slice(0, 2);
    const filePath = line.slice(3);
    entries.push({ status, filePath });
  }
  return entries;
}

export function hasUncommittedChanges(cwd = process.cwd()) {
  const r = runGit(['status', '--porcelain'], { cwd });
  return r.status === 0 && r.stdout.trim().length > 0;
}

export function hasUntrackedFiles(cwd = process.cwd()) {
  const r = runGit(['status', '--porcelain'], { cwd });
  if (r.status !== 0) return false;
  return r.stdout.split('\n').some((line) => line.startsWith('??'));
}

// ---------------------------------------------------------------------------
// Quét bảo mật
// ---------------------------------------------------------------------------

const SENSITIVE_GLOBS = [
  '**/.env',
  '**/.env.*',
  '**/secrets.env',
  '**/*.rvf',
  '**/*.rvf.lock',
  '**/*.pem',
  '**/*.key',
  '**/*id_rsa*',
  '**/*id_ed25519*',
];

const SECRET_PATTERNS = [
  /\bsk-[a-zA-Z0-9]{32,}\b/,
  /\bghp_[a-zA-Z0-9]{36}\b/,
  /\bghs_[a-zA-Z0-9]{36}\b/,
  /\beyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\b/,
  /\b(api[_-]?key|password|secret|token)\s*[:=]\s*['"]?[^'"\s]{8,}\b/i,
  /-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/,
];

export function listTrackedSensitiveFiles(cwd = process.cwd()) {
  const r = runGit(['ls-files'], { cwd });
  if (r.status !== 0) return [];

  const files = r.stdout.split('\n').filter(Boolean);
  const suspicious = [];

  for (const f of files) {
    const lower = f.toLowerCase();
    // Bỏ qua template/example
    if (lower.endsWith('.example') || lower.endsWith('.example.env')) continue;

    if (
      lower.includes('secrets.env') ||
      (lower.includes('.env') && !lower.includes('.env.example')) ||
      lower.endsWith('.rvf') ||
      lower.endsWith('.rvf.lock') ||
      lower.endsWith('.pem') ||
      lower.endsWith('.key') ||
      lower.includes('id_rsa') ||
      lower.includes('id_ed25519')
    ) {
      suspicious.push(f);
    }
  }

  return suspicious;
}

export function listStagedSensitiveFiles(cwd = process.cwd()) {
  // Chỉ kiểm tra file đang được thêm (A) hoặc sửa (M); bỏ qua file đang xóa (D)
  const r = runGit(['diff', '--cached', '--diff-filter=AM', '--name-only'], { cwd });
  if (r.status !== 0) return [];

  const files = r.stdout.split('\n').filter(Boolean);
  return files.filter((f) => {
    const lower = f.toLowerCase();
    return (
      lower.includes('secrets.env') ||
      lower.includes('.env') ||
      lower.endsWith('.rvf') ||
      lower.endsWith('.rvf.lock') ||
      lower.endsWith('.pem') ||
      lower.endsWith('.key') ||
      lower.includes('id_rsa') ||
      lower.includes('id_ed25519')
    );
  });
}

export function scanFilesForSecrets(filePaths, cwd = process.cwd()) {
  // Chỉ quét nội dung được thêm mới trong staged diff, không quét toàn bộ file cũ
  const args = ['diff', '--cached', '--no-color', '--no-ext-diff'];
  if (filePaths && filePaths.length > 0) {
    args.push('--');
    args.push(...filePaths);
  }
  const r = runGit(args, { cwd });
  if (r.status !== 0) return [];

  const findings = [];
  let currentFile = null;

  for (const line of r.stdout.split('\n')) {
    if (line.startsWith('diff --git ')) {
      const m = line.match(/^diff --git a\/(.+?) b\/.+$/);
      currentFile = m ? m[1] : null;
      continue;
    }
    if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@') || line.startsWith(' ')) {
      continue;
    }
    if (!line.startsWith('+') || line.startsWith('++')) continue;

    const added = line.slice(1);
    for (const pattern of SECRET_PATTERNS) {
      const matches = added.match(pattern);
      if (matches) {
        findings.push({
          file: currentFile ?? 'unknown',
          pattern: pattern.toString(),
          sample: matches[0].slice(0, 60) + (matches[0].length > 60 ? '...' : ''),
        });
        break;
      }
    }
  }

  return findings;
}

export function listUntrackedFiles(cwd = process.cwd()) {
  const r = runGit(['ls-files', '--others', '--exclude-standard'], { cwd });
  return r.status === 0 ? r.stdout.split('\n').filter(Boolean) : [];
}

export function findLargeFiles(cwd = process.cwd(), maxBytes = 100 * 1024 * 1024) {
  const r = runGit(['ls-files'], { cwd });
  if (r.status !== 0) return [];

  const large = [];
  for (const f of r.stdout.split('\n').filter(Boolean)) {
    const p = path.join(cwd, f);
    try {
      const s = fs.lstatSync(p);
      if (s.size > maxBytes) large.push({ file: f, size: s.size });
    } catch { /* ignore */ }
  }
  return large;
}

// ---------------------------------------------------------------------------
// .gitignore helpers
// ---------------------------------------------------------------------------

export function ensureGitIgnorePatterns(cwd, patterns) {
  const gitignorePath = path.join(cwd, '.gitignore');
  let content = '';
  if (fs.existsSync(gitignorePath)) {
    content = fs.readFileSync(gitignorePath, 'utf8');
  }

  let modified = false;
  for (const pattern of patterns) {
    const exists = content.split('\n').some((line) => line.trim() === pattern);
    if (!exists) {
      content += (content.endsWith('\n') ? '' : '\n') + pattern + '\n';
      modified = true;
    }
  }

  if (modified) {
    fs.writeFileSync(gitignorePath, content, 'utf8');
  }

  return modified;
}

export function listFilesNotIgnored(cwd, patterns) {
  const notIgnored = [];
  for (const pattern of patterns) {
    // git check-ignore trả về 0 nếu file bị ignore, 1 nếu không
    const r = runGit(['check-ignore', pattern], { cwd });
    if (r.status !== 0 && r.status !== 128) {
      notIgnored.push(pattern);
    }
  }
  return notIgnored;
}

// ---------------------------------------------------------------------------
// Prompt helper
// ---------------------------------------------------------------------------

export function prompt(question) {
  process.stderr.write(`${question} [y/N]: `);
  return new Promise((resolve) => {
    let input = '';
    process.stdin.resume();
    process.stdin.on('data', (data) => {
      input += data.toString();
      if (input.includes('\n')) {
        process.stdin.pause();
        const answer = input.trim().toLowerCase();
        resolve(answer === 'y' || answer === 'yes');
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Kiểm tra embedded git repos
// ---------------------------------------------------------------------------

export function findEmbeddedGitRepos(cwd = process.cwd()) {
  const r = runGit(['submodule', 'status'], { cwd });
  const submodules = r.status === 0 ? r.stdout.split('\n').filter(Boolean) : [];

  const nested = [];
  for (const entry of fs.readdirSync(cwd, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name !== '.git') {
      const gitDir = path.join(cwd, entry.name, '.git');
      if (fs.existsSync(gitDir)) {
        nested.push(entry.name);
      }
    }
  }

  return { submodules, nested };
}
