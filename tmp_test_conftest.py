#!/usr/bin/env python3
"""Test loading conftest.py via various methods."""
import importlib.util
import traceback
import sys

# Method 1: importlib
print("Method 1: importlib.util.spec_from_file_location")
try:
    spec = importlib.util.spec_from_file_location('conftest_test', 'tests/conftest.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("  OK")
except Exception as e:
    print(f"  Error: {type(e).__name__}: {e}")
    traceback.print_exc()

# Method 2: Check file encoding
print("\nMethod 2: Check file encoding")
import codecs
try:
    with codecs.open('tests/conftest.py', 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"  Content length: {len(content)}")
    print(f"  Has null: {'\\x00' in content}")
except Exception as e:
    print(f"  Error: {e}")

# Method 3: tokenize
print("\nMethod 3: tokenize.open")
try:
    import tokenize
    with open('tests/conftest.py', 'rb') as f:
        tokens = list(tokenize.tokenize(f.readline))
    print(f"  Tokens: {len(tokens)}")
except Exception as e:
    print(f"  Error: {e}")

# Method 4: read as bytes and check
print("\nMethod 4: Direct byte read")
with open('tests/conftest.py', 'rb') as f:
    raw = f.read()
print(f"  Raw length: {len(raw)}")
print(f"  Has null byte: {0 in raw}")
if 0 in raw:
    positions = [i for i, b in enumerate(raw) if b == 0]
    print(f"  Null positions: {positions[:10]}")

# Method 5: pytest's own loading
print("\nMethod 5: pytest._compat.import_path")
try:
    import pytest
    print(f"  pytest version: {pytest.__version__}")
    # Check if pytest can read the file
    from pathlib import Path
    p = Path('tests/conftest.py')
    print(f"  Path exists: {p.exists()}")
    print(f"  File size: {p.stat().st_size}")
except Exception as e:
    print(f"  Error: {e}")
    traceback.print_exc()

print("\nDone.")
