#!/usr/bin/env python3
"""skill_loader.py — Skill Loader with Trigger Validation (CHG-003).

Loads skill_index.json, validates triggers against schema,
and enforces core/dynamic namespace separation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure UTF-8
for _stream in (sys.stdout, sys.stderr):
    try:
        if getattr(_stream, "encoding", "") and _stream.encoding.lower() not in ("utf-8", "utf8"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass


class SkillLoadError(Exception):
    """Skill loading error with details."""
    def __init__(self, skill_id: str, message: str):
        self.skill_id = skill_id
        self.message = message
        super().__init__(f"Skill '{skill_id}': {message}")


class SkillLoader:
    """Loads and validates skills from skill_index.json."""

    def __init__(self, root: Path):
        self.root = root
        self.index_path = root / ".devin" / "skills" / "skill_index.json"
        self._index: Optional[Dict] = None

    def load_index(self) -> Dict:
        """Load and cache skill index."""
        if self._index is None:
            if not self.index_path.exists():
                raise FileNotFoundError(f"Skill index not found: {self.index_path}")
            self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
        return self._index

    def validate_trigger(self, trigger: str, schema: Dict) -> List[str]:
        """Validate a single trigger against schema. Returns list of errors."""
        errors = []
        pattern = schema.get("pattern", "^[a-z][a-z0-9-]*$")
        max_length = schema.get("max_length", 64)

        if not isinstance(trigger, str):
            errors.append(f"Trigger must be string, got {type(trigger).__name__}")
            return errors

        if len(trigger) > max_length:
            errors.append(f"Trigger exceeds max length {max_length}: '{trigger}'")

        if not re.match(pattern, trigger):
            errors.append(f"Trigger violates pattern {pattern}: '{trigger}'")

        return errors

    def validate_skill(self, skill_id: str, skill: Dict, schema: Dict) -> List[str]:
        """Validate a single skill entry. Returns list of errors."""
        errors = []

        # Check required fields
        required = ["path", "triggers", "executor", "description", "size_kb", "priority"]
        for field in required:
            if field not in skill:
                errors.append(f"Missing required field: {field}")

        # Validate triggers
        triggers = skill.get("triggers", [])
        if not isinstance(triggers, list):
            errors.append("triggers must be a list")
        else:
            for trigger in triggers:
                errors.extend(self.validate_trigger(trigger, schema))

        # Validate namespace
        namespace = skill.get("namespace")
        namespaces = self._index.get("namespaces", {}) if self._index else {}
        valid_namespaces = list(namespaces.keys())
        if namespace and namespace not in valid_namespaces:
            errors.append(f"Invalid namespace '{namespace}', valid: {valid_namespaces}")

        # Validate path exists (for non-built-in skills)
        path = skill.get("path", "")
        if path and path != "built-in":
            skill_path = self.root / path
            if not skill_path.exists():
                errors.append(f"Skill file not found: {skill_path}")

        return errors

    def load_and_validate(self) -> Dict[str, List[str]]:
        """Load index and validate all skills. Returns {skill_id: [errors]}."""
        index = self.load_index()
        self._index = index

        schema = index.get("trigger_schema", {
            "pattern": "^[a-z][a-z0-9-]*$",
            "max_length": 64,
        })

        results = {}
        for skill_id, skill in index.get("skills", {}).items():
            errors = self.validate_skill(skill_id, skill, schema)
            if errors:
                results[skill_id] = errors

        return results

    def get_skills_by_namespace(self, namespace: str) -> Dict:
        """Get all skills in a specific namespace."""
        index = self.load_index()
        return {
            sid: skill for sid, skill in index.get("skills", {}).items()
            if skill.get("namespace") == namespace
        }

    def get_core_skills(self) -> Dict:
        return self.get_skills_by_namespace("core")

    def get_dynamic_skills(self) -> Dict:
        return self.get_skills_by_namespace("dynamic")

    def get_skill(self, skill_id: str) -> Optional[Dict]:
        index = self.load_index()
        return index.get("skills", {}).get(skill_id)

    def get_trigger_schema(self) -> Dict:
        index = self.load_index()
        return index.get("trigger_schema", {})

    def get_namespaces(self) -> Dict:
        index = self.load_index()
        return index.get("namespaces", {})


def load_skill(skill_id: str, root: Optional[Path] = None) -> str:
    """Load full skill body by ID. Returns skill markdown content."""
    if root is None:
        root = Path.cwd()
        for parent in [root] + list(root.parents):
            if (parent / ".devin").is_dir():
                root = parent
                break

    loader = SkillLoader(root)
    skill = loader.get_skill(skill_id)
    if not skill:
        raise SkillLoadError(skill_id, "Skill not found in index")

    path = skill.get("path", "")
    if path == "built-in":
        return f"# {skill_id}\n\nBuilt-in skill - no file to load."

    skill_path = root / path
    if not skill_path.exists():
        raise SkillLoadError(skill_id, f"Skill file not found: {skill_path}")

    return skill_path.read_text(encoding="utf-8")


def validate_all_skills(root: Optional[Path] = None) -> int:
    """Validate all skills. Returns 0 on success, 1 on validation errors."""
    if root is None:
        root = Path.cwd()
        for parent in [root] + list(root.parents):
            if (parent / ".devin").is_dir():
                root = parent
                break

    loader = SkillLoader(root)
    try:
        errors = loader.load_and_validate()
    except Exception as e:
        print(f"FAIL: Failed to load index: {e}", file=sys.stderr)
        return 1

    if errors:
        print("SKILL VALIDATION FAILED:", file=sys.stderr)
        for skill_id, errs in errors.items():
            for err in errs:
                print(f"  {skill_id}: {err}", file=sys.stderr)
        return 1

    print("SUCCESS: All skills validated")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Skill Loader with Validation")
    parser.add_argument("--validate", action="store_true", help="Validate all skills")
    parser.add_argument("--load", help="Load skill by ID")
    parser.add_argument("--root", default=".", help="Repo root")
    parser.add_argument("--namespace", help="List skills by namespace")

    args = parser.parse_args()
    root = Path(args.root).resolve()

    if args.validate:
        sys.exit(validate_all_skills(root))

    if args.load:
        try:
            content = load_skill(args.load, root)
            print(content)
        except SkillLoadError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    if args.namespace:
        root = Path(args.root).resolve()
        loader = SkillLoader(root)
        skills = loader.get_skills_by_namespace(args.namespace)
        for sid, skill in skills.items():
            print(f"{sid}: {skill['description'][:60]}...")

    parser.print_help()