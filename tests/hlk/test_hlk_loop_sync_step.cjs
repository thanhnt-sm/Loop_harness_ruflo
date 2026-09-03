// Tests cho HLK/loop/hlk-loop.mjs auto-sync step (Plan 8 phase 1)
// Node test với `node --test tests/hlk/test_hlk_loop_sync_step.cjs`
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');

const HLK_LOOP = path.resolve(__dirname, '../../HLK/loop/hlk-loop.mjs');

test('hlk-loop.mjs file exists', () => {
  assert.strictEqual(fs.existsSync(HLK_LOOP), true);
});

test('hlk-loop.mjs has autoSyncMirrors function', () => {
  const content = fs.readFileSync(HLK_LOOP, 'utf8');
  assert.match(content, /function autoSyncMirrors/);
  assert.match(content, /sync_to_mirrors\.py/);
  assert.match(content, /--target/);
});

test('hlk-loop.mjs calls autoSyncMirrors at main() start', () => {
  const content = fs.readFileSync(HLK_LOOP, 'utf8');
  // Tìm "await autoSyncMirrors()" trong main()
  const mainMatch = content.match(/async function main\(\)\s*\{([\s\S]+?)\n\}/);
  assert.ok(mainMatch, 'main() function not found');
  const mainBody = mainMatch[1];
  // Phải có "await autoSyncMirrors()" ở đầu main body
  assert.match(mainBody, /await autoSyncMirrors\(\)/);
});

test('autoSyncMirrors respects DRY_RUN/STATUS/RESET', () => {
  const content = fs.readFileSync(HLK_LOOP, 'utf8');
  // Function phải check DRY_RUN || STATUS || RESET
  assert.match(content, /DRY_RUN\s*\|\|\s*STATUS\s*\|\|\s*RESET/);
});

test('autoSyncMirrors handles failure gracefully (no throw)', () => {
  const content = fs.readFileSync(HLK_LOOP, 'utf8');
  // Phải có try/resolve để không throw
  const fnMatch = content.match(/function autoSyncMirrors\(\)\s*\{([\s\S]+?)\n\}/);
  assert.ok(fnMatch);
  const fnBody = fnMatch[1];
  // Có .then / resolve / error handling
  assert.match(fnBody, /resolvePromise/);
  // Không throw
  assert.doesNotMatch(fnBody, /throw new Error/);
});
