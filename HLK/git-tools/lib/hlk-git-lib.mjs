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

// ---------------------------------------------------------------------------
// Audit tracked artifacts (toàn bộ tree, không chỉ staged)
// ---------------------------------------------------------------------------

// High-confidence secret patterns — tái dùng từ checkpoint.py redaction (T2.6).
const TRACKED_SECRET_PATTERNS = [
  /\bsk-[a-zA-Z0-9]{32,}\b/,
  /\bghp_[a-zA-Z0-9]{36}\b/,
  /\bghs_[a-zA-Z0-9]{36}\b/,
  /\bgho_[a-zA-Z0-9]{36}\b/,
  /\bghu_[a-zA-Z0-9]{36}\b/,
  /\bAKIA[A-Z0-9]{16}\b/,
  /\bAIza[A-Za-z0-9_-]{35}\b/,
  /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/,
  /\beyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\b/,
  /-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  /\bghp_[a-f0-9]{36}\b/,
];

export function auditTrackedArtifacts(cwd = process.cwd()) {
  const r = runGit(['ls-files'], { cwd });
  if (r.status !== 0) return { status: 'error', findings: [] };

  const findings = [];
  for (const f of r.stdout.split('\n').filter(Boolean)) {
    const lower = f.toLowerCase();

    // Bỏ qua template/example (nhất quán với listTrackedSensitiveFiles)
    if (lower.endsWith('.example') || lower.endsWith('.example.env')) continue;

    // Sensitive filename trong tracked tree
    const sensitiveName =
      lower.includes('secrets.env') ||
      (lower.includes('.env') && !lower.includes('.env.example')) ||
      lower.endsWith('.rvf') ||
      lower.endsWith('.rvf.lock') ||
      lower.endsWith('.pem') ||
      lower.endsWith('.key') ||
      lower.includes('id_rsa') ||
      lower.includes('id_ed25519');

    const p = path.join(cwd, f);
    let content = null;
    try {
      const stat = fs.lstatSync(p);
      if (stat.isFile() && stat.size <= 1024 * 1024) {
        content = fs.readFileSync(p, 'utf8');
      }
    } catch { /* ignore */ }

    if (sensitiveName) {
      findings.push({ file: f, type: 'sensitive_filename', sample: f, pattern: 'sensitive_name' });
      continue;
    }

    if (content) {
      for (const pattern of TRACKED_SECRET_PATTERNS) {
        const m = content.match(pattern);
        if (m) {
          findings.push({
            file: f,
            type: 'secret',
            pattern: pattern.toString(),
            sample: m[0].slice(0, 60) + (m[0].length > 60 ? '...' : ''),
          });
          break;
        }
      }
    }
  }

  return { status: 'ok', findings };
}

export function listStagedSensitiveFiles(cwd = process.cwd()) {
  // Chỉ kiểm tra file đang được thêm (A) hoặc sửa (M); bỏ qua file đang xóa (D)
  const r = runGit(['diff', '--cached', '--diff-filter=AM', '--name-only'], { cwd });
  if (r.status !== 0) return [];

  const files = r.stdout.split('\n').filter(Boolean);
  return files.filter((f) => {
    const lower = f.toLowerCase();
    // Bỏ qua template/example (file mẫu luôn được phép)
    if (lower.endsWith('.example') || lower.endsWith('.example.env')) return false;
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

// ---------------------------------------------------------------------------
// Quét unstaged/untracked files (trước khi add)
// ---------------------------------------------------------------------------

// Liệt kê untracked files có vẻ nhạy cảm (không staged, không ignored)
export function listUntrackedSensitiveFiles(cwd = process.cwd()) {
  const untracked = listUntrackedFiles(cwd);
  return untracked.filter((f) => {
    const lower = f.toLowerCase();
    // Bỏ qua template/example
    if (lower.endsWith('.example') || lower.endsWith('.example.env')) return false;
    return (
      lower.includes('secrets.env') ||
      (lower.includes('.env') && !lower.includes('.env.example')) ||
      lower.endsWith('.rvf') ||
      lower.endsWith('.rvf.lock') ||
      lower.endsWith('.pem') ||
      lower.endsWith('.key') ||
      lower.includes('id_rsa') ||
      lower.includes('id_ed25519')
    );
  });
}

// Liệt kê modified (chưa staged) files có vẻ nhạy cảm
export function listModifiedSensitiveFiles(cwd = process.cwd()) {
  const r = runGit(['diff', '--name-only'], { cwd });
  if (r.status !== 0) return [];
  return r.stdout.split('\n').filter(Boolean).filter((f) => {
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

// Quét secrets trong unstaged diff (file đã track nhưng modified, chưa add)
export function scanUnstagedForSecrets(cwd = process.cwd()) {
  const r = runGit(['diff', '--no-color', '--no-ext-diff'], { cwd });
  if (r.status !== 0) return [];

  const findings = [];
  let currentFile = null;

  for (const line of r.stdout.split('\n')) {
    if (line.startsWith('diff --git ')) {
      const m = line.match(/^diff --git a\/(.+?) b\/.+$/);
      currentFile = m ? m[1] : null;
      continue;
    }
    if (line.startsWith('+++') || line.startsWith('---') || line.startsWith('@@') || line.startsWith(' ')) continue;
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

// Quét secrets trong untracked files (đọc nội dung file trực tiếp)
export function scanUntrackedForSecrets(cwd = process.cwd()) {
  const untracked = listUntrackedFiles(cwd);
  const findings = [];

  for (const f of untracked) {
    const p = path.join(cwd, f);
    try {
      // Bỏ qua binary file hoặc file quá lớn
      const stat = fs.lstatSync(p);
      if (!stat.isFile() || stat.size > 1024 * 1024) continue; // skip > 1MB

      const content = fs.readFileSync(p, 'utf8');
      for (const pattern of SECRET_PATTERNS) {
        const matches = content.match(pattern);
        if (matches) {
          findings.push({
            file: f,
            pattern: pattern.toString(),
            sample: matches[0].slice(0, 60) + (matches[0].length > 60 ? '...' : ''),
          });
          break;
        }
      }
    } catch { /* ignore binary/permission errors */ }
  }

  return findings;
}

// Git add an toàn: add tất cả file trừ sensitive files, trả về danh sách file đã add
export function addAllSafe(cwd = process.cwd()) {
  const status = gitStatus(cwd);
  const toAdd = [];
  const skipped = [];

  for (const s of status) {
    const lower = s.filePath.toLowerCase();
    const isSensitive =
      lower.includes('secrets.env') ||
      (lower.includes('.env') && !lower.includes('.env.example')) ||
      lower.endsWith('.rvf') ||
      lower.endsWith('.rvf.lock') ||
      lower.endsWith('.pem') ||
      lower.endsWith('.key') ||
      lower.includes('id_rsa') ||
      lower.includes('id_ed25519');

    if (isSensitive) {
      skipped.push(s.filePath);
      continue;
    }
    toAdd.push(s.filePath);
  }

  if (toAdd.length > 0) {
    const r = runGit(['add', '--', ...toAdd], { cwd });
    if (r.status !== 0) {
      return { added: [], skipped, error: r.stderr };
    }
  }

  return { added: toAdd, skipped, error: null };
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
