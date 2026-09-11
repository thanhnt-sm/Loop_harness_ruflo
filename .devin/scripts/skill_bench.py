"""DEPRECATED: moved to HLK/chain/skill_bench — canonical source.
This file is a thin re-export shim for backward compat (explicit imports, no wildcard). Edit HLK/chain/skill_bench.py instead."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from HLK.chain.skill_bench import (BenchResult, DEFAULT_PARALLEL, DEFAULT_SCENARIOS_PER_SKILL,
    _generate_scenarios_from_skill, bench_skills, render_bench_report, _parse_skill_frontmatter)  # noqa: F401
