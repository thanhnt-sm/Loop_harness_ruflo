#!/usr/bin/env node
/**
 * HLK git merge driver — "ours" nhưng có log.
 *
 * Mục đích: `.gitattributes merge=ours` giữ bản địa khi merge upstream để bảo vệ
 * HLK customizations. Driver trước đây là `true` — im lặng hoàn toàn, nên khi
 * upstream sửa một lỗ hổng trong HLK/security/** hoặc HLK/wrappers/**, bản vá bị
 * giữ-bản-cũ một cách âm thầm (đóng băng security patch).
 *
 * Driver này: giữ nguyên ngữ nghĩa "ours" (giữ file bản địa) NHƯNG ghi một dòng
 * log cảnh báo vào HLK/logs/merge-ours.log để việc "giữ ours" không còn silent —
 * operator/CI biết upstream đã thay đổi file HLK để chủ động review/merge thủ công.
 *
 * Args (git merge driver protocol): %A (path hiện tại) %O (ancestor) %B (bên kia)
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const [ourPath, ancestorPath, theirPath] = process.argv.slice(2);

function gitShow(pathArg) {
  // pathArg dạng index:path hoặc path — lấy HEAD:/WORKING phiên bản để biết nội dung bên kia
  if (!pathArg || pathArg === '') return '[empty]';
  try {
    return execSync(`git show ${JSON.stringify(pathArg)}`, {
      encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], maxBuffer: 1024 * 1024,
    }).trim();
  } catch {
    return '[unreadable]';
  }
}

try {
  // Merge driver chỉ nên giữ-ours khi đang trong một merge thật (MERGE_HEAD tồn
  // tại). Nếu KHÔNG phải merge, KHÔNG được git checkout --ours — nếu không sẽ
  // ghi đè thay đổi working-tree của người dùng (footgun như đã gặp trong test).
  const inMerge = (() => {
    try {
      return execSync('git rev-parse -q --verify MERGE_HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim().length > 0;
    } catch {
      return false;
    }
  })();

  // Log dù có giữ ours hay không — nhưng chỉ log "đã giữ" khi thực sự merge.
  const ts = new Date().toISOString();
  const rel = ourPath || '(unknown)';
  const theirHash = gitShow(theirPath).length > 12
    ? gitShow(theirPath).slice(0, 12) + '…'
    : '';

  const logDir = path.resolve(__dirname, '../logs');
  fs.mkdirSync(logDir, { recursive: true });

  if (inMerge) {
    // Đang merge → giữ bản địa (ours) đúng ngữ nghĩa merge=ours
    try {
      execSync(`git checkout --ours -- ${JSON.stringify(ourPath || '')}`, {
        stdio: ['ignore', 'ignore', 'ignore'],
      });
    } catch { /* best-effort */ }
    const line = [
      `[${ts}] merge=ours (merge active) GIỮ bản địa: ${rel}`,
      theirHash ? ` | upstream changed (${theirHash}) — review thủ công nếu là security patch` : '',
      '\n',
    ].join('');
    fs.appendFileSync(path.join(logDir, 'merge-ours.log'), line, 'utf8');
  } else {
    // Không phải merge → KHÔNG đụng working-tree; chỉ ghi log cảnh báo nếu file
    // ngoài bản HEAD (tức working-tree có thay đổi không nên bị driver chạm tới).
    fs.appendFileSync(path.join(logDir, 'merge-ours.log'), `[${ts}] merge-ours driver gọi NGOÀI merge — bỏ qua (không ghi đè): ${rel}\n`, 'utf8');
  }
} catch (err) {
  // Best-effort: lỗi log không được làm hỏng merge
  process.stderr.write(`[HLK merge-ours] log lỗi: ${err.message}\n`);
}

process.exit(0);
