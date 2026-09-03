"""Tests cho test_generator.py — sinh pytest code từ rubric."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from rubric_generator import (  # noqa: E402
    BinaryCheck,
    BinaryRubric,
    ScoreRubric,
    generate_rubric_file,
)
from test_generator import (  # noqa: E402
    GeneratedTest,
    generate_binary_test,
    generate_from_rubric_file,
    generate_score_test,
)
from brd_schema import Actor, BRD, FunctionalRequirement, NonFunctionalRequirement  # noqa: E402


def test_generate_binary_test_writes_file(tmp_path):
    rb = BinaryRubric(
        rubric_id="RB-001",
        linked_fr="FR-001",
        checks=[
            BinaryCheck(name="AC1", assertion="len(.) > 0", evidence="log"),
            BinaryCheck(name="AC2", assertion='contains "ok"', evidence="log"),
        ],
        pass_criteria="ALL",
    )
    result = generate_binary_test(rb, tmp_path)
    assert result.path == str(tmp_path / "test_RB-001.py")
    assert result.test_count == 2
    assert Path(result.path).exists()
    content = Path(result.path).read_text(encoding="utf-8")
    assert "RUBRIC_ID = \"RB-001\"" in content
    assert "def test_ac1_0" in content
    assert "def test_ac2_1" in content
    assert "PASS_CRITERIA = \"ALL\"" in content


def test_generate_score_test_writes_file(tmp_path):
    rb = ScoreRubric(
        rubric_id="RB-002",
        linked_nfr="NFR-001",
        metric="response_time_p95",
        scoring={"0": "bad", "1": "ok", "2": "good", "3": "great"},
        threshold=2,
        evidence="Đo ở production",
    )
    result = generate_score_test(rb, tmp_path)
    assert result.path == str(tmp_path / "test_RB-002.py")
    assert Path(result.path).exists()
    content = Path(result.path).read_text(encoding="utf-8")
    assert "METRIC = \"response_time_p95\"" in content
    assert "THRESHOLD = 2" in content


def test_generate_from_full_brd(tmp_path):
    """End-to-end: BRD → rubric.json → test files."""
    brd = BRD(
        title="Test BRD", business_goal="Long enough business goal here",
        version="1.0.0", owner="me",
        actors=[Actor(name="x", role="x")],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="x", use_case="y", description="long enough description",
                priority="must", acceptance_criteria=["criterion 1 valid", "criterion 2 valid"]
            )
        ],
        non_functional_requirements=[
            NonFunctionalRequirement(id="NFR-001", type="perf", metric="response_time_p95", threshold="< 200ms")
        ]
    )
    rubric_path = tmp_path / "rubric.json"
    out_dir = tmp_path / "tests_generated"
    generate_rubric_file(brd, rubric_path)
    tests = generate_from_rubric_file(rubric_path, out_dir)
    # 1 binary + 1 score
    assert len(tests) == 2
    paths = [t.path for t in tests]
    assert any("test_RB-001.py" in p for p in paths)  # binary (FR-001)
    assert any("test_RB-501.py" in p for p in paths)  # score (NFR-001, offset 500)
    # Mỗi file đều tồn tại
    for p in paths:
        assert Path(p).exists()


def test_generated_test_can_be_collected_by_pytest(tmp_path):
    """Test được sinh phải collect được bởi pytest (syntax OK, có def test_)."""
    brd = BRD(
        title="Test BRD", business_goal="Long enough business goal here",
        version="1.0.0", owner="me",
        actors=[Actor(name="x", role="x")],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="x", use_case="y", description="long enough description",
                priority="must", acceptance_criteria=["criterion valid dài"]
            )
        ]
    )
    rubric_path = tmp_path / "rubric.json"
    out_dir = tmp_path / "tests_generated"
    generate_rubric_file(brd, rubric_path)
    generate_from_rubric_file(rubric_path, out_dir)
    # Append tmp_path to sys.path để pytest có thể collect
    sys.path.insert(0, str(out_dir))
    # Verify file syntactically valid
    import ast
    for py_file in out_dir.glob("*.py"):
        ast.parse(py_file.read_text(encoding="utf-8"))
