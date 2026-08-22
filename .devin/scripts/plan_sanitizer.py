#!/usr/bin/env python3
"""plan_sanitizer.py — Multi-layer plan content sanitization.

V10 fix: Plan content có thể chứa prompt injection (shell commands, env var
expansion, path traversal). Regex-only sanitizer dễ bị bypass. Module này
dùng 3 layers:

  Layer 1: Regex scan — detect shell commands, env var expansion, path traversal
  Layer 2: AST parse — detect dangerous patterns in code blocks
  Layer 3: LLM-as-judge (optional) — semantic check

Strip/quarantine suspicious content → tag sanitized.
"""
from __future__ import annotations

import ast
import re
from typing import Any

# Layer 1 patterns
SHELL_PATTERNS = [
    (r"\$\{[A-Z_]+\}", "env_var_expansion"),
    (r"\$\([^\)]+\)", "command_substitution"),
    # Pentest V10 fix: backtick execution — không match markdown code fences (```...```)
    # Chỉ match single backtick `command`, không match triple backtick ```code```
    (r"(?<!`)`([^`\n]+)`(?!`)", "backtick_execution"),
    (r"\brm\s+-rf\b", "rm_rf"),
    (r"\bcurl\s+[^\|]*\|\s*sh", "curl_pipe_sh"),
    (r"\bwget\s+[^\|]*\|\s*sh", "wget_pipe_sh"),
    (r"\beval\s+", "eval"),
    (r"\bexec\s+", "exec"),
    (r"\bchmod\s+\d{3,4}", "chmod"),
    (r"\bchown\s+", "chown"),
    (r"\bsudo\s+", "sudo"),
    (r"\.\./\.\./", "path_traversal"),
    (r"\b__import__\s*\(", "python_import"),
    (r"\bos\.system\s*\(", "os_system"),
    (r"\bsubprocess\.(call|run|Popen)\s*\(", "subprocess"),
    (r"\bopen\s*\([^)]*['\"]w", "file_write"),
]

# Layer 2 AST dangerous nodes
DANGEROUS_AST_NODES = {
    "os.system", "subprocess.call", "subprocess.run", "subprocess.Popen",
    "subprocess.check_output", "eval", "exec", "compile",
    "__import__", "pickle.loads", "marshal.loads",
}


def _regex_scan(text: str) -> list[dict]:
    """Layer 1: Regex scan cho dangerous patterns."""
    findings = []
    for pattern, name in SHELL_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            findings.append({
                "layer": 1,
                "type": name,
                "match": match.group(),
                "position": match.start(),
            })
    return findings


def _ast_parse(text: str) -> list[dict]:
    """Layer 2: AST parse cho code blocks — detect dangerous calls."""
    findings = []
    # Extract code blocks
    code_blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    for i, code in enumerate(code_blocks):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Get function name
                    func = node.func
                    if isinstance(func, ast.Attribute):
                        mod = func.value
                        mod_name = mod.id if isinstance(mod, ast.Name) else ""
                        call_name = f"{mod_name}.{func.attr}" if mod_name else func.attr
                    elif isinstance(func, ast.Name):
                        call_name = func.id
                    else:
                        continue
                    if call_name in DANGEROUS_AST_NODES:
                        findings.append({
                            "layer": 2,
                            "type": f"ast_dangerous_call:{call_name}",
                            "match": call_name,
                            "code_block": i,
                            "lineno": node.lineno,
                        })
        except SyntaxError:
            pass  # Not valid Python, skip
    return findings


def _llm_judge(text: str) -> list[dict]:
    """Layer 3: LLM-as-judge (optional) — semantic check.

    Placeholder: trong production, gọi LLM API để check semantic injection.
    Hiện tại trả empty list (không có LLM available trong test env).
    """
    return []


def sanitize(text: str, aggressive: bool = False) -> dict:
    """Sanitize plan content qua 3 layers.

    Returns:
        {
            "sanitized": str,       # text đã sanitize
            "findings": list[dict], # tất cả findings
            "quarantined": list,    # content bị strip
            "sanitized_tag": bool,  # True nếu có thay đổi
        }
    """
    findings = _regex_scan(text) + _ast_parse(text) + _llm_judge(text)

    sanitized = text
    quarantined = []

    # Strip dangerous patterns (Layer 1)
    for pattern, name in SHELL_PATTERNS:
        matches = list(re.finditer(pattern, sanitized, re.IGNORECASE))
        for m in reversed(matches):  # reverse để không shift positions
            # Pentest V10 fix: backtick pattern có group — strip toàn bộ match (group 0)
            quarantined.append({
                "type": name,
                "content": m.group(),
                "position": m.start(),
            })
            sanitized = sanitized[:m.start()] + "[QUARANTINED:" + name + "]" + sanitized[m.end():]

    # Strip dangerous AST calls (Layer 2) — replace trong code blocks
    for finding in findings:
        if finding["layer"] == 2:
            call_name = finding["match"]
            # Replace dangerous call names
            sanitized = sanitized.replace(call_name, f"[QUARANTINED:{call_name}]")

    sanitized_tag = len(findings) > 0

    return {
        "sanitized": sanitized,
        "findings": findings,
        "quarantined": quarantined,
        "sanitized_tag": sanitized_tag,
    }


if __name__ == "__main__":
    test = "Run `rm -rf /tmp/*` and ${HOME}/.ssh"
    result = sanitize(test)
    print(f"Findings: {len(result['findings'])}")
    print(f"Sanitized: {result['sanitized']}")
