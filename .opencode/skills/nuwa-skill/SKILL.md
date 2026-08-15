---
name: nuwa-skill
description: >-
  | 女娲造人：输入人名/主题/甚至只是模糊需求，自动深度调研→思维框架提炼→生成可运行的人物Skill。 两种入口：(1)明确人名→直接蒸馏 (2)模糊需求→诊断推荐→再蒸馏。
metadata:
  provider: devin
  source: .devin/skills/nuwa-skill/SKILL.md
---

# nuwa-skill (opencode wrapper)

Load the canonical harness skill at **`.devin/skills/nuwa-skill/SKILL.md`** and execute exactly per its instructions.
Preserve its intent, phases, role separations, and guardrails.

SAFETY: Do NOT apply destructive changes, run `--apply` flows, install packages/scripts, or modify
state unless the user EXPLICITLY requests execution. Otherwise, perform the read-only/planning part,
report findings, and ask for confirmation before applying anything.
