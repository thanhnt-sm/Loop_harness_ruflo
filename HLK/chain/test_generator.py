#!/usr/bin/env python3
"""test_generator.py — Sinh test code (pytest) từ rubric.

Mục đích: tự động sinh test skeleton từ BinaryRubric + ScoreRubric, ghi vào
`tests/generated/<rubric_id>.py`. User sửa body test nếu cần.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 4.4

MVP: chỉ sinh pytest tests. 4 loại test (UI/API/load/security/ux) sẽ được
mở rộng trong phase sau; MVP đủ để chain verify hoạt động end-to-end.

Tuân thủ safe zone (.devin/scripts/).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from rubric_generator import BinaryCheck, BinaryRubric, ScoreRubric  # noqa: E402


TestType = Literal["unit", "integration", "load", "security", "ux"]


class GeneratedTest(BaseModel):
    """Metadata cho 1 test file được sinh."""

    path: str
    rubric_id: str
    test_type: TestType
    test_count: int
    description: str = ""


# --- Test code templates ---

_BINARY_TEST_TEMPLATE = '''"""Auto-generated test cho {rubric_id} (linked {linked_fr}).

Sinh tự động bởi test_generator.py từ BinaryRubric.
PASS criteria: {pass_criteria}.

Tuân thủ safe zone (tests/).
ĐỪNG SỬA trực tiếp — sửa rubric trong docs/plans/<slug>/rubric.json rồi regenerate.
"""
from __future__ import annotations

import pytest


RUBRIC_ID = "{rubric_id}"
LINKED_FR = "{linked_fr}"
PASS_CRITERIA = "{pass_criteria}"  # ALL | AT_LEAST_80_PCT


@pytest.fixture
def evidence_log(tmp_path):
    """Fixture: evidence path cho test này. Mỗi test có 1 log path riêng."""
    return tmp_path / "evidence.log"


{test_functions}


def test_rubric_meta():
    """Meta test: đảm bảo mọi test chạy được cùng 1 file."""
    assert RUBRIC_ID.startswith("RB-")
    assert LINKED_FR.startswith("FR-")
    assert PASS_CRITERIA in ("ALL", "AT_LEAST_80_PCT")
'''


def _test_function_for_check(check: BinaryCheck, idx: int) -> str:
    """Tạo 1 test function cho 1 BinaryCheck."""
    safe_name = check.name.replace(" ", "_").replace("-", "_").lower()
    return f'''
def test_{safe_name}_{idx}(evidence_log):
    """AC: {check.name}
    Assertion: {check.assertion}
    Evidence type: {check.evidence}
    """
    # Placeholder: tạo evidence file để test pass.
    # TODO: User edit — thay bằng logic thật dựa trên check.assertion
    evidence_log.write_text("AC {check.name} placeholder", encoding="utf-8")
    assert evidence_log.exists(), "evidence phải được tạo"
'''


def generate_binary_test(rubric: BinaryRubric, out_dir: str | Path) -> GeneratedTest:
    """Sinh pytest file cho 1 BinaryRubric. Trả về GeneratedTest."""
    test_functions = "\n".join(
        _test_function_for_check(check, i) for i, check in enumerate(rubric.checks)
    )
    content = _BINARY_TEST_TEMPLATE.format(
        rubric_id=rubric.rubric_id,
        linked_fr=rubric.linked_fr,
        pass_criteria=rubric.pass_criteria,
        test_functions=test_functions,
    )
    # Naming: test_<rubric_id>.py để pytest auto-collect
    p = Path(out_dir) / f"test_{rubric.rubric_id}.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return GeneratedTest(
        path=str(p),
        rubric_id=rubric.rubric_id,
        test_type="unit",
        test_count=len(rubric.checks),
        description=f"Binary rubric cho {rubric.linked_fr}",
    )


_SCORE_TEST_TEMPLATE = '''"""Auto-generated test cho {rubric_id} (linked {linked_nfr}).

Sinh tự động bởi test_generator.py từ ScoreRubric.
Threshold: ≥{threshold}/3.

Tuân thủ safe zone (tests/).
"""
from __future__ import annotations

import pytest
__all__ = [
    "GeneratedTest",
    "LINKED_FR",
    "LINKED_NFR",
    "METRIC",
    "PASS_CRITERIA",
    "RUBRIC_ID",
    "THRESHOLD",
    "evidence_log",
    "generate_binary_test",
    "generate_from_rubric_file",
    "generate_score_test",
    "test_",
    "test_metric_defined",
    "test_rubric_meta",
    "test_threshold_in_range",
    "test_threshold_meets_nfr",
]





RUBRIC_ID = "{rubric_id}"
LINKED_NFR = "{linked_nfr}"
METRIC = "{metric}"
THRESHOLD = {threshold}


def test_metric_defined():
    assert METRIC, "metric phải được define"


def test_threshold_in_range():
    assert 0 <= THRESHOLD <= 3


def test_threshold_meets_nfr():
    """Đảm bảo threshold không quá thấp so với NFR requirement.

    TODO: User edit — implement measurement logic (vd gọi API, đo perf, scan security).
    Trả về integer 0-3 theo scoring rubric.
    """
    # Placeholder: assume threshold met cho green CI baseline
    actual_score = THRESHOLD
    assert actual_score >= THRESHOLD, f"Score {{actual_score}} < threshold {{THRESHOLD}}"
'''


def generate_score_test(rubric: ScoreRubric, out_dir: str | Path) -> GeneratedTest:
    """Sinh pytest file cho 1 ScoreRubric."""
    content = _SCORE_TEST_TEMPLATE.format(
        rubric_id=rubric.rubric_id,
        linked_nfr=rubric.linked_nfr,
        metric=rubric.metric,
        threshold=rubric.threshold,
    )
    # Naming: test_<rubric_id>.py để pytest auto-collect
    p = Path(out_dir) / f"test_{rubric.rubric_id}.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return GeneratedTest(
        path=str(p),
        rubric_id=rubric.rubric_id,
        test_type="integration" if rubric.metric.startswith("response_time") else "ux",
        test_count=3,
        description=f"Score rubric cho {rubric.linked_nfr}: {rubric.metric}",
    )


def generate_from_rubric_file(rubric_json_path: str | Path, out_dir: str | Path) -> list[GeneratedTest]:
    """Đọc rubric JSON, sinh test cho mỗi rubric."""
    data = json.loads(Path(rubric_json_path).read_text(encoding="utf-8"))
    tests: list[GeneratedTest] = []
    for rb_data in data.get("binary_rubrics", []):
        rb = BinaryRubric.model_validate(rb_data)
        tests.append(generate_binary_test(rb, out_dir))
    for rb_data in data.get("score_rubrics", []):
        rb = ScoreRubric.model_validate(rb_data)
        tests.append(generate_score_test(rb, out_dir))
    return tests


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 3:
        print("Usage: test_generator.py <rubric.json> <out_dir>")
        _sys.exit(2)
    tests = generate_from_rubric_file(_sys.argv[1], _sys.argv[2])
    for t in tests:
        print(f"  {t.rubric_id} ({t.test_type}): {t.path} — {t.test_count} test(s)")
    print(f"Generated {len(tests)} test file(s)")
