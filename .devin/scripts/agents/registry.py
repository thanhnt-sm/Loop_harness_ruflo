#!/usr/bin/env python3
"""Agent Registry — Dynamic agent discovery and capability matching.

Replaces hardcoded missions with a capability-based agent registry.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("agent_registry")


class AgentCapability(BaseModel):
    """Describes an agent's capabilities and metadata."""
    model_config = ConfigDict(frozen=True)

    id: str
    version: str
    capabilities: list[str] = Field(default_factory=list)
    model: str = "auto"
    cost_per_token: float = 0.0
    tools: list[str] = Field(default_factory=list)
    max_parallel: int = 1
    description: str = ""


class AgentRegistry:
    """Registry for agent capabilities with dynamic team formation."""

    def __init__(self, definitions_dir: Path, manifest_path: Path | None = None):
        self.definitions_dir = definitions_dir
        self.manifest_path = manifest_path or definitions_dir / "manifest.yaml"
        self._agents: dict[str, AgentCapability] = {}
        self._manifest: dict = {}
        self._loaded = False

    async def load(self) -> None:
        """Load agent definitions from YAML files."""
        if self._loaded:
            return

        # Load manifest
        if self.manifest_path.exists():
            with open(self.manifest_path, "r") as f:
                self._manifest = yaml.safe_load(f) or {}

        # Load agent definitions
        for agent_file in self.definitions_dir.glob("*.yaml"):
            if agent_file.name == "manifest.yaml":
                continue
            await self._load_agent_file(agent_file)

        for subdir in ["executor"]:
            subdir_path = self.definitions_dir / subdir
            if subdir_path.exists():
                for agent_file in subdir_path.glob("*.yaml"):
                    await self._load_agent_file(agent_file)

        self._loaded = True
        logger.info(f"Loaded {len(self._agents)} agent definitions")

    async def _load_agent_file(self, agent_file: Path) -> None:
        """Load a single agent definition from YAML file."""
        try:
            with open(agent_file, "r") as f:
                data = yaml.safe_load(f)

            if not data or "id" not in data:
                logger.warning(f"Invalid agent definition: {agent_file}")
                return

            capability = AgentCapability(**data)
            self._agents[capability.id] = capability
            logger.debug(f"Loaded agent: {capability.id}")
        except Exception as e:
            logger.warning(f"Failed to load agent {agent_file}: {e}")

    def get_agent(self, agent_id: str) -> Optional[AgentCapability]:
        """Get agent capability by ID."""
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentCapability]:
        """List all registered agents."""
        return list(self._agents.values())

    def match(
        self,
        required_capabilities: list[str],
        max_cost_per_token: float | None = None,
        prefer_streaming: bool = True,
        max_parallel: int | None = None,
    ) -> list[AgentCapability]:
        """Find agents matching required capabilities."""
        if not self._loaded:
            raise RuntimeError("Registry not loaded. Call load() first.")

        candidates = []
        for agent in self._agents.values():
            # Check capabilities
            if not all(cap in agent.capabilities for cap in required_capabilities):
                continue
            # Check cost
            if max_cost_per_token is not None:
                total_cost = agent.cost_per_token
                if total_cost > max_cost_per_token:
                    continue
            # Check parallelism
            if max_parallel is not None and agent.max_parallel > max_parallel:
                continue
            candidates.append((agent.cost_per_token, agent))

        # Sort by cost (cheapest first)
        candidates.sort(key=lambda x: x[0])
        return [agent for _, agent in candidates]

    def match_single(
        self,
        required_capabilities: list[str],
        max_cost_per_token: float | None = None,
    ) -> Optional[AgentCapability]:
        """Select single best agent for requirements."""
        matches = self.match(required_capabilities, max_cost_per_token)
        return matches[0] if matches else None

    def form_team(
        self,
        task_requirements: dict[str, list[str]],
        max_cost_per_token: float | None = None,
    ) -> dict[str, AgentCapability]:
        """Form a team from task requirements.

        Args:
            task_requirements: Dict of role -> required capabilities
            max_cost_per_token: Max cost per token for the team

        Returns:
            Dict of role -> matched agent
        """
        team = {}
        for role, capabilities in task_requirements.items():
            agent = self.match_single(capabilities, max_cost_per_token)
            if agent:
                team[role] = agent
            else:
                logger.warning(f"No agent found for role: {role} with capabilities {capabilities}")
        return team


class DynamicTeam:
    """Dynamic team formation from task requirements."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    async def form_team(
        self,
        task_description: str,
        complexity: str = "M",
        required_roles: Optional[dict[str, list[str]]] = None,
    ) -> dict[str, AgentCapability]:
        """Form a team based on task requirements."""
        if required_roles is None:
            required_roles = self._default_roles(complexity)

        return self.registry.form_team(
            task_requirements=required_roles,
            max_cost_per_token=self._max_cost_for_complexity(complexity),
        )

    def _default_roles(self, complexity: str) -> dict[str, list[str]]:
        """Get default role requirements based on complexity."""
        if complexity == "S":
            return {
                "builder": ["code_implementation", "test_writing"],
            }
        elif complexity == "M":
            return {
                "scout": ["code_search", "web_search", "dependency_analysis"],
                "architect": ["system_design", "architecture_review"],
                "builder": ["code_implementation", "test_writing"],
                "verifier": ["test_execution", "coverage_analysis"],
            }
        elif complexity == "L":
            return {
                "scout": ["code_search", "web_search", "dependency_analysis", "constraint_analysis"],
                "architect": ["system_design", "architecture_review", "tradeoff_analysis"],
                "reviewer": ["code_review", "security_audit", "performance_review"],
                "builder": ["code_implementation", "test_writing", "debugging", "refactoring"],
                "verifier": ["test_execution", "coverage_analysis", "acceptance_testing"],
            }
        else:  # XL
            return {
                "scout": ["code_search", "web_search", "dependency_analysis", "constraint_analysis", "test_coverage_analysis"],
                "architect": ["system_design", "architecture_review", "tradeoff_analysis", "scalability_planning"],
                "reviewer": ["code_review", "security_audit", "performance_review", "maintainability_assessment"],
                "builder": ["code_implementation", "test_writing", "debugging", "refactoring", "documentation"],
                "verifier": ["test_execution", "coverage_analysis", "acceptance_testing", "contract_verification"],
                "security_auditor": ["security_audit", "vulnerability_assessment", "compliance_check"],
            }

    def _max_cost_for_complexity(self, complexity: str) -> float:
        """Get max cost per token for complexity level."""
        costs = {
            "S": 0.00001,
            "M": 0.000005,
            "L": 0.000002,
            "XL": 0.000001,
        }
        return costs.get(complexity, 0.000005)


class CapabilityMatcher:
    """Match tasks to agents based on capabilities."""

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def match_task(
        self,
        task_description: str,
        required_capabilities: list[str],
        complexity: str = "M",
    ) -> list[AgentCapability]:
        """Match a task to capable agents."""
        return self.registry.match(
            required_capabilities=required_capabilities,
            max_cost_per_token=self._max_cost_for_complexity(complexity),
        )

    def _max_cost_for_complexity(self, complexity: str) -> float:
        costs = {
            "S": 0.00001,
            "M": 0.000005,
            "L": 0.000002,
            "XL": 0.000001,
        }
        return costs.get(complexity, 0.000005)


# Factory function
async def create_agent_registry(
    definitions_dir: Path | None = None,
    manifest_path: Path | None = None,
) -> AgentRegistry:
    """Create and load agent registry."""
    if definitions_dir is None:
        definitions_dir = Path(__file__).resolve().parent / "definitions"

    registry = AgentRegistry(definitions_dir, manifest_path)
    await registry.load()
    return registry