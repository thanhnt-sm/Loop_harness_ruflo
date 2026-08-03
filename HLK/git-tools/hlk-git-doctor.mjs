#!/usr/bin/env node
/**
 * hlk-git-doctor.mjs
 * ==================
 * Chẩn đoán và tự động sửa các vấn đề git thường gặp trong workspace Ruflo.
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-doctor.mjs [--fix] [--yes]
 *
 * Options:
 *   --fix   Tự động sửa các vấn đề an toàn.
 *   --yes   Không hỏi xác nhận (vẫn không force/rewrite history).
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  log,
  runGit,
  getRepoRoot,
  isGitRepo,
  getBranch,
  isDetachedHead,
  getRemotes,
  getTrackingBranch,
  gitStatus,
  hasUncommittedChanges,
  listTrackedSensitiveFiles,
  listStagedSensitiveFiles,
  listUntrackedFiles,
  scanFilesForSecrets,
  findLargeFiles,
  ensureGitIgnorePatterns,
  findEmbeddedGitRepos,
  prompt,
} from './lib/hlk-git-lib.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CWD = process.cwd();

const FIX = process.argv.includes('--fix');
const YES = process.argv.includes('--yes');

let issues = [];
let fixed = [];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function ask(question) {
  if (YES) return true;
  return prompt(question);
}

function reportIssue(level, desc, file = null) {
  issues.push({ level, desc, file });
  if (level === 'error') log('error', desc + (file ? ` → ${file}` : ''));
  else if (level === 'warn') log('warn', desc + (file ? ` → ${file}` : ''));
  else log('info', desc + (file ? ` → ${file}` : ''));
}

function addFix(desc) {
  fixed.push(desc);
  log('success', `Đã sửa: ${desc}`);
}

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

// ---------------------------------------------------------------------------
// Kiểm tra repo
// ---------------------------------------------------------------------------

function checkRepo() {
  if (!isGitRepo(CWD)) {
    reportIssue('error', 'Thư mục hiện tại không phải git repo');
    return false;
  }
  const root = getRepoRoot(CWD);
  log('info', `Git repo: ${root}`);
  return true;
}

// ---------------------------------------------------------------------------
// Kiểm tra branch
// ---------------------------------------------------------------------------

async function checkBranch() {
  if (isDetachedHead(CWD)) {
    reportIssue('error', 'HEAD bị detached. Không thể commit/push an toàn.');
    if (FIX && await ask('Bạn có muốn checkout branch main hiện tại?')) {
      const r = runGit(['checkout', 'main'], { cwd: CWD });
      if (r.status === 0) addFix('Checkout main từ detached HEAD');
    }
    return;
  }

  const branch = getBranch(CWD);
  if (!branch) {
    reportIssue('error', 'Không xác định được branch hiện tại');
    return;
  }

  log('info', `Branch hiện tại: ${branch}`);

  if (branch === 'master') {
    reportIssue('warn', 'Branch đang là "master". Đề xuất đổi thành "main".');
    if (FIX && await ask('Đổi branch master → main không?')) {
      const r = runGit(['branch', '-m', 'master', 'main'], { cwd: CWD });
      if (r.status === 0) {
        addFix('Đổi branch master → main');
      } else {
        reportIssue('error', 'Không đổi được branch', r.stderr);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra remote
// ---------------------------------------------------------------------------

async function checkRemote() {
  const remotes = getRemotes(CWD);
  if (remotes.length === 0) {
    reportIssue('error', 'Không có remote nào. Không thể push.');
    if (FIX && await ask('Thêm remote origin từ origin URL hiện có?')) {
      log('info', 'Vui lòng cung cấp URL remote:');
      // Không hỗ trợ nhập trong non-TTY; user phải tự thêm.
      log('info', 'Gợi ý: git remote add origin <URL>');
    }
    return;
  }

  log('info', `Remotes: ${remotes.join(', ')}`);

  const tracking = getTrackingBranch(CWD);
  if (!tracking) {
    reportIssue('warn', `Branch hiện tại không track remote.`);
    if (FIX && await ask(`Set upstream cho branch ${getBranch(CWD)}?`)) {
      const branch = getBranch(CWD);
      const r = runGit(['push', '-u', 'origin', branch], { cwd: CWD, stdio: 'inherit' });
      if (r.status === 0) addFix(`Set upstream origin/${branch}`);
      else reportIssue('error', 'Không set được upstream', r.stderr);
    }
  } else {
    log('info', `Tracking: ${tracking}`);
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra changes/conflict
// ---------------------------------------------------------------------------

async function checkWorkingTree() {
  const status = gitStatus(CWD);

  // Kiểm tra merge conflict
  const conflicts = status.filter((s) => s.status.includes('U') || s.status === 'AA' || s.status === 'DD' || s.status === 'UU');
  if (conflicts.length > 0) {
    reportIssue('error', `Có ${conflicts.length} file đang conflict.`, conflicts.map((x) => x.filePath).join(', '));
    if (FIX && await ask('Bạn có muốn abort merge/rebase hiện tại?')) {
      const isRebase = fs.existsSync(path.join(getRepoRoot(CWD), '.git', 'rebase-merge')) ||
        fs.existsSync(path.join(getRepoRoot(CWD), '.git', 'rebase-apply'));
      const cmd = isRebase ? ['rebase', '--abort'] : ['merge', '--abort'];
      const r = runGit(cmd, { cwd: CWD });
      if (r.status === 0) addFix('Đã abort merge/rebase');
      else reportIssue('error', 'Không abort được', r.stderr);
    }
    return;
  }

  // Kiểm tra uncommitted
  if (hasUncommittedChanges(CWD)) {
    const stats = status.reduce((acc, s) => {
      const indexStatus = s.status[0];
      const worktreeStatus = s.status[1];
      if (indexStatus !== ' ' && indexStatus !== '?') acc.staged++;
      if (worktreeStatus !== ' ' || indexStatus === '?') acc.unstaged++;
      return acc;
    }, { staged: 0, unstaged: 0 });
    reportIssue('warn', `Có thay đổi chưa commit: staged=${stats.staged}, unstaged=${stats.unstaged}`);
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra sensitive files
// ---------------------------------------------------------------------------

async function checkSensitiveFiles() {
  const tracked = listTrackedSensitiveFiles(CWD);
  if (tracked.length > 0) {
    for (const f of tracked) {
      reportIssue('error', 'File nhạy cảm đã bị track', f);
    }
    log('warn', 'Cần xóa file khỏi history bằng git filter-repo hoặc BFG. Không tự động.');
  }

  const staged = listStagedSensitiveFiles(CWD);
  if (staged.length > 0) {
    for (const f of staged) {
      reportIssue('error', 'File nhạy cảm đang staged', f);
    }
    if (FIX && await ask('Unstage các file nhạy cảm khỏi staging?')) {
      const r = runGit(['reset', 'HEAD', '--', ...staged], { cwd: CWD });
      if (r.status === 0) addFix(`Unstage ${staged.length} file nhạy cảm`);
    }
  }

  const untracked = listUntrackedFiles(CWD);
  const sensitiveUntracked = untracked.filter((f) => {
    const lower = f.toLowerCase();
    return lower.includes('secrets.env') || lower.includes('.env') || lower.endsWith('.rvf') || lower.endsWith('.rvf.lock') || lower.endsWith('.pem') || lower.endsWith('.key');
  });

  if (sensitiveUntracked.length > 0) {
    for (const f of sensitiveUntracked) {
      reportIssue('warn', 'File nhạy cảm untracked', f);
    }
    if (FIX) {
      const patterns = new Set();
      for (const f of sensitiveUntracked) {
        // Tạo pattern dựa trên vị trí
        const parts = f.split(/[\\/]/);
        if (parts.length === 1) patterns.add(parts[0]);
        else patterns.add(parts.join('/'));
      }
      const addedPatterns = [...patterns];
      const modified = ensureGitIgnorePatterns(CWD, addedPatterns);
      if (modified) addFix(`Thêm ${addedPatterns.length} pattern vào .gitignore`);
    }
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra secrets trong staged files
// ---------------------------------------------------------------------------

async function checkSecretsInStaged() {
  const r = runGit(['diff', '--cached', '--name-only', '--diff-filter=ACMR'], { cwd: CWD });
  const staged = r.status === 0 ? r.stdout.split('\n').filter(Boolean) : [];
  if (staged.length === 0) return;

  const findings = scanFilesForSecrets(staged, CWD);
  if (findings.length > 0) {
    for (const f of findings) {
      reportIssue('error', `Phát hiện secret trong staged file: ${f.sample}`, f.file);
    }
    if (FIX && await ask('Unstage các file chứa secret?')) {
      const r2 = runGit(['reset', 'HEAD', '--', ...findings.map((x) => x.file)], { cwd: CWD });
      if (r2.status === 0) addFix(`Unstage ${findings.length} file chứa secret`);
    }
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra file lớn
// ---------------------------------------------------------------------------

function checkLargeFiles() {
  const large = findLargeFiles(CWD, 100 * 1024 * 1024);
  if (large.length > 0) {
    for (const f of large) {
      reportIssue('error', `File quá lớn (>100MB): ${humanSize(f.size)}`, f.file);
    }
    log('warn', 'GitHub từ chối file >100MB. Cần dùng Git LFS hoặc xóa.');
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra embedded git repos
// ---------------------------------------------------------------------------

async function checkEmbeddedRepos() {
  const { nested, submodules } = findEmbeddedGitRepos(CWD);
  if (nested.length > 0) {
    for (const d of nested) {
      reportIssue('error', 'Phát hiện embedded git repo (nested)', d);
    }
    if (FIX && await ask('Bạn có muốn xóa .git trong các nested repo để merge vào repo chính?')) {
      for (const d of nested) {
        const gitDir = path.join(CWD, d, '.git');
        try {
          // Không xóa, đổi tên thành .git-embedded-backup để user quyết định
          fs.renameSync(gitDir, `${gitDir}-embedded-backup`);
          addFix(`Đổi tên .git trong ${d} thành .git-embedded-backup`);
        } catch (err) {
          reportIssue('error', `Không xử lý được ${d}`, err.message);
        }
      }
    }
  }

  if (submodules.length > 0) {
    log('info', `Có ${submodules.length} submodule.`);
    for (const s of submodules) {
      log('info', `  - ${s}`);
    }
  }
}

// ---------------------------------------------------------------------------
// Kiểm tra divergent
// ---------------------------------------------------------------------------

function checkDivergence() {
  const tracking = getTrackingBranch(CWD);
  if (!tracking) return;

  const r = runGit(['rev-list', '--left-right', '--count', `${tracking}...HEAD`], { cwd: CWD });
  if (r.status !== 0) return;

  const match = r.stdout.match(/(\d+)\s+(\d+)/);
  if (!match) return;

  const behind = parseInt(match[1], 10);
  const ahead = parseInt(match[2], 10);

  if (behind > 0 && ahead > 0) {
    reportIssue('error', `Branch diverged: ${behind} commit behind, ${ahead} commit ahead so với ${tracking}.`);
    log('warn', 'Cần pull/merge trước khi push. Không tự động.');
  } else if (behind > 0) {
    reportIssue('warn', `Branch ${behind} commit behind ${tracking}. Nên pull.`);
  } else if (ahead > 0) {
    log('info', `Branch ${ahead} commit ahead. Có thể push.`);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Git Doctor ===');
  log('info', `Workspace: ${CWD}`);

  if (!checkRepo()) {
    process.exit(1);
  }

  await checkBranch();
  await checkRemote();
  await checkWorkingTree();
  await checkSensitiveFiles();
  await checkSecretsInStaged();
  checkLargeFiles();
  await checkEmbeddedRepos();
  checkDivergence();

  log('info', '');
  if (issues.length === 0) {
    log('success', 'Không phát hiện vấn đề nào. Repo sạch.');
  } else {
    const errors = issues.filter((i) => i.level === 'error').length;
    const warns = issues.filter((i) => i.level === 'warn').length;
    log('warn', `Tổng kết: ${errors} lỗi, ${warns} cảnh báo.`);
    if (FIX && fixed.length > 0) {
      log('success', `Đã tự động sửa ${fixed.length} vấn đề.`);
    }
    if (errors > 0) {
      process.exit(1);
    }
  }
}

main();
