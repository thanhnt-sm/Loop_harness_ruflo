#!/usr/bin/env python3
"""token_registry.py — Local Token Registry for Delegation Lifecycle (CHG-001).

Provides in-memory + file-backed token registry with:
- Token issuance with expiry, scope, audience, revocation_source
- Revocation list checking (per V5 REVOCATION_BOUND)
- Hook integration for pre-tool-use validation
- File-backed persistence for cross-session survival
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8
import sys
for _stream in (sys.stdout, sys.stderr):
    try:
        if getattr(_stream, "encoding", "") and _stream.encoding.lower() not in ("utf-8", "utf8"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


class TokenRegistry:
    """Local token registry with revocation support."""

    def __init__(self, root: Path):
        self.root = root
        self.registry_path = root / ".devin" / "token_registry.json"
        self.revocation_path = root / ".devin" / "revocation_list.json"
        self._tokens: Dict[str, Dict] = {}
        self._revoked: set = set()
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        try:
            if self.registry_path.exists():
                self._tokens = json.loads(self.registry_path.read_text(encoding="utf-8"))
            if self.revocation_path.exists():
                self._revoked = set(json.loads(self.revocation_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            self._tokens = {}
            self._revoked = set()

    def _save(self) -> None:
        """Save registry to disk atomically."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.registry_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._tokens, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.registry_path)

        tmp2 = self.revocation_path.with_suffix(".tmp")
        tmp2.write_text(json.dumps(list(self._revoked), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp2.replace(self.revocation_path)

    def issue_token(
        self,
        subject: str,
        audience: str,
        scope: List[str],
        ttl_seconds: int = 3600,
        revocation_source: str = "manual",
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Issue a new delegation token."""
        token_id = str(uuid.uuid4())
        now = time.time()
        token = {
            "token_id": token_id,
            "subject": subject,
            "audience": audience,
            "scope": scope,
            "issued_at": now,
            "expires_at": now + ttl_seconds,
            "revocation_source": revocation_source,
            "metadata": metadata or {},
            "revoked": False,
        }
        self._tokens[token_id] = token
        self._save()
        return token

    def validate_token(self, token_id: str, required_scope: Optional[str] = None) -> Dict[str, Any]:
        """Validate token and check revocation. Returns validation result."""
        if token_id in self._revoked:
            return {"valid": False, "reason": "REVOKED", "token_id": token_id}

        token = self._tokens.get(token_id)
        if not token:
            return {"valid": False, "reason": "NOT_FOUND", "token_id": token_id}

        if time.time() > token["expires_at"]:
            return {"valid": False, "reason": "EXPIRED", "token_id": token_id}

        if required_scope and required_scope not in token["scope"]:
            return {"valid": False, "reason": "SCOPE_MISMATCH", "token_id": token_id, "required": required_scope, "has": token["scope"]}

        return {"valid": True, "token": token}

    def revoke_token(self, token_id: str, reason: str = "") -> bool:
        """Revoke a token by adding to revocation list."""
        if token_id in self._tokens:
            self._tokens[token_id]["revoked"] = True
        self._revoked.add(token_id)
        self._save()
        return True

    def check_revocation_bound(self, max_age_seconds: int = 300) -> Dict[str, Any]:
        """Check REVOCATION_BOUND - all high-risk permissions must be checked within bound."""
        now = time.time()
        stale_revoked = []
        for tid in self._revoked:
            token = self._tokens.get(tid)
            if token and (now - token.get("expires_at", now)) > max_age_seconds:
                stale_revoked.append(tid)

        return {
            "bound_ok": len(stale_revoked) == 0,
            "stale_revoked": stale_revoked,
            "total_revoked": len(self._revoked),
            "max_age_seconds": max_age_seconds,
        }

    def get_token(self, token_id: str) -> Optional[Dict]:
        return self._tokens.get(token_id)

    def list_tokens(self, subject: Optional[str] = None) -> List[Dict]:
        tokens = list(self._tokens.values())
        if subject:
            tokens = [t for t in tokens if t["subject"] == subject]
        return tokens


# Global registry instance (per-process)
_REGISTRY: Optional[TokenRegistry] = None


def get_registry(root: Path) -> TokenRegistry:
    """Get or create global registry instance."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = TokenRegistry(root)
    return _REGISTRY


def check_revocation_gate(data: dict) -> None:
    """Hook gate: Check token revocation for high-risk tool calls."""
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    session_id = data.get("session_id", "")

    if not session_id:
        return  # No session to check

    # High-risk tools that require token validation
    high_risk_tools = {"bash", "write", "edit", "notebook_edit", "task", "mcp__*"}

    is_high_risk = any(
        tool_name == hr or (hr.endswith("*") and tool_name.startswith(hr[:-1]))
        for hr in high_risk_tools
    )

    if not is_high_risk:
        return

    # Extract token from tool input or session
    token_id = tool_input.get("delegation_token") or data.get("delegation_token")
    if not token_id:
        # No token provided - allow but warn (fail-open for backward compat)
        print(
            f"[TOKEN REGISTRY] WARNING: High-risk tool '{tool_name}' called without delegation token.",
            file=sys.stderr,
        )
        return

    root = Path.cwd()
    for parent in [root] + list(root.parents):
        if (parent / ".devin").is_dir():
            root = parent
            break

    registry = get_registry(root)
    result = registry.validate_token(token_id, required_scope=tool_name)

    if not result["valid"]:
        print(
            f"[TOKEN REGISTRY] BLOCKED: Token validation failed for '{tool_name}': {result['reason']}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Check revocation bound periodically
    if int(time.time()) % 60 == 0:  # Every ~60 seconds
        bound = registry.check_revocation_bound()
        if not bound["bound_ok"]:
            print(
                f"[TOKEN REGISTRY] REVOCATION_BOUND VIOLATION: {bound['stale_revoked']}",
                file=sys.stderr,
            )


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Token Registry CLI")
    parser.add_argument("--root", default=".", help="Repo root")
    parser.add_argument("--issue", action="store_true", help="Issue new token")
    parser.add_argument("--subject", help="Token subject")
    parser.add_argument("--audience", help="Token audience")
    parser.add_argument("--scope", nargs="+", help="Token scopes")
    parser.add_argument("--ttl", type=int, default=3600, help="TTL seconds")
    parser.add_argument("--validate", help="Validate token ID")
    parser.add_argument("--revoke", help="Revoke token ID")
    parser.add_argument("--list", action="store_true", help="List tokens")
    parser.add_argument("--check-bound", action="store_true", help="Check revocation bound")

    args = parser.parse_args()
    root = Path(args.root).resolve()

    registry = get_registry(root)

    if args.issue:
        if not args.subject or not args.audience or not args.scope:
            print("Error: --issue requires --subject, --audience, --scope", file=sys.stderr)
            sys.exit(1)
        token = registry.issue_token(args.subject, args.audience, args.scope, args.ttl)
        print(f"Issued token: {token['token_id']}")
        print(f"Expires: {token['expires_at']}")

    elif args.validate:
        result = registry.validate_token(args.validate)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["valid"] else 1)

    elif args.revoke:
        registry.revoke_token(args.revoke)
        print(f"Revoked token: {args.revoke}")

    elif args.list:
        tokens = registry.list_tokens(args.subject)
        for t in tokens:
            print(f"{t['token_id']}: {t['subject']} -> {t['audience']} [{', '.join(t['scope'])}]")

    elif args.check_bound:
        result = registry.check_revocation_bound()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["bound_ok"] else 1)

    else:
        parser.print_help()