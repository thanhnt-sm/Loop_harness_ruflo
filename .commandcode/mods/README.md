# Command Code MODs (.commandcode/mods/)

Mods là TypeScript plugin tự viết, load qua `cmd --mod <path>` hoặc đặt
trong `.commandcode/mods/` để tự load.

## Convention

- File `.ts` (TypeScript ESM) export default function nhận `ModApi`, return `Mod`.
- Mỗi mod có `name`, `version`, `description`.
- Mod có thể define `commands` (slash command), `tools` (inline tool), và
  `api.on(event, handler)` lifecycle observer.

## Mods hiện có

| File | Tên | Mục đích |
|------|-----|----------|
| `hlk-guardian.ts` | hlk-guardian | Tự verify HLK mỗi session start; expose `/hlk-quick` slash + `hlk_status` inline tool |

## Cú pháp load

```bash
# Load 1 mod qua flag
cmd --mod ./.commandcode/mods/hlk-guardian.ts

# Load tất cả mod trong thư mục (auto-discover)
cmd --mod-dir ./.commandcode/mods

# Hoặc đặt trong project → auto-load khi start
```

## Reference

- Spec: `commandcode.ai/docs/mods` (ModApi)
- Bundled skill: `mod-builder` (gõ `/mod-builder` trong cmdc để scaffold)
- Type definitions: `command-code/mod-api` package
