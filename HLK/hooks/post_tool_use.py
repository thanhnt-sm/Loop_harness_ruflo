#!/usr/bin/env python3
"""Post-tool-use hook — entry point (đã tách logic vào các module post_tool_*).

Giữ nguyên contract:
  - Đọc JSON từ stdin: {"tool_name": ..., "tool_input": ..., "tool_response": ..., "session_id": ...}
  - Ghi session_state / journal / context_flags, phát hiện candidate memory
    và chạy các enforcement hooks (U57-U62).
  - Luôn exit 0 (post-hook không bao giờ block).

Toàn bộ logic nằm ở post_tool_config / post_tool_helpers / post_tool_sha /
post_tool_memory_candidate / post_tool_bounded / post_tool_enforce_quality /
post_tool_enforce_loop / post_tool_engine. File này chỉ import và chạy main(),
đồng thời re-export mọi hàm/hằng số công khai để giữ nguyên API
(vd: `import post_tool_use as ptu; ptu.VALID_CORRECT_ACTIONS`).
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

# Đảm bảo thư mục .devin/hooks có trên sys.path (để import các module post_tool_*
# và ahd_session khi hook được chạy trực tiếp hoặc import qua test).
_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from post_tool_config import (
    HOOK_TIMEOUT_SECONDS,
    MAX_ITERATIONS_WITHOUT_STATE_WRITE,
    MIN_COMPRESSION_THRESHOLD,
    MAX_OUTPUT_SIZE_COMPRESSION,
    DEFAULT_COMPRESSION_THRESHOLD,
    MAX_FAILURE_THRESHOLD,
    _CONTEXT_FLAGS_CACHE,
    _CONTEXT_FLAGS_LOADED,
    _STATE_WRITE_COUNTER,
    _STATE_WRITE_BATCH,
    CONTEXT_OVERSIZE_THRESHOLD,
    CANDIDATE_MEMORY_MAX,
    VALID_CORRECT_ACTIONS,
    CANDIDATE_MEMORY_PER_HOUR,
    CANDIDATE_MEMORY_WINDOW_SECONDS,
    _SECRET_PATTERNS,
)
from post_tool_helpers import (
    _redact,
    _response_size,
    _extract_file_path,
    _extract_command,
)
from post_tool_sha import (
    _compute_sha256,
    _track_file_sha,
)
from post_tool_memory_candidate import (
    _repeated_failure_count,
    _extract_candidate_memory,
    _memory_rate_limited,
    _audit_candidate,
)
from post_tool_bounded import (
    _append_bounded_jsonl,
    _rotate,
)
from post_tool_enforce_quality import (
    _u57_auto_quality_checks,
    _u58_done_detection,
    _u59_skill_auto_router,
)
from post_tool_enforce_loop import (
    _u60_loop_enforcement,
    _u61_state_write_verification,
    _u62_memory_confidence,
)
from post_tool_engine import main


if __name__ == "__main__":
    # U15: Internal timeout — post-hook always exits 0, just fail silently if too slow.
    t = threading.Thread(target=main, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        print("[post_tool_use] U15 timeout — exiting (non-blocking)", file=sys.stderr)
    sys.exit(0)
