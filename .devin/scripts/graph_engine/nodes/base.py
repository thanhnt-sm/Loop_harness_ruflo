#!/usr/bin/env python3
"""Base node classes and utilities."""
from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict


@dataclass
class NodeResult:
    """Result of node execution."""
    updates: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class BaseNode(ABC):
    """Abstract base class for graph nodes."""

    def __init__(
        self,
        name: str,
        retries: int = 0,
        timeout: float = 300.0,
        metadata: Optional[dict] = None,
    ):
        self.name = name
        self.retries = retries
        self.timeout = timeout
        self.metadata = metadata or {}

    @abstractmethod
    async def execute(self, state: Any, context: Any) -> dict:
        """Execute node logic.

        Args:
            state: Current graph state
            context: Execution context (optional)

        Returns:
            Partial state update (dict)
        """
        pass

    async def run_with_retry(self, state: Any, context: Any) -> dict:
        """Execute with retry logic."""
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                return await asyncio.wait_for(
                    self.execute(state, None),
                    timeout=self.timeout,
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if attempt < self.retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise RuntimeError(f"Node {self.name} failed after {self.retries + 1} attempts") from e


class LLMNode(BaseNode):
    """Node that calls an LLM with streaming support."""

    def __init__(
        self,
        name: str,
        prompt_template: str,
        system_prompt: str = "",
        model: str = "glm",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        retries: int = 2,
        timeout: float = 120.0,
        **kwargs,
    ):
        super().__init__(name, retries, **kwargs)
        self.prompt_template = prompt_template
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def execute(self, state: Any, context: Any) -> dict:
        # Render prompt from state
        prompt = self._render_prompt(state)

        # Call LLM (would use StreamAdapter in real implementation)
        response = await self._call_llm(prompt)

        return self._parse_response(response, state)

    def _render_prompt(self, state: Any) -> str:
        """Render prompt template with state variables."""
        # Simple template substitution
        if hasattr(state, 'model_dump'):
            vars_dict = state.model_dump()
        elif isinstance(state, dict):
            vars_dict = state
        else:
            vars_dict = {}

        return self.prompt_template.format(**vars_dict)

    async def _call_llm(self, prompt: str) -> str:
        # Placeholder - would use StreamAdapter in real implementation
        return f"LLM response for: {prompt[:100]}"

    def _parse_response(self, response: str, state: Any) -> dict:
        """Parse LLM response into state updates."""
        return {"llm_response": response}


class ToolNode(BaseNode):
    """Node that executes a tool/function."""

    def __init__(
        self,
        name: str,
        tool_func: Callable,
        input_key: str = "tool_input",
        output_key: str = "tool_output",
        retries: int = 2,
        timeout: float = 60.0,
        **kwargs,
    ):
        super().__init__(name, retries, **kwargs)
        self.tool_func = tool_func
        self.input_key = input_key
        self.output_key = output_key

    async def execute(self, state: Any, context: Any) -> dict:
        # Extract input from state
        if hasattr(state, 'model_dump'):
            input_data = getattr(state, self.input_key, {})
        else:
            input_data = state.get(self.input_key, {})

        # Execute tool
        if inspect.iscoroutinefunction(self.tool_func):
            result = await self.tool_func(**input_data)
        else:
            result = await asyncio.to_thread(self.tool_func, **input_data)

        return {self.output_key: result}


class HumanNode(BaseNode):
    """Node that interrupts for human input."""

    def __init__(
        self,
        name: str,
        prompt: str,
        resume_key: str = "human_input",
        timeout: float = 3600.0,  # 1 hour default
        **kwargs,
    ):
        super().__init__(name, retries=0, timeout=timeout, **kwargs)
        self.prompt = prompt
        self.resume_key = resume_key

    async def execute(self, state: Any, context: Any) -> dict:
        # Check if human input already provided
        if hasattr(state, self.resume_key) and getattr(state, self.resume_key):
            return {}

        # In real implementation, this would:
        # 1. Persist current state
        # 2. Send interrupt to human (via UI/notification)
        # 3. Wait for resume signal
        # 4. Return human input as state update

        # For now, return a placeholder
        return {
            "awaiting_human": True,
            "human_prompt": self.prompt,
            self.resume_key: None,  # Will be filled on resume
        }

    def resume(self, human_input: Any) -> dict:
        """Call this to resume after human provides input."""
        return {self.resume_key: human_input}


class SubGraphNode(BaseNode):
    """Node that executes a nested sub-graph."""

    def __init__(
        self,
        name: str,
        subgraph: "CompiledStateGraph",
        input_mapping: Optional[dict[str, str]] = None,
        output_mapping: Optional[dict[str, str]] = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.subgraph = subgraph
        self.input_mapping = input_mapping or {}
        self.output_mapping = output_mapping or {}

    async def execute(self, state: Any, context: Any) -> dict:
        # Map parent state to subgraph input
        subgraph_input = {}
        for sub_key, parent_key in self.input_mapping.items():
            if hasattr(state, parent_key):
                subgraph_input[sub_key] = getattr(state, parent_key)
            elif isinstance(state, dict) and parent_key in state:
                subgraph_input[sub_key] = state[parent_key]

        # Run subgraph
        result = await self.subgraph.ainvoke(subgraph_input)

        # Map subgraph output to parent state
        updates = {}
        for parent_key, sub_key in self.output_mapping.items():
            if hasattr(result, sub_key):
                updates[parent_key] = getattr(result, sub_key)
            elif isinstance(result, dict) and sub_key in result:
                updates[parent_key] = result[sub_key]

        return updates


class ConditionalNode(BaseNode):
    """Node that routes based on condition."""

    def __init__(
        self,
        name: str,
        condition: Callable[[Any], str],
        true_node: str,
        false_node: str,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.condition = condition
        self.true_node = true_node
        self.false_node = false_node

    async def execute(self, state: Any, context: Any) -> dict:
        result = self.condition(state)
        next_node = self.true_node if result else self.false_node
        return {"next_node": next_node, "condition_result": result}


class ParallelNode(BaseNode):
    """Node that executes multiple sub-nodes in parallel."""

    def __init__(
        self,
        name: str,
        sub_nodes: list[BaseNode],
        reducer: Optional[Callable[[list[dict]], dict]] = None,
        **kwargs,
    ):
        super().__init__(name, **kwargs)
        self.sub_nodes = sub_nodes
        self.reducer = reducer or self._default_reducer

    @staticmethod
    def _default_reducer(results: list[dict]) -> dict:
        """Merge results by combining keys."""
        merged = {}
        for r in results:
            merged.update(r)
        return merged

    async def execute(self, state: Any, context: Any) -> dict:
        tasks = [node.run_with_retry(state, context) for node in self.sub_nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_results = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                # Log error but continue
                pass
            else:
                valid_results.append(r)

        return self.reducer(valid_results)