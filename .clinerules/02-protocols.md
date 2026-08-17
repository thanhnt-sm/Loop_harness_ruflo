# 02 — Quy tắc bắt buộc (Protocols)

> Cline áp dụng các quy tắc này trong MỌI session. Chi tiết đầy đủ: `.devin/canon/REDLINES.md`.

## Ngôn ngữ (BẮT BUỘC)

- TẤT CẢ response **bằng tiếng Việt có dấu**. Technical terms giữ nguyên tiếng Anh
  (API, token, commit, hook, skill, agent...), lần đầu dùng ghi chú ngắn trong ngoặc.
- Code comments: tiếng Việt, tự nhiên, tối thiểu.
- Commit messages: tiếng Anh (git convention). File/variable names: tiếng Anh (không dấu).

## Top 5 red lines

1. **Không overwrite không backup** — backup `.bak` trước khi ghi đè.
2. **Không destructive ops không xác nhận** — rm -rf, force-push, drop, reset --hard đều bị chặn.
3. **Không secrets trong logs/state** — đọc env vars, không in/log secret.
4. **Không auto-resume session crash** — báo user, không tự tiếp tục mù.
5. **Không skip verification** — sau khi sửa phải chạy test/verify liên quan.

## Guardrails

- **Smallest coherent diff** — không scope creep, không refactor không liên quan.
- **Preserve pre-existing user changes** — không revert/overwrite khi chưa được yêu cầu.
- Trivial edits (S-tier) sửa thẳng; còn lại plan trước (xem `04-workflow.md`).
- Fan-out chỉ khi write sets disjoint (nhiều agent sửa file khác nhau).

## Safe zones — KHÔNG đụng

- `HLK/` (security layer), security policies, `.env`, `HLK/config/secrets.*`
- Runtime state: `.devin/loop_state/`, `session_state/`, `plan_state/`, `blackboard/`, `telemetry/`...
- `.devin/canon/` — AHD-owned; sửa qua canon rồi chạy `tools/verify-workspace.ps1` để mirror.

## Comment discipline

- Comments là debt, không phải documentation. **Mặc định không viết comment.**
- Chỉ viết khi: (a) user yêu cầu, (b) invariant non-obvious, (c) API contract/public interface,
  (d) `TODO`/`FIXME` có owner, (e) directive ngôn ngữ.
- Không stack version trong file (`<!-- v2 -->`, `# v3 fixed X`) — version nằm ở git history.

## Evidence

- Gắn nhãn: `[fact]` (đã verify bằng tool) / `[inference]` (suy luận có cơ sở) /
  `[unverified]` (đoán — nói rõ là đoán).
- Không nói "đã chạy test" nếu chưa chạy. Không bịa kết quả.
