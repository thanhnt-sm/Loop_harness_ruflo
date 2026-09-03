# HLK Loaders

## Tổng quan

HLK loaders là các Node.js modules chạy TRƯỚC khi CLI/agent bắt đầu. Mục đích:
- **Sanitize argv** (chống prompt injection từ BRD content)
- **Patch global APIs** (intercepts child_process calls — opt-in only)
- **Audit log** (ghi lại mọi spawn/exec cho verify-first)

## Files

| File | Purpose |
|---|---|
| `wrap_helpers.js` | Standalone wrap helpers (santizeArgv, wrapSpawn, wrapExecFile, enablePatching, disablePatching) |
| `verify-first-loader.js` | High-level loader: chỉ patch khi `HLK_VERIFY_FIRST_ACTIVE=1` (opt-in) |

## Cách dùng

### 1. Standalone (chỉ wrap khi cần)

```js
import { wrapSpawn, sanitizeArgv } from "HLK/chain/loaders/wrap_helpers.js";
import { spawn } from "node:child_process";

// Option A: chỉ sanitize, không patch
const { sanitized, warnings } = sanitizeArgv(["py", "verify_first_cli.py", "--live", "; rm -rf /"]);
console.log(warnings);  // ['argv[3] contains shell metachar: ; rm -rf /']
const child = spawn(sanitized[0], sanitized.slice(1));

// Option B: wrap 1 function cụ thể
import { spawn as origSpawn } from "node:child_process";
const mySpawn = wrapSpawn(origSpawn, { enabled: true });
const child = mySpawn("py", ["verify_first_cli.py"]);
```

### 2. Opt-in global patch

```js
// Set env var: HLK_VERIFY_FIRST_ACTIVE=1
// Sau đó load module:
process.env.HLK_VERIFY_FIRST_ACTIVE = "1";
await import("HLK/chain/loaders/verify-first-loader.js");
// Từ giờ, mọi spawn() cho verify_first_cli.py sẽ tự động sanitize argv
```

### 3. Manual enable/disable

```js
import cp from "node:child_process";
import { enablePatching, disablePatching, isPatched } from "HLK/chain/loaders/wrap_helpers.js";

enablePatching(cp);
console.log(isPatched());  // true
// ... do stuff ...
disablePatching(cp);
console.log(isPatched());  // false
```

## API reference

### `sanitizeArgv(argv: string[]) -> { sanitized, warnings }`

Strip shell metacharacters (`|`, `&`, `;`, `<`, `>`, `$`, `` ` ``, `"`, `'`, `*`, `?`, `{`, `}`, `\n`, `\r`, `\t`).

**Note**: Backslash (`\\`) is **NOT** in the metachar set to allow Windows paths like `C:\Users\foo`.

Returns:
- `sanitized`: list of strings with metachars replaced by `_`
- `warnings`: list of warning messages (one per replaced arg)

### `wrapSpawn(originalSpawn, options) -> wrappedSpawn`

Returns a wrapped version of `originalSpawn` that sanitizes `cmd` and `args` before invocation.

Options:
- `enabled: bool` — whether wrapping is active (default: true)
- `onWarning: fn(string) -> void` — callback for each warning

### `wrapExecFile(originalExecFile, options) -> wrappedExecFile`

Same as `wrapSpawn` but for `execFile`.

### `enablePatching(childProcessModule, options) -> bool`

Patches `childProcessModule.spawn` and `childProcessModule.execFile` globally.
Idempotent: returns `false` if already patched.

### `disablePatching(childProcessModule) -> bool`

Restores original `spawn` and `execFile`. Idempotent: returns `false` if not patched.

### `isPatched() -> bool`

Returns `true` if currently patched, `false` otherwise.

## Security

- **Backslash allowed**: `\\` is not in metachar set (Windows path support)
- **All other metachars replaced with `_`**: prevents shell injection
- **No code execution**: only string replacement, no eval
- **Opt-in by default**: no side effects on import (unless env var set)

## Testing

```bash
node --test tests/hlk/test_loader_scoping.cjs
node --test tests/hlk/test_wrap_helpers.cjs
```

## Backward compatibility

- Phase 1 design (auto-load on every subprocess): **DEPRECATED** — moved to opt-in
- Phase 2 design (explicit opt-in via env): **CURRENT**
- Apps not setting `HLK_VERIFY_FIRST_ACTIVE=1` are not affected

## Migration guide (từ Phase 1)

Nếu app cũ dùng `HLK_VERIFY_FIRST_ACTIVE=1` để tự động patch, behavior vẫn giống. Nếu muốn manual control, dùng `enablePatching()`/`disablePatching()` thay vì env var.

## See also

- `HLK/chain/hlk_wrappers/verify-first-wrapper.mjs` — Node wrapper (audit log + rotation)
- `HLK/reports/verify-first-consolidation-redteam.md` — security review
- Plan 8 (final-implementation) — source of this design
