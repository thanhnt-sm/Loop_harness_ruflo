#!/usr/bin/env node
/**
 * hlk-git-commit.mjs
 * ==================
 * Commit an toàn: kiểm tra secrets, file nhạy cảm, trống, rồi mới commit.
 * Hỗ trợ --add để tự động git add các file mới/modifed (bỏ qua sensitive).
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-commit.mjs [options]
 *
 * Options:
 *   -m, --message "msg"   Commit message.
 *   -a, --add             Tự động git add tất cả file (bỏ qua sensitive).
 *   --yes                 Không hỏi xác nhận.
 *   --no-verify           Bỏ qua kiểm tra (KHÔNG khuyến nghị).
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
  gitStatus,
  listStagedSensitiveFiles,
  scanFilesForSecrets,
  scanUnstagedForSecrets,
  scanUntrackedForSecrets,
  addAllSafe,
  findLargeFiles,
  prompt,
} from './lib/hlk-git-lib.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CWD = process.cwd();

const args = process.argv.slice(2);
let MESSAGE = null;
let YES = args.includes('--yes');
let NO_VERIFY = args.includes('--no-verify');
let AUTO_ADD = args.includes('--add') || args.includes('-a');

for (let i = 0; i < args.length; i++) {
  if ((args[i] === '-m' || args[i] === '--message') && args[i + 1]) {
    MESSAGE = args[i + 1];
    i++;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function ask(question) {
  if (YES) return true;
  return prompt(question);
}

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

// ---------------------------------------------------------------------------
// Kiểm tra an toàn trước commit
// ---------------------------------------------------------------------------

async function preCommitChecks() {
  const errors = [];
  const warns = [];

  // 1. Kiểm tra repo
  if (!isGitRepo(CWD)) {
    log('error', 'Không phải git repo.');
    process.exit(1);
  }

  // 2. Kiểm tra branch
  const branch = getBranch(CWD);
  if (!branch) {
    log('error', 'Không xác định được branch.');
    process.exit(1);
  }
  log('info', `Branch: ${branch}`);

  // 2b. Nếu --add: quét secrets TRƯỚC khi add, rồi add an toàn (bỏ qua sensitive)
  if (AUTO_ADD) {
    log('info', '--add: quét secrets trong file chưa staged/untracked...');

    // Quét unstaged modified files
    const unstagedSecrets = scanUnstagedForSecrets(CWD);
    for (const f of unstagedSecrets) {
      errors.push(`Phát hiện secret trong ${f.file} (chưa staged): ${f.sample}`);
      log('error', `Phát hiện secret trong ${f.file} (chưa staged): ${f.sample}`);
    }

    // Quét untracked files
    const untrackedSecrets = scanUntrackedForSecrets(CWD);
    for (const f of untrackedSecrets) {
      errors.push(`Phát hiện secret trong ${f.file} (untracked): ${f.sample}`);
      log('error', `Phát hiện secret trong ${f.file} (untracked): ${f.sample}`);
    }

    if (errors.length > 0 && !NO_VERIFY) {
      log('error', `Tìm thấy ${errors.length} secret. Không add. Commit bị hủy.`);
      process.exit(1);
    }

    // Add an toàn — bỏ qua sensitive files
    log('info', '--add: git add tất cả file (bỏ qua sensitive)...');
    const addResult = addAllSafe(CWD);
    if (addResult.error) {
      log('error', `git add thất bại: ${addResult.error}`);
      process.exit(1);
    }
    if (addResult.added.length > 0) {
      log('success', `Đã add ${addResult.added.length} file.`);
      for (const f of addResult.added) {
        log('info', `  + ${f}`);
      }
    }
    if (addResult.skipped.length > 0) {
      log('warn', `Đã bỏ qua ${addResult.skipped.length} file nhạy cảm:`);
      for (const f of addResult.skipped) {
        log('warn', `  ! ${f}`);
      }
    }
  }

  // 3. Kiểm tra staged files
  const status = gitStatus(CWD);
  const staged = status.filter((s) => s.status[0] !== ' ' && s.status[0] !== '?');
  if (staged.length === 0) {
    log('warn', 'Không có file nào staged. Không có gì để commit.');
    log('info', 'Mẹo: dùng --add để tự động git add các file mới/modifed.');
    process.exit(0);
  }

  log('info', `Staged files: ${staged.length}`);
  for (const s of staged) {
    log('info', `  [${s.status}] ${s.filePath}`);
  }

  // 4. Kiểm tra sensitive file staged
  const sensitive = listStagedSensitiveFiles(CWD);
  if (sensitive.length > 0) {
    for (const f of sensitive) {
      errors.push(`File nhạy cảm đang staged: ${f}`);
      log('error', `File nhạy cảm đang staged: ${f}`);
    }
    const r = runGit(['reset', 'HEAD', '--', ...sensitive], { cwd: CWD });
    if (r.status === 0) {
      log('success', `Đã unstage các file nhạy cảm: ${sensitive.join(', ')}`);
    } else {
      log('error', 'Không unstage được.');
    }
  }

  // 5. Kiểm tra secret trong staged files
  const stagedPaths = staged.map((s) => s.filePath);
  const secretFindings = scanFilesForSecrets(stagedPaths, CWD);
  if (secretFindings.length > 0) {
    for (const f of secretFindings) {
      errors.push(`Phát hiện secret trong ${f.file}: ${f.sample}`);
      log('error', `Phát hiện secret trong ${f.file}: ${f.sample}`);
    }
  }

  // 6. Kiểm tra file lớn
  const large = findLargeFiles(CWD, 100 * 1024 * 1024);
  const stagedLarge = large.filter((x) => staged.some((s) => s.filePath === x.file));
  if (stagedLarge.length > 0) {
    for (const f of stagedLarge) {
      errors.push(`File quá lớn: ${f.file} (${humanSize(f.size)})`);
      log('error', `File quá lớn: ${f.file} (${humanSize(f.size)})`);
    }
  }

  // 7. Kiểm tra HLK dist tarballs bị staged
  const tarballs = staged.filter((s) => s.filePath.startsWith('HLK/dist/') && s.filePath.endsWith('.tgz'));
  if (tarballs.length > 0) {
    for (const t of tarballs) {
      warns.push(`Tarball HLK bị staged: ${t.filePath}`);
      log('warn', `Tarball HLK bị staged: ${t.filePath}`);
    }
    if (await ask('Unstage các tarball HLK?')) {
      runGit(['reset', 'HEAD', '--', ...tarballs.map((t) => t.filePath)], { cwd: CWD });
    }
  }

  if (errors.length > 0) {
    log('error', `Tìm thấy ${errors.length} lỗi nghiêm trọng. Commit bị hủy.`);
    if (!NO_VERIFY) process.exit(1);
    if (!(await ask('Bạn vẫn muốn commit bằng --no-verify?'))) {
      process.exit(1);
    }
  }

  return { staged, warns };
}

// ---------------------------------------------------------------------------
// Tạo commit message
// ---------------------------------------------------------------------------

async function getCommitMessage() {
  if (MESSAGE) return MESSAGE;

  // Gợi ý message từ các file thay đổi
  const r = runGit(['status', '--short'], { cwd: CWD });
  const lines = r.stdout.split('\n').filter(Boolean);

  const added = [];
  const modified = [];
  const deleted = [];

  for (const line of lines) {
    const st = line.slice(0, 2);
    const f = line.slice(3);
    if (st[0] === 'A') added.push(f);
    else if (st[1] === 'M') modified.push(f);
    else if (st[0] === 'D' || st[1] === 'D') deleted.push(f);
  }

  let scope = '';
  if (added.length > 0 && modified.length === 0 && deleted.length === 0) scope = 'feat';
  else if (deleted.length > 0 && added.length === 0) scope = 'chore';
  else if (lines.some((l) => l.includes('docs') || l.includes('README'))) scope = 'docs';
  else scope = 'chore';

  const topFile = lines[0]?.slice(3) ?? 'files';
  const suggestion = `${scope}: update ${topFile}`;

  if (YES) return suggestion;

  log('info', `Gợi ý commit message: "${suggestion}"`);
  process.stderr.write('Nhập commit message (Enter để dùng gợi ý): ');

  return new Promise((resolve) => {
    let input = '';
    process.stdin.resume();
    process.stdin.on('data', (data) => {
      input += data.toString();
      if (input.includes('\n')) {
        process.stdin.pause();
        const msg = input.trim() || suggestion;
        resolve(msg);
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Git Commit ===');

  const { staged, warns } = await preCommitChecks();
  if (staged.length === 0) return;

  const message = await getCommitMessage();
  if (!message) {
    log('error', 'Commit message trống.');
    process.exit(1);
  }

  if (!YES) {
    const ok = await ask(`Commit với message: "${message}"?`);
    if (!ok) {
      log('info', 'Hủy commit.');
      process.exit(0);
    }
  }

  const r = runGit(['commit', '-m', message], { cwd: CWD, stdio: 'inherit' });
  if (r.status !== 0) {
    log('error', 'Commit thất bại.');
    process.exit(r.status ?? 1);
  }

  log('success', 'Commit thành công.');
}

main();
