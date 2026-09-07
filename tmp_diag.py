#!/usr/bin/env python3
"""Quick diagnostic for conftest.py issue."""
import sys

# Read raw bytes
with open('tests/conftest.py', 'rb') as f:
    data = f.read()

print(f'file size: {len(data)}')
print(f'has null bytes: {b"\\x00" in data}')
print(f'first 10 bytes: {list(data[:10])}')
print(f'last 10 bytes: {list(data[-10:])}')

# Try compiling
try:
    code = compile(data, 'tests/conftest.py', 'exec')
    print('compile: OK')
except SyntaxError as e:
    print(f'compile error: {e}')

# Try importing pytest conftest loading
try:
    import py_compile
    py_compile.compile('tests/conftest.py', doraise=True)
    print('py_compile: OK')
except py_compile.PyCompileError as e:
    print(f'py_compile error: {e}')
