---
name: user-preference
description: Learn and apply user preferences — coding style, communication style, tool preferences, workflow habits.
triggers:
  - model
---

# User Preference — Learn & Apply Preferences

## Khi nào dùng
- Khi user expresses a preference (explicit or implicit)
- Khi user corrects agent behavior
- Khi session starts (recall preferences)

## Cách dùng

1. **Recall** — aide_recall "user-preference" at session start
2. **Detect preferences** — from:
   - Explicit statements: "I prefer X"
   - Corrections: "No, do it this way"
   - Patterns: user always rejects verbose output
   - Edits: user removes comments, prefers compact code
3. **Store** — aide_remember with tag "user-preference"
   - Category: coding, communication, tools, workflow
   - Confidence: how strong is the signal?
4. **Apply** — use preferences in all subsequent work
5. **Update** — when user corrects, update stored preference

## Categories
- **Coding**: naming, style, comment density, file organization
- **Communication**: language, verbosity, format, detail level
- **Tools**: preferred commands, editors, test frameworks
- **Workflow**: commit style, branch naming, PR format

## Output format

```text
USER PREFERENCES: <count> active

CODING
- <preference> (confidence: <pct>%)

COMMUNICATION
- <preference> (confidence: <pct>%)

TOOLS
- <preference> (confidence: <pct>%)

WORKFLOW
- <preference> (confidence: <pct>%)

NEWLY DETECTED
- <preference> — <source of detection>
```
