---
name: hlk-upstream-pull
description: >-
  Pull source mới nhất từ upstream ruflo (https://github.com/ruvnet/ruflo) vào workspace và tự
  cài lại HLK layer (patch .claude/settings.json, .gitattributes, .gitignore, replay skills, install
  post-merge hook) rồi verify integrity. Dùng khi cần update Ruflo từ git upstream, đồng bộ code,
  khôi phục HLK sau khi pull upstream. Nguồn canonical: HLK/skills/hlk-upstream-pull/SKILL.md.
  THẬN TRỌNG: thao tác này có thể thay đổi nhiều file — cần backup và xác nhận.
---

# hlk-upstream-pull (opencode wrapper)

Load và thực thi theo canonical skill tại **`HLK/skills/hlk-upstream-pull/SKILL.md`**.

## Tóm tắt nhanh

```bash
node HLK/upstream/hlk-upstream-pull.mjs [options]
```

| Option | Mặc định | Mô tả |
|--------|----------|-------|
| `--upstream <url>` | `https://github.com/ruvnet/ruflo.git` | URL git upstream |
| `--branch <name>` | `main` | Branch cần pull |
| `--yes` | false | Không hỏi xác nhận |
| `--dry-run` | false | Chỉ clone + list, không copy/reinstall |
| `--keep-backup` | false | Giữ backup trong `HLK/backups/` |

Luồng: clone upstream → backup 3 file cấu hình → copy source (bỏ qua `HLK/`, `.git/`, `node_modules/`, `.rvf`, `.env`) → patch lại HLK layer → verify integrity → cleanup.

> ⚠️ Guardrail: KHÔNG chạy `--yes` mặc định; luôn để user xác nhận. Không đụng `.env`, `agentdb.rvf`.
