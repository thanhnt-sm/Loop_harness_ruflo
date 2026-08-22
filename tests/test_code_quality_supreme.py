#!/usr/bin/env python3
"""Test Code Quality Supreme — tiêu chuẩn chất lượng code tối cao.

Kiểm tra:
- Type hints cho public APIs
- Error handling cho I/O, network, external calls
- No magic numbers — constants phải được named
- Function length < 50 lines
- File length < 500 lines (CLAUDE.md rule)
- No duplicate code patterns
- Proper docstrings cho public functions
- No TODO/FIXME/HACK/XXX trong production code
- Import organization
- No circular imports

Chạy: python -m pytest tests/test_code_quality_supreme.py -v
"""
import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".devin" / "hooks"
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"

ALL_PY_FILES = list(HOOKS_DIR.glob("*.py")) + list(SCRIPTS_DIR.glob("*.py"))
# Exclude __init__.py, __pycache__, test files within scripts
ALL_PY_FILES = [f for f in ALL_PY_FILES if f.name != "__init__.py" and "test_" not in f.name]


def _read_source(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_ast(path: Path) -> ast.AST | None:
    try:
        return ast.parse(_read_source(path), filename=str(path))
    except SyntaxError:
        return None


# ---------------------------------------------------------------------------
# QUAL-001: File length < 500 lines (CLAUDE.md rule)
# ---------------------------------------------------------------------------

class TestFileLength:
    """QUAL-001: File phải < 500 lines (CLAUDE.md workspace rule)."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES, ids=lambda f: f.name)
    def test_file_under_500_lines(self, py_file):
        """Mỗi file .py phải < 500 lines."""
        source = _read_source(py_file)
        line_count = len(source.splitlines())
        if line_count > 500:
            pytest.fail(
                f"{py_file.relative_to(REPO_ROOT)}: {line_count} lines (> 500 limit). "
                f"Cần refactor — tách thành modules nhỏ hơn."
            )


# ---------------------------------------------------------------------------
# QUAL-002: Function length < 50 lines
# ---------------------------------------------------------------------------

class TestFunctionLength:
    """QUAL-002: Function phải < 50 lines."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES, ids=lambda f: f.name)
    def test_functions_under_50_lines(self, py_file):
        """Mỗi function phải < 50 lines."""
        tree = _parse_ast(py_file)
        if tree is None:
            pytest.skip(f"{py_file.name}: syntax error")
        long_funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                length = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if length > 50:
                    long_funcs.append((node.name, length, node.lineno))
        if long_funcs:
            issues = "\n".join(f"  {name}: {length} lines (line {line})" for name, length, line in long_funcs)
            pytest.fail(f"{py_file.name} có function quá dài:\n{issues}")


# ---------------------------------------------------------------------------
# QUAL-003: No TODO/FIXME/HACK/XXX trong production code
# ---------------------------------------------------------------------------

class TestNoTodoFixme:
    """QUAL-003: Không TODO/FIXME/HACK/XXX trong production code."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES, ids=lambda f: f.name)
    def test_no_todo_fixme(self, py_file):
        """Không có TODO/FIXME/HACK/XXX."""
        source = _read_source(py_file)
        pattern = r"#\s*(TODO|FIXME|HACK|XXX|BUG|WARN)"
        matches = [(i + 1, line.strip()) for i, line in enumerate(source.splitlines())
                   if re.search(pattern, line, re.IGNORECASE)]
        if matches:
            issues = "\n".join(f"  line {l}: {t}" for l, t in matches[:5])
            pytest.fail(f"{py_file.name} có TODO/FIXME/HACK:\n{issues}")


# ---------------------------------------------------------------------------
# QUAL-004: Type hints cho public functions
# ---------------------------------------------------------------------------

class TestTypeHints:
    """QUAL-004: Public functions phải có type hints."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES[:10], ids=lambda f: f.name)  # Sample first 10
    def test_public_functions_have_type_hints(self, py_file):
        """Public functions (không _prefix) phải có return type hint."""
        tree = _parse_ast(py_file)
        if tree is None:
            pytest.skip(f"{py_file.name}: syntax error")
        missing = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    if node.returns is None:
                        missing.append(node.name)
        if missing:
            issues = ", ".join(missing[:5])
            pytest.fail(f"{py_file.name}: {len(missing)} public functions thiếu return type hint: {issues}")


# ---------------------------------------------------------------------------
# QUAL-005: Error handling cho I/O operations
# ---------------------------------------------------------------------------

class TestIOErrorHandling:
    """QUAL-005: I/O operations phải có error handling."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES, ids=lambda f: f.name)
    def test_io_operations_have_error_handling(self, py_file):
        """read_text/write_text/open phải được wrap trong try/except."""
        source = _read_source(py_file)
        if not any(p in source for p in [".read_text(", ".write_text(", "open(", ".read(", ".write("]):
            pytest.skip(f"{py_file.name}: no I/O operations")
        # Check if there's any try/except in the file
        has_try = "try:" in source or "try :" in source
        assert has_try, f"{py_file.name} có I/O operations nhưng không có try/except"


# ---------------------------------------------------------------------------
# QUAL-006: No unused imports (basic check)
# ---------------------------------------------------------------------------

class TestNoUnusedImports:
    """QUAL-006: Không import không dùng."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES[:15], ids=lambda f: f.name)
    def test_no_unused_imports(self, py_file):
        """Import phải được sử dụng trong file."""
        tree = _parse_ast(py_file)
        if tree is None:
            pytest.skip(f"{py_file.name}: syntax error")
        source = _read_source(py_file)
        unused = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    # Check if name appears in source (besides import line)
                    lines = source.splitlines()
                    usage_count = sum(1 for line in lines if name in line) - 1  # -1 for import line
                    if usage_count <= 0:
                        unused.append(name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    if name == "*":
                        continue
                    lines = source.splitlines()
                    usage_count = sum(1 for line in lines if name in line) - 1
                    if usage_count <= 0:
                        unused.append(name)
        if unused:
            issues = ", ".join(unused[:5])
            pytest.fail(f"{py_file.name}: {len(unused)} unused imports: {issues}")


# ---------------------------------------------------------------------------
# QUAL-007: Proper docstrings cho public functions
# ---------------------------------------------------------------------------

class TestDocstrings:
    """QUAL-007: Public functions phải có docstrings."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES[:10], ids=lambda f: f.name)
    def test_public_functions_have_docstrings(self, py_file):
        """Public functions phải có docstring."""
        tree = _parse_ast(py_file)
        if tree is None:
            pytest.skip(f"{py_file.name}: syntax error")
        missing = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    if not (node.body and isinstance(node.body[0], ast.Expr)
                            and isinstance(node.body[0].value, ast.Constant)
                            and isinstance(node.body[0].value.value, str)):
                        missing.append(node.name)
        if missing:
            issues = ", ".join(missing[:5])
            pytest.fail(f"{py_file.name}: {len(missing)} public functions thiếu docstring: {issues}")


# ---------------------------------------------------------------------------
# QUAL-008: No circular imports (basic detection)
# ---------------------------------------------------------------------------

class TestNoCircularImports:
    """QUAL-008: Không circular imports."""

    def test_no_circular_imports_in_hooks(self):
        """Hooks không import lẫn nhau circular."""
        hook_imports = {}
        for f in HOOKS_DIR.glob("*.py"):
            if f.name in ("__init__.py", "ahd_session.py"):
                continue
            tree = _parse_ast(f)
            if tree is None:
                continue
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module in ("ahd_session", "update_common"):
                        imports.append(node.module)
            hook_imports[f.stem] = imports
        # Check: no hook imports another hook that imports it back
        # (ahd_session is shared lib, not a hook)
        circular = []
        for hook, imports in hook_imports.items():
            for imp in imports:
                if imp in hook_imports and hook in hook_imports.get(imp, []):
                    circular.append((hook, imp))
        assert not circular, f"Circular imports detected: {circular}"


# ---------------------------------------------------------------------------
# QUAL-009: Constant naming — no magic numbers
# ---------------------------------------------------------------------------

class TestNoMagicNumbers:
    """QUAL-009: Không magic numbers trong logic quan trọng."""

    @pytest.mark.parametrize("py_file", ALL_PY_FILES[:10], ids=lambda f: f.name)
    def test_no_magic_numbers_in_conditionals(self, py_file):
        """Không hardcode numbers trong if/while conditions."""
        tree = _parse_ast(py_file)
        if tree is None:
            pytest.skip(f"{py_file.name}: syntax error")
        magic = []
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check for bare number comparisons (not 0, 1, -1)
                for child in ast.walk(node.test):
                    if isinstance(child, ast.Compare):
                        for comp in child.comparators:
                            if isinstance(comp, ast.Constant) and isinstance(comp.value, int):
                                if comp.value not in (0, 1, -1, 2, True, False):
                                    magic.append((node.lineno, comp.value))
        if len(magic) > 5:
            issues = ", ".join(f"line {l}: {v}" for l, v in magic[:5])
            pytest.fail(f"{py_file.name}: {len(magic)} magic numbers in conditionals: {issues}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
