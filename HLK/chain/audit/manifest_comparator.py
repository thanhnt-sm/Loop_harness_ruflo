import hashlib
import os

def generate_fingerprint(content: str) -> str:
    """
    Computes a SHA-256 hex hash of the content.
    Normalizes CRLF to LF before hashing to ensure consistency across platforms.
    """
    normalized_content = content.replace('\\r\\n', '\\n')
    return hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()

def generate_file_fingerprint(filepath: str) -> str:
    """
    Computes the fingerprint of a file's content.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    return generate_fingerprint(content)

def compare_manifests(old: dict, new: dict, base: dict) -> dict:
    """
    Performs a three-way merge logic on manifests.
    Returns a struct distinguishing 'added', 'removed', 'changed', and 'conflicts'.
    """
    result = {'added': {}, 'removed': {}, 'changed': {}, 'conflicts': {}}
    
    all_keys = set(old.keys()) | set(new.keys()) | set(base.keys())
    
    for key in all_keys:
        in_base = key in base
        base_val = base.get(key)
        old_val = old.get(key)
        new_val = new.get(key)
        
        # Unchanged in both
        if old_val == base_val and new_val == base_val:
            if in_base and key not in old and key not in new:
                result['removed'][key] = base_val
            continue
            
        # Changed in old, unchanged in new
        if old_val != base_val and new_val == base_val:
            if key not in old:
                result['removed'][key] = base_val
            elif not in_base:
                result['added'][key] = old_val
            else:
                result['changed'][key] = old_val
            continue
            
        # Changed in new, unchanged in old
        if new_val != base_val and old_val == base_val:
            if key not in new:
                result['removed'][key] = base_val
            elif not in_base:
                result['added'][key] = new_val
            else:
                result['changed'][key] = new_val
            continue
            
        # Changed in both
        if old_val == new_val:
            if key not in old:
                result['removed'][key] = base_val
            elif not in_base:
                result['added'][key] = old_val
            else:
                result['changed'][key] = old_val
        else:
            result['conflicts'][key] = {'base': base_val, 'old': old_val, 'new': new_val}
            
    return result

def verify_integrity_hash(manifest_path: str, expected_hash: str) -> bool:
    """
    Verifies if the file's hash matches the expected hash.
    """
    actual_hash = generate_file_fingerprint(manifest_path)
    return actual_hash == expected_hash
