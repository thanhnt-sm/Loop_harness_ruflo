#!/usr/bin/env python3
"""reflection_gate.py — Reflection Gate (T4.9, REQ-012).

Mục đích: reflection trước khi thực hiện action, đa cấp (intra/inter/foresight).
- intra: kiểm tra nội bộ action (có hợp lệ không, có destructive không).
- inter: kiểm tra tương tác với action trước đó (có xung đột không).
- foresight: kiểm tra hậu quả dự kiến (có gây hại không).

Action destructive (delete, force_push, drop, reset_hard) -> block + yêu cầu
human confirm. Multi-level trả ReflectVerdict.

Hàm chính: reflect(action, level) -> ReflectVerdict.

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
File < 500 dòng, typed interface (Pydantic).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Thêm .devin/scripts vào sys.path để import data_models khi chạy trực tiếp
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from data_models import Action, ReflectVerdict  # noqa: E402


# Danh mục action destructive — luôn block + yêu cầu human confirm
DESTRUCTIVE_CATEGORIES = frozenset({
    "delete", "force_push", "drop", "reset_hard",
})

# Các cấp reflection theo thứ tự từ nông đến sâu
REFLECTION_LEVELS = ("intra", "inter", "foresight")


def _check_intra(action: Action) -> tuple[bool, str, bool]:
    """Cấp intra: kiểm tra nội bộ action.

    Trả về (block, reason, human_confirm_required).
    """
    # Action destructive -> block + human confirm
    if action.category in DESTRUCTIVE_CATEGORIES or action.destructive:
        return (
            True,
            f"Action '{action.category}' is destructive - not auto-executed.",
            True,
        )
    # Action write/external_call không destructive -> cho phép nhưng cảnh báo
    if action.category == "external_call" and not action.target.startswith(("http://", "https://")):
        return (False, "external_call has no valid URL - warning.", False)
    if action.category == "write" and ".." in action.target:
        return (True, "write contains path traversal '..' - blocked.", False)
    # Action read -> luôn an toàn ở cấp intra
    return (False, "Action valid at intra level.", False)


def _check_inter(action: Action) -> tuple[bool, str, bool]:
    """Cấp inter: kiểm tra tương tác với action trước đó.

    Mô phỏng: nếu action là write lên file đang được đọc (target trùng) ->
    cảnh báo nhưng không block. Nếu action là delete lên target vừa write -> block.
    """
    # Pentest fix: action destructive (delete, force_push, drop, reset_hard)
    # phải bị block ở mọi cấp reflection, kể cả inter.
    if action.category in DESTRUCTIVE_CATEGORIES or action.destructive:
        return (
            True,
            f"Action '{action.category}' is destructive - blocked at inter level.",
            True,
        )
    # Không có state action trước trong fixture -> mặc định an toàn
    # nhưng nếu target chứa pattern nhạy cảm -> cảnh báo
    sensitive_patterns = (".env", "HLK/", "credentials/", "secrets/", ".git/")
    for pat in sensitive_patterns:
        if pat in action.target:
            return (
                True,
                f"Action touches sensitive zone '{pat}' - blocked at inter level.",
                True,
            )
    return (False, "No conflict with previous action.", False)


def _check_foresight(action: Action) -> tuple[bool, str, bool]:
    """Cấp foresight: kiểm tra hậu quả dự kiến.

    Action destructive -> hậu quả nguy hiểm -> block + human confirm.
    Action external_call tới host không allowlist -> cảnh báo.
    """
    if action.category in DESTRUCTIVE_CATEGORIES or action.destructive:
        return (
            True,
            "Foresight: irreversible data loss - blocked + human confirm required.",
            True,
        )
    if action.category == "external_call":
        # Kiểm tra host có trong allowlist mặc định không
        host = action.target.split("/")[2] if "://" in action.target else action.target
        allowlist = {"example.com", "api.github.com", "api.openai.com"}
        is_allowed = any(host == h or host.endswith(f".{h}") for h in allowlist)
        if not is_allowed:
            return (False, f"external_call to non-allowlisted host '{host}' - warning.", False)
    return (False, "Foresight: consequences safe.", False)


_LEVEL_CHECKS = {
    "intra": _check_intra,
    "inter": _check_inter,
    "foresight": _check_foresight,
}


def reflect(action: Action, level: str = "intra") -> ReflectVerdict:
    """Reflection trước khi thực hiện action ở cấp chỉ định.

    Nhận vào:
        action — Action cần đánh giá.
        level  — cấp reflection: "intra", "inter", hoặc "foresight".

    Trả về ReflectVerdict:
      - block=True nếu action bị chặn.
      - human_confirm_required=True nếu cần xác nhận con người.
      - reason: lý do dạng text.

    Nếu level không hợp lệ, raise ValueError.
    """
    if not isinstance(action, Action):
        raise TypeError("action phải là Action")
    if level not in REFLECTION_LEVELS:
        raise ValueError(f"level phải là một trong {REFLECTION_LEVELS}, nhận '{level}'")

    check_fn = _LEVEL_CHECKS[level]
    block, reason, human_confirm = check_fn(action)

    return ReflectVerdict(
        action_id=action.id,
        level=level,  # type: ignore[arg-type]
        block=block,
        reason=reason,
        human_confirm_required=human_confirm,
    )


def check_reflection(action_input: dict) -> ReflectVerdict | None:
    """Helper cho hook pre_tool_use: chuyển tool_input thành Action rồi reflect.

    Nhận vào dict dạng:
      {"category": "delete", "target": "...", "id": "...", "args": {...}}

    Trả về ReflectVerdict hoặc None nếu không thể xây Action (không phải action
    cần reflection — vd read thuần).
    """
    if not isinstance(action_input, dict):
        return None
    category = action_input.get("category")
    if not category:
        return None
    try:
        action = Action(
            id=str(action_input.get("id", "unknown")),
            category=category,  # type: ignore[arg-type]
            target=str(action_input.get("target", "")),
            args=action_input.get("args", {}) or {},
            destructive=bool(action_input.get("destructive", False)),
        )
    except Exception:
        return None
    # Dùng cấp foresight (sâu nhất) cho hook integration
    return reflect(action, level="foresight")


def _cli() -> int:
    """CLI stub: đọc action JSON từ stdin, in ReflectVerdict."""
    import json
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
        verdict = check_reflection(data)
        if verdict is None:
            print(json.dumps({"block": False, "reason": "không phải action cần reflection"}))
            return 0
        print(json.dumps(verdict.model_dump(by_alias=True), ensure_ascii=False, indent=2))
        return 0 if not verdict.block else 2
    except Exception as e:
        print(f"[reflection_gate] lỗi: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
