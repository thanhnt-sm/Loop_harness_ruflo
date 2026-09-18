import os
import pytest
from HLK.chain.audit.path_validator import is_safe_path

def test_safe_path_inside_root(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    target = root / "file.txt"
    target.write_text("hello")
    
    assert is_safe_path(str(target), [str(root)]) == True

def test_safe_path_outside_root(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("hello")
    
    assert is_safe_path(str(outside), [str(root)]) == False

def test_symlink_escaping_root(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    
    symlink = root / "link.txt"
    os.symlink(str(outside), str(symlink))
    
    assert is_safe_path(str(symlink), [str(root)]) == False

def test_symlink_inside_root(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    
    inside = root / "regular.txt"
    inside.write_text("regular")
    
    symlink = root / "link.txt"
    os.symlink(str(inside), str(symlink))
    
    assert is_safe_path(str(symlink), [str(root)]) == True

def test_directory_traversal(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    
    target = root / ".." / "secret.txt"
    
    assert is_safe_path(str(target), [str(root)]) == False

def test_nonexistent_file(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    
    target = root / "missing.txt"
    
    assert is_safe_path(str(target), [str(root)]) == True

def test_nonexistent_escaping_file(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    
    target = root / ".." / "missing.txt"
    
    assert is_safe_path(str(target), [str(root)]) == False
