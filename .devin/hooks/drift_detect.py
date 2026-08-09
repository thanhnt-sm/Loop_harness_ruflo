#!/usr/bin/env python3
"""drift_detect.py — Phat hien lech hanh vi (behavioral drift) bang JS divergence.

Day la hook PostToolUse: chay sau moi lan goi tool de theo doi 12 chieu hanh vi
(behavioral dimensions) va so sanh voi baseline (van hanh binh thuong).
Neu do lech (divergence) vuot 3 sigma (nguong y nghia thong ke) thi canh bao.

12 chieu hanh vi:
  1. tool_sequence      — thu tu tool duoc goi
  2. decision_pattern   — pattern quyet dinh (edit/write/read ratio)
  3. latency_distribution — phan phoi do tre
  4. output_length      — do dai output
  5. loop_depth         — do sau vong lap
  6. retry_count        — so lan thu lai
  7. error_rate         — ty le loi
  8. file_diversity     — da dang file bi anh huong
  9. command_diversity  — da dang lenh
  10. context_usage     — muc su dung context
  11. token_consumption — muc tieu hao token
  12. plan_adherence    — do tuan theo ke hoach (bigram Jaccard)

Dau vao (tu hook system, JSON tren stdin):
  {"tool_name": str, "tool_input": dict, "tool_output": dict/str,
   "latency_ms": int, "session_id": str}

Dau ra (JSON stdout):
  {"drift_detected": bool, "dimension": str, "divergence": float, "threshold": float}

Trang thai:
  .devin/telemetry/baseline.json  — van hanh baseline (tu N sample dau)
  .devin/telemetry/drift_state.json — cua so hien tai + lich su
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, deque
from pathlib import Path

# Cau hinh
TELEMETRY_DIR = ".devin/telemetry"
BASELINE_FILE = f"{TELEMETRY_DIR}/baseline.json"
STATE_FILE = f"{TELEMETRY_DIR}/drift_state.json"

# So sample toi thieu de tao baseline va de kiem tra drift
BASELINE_MIN_SAMPLES = 50  # can >= 50 sample moi kiem tra drift (3 sigma)
WINDOW_SIZE = 50  # kich thuoc cua so truot (sliding window)

# 12 chieu hanh vi
DIMENSIONS = [
    "tool_sequence",
    "decision_pattern",
    "latency_distribution",
    "output_length",
    "loop_depth",
    "retry_count",
    "error_rate",
    "file_diversity",
    "command_diversity",
    "context_usage",
    "token_consumption",
    "plan_adherence",
]


def _repo_root() -> Path:
    """Tim thu muc goc repo (co .devin)."""
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


def _ensure_dirs(root: Path) -> None:
    """Tao thu muc telemetry neu chua co."""
    (root / TELEMETRY_DIR).mkdir(parents=True, exist_ok=True)


# --- Ham tien ich xac suat ---

def _js_divergence(p: dict, q: dict) -> float:
    """Tinh Jensen-Shannon divergence giua 2 phan phoi (dict key -> trong so).

    JS(P||Q) = 0.5 * KL(P||M) + 0.5 * KL(Q||M), voi M = (P+Q)/2.
    Tra ve gia tri trong [0, ln(2)] ~ [0, 0.693] (neu log tu nhien).
    """
    # Bước 1: gom tat ca key, chuan hoa thanh phan phoi xac suat
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    p_sum = sum(p.values()) or 1
    q_sum = sum(q.values()) or 1
    p_norm = {k: p.get(k, 0) / p_sum for k in keys}
    q_norm = {k: q.get(k, 0) / q_sum for k in keys}
    # Bước 2: tinh phan phoi trung binh M
    m = {k: 0.5 * (p_norm[k] + q_norm[k]) for k in keys}
    # Bước 3: tinh KL divergence (tranh log(0))
    def _kl(a: dict, b: dict) -> float:
        s = 0.0
        for k in keys:
            ai = a[k]
            bi = b[k]
            if ai > 0 and bi > 0:
                s += ai * math.log(ai / bi)
        return s
    return 0.5 * _kl(p_norm, m) + 0.5 * _kl(q_norm, m)


def _to_histogram(values, bins: int = 10) -> dict:
    """Chuyen danh sach gia tri so thanh histogram (dict bin -> count)."""
    if not values:
        return {}
    lo = min(values)
    hi = max(values)
    if hi == lo:
        # Pentest fix: các hằng số khác nhau phải có bin khác nhau để phát hiện drift.
        return {f"bin_const_{lo}": len(values)}
    width = (hi - lo) / bins
    hist = Counter()
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        hist[f"bin_{idx}"] += 1
    return dict(hist)


def _bigrams(seq) -> list:
    """Tinh danh sach bigram (cap lien nhau) tu mot day."""
    return [(seq[i], seq[i + 1]) for i in range(len(seq) - 1)]


def _jaccard(a: list, b: list) -> float:
    """He so Jaccard giua 2 tap bigram: |A giao B| / |A hop B|."""
    sa = set(a)
    sb = set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


# --- Trich xuat dac trung tu 1 lan goi tool ---

def _extract_features(data: dict, state: dict) -> dict:
    """Trich xuat 12 dac trung tu du lieu dau vao cua hook.

    data: JSON tu hook system.
    state: trang thai drift hien tai (de lay lich su tool_sequence, plan steps).
    """
    tool_name = str(data.get("tool_name", "unknown"))
    tool_input = data.get("tool_input", {}) or {}
    tool_output = data.get("tool_output", "")
    latency_ms = float(data.get("latency_ms", 0) or 0)

    # output length (so ky tu)
    if isinstance(tool_output, dict):
        out_str = str(tool_output.get("content", tool_output))
    else:
        out_str = str(tool_output)
    output_len = len(out_str)

    # token consumption uoc luong (4 ky tu ~ 1 token)
    token_consumption = output_len / 4

    # error_rate: output co chua tu khoa loi?
    err_markers = ("error", "failed", "exception", "traceback", "permission denied")
    is_error = int(any(m in out_str.lower() for m in err_markers))

    # retry_count: dem so lan tool giong nhau lien tiep
    history = state.get("recent_tools", [])
    retry = 0
    for prev in reversed(history):
        if prev == tool_name:
            retry += 1
        else:
            break

    # file_diversity: so file khac nhau trong lich su gan day
    file_path = ""
    for key in ("file_path", "path", "notebook_path", "file"):
        if key in tool_input:
            file_path = str(tool_input[key])
            break
    recent_files = state.get("recent_files", [])
    all_files = set(recent_files[-WINDOW_SIZE:])
    if file_path:
        all_files.add(file_path)
    file_diversity = len(all_files)

    # command_diversity: so lenh khac nhau
    command = str(tool_input.get("command", tool_input.get("query", tool_name)))
    recent_commands = state.get("recent_commands", [])
    all_commands = set(recent_commands[-WINDOW_SIZE:])
    all_commands.add(command)
    command_diversity = len(all_commands)

    # loop_depth: so lan tool lap lai gan day (don gian)
    loop_depth = retry

    # context_usage: uoc luong tu output_len / 4000
    context_usage = output_len / 4000.0

    # plan_adherence: Jaccard bigram giua plan steps va executed actions
    plan_steps = state.get("plan_steps", [])
    executed = state.get("recent_tools", []) + [tool_name]
    plan_bigrams = _bigrams(plan_steps) if plan_steps else []
    exec_bigrams = _bigrams(executed)
    plan_adherence = _jaccard(plan_bigrams, exec_bigrams) if plan_bigrams else 1.0

    return {
        "tool_sequence": tool_name,
        "decision_pattern": "write" if tool_name.lower() in ("write", "edit", "notebook_edit") else "read",
        "latency_distribution": latency_ms,
        "output_length": float(output_len),
        "loop_depth": float(loop_depth),
        "retry_count": float(retry),
        "error_rate": float(is_error),
        "file_diversity": float(file_diversity),
        "command_diversity": float(command_diversity),
        "context_usage": context_usage,
        "token_consumption": token_consumption,
        "plan_adherence": plan_adherence,
    }


def _build_distribution(features_list: list, dim: str) -> dict:
    """Xay dung phan phoi baseline cho 1 chieu tu danh sach dac trung."""
    values = [f.get(dim, 0) for f in features_list]
    # Cac chieu so lien tuc -> histogram; cac chieu phan loai -> dem tan so
    categorical = {"tool_sequence", "decision_pattern"}
    if dim in categorical:
        return dict(Counter(values))
    return _to_histogram(values)


def _load_json(path: Path, default):
    """Doc JSON an toan (tra ve default neu loi/khong ton tai)."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    except Exception:
        pass
    return default


def _save_json(path: Path, data) -> None:
    """Ghi JSON an toan (atomic tmp + rename, tên tmp duy nhất theo pid)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        pid = os.getpid()
        tmp = path.with_suffix(f"{path.suffix}.{pid}.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"[drift_detect] khong the ghi {path}: {e}", file=sys.stderr)


    except Exception as e:
        print(f"[drift_detect] khong the ghi {path}: {e}", file=sys.stderr)


def _update_state(state: dict, features: dict) -> None:
    """Cap nhat trang thai drift trong bộ nhớ (không ghi file).

    Ghi file được tập trung ở cuối detect_drift để tránh double-write.
    """
    state.setdefault("samples", []).append(features)
    # Giu cua so truot trong WINDOW_SIZE
    if len(state["samples"]) > WINDOW_SIZE * 2:
        state["samples"] = state["samples"][-WINDOW_SIZE * 2:]
    # Lich su tool/file/command
    state.setdefault("recent_tools", []).append(features["tool_sequence"])
    state["recent_tools"] = state["recent_tools"][-WINDOW_SIZE:]
    # file_path duoc truyen rieng qua state (cap nhat tu caller)
    state["recent_files"] = state.get("recent_files", [])[-WINDOW_SIZE:]
    state["recent_commands"] = state.get("recent_commands", [])[-WINDOW_SIZE:]


def detect_drift(root: Path, data: dict) -> dict:
    """Ham chinh: phat hien lech hanh vi cho 1 lan goi tool.

    Tra ve dict {"drift_detected", "dimension", "divergence", "threshold"}.
    """
    _ensure_dirs(root)
    baseline_path = root / BASELINE_FILE
    state_path = root / STATE_FILE

    # Bước 1: tai trang thai (xu ly state hong/thieu)
    state = _load_json(state_path, {})
    if not isinstance(state, dict):
        state = {}

    # Bước 2: trich xuat dac trung tu lan goi tool nay
    features = _extract_features(data, state)

    # Cap nhat recent_files/commands truoc khi luu
    tool_input = data.get("tool_input", {}) or {}
    for key in ("file_path", "path", "notebook_path", "file"):
        if key in tool_input:
            state.setdefault("recent_files", []).append(str(tool_input[key]))
            state["recent_files"] = state["recent_files"][-WINDOW_SIZE:]
            break
    command = str(tool_input.get("command", tool_input.get("query", "")))
    if command:
        state.setdefault("recent_commands", []).append(command)
        state["recent_commands"] = state["recent_commands"][-WINDOW_SIZE:]

    # Bước 3: tai baseline (neu chua co -> chua the kiem tra)
    baseline = _load_json(baseline_path, {})
    baseline_samples = baseline.get("samples", []) if isinstance(baseline, dict) else []
    baseline_count = len(baseline_samples)

    # Bước 4: neu chua du sample baseline -> tich luy vao baseline (có giới hạn)
    if baseline_count < BASELINE_MIN_SAMPLES:
        baseline.setdefault("samples", []).append(features)
        # Pentest fix: giới hạn baseline samples để tránh file tăng không kiểm soát.
        if len(baseline["samples"]) > BASELINE_MIN_SAMPLES:
            baseline["samples"] = baseline["samples"][-BASELINE_MIN_SAMPLES:]
        _save_json(baseline_path, baseline)
        _update_state(state, features)
        _save_json(state_path, state)
        return {
            "drift_detected": False,
            "dimension": "none",
            "divergence": 0.0,
            "threshold": 0.0,
            "reason": f"baseline_dang_tich_luy ({min(baseline_count + 1, BASELINE_MIN_SAMPLES)}/{BASELINE_MIN_SAMPLES})",
        }

    # Bước 5: cap nhat state + lay cua so hien tai
    _update_state(state, features)
    window = state.get("samples", [])[-WINDOW_SIZE:]
    if len(window) < BASELINE_MIN_SAMPLES:
        _save_json(state_path, state)
        return {
            "drift_detected": False,
            "dimension": "none",
            "divergence": 0.0,
            "threshold": 0.0,
            "reason": f"khong_du_sample ({len(window)}/{BASELINE_MIN_SAMPLES})",
        }

    # Bước 6: tinh JS divergence cho tung chieu va kiem tra 3 sigma
    # Nguong 3 sigma: dung do lech lich su de uoc luong std
    divergences = {}
    for dim in DIMENSIONS:
        base_dist = _build_distribution(baseline_samples, dim)
        curr_dist = _build_distribution(window, dim)
        divergences[dim] = _js_divergence(base_dist, curr_dist)

    # Luu lich su divergence de tinh sigma
    state.setdefault("divergence_history", []).append(divergences)
    state["divergence_history"] = state["divergence_history"][-100:]
    # Pentest fix: ghi state một lần duy nhất ở cuối, tránh double-write giữa các bước.
    _save_json(state_path, state)

    # Tinh trung binh + std cua lich su divergence (de co 3 sigma threshold)
    hist = state.get("divergence_history", [])
    if len(hist) < 5:
        # Qua it lich su -> dung nguong co dinh ln(2) * 0.5
        threshold = 0.35
    else:
        # Tinh nguong 3 sigma cho moi chieu
        drift_dim = None
        drift_val = 0.0
        drift_thr = 0.0
        for dim in DIMENSIONS:
            vals = [h.get(dim, 0.0) for h in hist]
            mean = sum(vals) / len(vals)
            var = sum((v - mean) ** 2 for v in vals) / len(vals)
            std = math.sqrt(var) or 1e-9
            thr = mean + 3 * std
            cur = divergences[dim]
            if cur > thr and cur > drift_val:
                drift_dim = dim
                drift_val = cur
                drift_thr = thr
        if drift_dim:
            return {
                "drift_detected": True,
                "dimension": drift_dim,
                "divergence": round(drift_val, 6),
                "threshold": round(drift_thr, 6),
            }
        return {
            "drift_detected": False,
            "dimension": "none",
            "divergence": 0.0,
            "threshold": 0.0,
        }

    # Fallback: nguong co dinh
    for dim in DIMENSIONS:
        if divergences[dim] > threshold:
            return {
                "drift_detected": True,
                "dimension": dim,
                "divergence": round(divergences[dim], 6),
                "threshold": round(threshold, 6),
            }
    return {
        "drift_detected": False,
        "dimension": "none",
        "divergence": 0.0,
        "threshold": round(threshold, 6),
    }


def main() -> int:
    """Doc JSON tu stdin, phat hien drift, in ket qua JSON ra stdout."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(json.dumps({
            "drift_detected": False,
            "dimension": "none",
            "divergence": 0.0,
            "threshold": 0.0,
            "error": f"input_khong_hop_le: {e}",
        }))
        return 0

    except Exception as e:
        print(json.dumps({
            "drift_detected": False,
            "dimension": "none",
            "divergence": 0.0,
            "threshold": 0.0,
            "error": f"input_khong_hop_le: {e}",
        }))
        return 0

    root = _repo_root()
    try:
        result = detect_drift(root, data)
    except Exception as e:
        result = {
            "drift_detected": False,
            "dimension": "none",
            "divergence": 0.0,
            "threshold": 0.0,
            "error": f"loi_xu_ly: {e}",
        }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
