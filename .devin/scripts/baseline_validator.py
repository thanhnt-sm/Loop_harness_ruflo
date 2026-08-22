#!/usr/bin/env python3
"""baseline_validator.py — Validate drift detection baseline quality.

V5 fix: drift_detect.py build baseline từ 50 sample đầu. Nếu agent drift
từ đầu → baseline bị poison → drift không bao giờ detect. Module này
validate baseline trước khi dùng, fallback sang default nếu invalid.

Checks:
  1. Đủ 12 dimensions
  2. Variance > threshold (baseline bị poison = variance thấp)
  3. No extreme outliers
"""
from __future__ import annotations

import math
from typing import Any

# 12 dimensions từ drift_detect.py
DIMENSIONS = [
    "tool_sequence", "decision_pattern", "latency_distribution",
    "output_length", "loop_depth", "retry_count", "error_rate",
    "file_diversity", "command_diversity", "context_usage",
    "token_consumption", "plan_adherence",
]

# Ngưỡng validation
MIN_VARIANCE = 0.01  # baseline bị poison = tất cả giá trị giống nhau
MIN_SAMPLES = 10     # tối thiểu samples để validate
MAX_OUTLIER_RATIO = 0.5  # >50% outlier = baseline không đáng tin


def _extract_values(samples: list[dict], dim: str) -> list[float]:
    """Trích giá trị số cho 1 dimension từ danh sách samples."""
    values = []
    for s in samples:
        v = s.get(dim, 0)
        try:
            values.append(float(v))
        except (TypeError, ValueError):
            pass
    return values


def _variance(values: list[float]) -> float:
    """Tính variance của danh sách giá trị."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / len(values)
    return var


def _outlier_ratio(values: list[float]) -> float:
    """Tính tỷ lệ outlier.

    Pentest V5 fix: detect bimodal/anomalous distribution.
    - Detect bimodal: nếu range (max-min) > 100x std → anomalous
    - Fallback: MAD (median absolute deviation) cho moderate outliers
    - Fallback: IQR cho normal outliers
    """
    if len(values) < 4:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    median = sorted_vals[n // 2]

    # Detect bimodal/anomalous: range quá lớn so với std
    val_range = sorted_vals[-1] - sorted_vals[0]
    var = _variance(values)
    std = math.sqrt(var)
    if std > 1e-9 and val_range / std > 100:
        # Range > 100x std → bimodal/anomalous → flag high outlier ratio
        return 0.5  # Report 50%+ outlier

    # MAD method
    abs_devs = sorted(abs(v - median) for v in values)
    mad = abs_devs[n // 2]
    if mad > 1e-9:
        outliers = sum(1 for v in values if abs(v - median) > 3 * mad)
        return outliers / len(values)

    # IQR fallback
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1
    if iqr < 1e-9:
        return 0.0
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    outliers = sum(1 for v in values if v < lower or v > upper)
    return outliers / len(values)


def validate_baseline(baseline: dict) -> dict:
    """Validate baseline quality trước khi dùng cho drift detection.

    Returns:
        {"valid": bool, "reason": str, "dimension_issues": list}

    Nếu invalid → caller nên dùng default baseline (hardcoded normal distribution).
    """
    if not isinstance(baseline, dict):
        return {"valid": False, "reason": "baseline không phải dict", "dimension_issues": []}

    samples = baseline.get("samples", [])
    if not isinstance(samples, list):
        return {"valid": False, "reason": "samples không phải list", "dimension_issues": []}

    if len(samples) < MIN_SAMPLES:
        return {"valid": False, "reason": f"insufficient_samples ({len(samples)}/{MIN_SAMPLES})", "dimension_issues": []}

    issues = []
    low_variance_count = 0

    for dim in DIMENSIONS:
        values = _extract_values(samples, dim)
        if not values:
            issues.append(f"{dim}: thiếu dữ liệu")
            continue

        var = _variance(values)
        if var < MIN_VARIANCE:
            issues.append(f"{dim}: variance quá thấp ({var:.4f} < {MIN_VARIANCE})")
            low_variance_count += 1

        outlier_ratio = _outlier_ratio(values)
        if outlier_ratio > MAX_OUTLIER_RATIO:
            issues.append(f"{dim}: quá nhiều outlier ({outlier_ratio:.1%})")

    # Nếu >6/12 dimensions có variance thấp → baseline bị poison
    if low_variance_count > 6:
        return {
            "valid": False,
            "reason": f"baseline_poisoned: {low_variance_count}/12 dimensions có variance thấp",
            "dimension_issues": issues,
        }

    if len(issues) > 8:
        return {
            "valid": False,
            "reason": f"too_many_issues: {len(issues)} dimension issues",
            "dimension_issues": issues,
        }

    return {"valid": True, "reason": "", "dimension_issues": issues}


def default_baseline() -> dict:
    """Trả về default baseline (hardcoded normal distribution).

    Dùng khi baseline thực tế invalid (poisoned hoặc insufficient).
    """
    return {
        "samples": [
            {dim: 0.0 for dim in DIMENSIONS},
        ],
        "default": True,
        "reason": "default baseline — actual baseline was invalid",
    }


if __name__ == "__main__":
    # Test với baseline rỗng
    result = validate_baseline({})
    print(f"Empty baseline: {result}")
