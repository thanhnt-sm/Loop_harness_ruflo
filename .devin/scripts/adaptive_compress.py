#!/usr/bin/env python3
"""adaptive_compress.py — Adaptive Compression (T3.2, REQ-002).

Mục đích: nén lịch sử hội thoại (history) theo độ phức tạp của query:
  - Query đơn giản (ít từ, không dấu hiệu phức tạp) → nén tối thiểu: giữ gần như
    toàn bộ history, chỉ gộp các turn trống/rỗng.
  - Query phức tạp (nhiều từ, có dấu hiệu "phân tích/so sánh/lý luận") → nén sâu:
    gộp nhiều turn liên tiếp cùng role thành 1 turn tóm tắt, giữ turn gần nhất
    của mỗi role nguyên vẹn để không mất ngữ cảnh gần.

Extended with P1-04: Adaptive WM + Prefix-Cache Compaction
- Auto WM budget from context window (8K→~6K, 200K→~159K)
- Prefix-cache aware compaction (static system prompt + pinned memory)
- Pressure-based compaction (compact_at_context_fraction=0.5, retain=0.15)
- Background memory accumulation, foreground cache stable

Hàm chính:
  compress(history, query, mode) -> list[Turn]
  prefix_stable_hash(before, after) -> bool
  get_wm_budget_for_model(model) -> int
  compact_by_pressure(history, current_usage, budget) -> list[Turn]

prefix_stable_hash: kiểm tra hash tiền tố (prefix) của history trước và sau nén
có ổn định không — tức phần đầu không bị thay đổi. Dùng cho việc cache/invalidation:
nếu prefix ổn định thì các kết quả phụ thuộc prefix trước đó vẫn còn giá trị.

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from typing import Literal

from data_models import Turn

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_SCRIPT_DIR = __import__("pathlib").Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

# ============================================================================
# P1-04: Adaptive WM Configuration
# ============================================================================

# Context window sizes per model (tokens)
MODEL_CONTEXT_WINDOWS = {
    "default": 8192,
    "glm-5.2": 200000,
    "kimi-k2.7": 128000,
    "lightning": 200000,
    "small": 8192,
}

# Auto WM budget: 80% of (window - reserved)
WM_BUDGET_FRACTION = 0.8
RESERVED_TOKENS_HEADROOM_PCT = 0.20  # 20% headroom for system prompt/memory/tools

# Compaction pressure thresholds
COMPACT_AT_CONTEXT_FRACTION = 0.5   # trigger at 50% usage
RETAIN_CONTEXT_FRACTION = 0.15      # retain 15% newest after compact

# Ngưỡng số từ trong query để coi là "phức tạp".
_COMPLEX_QUERY_WORD_THRESHOLD = 8
# Các từ khóa báo hiệu query phức tạp (đánh giá/lý luận/so sánh).
_COMPLEX_KEYWORDS = {
    "phân tích", "so sánh", "lý giải", "tại sao", "đánh giá",
    "analyze", "compare", "explain", "why", "reason", "justify",
    "trade-off", "tradeoff", "evaluate",
}

CompressMode = Literal["auto", "minimal", "deep", "pressure"]


@dataclass
class AdaptiveWM:
    """Auto Working Memory budget from context window.

    Adapts automatically when model is swapped:
    - 8K model → ~6K WM (80% of 8K - 20% headroom)
    - 200K model → ~128K WM (80% of 200K - 20% headroom)
    """
    model: str = "default"
    window_size: int = 8192
    reserved_tokens: int = 0  # system prompt + pinned memory + tool schemas

    def __post_init__(self):
        self.window_size = MODEL_CONTEXT_WINDOWS.get(self.model, 8192)

    @property
    def reserved_budget(self) -> int:
        """Reserved tokens for system prompt, pinned memory, tool schemas (20% headroom)."""
        return int(self.window_size * RESERVED_TOKENS_HEADROOM_PCT)

    @property
    def wm_budget(self) -> int:
        """WM budget = 80% of (window - reserved_budget)."""
        available = max(0, self.window_size - self.reserved_budget)
        return int(available * WM_BUDGET_FRACTION)

    @property
    def total_budget(self) -> int:
        """Total context budget (WM + reserved)."""
        return self.wm_budget + self.reserved_budget

    @property
    def usage_pct(self) -> float:
        """Current usage as percentage of window."""
        if self.window_size == 0:
            return 0.0
        return (self.wm_budget + self.reserved_tokens) / self.window_size * 100

    def set_model(self, model: str) -> None:
        """Switch model and recalculate budget."""
        self.model = model
        self.window_size = MODEL_CONTEXT_WINDOWS.get(model, 8192)

    def set_reserved(self, tokens: int) -> None:
        """Set reserved tokens (system prompt + pinned memory + tool schemas)."""
        self.reserved_tokens = min(tokens, int(self.window_size * RESERVED_TOKENS_HEADROOM_PCT))

    def should_compact(self, current_usage: int) -> bool:
        """Check if compaction should trigger based on pressure (not turn count)."""
        threshold = int(self.window_size * COMPACT_AT_CONTEXT_FRACTION)
        return current_usage >= threshold


def get_wm_budget_for_model(model: str) -> int:
    """Get auto WM budget for a model.

    Returns:
        WM budget in tokens (adapts: 8K→~6K, 200K→~128K)
    """
    window = MODEL_CONTEXT_WINDOWS.get(model, 8192)
    reserved = int(window * RESERVED_TOKENS_HEADROOM_PCT)
    available = max(0, window - reserved)
    return int(available * WM_BUDGET_FRACTION)


# ============================================================================
# Original Adaptive Compression Logic
# ============================================================================

def _word_count(text: str) -> int:
    """Đếm số từ trong text (tách theo khoảng trắng)."""
    return len(text.split())


def _is_complex_query(query: str) -> bool:
    """Phát hiện query phức tạp: nhiều từ HOẶC chứa từ khóa lý luận."""
    if not query:
        return False
    ql = query.lower()
    if any(kw in ql for kw in _COMPLEX_KEYWORDS):
        return True
    return _word_count(query) >= _COMPLEX_QUERY_WORD_THRESHOLD


def _summarize(text: str, max_chars: int = 400) -> str:
    """Tóm tắt đơn giản: lấy max_chars ký tự đầu + dấu hiệu cắt."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + " …[tóm tắt]"


def _estimate_tokens(text: str) -> int:
    """Ước lượng token: 4 ký tự ~ 1 token."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _minimal_compress(history: list[Turn]) -> list[Turn]:
    """Nén tối thiểu: bỏ turn có content rỗng, giữ nguyên phần còn lại."""
    return [t for t in history if t.content.strip()]


def _deep_compress(history: list[Turn]) -> list[Turn]:
    """Nén sâu: gộp các turn liên tiếp cùng role thành 1 turn tóm tắt.

    Quy tắc:
      - Giữ nguyên turn gần nhất của mỗi role (để giữ ngữ cảnh gần).
      - Các turn cũ hơn cùng role liên tiếp → gộp thành 1 turn tóm tắt.
      - Thứ tự role vẫn được giữ theo mốc xuất hiện.
    """
    if not history:
        return []

    # Bước 1: tìm index của turn gần nhất cho mỗi role.
    last_idx_by_role: dict[str, int] = {}
    for i, t in enumerate(history):
        last_idx_by_role[t.role] = i

    result: list[Turn] = []
    # Bước 2: duyệt theo nhóm liên tiếp cùng role.
    i = 0
    n = len(history)
    while i < n:
        role = history[i].role
        j = i
        # Gom nhóm liên tiếp cùng role.
        while j < n and history[j].role == role:
            j += 1
        group = history[i:j]
        last_role_idx = last_idx_by_role[role]

        if len(group) == 1:
            # Chỉ 1 turn → giữ nguyên (dù có thể là last hoặc không).
            result.append(group[0])
        else:
            # Nhiều turn liên tiếp cùng role.
            # Tách turn cuối nhóm nếu nó là last của role → giữ nguyên, gộp phần còn lại.
            if group[-1] is history[last_role_idx]:
                # Phần đầu (cũ) gộp thành 1 tóm tắt, phần cuối giữ nguyên.
                to_merge = group[:-1]
                if to_merge:
                    merged_text = "\n".join(t.content for t in to_merge)
                    summary = _summarize(merged_text)
                    result.append(
                        Turn(
                            role=role,
                            content=summary,
                            tokens=_estimate_tokens(summary),
                            timestamp=to_merge[-1].timestamp,
                            tool_call_id=to_merge[-1].tool_call_id,
                        )
                    )
                result.append(group[-1])
            else:
                # Toàn bộ nhóm là turn cũ → gộp thành 1 tóm tắt.
                merged_text = "\n".join(t.content for t in group)
                summary = _summarize(merged_text)
                result.append(
                    Turn(
                        role=role,
                        content=summary,
                        tokens=_estimate_tokens(summary),
                        timestamp=group[-1].timestamp,
                        tool_call_id=group[-1].tool_call_id,
                    )
                )
        i = j
    return result


# ============================================================================
# P1-04: Pressure-Based Compaction
# ============================================================================

def compact_by_pressure(
    history: list[Turn],
    current_usage: int,
    wm: AdaptiveWM,
    retain_fraction: float = RETAIN_CONTEXT_FRACTION,
) -> list[Turn]:
    """P1-04: Compact history by context-size pressure, not turn count.

    Triggers at COMPACT_AT_CONTEXT_FRACTION (50%),
    retains RETAIN_CONTEXT_FRACTION (15%) newest verbatim.

    Args:
        history: list of Turn objects
        current_usage: current token usage
        wm: AdaptiveWM instance with budget info
        retain_fraction: fraction of newest turns to retain verbatim (default 15%)

    Returns:
        Compacted list of Turn objects
    """
    if not wm.should_compact(current_usage):
        return history  # No pressure, return as-is

    if not history:
        return []

    # Calculate how many turns to retain
    total_turns = len(history)
    retain_count = max(1, int(total_turns * retain_fraction))

    # Keep newest 'retain_count' turns verbatim
    # Compress older turns using deep compression
    older_turns = history[:-retain_count] if retain_count < total_turns else []
    newest_turns = history[-retain_count:] if retain_count > 0 else []

    if not older_turns:
        return newest_turns

    # Deep compress older turns
    compressed_older = _deep_compress(older_turns)

    return compressed_older + newest_turns


def compress(
    history: list[Turn],
    query: str,
    mode: CompressMode = "auto",
    wm: AdaptiveWM | None = None,
    current_usage: int | None = None,
) -> list[Turn]:
    """T3.2 + P1-04: Nén history theo độ phức tạp query HOẶC context pressure.

    Nhận vào:
        history — list[Turn] lịch sử hội thoại.
        query   — câu truy vấn hiện tại.
        mode    - "auto" (mặc định: tự chọn theo query), "minimal", "deep", "pressure".
        wm      - AdaptiveWM instance (required for "pressure" mode).
        current_usage - Current token usage (required for "pressure" mode).

    Trả về:
        list[Turn] đã nén. Không thay đổi history đầu vào.
    """
    if not isinstance(history, list):
        raise TypeError("history phải là list[Turn]")
    if not isinstance(query, str):
        raise TypeError("query phải là chuỗi")

    # Bảo vệ input: copy nông để không thay đổi list gốc.
    work = list(history)

    if mode == "minimal":
        return _minimal_compress(work)
    if mode == "deep":
        return _deep_compress(work)
    if mode == "pressure":
        if wm is None or current_usage is None:
            raise ValueError("wm and current_usage required for pressure mode")
        return compact_by_pressure(work, current_usage, wm)
    # mode == "auto": chọn theo độ phức tạp query.
    if _is_complex_query(query):
        return _deep_compress(work)
    return _minimal_compress(work)


def _prefix_hash(turns: list[Turn], n: int) -> str:
    """Tính hash SHA-256 của n turn đầu trong list (dựa trên role+content)."""
    h = hashlib.sha256()
    for t in turns[:n]:
        payload = f"{t.role}|{t.content}".encode("utf-8", errors="replace")
        h.update(payload)
        h.update(b"\x00")
    return h.hexdigest()


def prefix_stable_hash(before: list[Turn], after: list[Turn]) -> bool:
    """T3.2: Kiểm tra hash tiền tố của history trước/sau nén có ổn định không.

    "Tiền tố ổn định" nghĩa là: phần đầu của history (các turn đầu theo role)
    không bị thay đổi bởi nén. Cụ thể: với mỗi role, turn đầu tiên xuất hiện
    trong `before` phải còn nguyên vẹn (cùng role + content) trong `after`.

    Trả về True nếu prefix ổn định, False nếu bị thay đổi.

    Quy ước:
      - before rỗng → luôn ổn định (không có gì để thay đổi).
      - after rỗng nhưng before không rỗng → không ổn định (mất dữ liệu).
    """
    if not before:
        return True
    if not after:
        return False

    # Lấy danh sách (role, content) của turn đầu tiên mỗi role trong before.
    first_by_role: dict[str, str] = {}
    order: list[str] = []
    for t in before:
        if t.role not in first_by_role:
            first_by_role[t.role] = t.content
            order.append(t.role)

    # Duyệt after, kiểm tra turn đầu mỗi role khớp với before.
    seen: set[str] = set()
    ai = 0
    for role in order:
        # Tìm turn đầu tiên của role này trong after (bắt đầu từ ai).
        while ai < len(after) and after[ai].role != role:
            ai += 1
        if ai >= len(after):
            # Role mất trong after → prefix không ổn định.
            return False
        if after[ai].content != first_by_role[role]:
            return False
        seen.add(role)
        ai += 1
    return True


def _cli() -> int:
    """CLI stub: đọc history JSON từ stdin, in ra list[Turn] đã nén.

    Pentest fix: xử lý stdin rỗng/sai JSON (trả 1 thay vì crash).

    Extended with P1-04: supports pressure mode with wm model and current_usage.
    """
    import json

    data = sys.stdin.read()
    try:
        payload = json.loads(data) if data.strip() else {}
    except json.JSONDecodeError as e:
        print(f"[adaptive_compress] lỗi parse JSON stdin: {e}", file=sys.stderr)
        return 1

    history = [Turn.model_validate(t) for t in payload.get("history", [])]
    query = payload.get("query", "")
    mode = payload.get("mode", "auto")

    # P1-04: Support pressure mode
    wm = None
    current_usage = None
    if mode == "pressure":
        model = payload.get("model", "default")
        wm = AdaptiveWM(model=model)
        current_usage = payload.get("current_usage", 0)

    out = compress(history, query, mode=mode, wm=wm, current_usage=current_usage)
    sys.stdout.write("[" + ",".join(t.model_dump_json(by_alias=True) for t in out) + "]")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())