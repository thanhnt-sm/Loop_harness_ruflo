# HLK Skills Templates

> Thư mục chứa skills templates — khi `hlk-install.mjs` chạy, các skills
> này sẽ được copy vào `.claude/skills/` và `.devin/skills/` của workspace.

## Cấu trúc

```
HLK/skills/
├── hlk-upstream-pull/     # Skill pull upstream + reinstall HLK
│   └── SKILL.md
├── hlk-git-tools/         # Skill git tools an toàn
│   └── SKILL.md
├── hlk-integrity-check/   # Skill verify HLK layer
│   └── SKILL.md
├── post-merge.template    # Template cho .githooks/post-merge
└── README.md              # File này
```

## Cài đặt

Khi chạy `hlk-install.mjs` (hoặc `hlk-upstream-pull.mjs`):

1. **`.claude/skills/hlk-*`** — copy tất cả thư mục `hlk-*` từ đây sang
2. **`.devin/skills/hlk-*`** — copy tất cả thư mục `hlk-*` từ đây sang
3. **`.githooks/post-merge`** — copy `post-merge.template` sang, `chmod +x`

## Lợi ích

- **Claude Code** tự scan `.claude/skills/` và nhận skills không cần khai báo
- **Devin CLI** tự scan `.devin/skills/` và nhận skills
- **Git** tự chạy `hlk-verify-integrity.js` sau mỗi `git pull`/`git merge`
  (khi `core.hooksPath = .githooks`)

## Thêm skill mới

1. Tạo thư mục `HLK/skills/<ten-skill>/SKILL.md`
2. SKILL.md phải có YAML frontmatter (`name`, `description`, `keywords`)
3. Chạy lại `hlk-install.mjs` để copy sang workspace
