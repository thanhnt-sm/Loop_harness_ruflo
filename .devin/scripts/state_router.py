#!/usr/bin/env python3
"""state_router.py — Phase D: Bộ định tuyến đồ thị trạng thái có điều kiện.

Mô hình theo LangGraph: mỗi bước (step) có nhiều cạnh ra (outgoing edges),
mỗi cạnh gắn với một điều kiện. Router đọc trạng thái hiện tại, đánh giá
các điều kiện theo thứ tự ưu tiên, và quyết định bước tiếp theo cùng
agent phụ trách. Nếu không có cạnh nào thỏa → trả về DONE (kết thúc).

CLI:
    python state_router.py --route <state.json>
        Đọc toàn bộ trạng thái, xác định bước + agent tiếp theo.

    python state_router.py --next <current_step> <state.json>
        Cho trước bước hiện tại + trạng thái, chỉ trả bước tiếp theo.

Output (JSON):
    {
      "next_step": str,
      "next_agent": str,
      "reason": str,
      "state_update": dict
    }

Mã thoát:
    0 — thành công
    1 — không có chuyển tiếp hợp lệ (trả DONE) hoặc lỗi đầu vào
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Lược đồ trạng thái (state schema)
# ---------------------------------------------------------------------------
# Các trường bắt buộc + giá trị mặc định khi thiếu.
# Mỗi trường có kiểu dữ liệu rõ ràng để router kiểm tra trước khi định tuyến.

DEFAULT_STATE: dict[str, Any] = {
    "phase": "PLAN",            # PLAN | APPROVE | EXECUTE | DONE
    "step": "ANALYZE",          # bước hiện tại trong đồ thị
    "findings": [],             # danh sách phát hiện từ SCOUT
    "design": None,             # bản thiết kế từ ARCHITECT (str | None)
    "plan": None,               # kế hoạch từ PLANNER (str | None)
    "quality_score": None,      # điểm chất lượng 0.0–1.0 (float | None)
    "approved": False,          # đã được phê duyệt chưa (bool)
    "coverage_pct": None,       # phần trăm phủ kiểm thử (float | None)
    "drift_detected": False,    # phát hiện trôi dạt (drift) hay chưa
    "error": None,              # thông báo lỗi nếu có (str | None)
}

# Bước → agent phụ trách. Ánh xạ đơn giản, dùng cho output next_agent.
STEP_TO_AGENT: dict[str, str] = {
    "ANALYZE": "SCOUT",
    "DESIGN": "ARCHITECT",
    "PLAN": "PLANNER",
    "QUALITY_CHECK": "QUALITY_CHECKER",
    "APPROVE": "APPROVER",
    "DISPATCH": "COMMANDER",
    "EXECUTE": "BUILDER",
    "VERIFY": "VERIFIER",
    "REPORT": "REPORTER",
    "DONE": "NONE",
}

# Phase tương ứng với mỗi bước (dùng để cập nhật phase khi chuyển bước).
STEP_TO_PHASE: dict[str, str] = {
    "ANALYZE": "PLAN",
    "DESIGN": "PLAN",
    "PLAN": "PLAN",
    "QUALITY_CHECK": "PLAN",
    "APPROVE": "APPROVE",
    "DISPATCH": "APPROVE",
    "EXECUTE": "EXECUTE",
    "VERIFY": "EXECUTE",
    "REPORT": "EXECUTE",
    "DONE": "DONE",
}


# ---------------------------------------------------------------------------
# Định nghĩa các cạnh điều kiện (conditional edges)
# ---------------------------------------------------------------------------
# Mỗi cạnh: (bước nguồn, hàm điều kiện, bước đích, lý do, cập nhật trạng thái)
# Hàm điều kiện nhận state, trả True/False. Router duyệt theo thứ tự,
# lấy cạnh đầu tiên thỏa.

Edge = tuple[str, Callable[[dict], bool], str, str, dict]


def _cond_analyze_to_design(state: dict) -> bool:
    """ANALYZE → DESIGN khi đã đủ phát hiện (findings >= 5)."""
    return len(state.get("findings", []) or []) >= 5


def _cond_analyze_loop(state: dict) -> bool:
    """ANALYZE → ANALYZE khi chưa đủ phát hiện (findings < 5), cần nghiên cứu thêm."""
    return len(state.get("findings", []) or []) < 5


def _cond_design_to_plan(state: dict) -> bool:
    """DESIGN → PLAN khi đã có bản thiết kế (design không None)."""
    return state.get("design") is not None


def _cond_plan_to_quality(state: dict) -> bool:
    """PLAN → QUALITY_CHECK khi đã có kế hoạch (plan không None)."""
    return state.get("plan") is not None


def _cond_quality_loop_design(state: dict) -> bool:
    """QUALITY_CHECK → DESIGN khi điểm chất lượng thấp (< 0.8), cần thiết kế lại."""
    score = state.get("quality_score")
    return score is not None and score < 0.8


def _cond_quality_to_approve(state: dict) -> bool:
    """QUALITY_CHECK → APPROVE khi điểm chất lượng đạt (>= 0.8)."""
    score = state.get("quality_score")
    return score is not None and score >= 0.8


def _cond_approve_to_dispatch(state: dict) -> bool:
    """APPROVE → DISPATCH khi đã được phê duyệt (approved == True)."""
    return bool(state.get("approved", False)) is True


def _cond_approve_to_done(state: dict) -> bool:
    """APPROVE → DONE khi bị từ chối (approved == False)."""
    return bool(state.get("approved", False)) is False


def _cond_dispatch_to_execute(state: dict) -> bool:
    """DISPATCH → EXECUTE khi đã phân tác vụ (tasks_dispatched == True)."""
    # Trường tasks_dispatched có thể không có trong schema mặc định,
    # mặc định coi như đã dispatch nếu bước hiện tại là DISPATCH.
    return bool(state.get("tasks_dispatched", True))


def _cond_execute_to_verify(state: dict) -> bool:
    """EXECUTE → VERIFY khi mọi tác vụ hoàn thành (all_tasks_complete == True)."""
    return bool(state.get("all_tasks_complete", False)) is True


def _cond_execute_loop(state: dict) -> bool:
    """EXECUTE → EXECUTE khi vẫn còn tác vụ đang chạy (all_tasks_complete != True)."""
    return bool(state.get("all_tasks_complete", False)) is False


def _cond_verify_to_report(state: dict) -> bool:
    """VERIFY → REPORT khi mọi cổng kiểm soát đạt (all_gates_pass == True)."""
    return bool(state.get("all_gates_pass", False)) is True


def _cond_verify_loop_execute(state: dict) -> bool:
    """VERIFY → EXECUTE khi có cổng thất bại (all_gates_pass != True), cần thử lại."""
    return bool(state.get("all_gates_pass", False)) is False


# Danh sách cạnh điều kiện, theo thứ tự ưu tiên (duyệt từ trên xuống).
EDGES: list[Edge] = [
    ("ANALYZE", _cond_analyze_to_design, "DESIGN",
     "Đã đủ phát hiện (>= 5), chuyển sang thiết kế",
     {"phase": "PLAN"}),
    ("ANALYZE", _cond_analyze_loop, "ANALYZE",
     "Chưa đủ phát hiện (< 5), cần nghiên cứu thêm",
     {}),
    ("DESIGN", _cond_design_to_plan, "PLAN",
     "Đã có bản thiết kế, chuyển sang lập kế hoạch",
     {"phase": "PLAN"}),
    ("PLAN", _cond_plan_to_quality, "QUALITY_CHECK",
     "Đã có kế hoạch, chuyển sang kiểm tra chất lượng",
     {"phase": "PLAN"}),
    ("QUALITY_CHECK", _cond_quality_loop_design, "DESIGN",
     "Điểm chất lượng thấp (< 0.8), lặp lại thiết kế",
     {"phase": "PLAN"}),
    ("QUALITY_CHECK", _cond_quality_to_approve, "APPROVE",
     "Điểm chất lượng đạt (>= 0.8), chuyển sang phê duyệt",
     {"phase": "APPROVE"}),
    ("APPROVE", _cond_approve_to_dispatch, "DISPATCH",
     "Đã được phê duyệt, chuyển sang phân tác vụ",
     {"phase": "APPROVE"}),
    ("APPROVE", _cond_approve_to_done, "DONE",
     "Bị từ chối phê duyệt, kết thúc",
     {"phase": "DONE"}),
    ("DISPATCH", _cond_dispatch_to_execute, "EXECUTE",
     "Đã phân tác vụ, chuyển sang thực thi",
     {"phase": "EXECUTE"}),
    ("EXECUTE", _cond_execute_to_verify, "VERIFY",
     "Mọi tác vụ hoàn thành, chuyển sang kiểm chứng",
     {"phase": "EXECUTE"}),
    ("EXECUTE", _cond_execute_loop, "EXECUTE",
     "Vẫn còn tác vụ đang chạy, tiếp tục thực thi",
     {}),
    ("VERIFY", _cond_verify_to_report, "REPORT",
     "Mọi cổng kiểm soát đạt, chuyển sang báo cáo",
     {"phase": "EXECUTE"}),
    ("VERIFY", _cond_verify_loop_execute, "EXECUTE",
     "Có cổng thất bại, thử lại thực thi",
     {"phase": "EXECUTE"}),
    ("REPORT", lambda s: True, "DONE",
     "Hoàn tất báo cáo, kết thúc",
     {"phase": "DONE"}),
]


# ---------------------------------------------------------------------------
# Hàm xử lý chính
# ---------------------------------------------------------------------------

def _normalize_state(raw: Any) -> dict:
    """Chuẩn hóa trạng thái đầu vào: điền giá trị mặc định cho trường thiếu.

    Bước 1: Nếu raw không phải dict → trả về trạng thái mặc định.
    Bước 2: Với mỗi trường trong DEFAULT_STATE, nếu thiếu thì điền mặc định.
    Bước 3: Trả về state đã chuẩn hóa.
    """
    if not isinstance(raw, dict):
        return dict(DEFAULT_STATE)
    state = dict(DEFAULT_STATE)
    for key, default in DEFAULT_STATE.items():
        if key in raw:
            state[key] = raw[key]
    return state


def _find_edge(step: str, state: dict) -> Edge | None:
    """Tìm cạnh điều kiện đầu tiên thỏa cho bước hiện tại.

    Bước 1: Duyệt danh sách EDGES theo thứ tự ưu tiên.
    Bước 2: Bỏ qua các cạnh có bước nguồn khác step hiện tại.
    Bước 3: Gọi hàm điều kiện, nếu True → trả về cạnh đó.
    Bước 4: Nếu không có cạnh nào thỏa → trả về None.
    """
    for edge in EDGES:
        src, cond, dst, reason, update = edge
        if src != step:
            continue
        try:
            if cond(state):
                return edge
        except Exception:
            # Lỗi đánh giá điều kiện → bỏ qua cạnh này, thử cạnh kế tiếp.
            continue
    return None


def route(state: dict) -> dict:
    """Định tuyến từ trạng thái đầy đủ: đọc step hiện tại, quyết định bước tiếp.

    Trả về dict: {next_step, next_agent, reason, state_update}.
    Nếu không có cạnh thỏa → next_step = "DONE", exit code nên là 1.
    """
    step = state.get("step", "ANALYZE")
    return route_next(step, state)


def route_next(current_step: str, state: dict) -> dict:
    """Định tuyến từ bước hiện tại + trạng thái, chỉ trả bước tiếp theo.

    Bước 1: Chuẩn hóa current_step (in hoa).
    Bước 2: Tìm cạnh điều kiện thỏa.
    Bước 3: Nếu tìm thấy → trả next_step, next_agent, reason, state_update.
    Bước 4: Nếu không tìm thấy → trả DONE (không có chuyển tiếp hợp lệ).
    """
    step = (current_step or "ANALYZE").strip().upper()
    edge = _find_edge(step, state)
    if edge is None:
        # Không có cạnh nào thỏa → kết thúc.
        return {
            "next_step": "DONE",
            "next_agent": STEP_TO_AGENT.get("DONE", "NONE"),
            "reason": f"Không có chuyển tiếp hợp lệ từ bước {step}",
            "state_update": {"phase": "DONE", "step": "DONE"},
            "_exit_code": 1,
        }
    src, _cond, dst, reason, update = edge
    # Cập nhật phase theo bước đích.
    phase = STEP_TO_PHASE.get(dst, state.get("phase", "PLAN"))
    full_update = dict(update)
    full_update.setdefault("phase", phase)
    full_update["step"] = dst
    return {
        "next_step": dst,
        "next_agent": STEP_TO_AGENT.get(dst, "UNKNOWN"),
        "reason": reason,
        "state_update": full_update,
        "_exit_code": 0,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_state_file(path: str) -> dict:
    """Đọc file JSON trạng thái. Nếu lỗi → trả dict rỗng (sẽ dùng mặc định)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[state_router] Không đọc được trạng thái từ {path}: {exc}",
              file=sys.stderr)
        return {}


def _build_arg_parser() -> argparse.ArgumentParser:
    """Xây dựng trình phân tích tham số dòng lệnh."""
    ap = argparse.ArgumentParser(
        description="Phase D: Bộ định tuyến đồ thị trạng thái có điều kiện"
    )
    ap.add_argument("--route", metavar="state.json",
                    help="Đọc toàn bộ trạng thái, xác định bước + agent tiếp theo")
    ap.add_argument("--next", nargs=2, metavar=("current_step", "state.json"),
                    help="Cho trước bước hiện tại + trạng thái, trả bước tiếp theo")
    return ap


def main(argv: list[str] | None = None) -> int:
    """Hàm chính: phân tích tham số, thực thi, in kết quả JSON."""
    ap = _build_arg_parser()
    args = ap.parse_args(argv)

    if not args.route and not args.next:
        ap.print_help(sys.stderr)
        return 1

    if args.route:
        # Chế độ --route: đọc toàn bộ trạng thái, tự xác định step hiện tại.
        raw = _read_state_file(args.route)
        state = _normalize_state(raw)
        result = route(state)
    else:
        # Chế độ --next: bước hiện tại + trạng thái.
        current_step, state_path = args.next
        raw = _read_state_file(state_path)
        state = _normalize_state(raw)
        result = route_next(current_step, state)

    exit_code = result.pop("_exit_code", 0)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
