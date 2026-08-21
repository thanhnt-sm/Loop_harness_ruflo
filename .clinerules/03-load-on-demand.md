# 03 — Nạp file theo nhu cầu (Progressive Disclosure)

> Cline tự nạp đầu session: `AGENTS.md`, `CLAUDE.md`, toàn bộ `.clinerules/`.
> **KHÔNG đọc hết workspace.** Tra `00-source-map.md` (luôn trong context) rồi mở đúng file.

## Task → đọc gì (bảng nạp on-demand)

| Loại task | Đọc |
|-----------|-----|
| Hiểu harness tổng quan | `.devin/AGENTS.md`, `docs/USAGE_GUIDE.md`, `docs/CONTINUOUS_LOOP_GUIDE.md` |
| Sửa script `.devin/scripts/*.py` | đúng script + `tests/test_<script>.py` + script cùng nhóm (xem map mục 3.6) |
| Sửa hook `.devin/hooks/*.py` | đúng hook + `tests/test_<hook>.py` + `ahd_session.py` (lib dùng chung) |
| Sửa skill | `.devin/skills/<skill>/SKILL.md` + `skill_index.json` |
| Quyết định theo canon | `.devin/canon/<file>.md` (REDLINES, BOOT_PROTOCOL, VERIFICATION_PROTOCOL...) |
| Quy hoạch file/folder, plan↔act | `.devin/rules/WORKSPACE_GOVERNANCE.md` (canonical) + `tools/check_governance.py` |
| Chạy/viết test | `pytest.ini`, `tests/conftest.py`, `tests/test_<module>.py` |
| Cấu hình Devin CLI | `.devin/config.json`, `.devin/tool_registry.json`, `pyproject.toml` |
| Task opencode | `.opencode/README.md` + agent/skill/tool cụ thể |
| Task HLK (chỉ đọc) | `HLK/README.md` + module cụ thể |
| CI/CD | `.github/workflows/<file>.yml` |
| Chi phí/telemetry | `.devin/scripts/cost_*.py`, `docs/reports/COST_DASHBOARD.md` |
| Memory cross-session | `.devin/loop_state.md`, `.devin/canon/MEMORY_PROTOCOL.md` |
| Lịch sử quyết định | `docs/reports/`, `docs/plans/` (chỉ khi cần) |

## NEVER READ (đừng mở trừ khi thật sự cần)

- `.devin/AGENTS_full.md` — 186KB full body.
- Báo cáo lịch sử trong `docs/reports/` và `docs/plans/` — chỉ khi cần context quá khứ.
- Runtime dirs: `.devin/loop_state/`, `session_state/`, `plan_state/`, `telemetry/`,
  `blackboard/`, `.omo/`, `.codegraph/`, `node_modules/`, `.venv/`.
- `.gitignore` đã loại runtime — file tracked mới là source thật.

## Duy trì source map

- Source map `00-source-map.md` tự sinh bởi `tools/gen_source_map.py` (dữ liệu mô tả ở
  `tools/source_map_data.py`).
- **Sau khi thêm/xóa/di chuyển module, skill, hook, script** → chạy
  `python3 tools/gen_source_map.py` để refresh map, rồi mới kết thúc task.
