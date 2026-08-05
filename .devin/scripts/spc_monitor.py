#!/usr/bin/env python3
"""spc_monitor.py — Statistical Process Control (SPC) cho 6 chi so.

Su dung control chart 3 sigma va 5 luat Western Electric de phat hien
hanh vi bat thuong (out-of-control) cua cac chi so chat luong.

6 chi so:
  - accuracy           — do chinh xac
  - hallucination_rate — ty le ao tuong
  - tone_deviation     — do lech tone
  - task_accuracy      — do chinh xac nhiem vu
  - response_length   — do dai phan hoi
  - latency_ms         — do tre (ms)

5 luat Western Electric:
  1. 1 diem ngoai 3 sigma
  2. 9 diem lien tiep cung phia center
  3. 6 diem lien tiep tang/giam
  4. 2/3 diem lien tiep ngoai 2 sigma
  5. 4/5 diem lien tiep ngoai 1 sigma

CLI:
  python spc_monitor.py --update <metric> <value>   # Them 1 diem du lieu
  python spc_monitor.py --check                      # Kiem tra luat WE
  python spc_monitor.py --report                     # Sinh bao cao Markdown

Ma thoat:
  0 = khong vi pham
  1 = co vi pham luat
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

# Cau hinh
TELEMETRY_DIR = ".devin/telemetry"
STATE_FILE = f"{TELEMETRY_DIR}/spc_state.json"
REPORT_DIR = "docs/plans"

# 6 chi so theo doi
METRICS = [
    "accuracy",
    "hallucination_rate",
    "tone_deviation",
    "task_accuracy",
    "response_length",
    "latency_ms",
]

# So diem toi thieu de ap dung luat 2-5 (luat 1 luon ap dung)
MIN_POINTS_FOR_RULES = 20

# So diem giu trong lich su moi metric
MAX_HISTORY = 200


def _repo_root() -> Path:
    """Tim thu muc goc repo (co .devin)."""
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


def _load_state(root: Path) -> dict:
    """Doc trang thai SPC (tao moi neu khong co / hong)."""
    path = root / STATE_FILE
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"metrics": {m: [] for m in METRICS}, "updated_at": ""}


def _save_state(root: Path, state: dict) -> None:
    """Ghi trang thai SPC an toan."""
    path = root / STATE_FILE
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = datetime.now().isoformat()
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[spc_monitor] khong the ghi state: {e}", file=sys.stderr)


def _mean_std(values: list) -> tuple:
    """Tinh trung binh va do lech chuan. Tra ve (mean, std)."""
    if not values:
        return 0.0, 0.0
    mean = statistics.fmean(values)
    if len(values) < 2:
        return mean, 0.0
    std = statistics.stdev(values)
    return mean, std


# --- 5 luat Western Electric ---

def _rule1_beyond_3sigma(values: list, mean: float, std: float) -> list:
    """Luat 1: 1 diem ngoai 3 sigma."""
    if std <= 0:
        return []
    ucl = mean + 3 * std
    lcl = mean - 3 * std
    violations = []
    for i, v in enumerate(values):
        if v > ucl or v < lcl:
            violations.append({"rule": 1, "index": i, "value": v, "ucl": ucl, "lcl": lcl})
    return violations


def _rule2_9_same_side(values: list, mean: float) -> list:
    """Luat 2: 9 diem lien tiep cung phia center."""
    violations = []
    if len(values) < 9:
        return violations
    for i in range(len(values) - 8):
        window = values[i:i + 9]
        if all(v > mean for v in window) or all(v < mean for v in window):
            violations.append({"rule": 2, "index": i, "window": window})
    return violations


def _rule3_6_trend(values: list) -> list:
    """Luat 3: 6 diem lien tiep tang hoac giam."""
    violations = []
    if len(values) < 6:
        return violations
    for i in range(len(values) - 5):
        window = values[i:i + 6]
        if all(window[j] < window[j + 1] for j in range(5)):
            violations.append({"rule": 3, "index": i, "trend": "increasing"})
        elif all(window[j] > window[j + 1] for j in range(5)):
            violations.append({"rule": 3, "index": i, "trend": "decreasing"})
    return violations


def _rule4_2of3_beyond_2sigma(values: list, mean: float, std: float) -> list:
    """Luat 4: 2/3 diem lien tiep ngoai 2 sigma (cung phia)."""
    if std <= 0 or len(values) < 3:
        return []
    ucl2 = mean + 2 * std
    lcl2 = mean - 2 * std
    violations = []
    for i in range(len(values) - 2):
        window = values[i:i + 3]
        above = sum(1 for v in window if v > ucl2)
        below = sum(1 for v in window if v < lcl2)
        if above >= 2 or below >= 2:
            violations.append({"rule": 4, "index": i, "window": window})
    return violations


def _rule5_4of5_beyond_1sigma(values: list, mean: float, std: float) -> list:
    """Luat 5: 4/5 diem lien tiep ngoai 1 sigma (cung phia)."""
    if std <= 0 or len(values) < 5:
        return []
    ucl1 = mean + 1 * std
    lcl1 = mean - 1 * std
    violations = []
    for i in range(len(values) - 4):
        window = values[i:i + 5]
        above = sum(1 for v in window if v > ucl1)
        below = sum(1 for v in window if v < lcl1)
        if above >= 4 or below >= 4:
            violations.append({"rule": 5, "index": i, "window": window})
    return violations


def check_rules(values: list) -> dict:
    """Kiem tra tat ca luat Western Electric cho 1 metric.

    Tra ve {"violations": [...], "mean", "std", "ucl", "lcl", "n"}.
    """
    n = len(values)
    mean, std = _mean_std(values)
    ucl = mean + 3 * std if std > 0 else mean
    lcl = mean - 3 * std if std > 0 else mean

    violations = []
    # Luat 1 luon ap dung
    violations.extend(_rule1_beyond_3sigma(values, mean, std))
    # Luat 2-5 chi ap dung khi du du lieu
    if n >= MIN_POINTS_FOR_RULES:
        violations.extend(_rule2_9_same_side(values, mean))
        violations.extend(_rule3_6_trend(values))
        violations.extend(_rule4_2of3_beyond_2sigma(values, mean, std))
        violations.extend(_rule5_4of5_beyond_1sigma(values, mean, std))

    return {
        "violations": violations,
        "mean": round(mean, 6),
        "std": round(std, 6),
        "ucl": round(ucl, 6),
        "lcl": round(lcl, 6),
        "n": n,
    }


def cmd_update(root: Path, metric: str, value: float) -> int:
    """Them 1 diem du lieu vao lich su cua metric."""
    if metric not in METRICS:
        print(f"[ERROR] metric khong hop le: {metric}. Cho phep: {', '.join(METRICS)}")
        return 1
    state = _load_state(root)
    state.setdefault("metrics", {}).setdefault(metric, []).append(float(value))
    # Gioi han lich su
    if len(state["metrics"][metric]) > MAX_HISTORY:
        state["metrics"][metric] = state["metrics"][metric][-MAX_HISTORY:]
    _save_state(root, state)
    print(f"[OK] Da them {value} vao metric '{metric}' (n={len(state['metrics'][metric])})")
    return 0


def cmd_check(root: Path) -> int:
    """Kiem tra tat ca luat WE cho moi metric. Ma thoat 1 neu co vi pham."""
    state = _load_state(root)
    metrics = state.get("metrics", {})
    any_violation = False
    for metric in METRICS:
        values = metrics.get(metric, [])
        if not values:
            print(f"[{metric}] khong co du lieu")
            continue
        result = check_rules(values)
        n_viol = len(result["violations"])
        status = "VI PHAM" if n_viol > 0 else "ON DINH"
        if n_viol > 0:
            any_violation = True
        print(
            f"[{metric}] {status} | n={result['n']} mean={result['mean']} "
            f"std={result['std']} UCL={result['ucl']} LCL={result['lcl']} "
            f"violations={n_viol}"
        )
        for v in result["violations"]:
            print(f"    - Luat {v['rule']} tai index {v['index']}: {v}")
    return 1 if any_violation else 0


def cmd_report(root: Path) -> int:
    """Sinh bao cao SPC Markdown."""
    state = _load_state(root)
    metrics = state.get("metrics", {})
    date_str = datetime.now().strftime("%Y%m%d")
    report_path = root / REPORT_DIR / f"SPC_REPORT_{date_str}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Bao cao SPC — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "Bao cao Statistical Process Control cho 6 chi so chat luong.",
        "",
        "## Tong quan",
        "",
        f"- So metric theo doi: {len(METRICS)}",
        f"- Nguong 3 sigma (UCL/LCL) duoc tinh tu mean ± 3 std.",
        f"- Luat Western Electric: 5 luat.",
        f"- So diem toi thieu de ap dung luat 2-5: {MIN_POINTS_FOR_RULES}",
        "",
        "## Chi tiet tung metric",
        "",
    ]

    any_violation = False
    for metric in METRICS:
        values = metrics.get(metric, [])
        if not values:
            lines += [f"### {metric}", "", "*Khong co du lieu.*", ""]
            continue
        result = check_rules(values)
        n_viol = len(result["violations"])
        if n_viol > 0:
            any_violation = True
        lines += [
            f"### {metric}",
            "",
            f"- So diem (n): **{result['n']}**",
            f"- Trung binh (mean): **{result['mean']}**",
            f"- Do lech chuan (std): **{result['std']}**",
            f"- UCL (mean + 3σ): **{result['ucl']}**",
            f"- LCL (mean - 3σ): **{result['lcl']}**",
            f"- So vi pham: **{n_viol}**",
            "",
        ]
        if n_viol > 0:
            lines += ["| Luat | Index | Chi tiet |", "|------|-------|----------|"]
            for v in result["violations"]:
                detail = json.dumps(v, ensure_ascii=False)
                lines.append(f"| {v['rule']} | {v['index']} | {detail} |")
            lines.append("")
        else:
            lines += ["*Metric on dinh, khong vi pham.*", ""]

    lines += [
        "## Ket luan",
        "",
        f"**Trang thai:** {'CO VI PHAM — can canh bao' if any_violation else 'ON DINH'}",
        "",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Bao cao da sinh: {report_path}")
    return 1 if any_violation else 0


def main() -> int:
    """Xu ly CLI."""
    import argparse
    ap = argparse.ArgumentParser(description="SPC monitor — 6 chi so, 5 luat Western Electric")
    ap.add_argument("--update", nargs=2, metavar=("METRIC", "VALUE"), help="Them 1 diem du lieu")
    ap.add_argument("--check", action="store_true", help="Kiem tra luat Western Electric")
    ap.add_argument("--report", action="store_true", help="Sinh bao cao Markdown")
    ap.add_argument("--root", default=".", help="Thu muc goc repo")
    args = ap.parse_args()

    root = Path(args.root).resolve()

    if args.update:
        metric, value = args.update
        try:
            val = float(value)
        except ValueError:
            print(f"[ERROR] value khong phai so: {value}")
            return 1
        return cmd_update(root, metric, val)
    elif args.check:
        return cmd_check(root)
    elif args.report:
        return cmd_report(root)
    else:
        ap.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
