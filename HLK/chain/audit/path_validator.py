import os
from pathlib import Path

def is_safe_path(target_path: str, allowed_roots: list[str]) -> bool:
    """
    Validates that a path is safe to access (not a symlink escaping bounds, etc).
    Must use os.path.realpath() and os.lstat().
    Explicitly rejects symlinks escaping allowed_roots.
    """
    if not target_path or not allowed_roots:
        return False
    
    # Check if target is a symlink using lstat
    try:
        stat_info = os.lstat(target_path)
        is_symlink = stat_info.st_mode & 0o170000 == 0o120000
    except FileNotFoundError:
        # If the file doesn't exist, we can't lstat it. We still need to check if the 
        # resolved path would be safe if it were created.
        pass

    real_path = os.path.realpath(target_path)
    
    for root in allowed_roots:
        real_root = os.path.realpath(root)
        
        # Check if the real_path starts with the real_root
        if real_path == real_root or real_path.startswith(real_root + os.sep):
            return True
            
    return False
