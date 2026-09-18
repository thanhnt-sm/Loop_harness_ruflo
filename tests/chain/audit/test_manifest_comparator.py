import pytest
import os
from HLK.chain.audit.manifest_comparator import generate_fingerprint, generate_file_fingerprint

def test_generate_fingerprint_crlf_normalization():
    content_lf = "line1\\nline2\\nline3"
    content_crlf = "line1\\r\\nline2\\r\\nline3"
    
    hash_lf = generate_fingerprint(content_lf)
    hash_crlf = generate_fingerprint(content_crlf)
    
    assert hash_lf == hash_crlf
    assert len(hash_lf) == 64  # SHA-256 is 64 hex characters

def test_generate_file_fingerprint(tmp_path):
    # Test with LF
    file_lf = tmp_path / "lf.txt"
    with open(file_lf, 'wb') as f:
        f.write(b"line1\\nline2\\nline3")
        
    # Test with CRLF
    file_crlf = tmp_path / "crlf.txt"
    with open(file_crlf, 'wb') as f:
        f.write(b"line1\\r\\nline2\\r\\nline3")
        
    hash_lf = generate_file_fingerprint(str(file_lf))
    hash_crlf = generate_file_fingerprint(str(file_crlf))
    
    assert hash_lf == hash_crlf

def test_generate_file_fingerprint_missing():
    with pytest.raises(FileNotFoundError):
        generate_file_fingerprint("nonexistent_file_xyz.txt")

from HLK.chain.audit.manifest_comparator import compare_manifests, verify_integrity_hash

def test_compare_manifests():
    base = {'a': '1', 'b': '2', 'c': '3', 'd': '4'}
    old = {'a': '1', 'b': '22', 'c': '3', 'e': '5', 'f': '6'} # b changed, d removed, e added, f added
    new = {'a': '11', 'b': '2', 'c': '3', 'e': '5', 'g': '7'} # a changed, d removed, e added, g added
    
    # Conflict: f added in old, missing in new (not in base)
    # Wait, 'f' is added in old, unchanged (missing) in new. So it should be added.
    
    # Let's test specific scenarios:
    base2 = {'unchanged': '1', 'changed_old': '2', 'changed_new': '3', 'changed_both_same': '4', 'conflict_diff': '5', 'removed_old': '6', 'removed_new': '7', 'removed_both': '8', 'conflict_remove_change': '9'}
    old2 = {'unchanged': '1', 'changed_old': '22', 'changed_new': '3', 'changed_both_same': '44', 'conflict_diff': '55', 'removed_new': '7', 'conflict_remove_change': '99', 'added_old': 'A', 'added_both_same': 'C', 'added_conflict': 'D1'}
    new2 = {'unchanged': '1', 'changed_old': '2', 'changed_new': '33', 'changed_both_same': '44', 'conflict_diff': '555', 'removed_old': '6', 'conflict_remove_change': '9', 'added_new': 'B', 'added_both_same': 'C', 'added_conflict': 'D2'}
    
    # Adjusting new2 for conflict_remove_change: old changes to 99, new removes it
    del new2['conflict_remove_change']
    
    res = compare_manifests(old2, new2, base2)
    
    assert res['added'] == {'added_old': 'A', 'added_new': 'B', 'added_both_same': 'C'}
    assert res['removed'] == {'removed_old': '6', 'removed_new': '7', 'removed_both': '8'}
    assert res['changed'] == {'changed_old': '22', 'changed_new': '33', 'changed_both_same': '44'}
    assert res['conflicts'] == {
        'conflict_diff': {'base': '5', 'old': '55', 'new': '555'},
        'conflict_remove_change': {'base': '9', 'old': '99', 'new': None},
        'added_conflict': {'base': None, 'old': 'D1', 'new': 'D2'}
    }

def test_verify_integrity_hash(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text("hello world")
    
    import hashlib
    expected = hashlib.sha256(b"hello world").hexdigest()
    
    assert verify_integrity_hash(str(file_path), expected) is True
    assert verify_integrity_hash(str(file_path), "wronghash") is False
