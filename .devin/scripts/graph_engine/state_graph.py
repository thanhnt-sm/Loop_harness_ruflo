#!/usr/bin/env python3
"""StateGraph — LangGraph-compatible dynamic graph engine.

Core API:
    graph = StateGraph(MyState)
    graph.add_node("node_name", node_func)
    graph.add_edge("from_node", "to_node")
    graph.add_conditional_edge("from_node", predicate, {"true": "node_a", "false": "node_b"})
    compiled = graph.compile()
    await compiled.ainvoke(initial_state)
"""
from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, Optional, TypeVar, Union

from pydantic import BaseModel, ConfigDict, PrivateAttr

from .nodes.base import BaseNode, NodeResult
from .edges.base import Edge, DirectEdge, ConditionalEdge, FanOutEdge, FanInEdge

StateT = TypeVar("StateT", bound=BaseModel)


class NodeDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    func: Callable
    is_async: bool
    retries: int = 0
    timeout: float = 300.0
    metadata: dict = field(default_factory=dict)


class EdgeDefinition(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    source: str
    target: Union[str, dict[str, str]]  # str for direct, dict for conditional
    edge: Edge
    priority: int = 0  # For fan-out ordering


class StateGraph(BaseModel):
    """Dynamic graph builder — LangGraph-compatible API."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    state_schema: type[BaseModel]
    context_schema: Optional[type[BaseModel]] = None
    input_schema: Optional[type[BaseModel]] = None

    _nodes: dict[str, NodeDefinition] = PrivateAttr(default_factory=dict)
    _edges: list[EdgeDefinition] = PrivateAttr(default_factory=list)
    _entry_point: Optional[str] = PrivateAttr(default=None)
    _reducers: dict[str, Callable] = PrivateAttr(default_factory=dict)

    def add_node(
        self,
        name: str,
        func: Callable,
        retries: int = 0,
        timeout: float = 300.0,
        metadata: Optional[dict] = None,
    ) -> "StateGraph":
        """Add a node to the graph.

        Args:
            name: Unique node name
            func: Callable(state) -> partial_state_update
            retries: Max retries on failure
            timeout: Max execution time in seconds
            metadata: Additional metadata

        Returns:
            self (for chaining)
        """
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already exists")

        is_async = inspect.iscoroutinefunction(func)
        self._nodes[name] = NodeDefinition(
            name=name,
            func=func,
            is_async=is_async,
            retries=retries,
            timeout=timeout,
            metadata=metadata or {},
        )
        return self

    def add_edge(self, source: str, target: str) -> "StateGraph":
        """Add a direct edge (always transitions)."""
        if source not in self._nodes:
            raise ValueError(f"Source node '{source}' not found")
        if target not in self._nodes and target != "__end__":
            raise ValueError(f"Target node '{target}' not found")

        self._edges.append(EdgeDefinition(
            source=source,
            target=target,
            edge=DirectEdge(target=target),
        ))
        return self

    def add_conditional_edge(
        self,
        source: str,
        condition: Callable[[BaseModel], Union[str, dict[str, str]]],
        targets: dict[str, str],
    ) -> "StateGraph":
        """Add a conditional edge.

        Args:
            source: Source node name
            condition: Function(state) -> target_name or {condition_name: target_name}
            targets: Mapping of condition results to target nodes

        Example:
            graph.add_conditional_edge(
                "decide",
                lambda s: "approve" if s.approved else "reject",
                {"approve": "execute", "reject": "notify"}
            )
        """
        if source not in self._nodes:
            raise ValueError(f"Source node '{source}' not found")
        for target in targets.values():
            if target not in self._nodes and target != "__end__":
                raise ValueError(f"Target node '{target}' not found")

        self._edges.append(EdgeDefinition(
            source=source,
            target=targets,
            edge=ConditionalEdge(condition=condition, targets=targets),
        ))
        return self

    def add_fanout_edge(
        self,
        source: str,
        targets: list[str],
        reducer: Optional[Callable[[list[Any]], Any]] = None,
    ) -> "StateGraph":
        """Add fan-out edge for parallel execution.

        All target nodes run in parallel. Results combined with reducer.
        """
        for target in targets:
            if target not in self._nodes:
                raise ValueError(f"Target node '{target}' not found")

        self._edges.append(EdgeDefinition(
            source=source,
            target=targets,
            edge=FanOutEdge(reducer=reducer),
        ))
        return self

    def add_fanin_edge(
        self,
        sources: list[str],
        target: str,
        reducer: Optional[Callable[[list[Any]], Any]] = None,
    ) -> "StateGraph":
        """Add fan-in edge (join parallel branches)."""
        for source in sources:
            if source not in self._nodes:
                raise ValueError(f"Source node '{source}' not found")
        if target not in self._nodes:
            raise ValueError(f"Target node '{target}' not found")

        # Add edge from each source
        for source in sources:
            self._edges.append(EdgeDefinition(
                source=source,
                target=target,
                edge=FanInEdge(reducer=reducer),
            ))
        return self

    def set_entry_point(self, node_name: str) -> "StateGraph":
        """Set the graph entry point."""
        if node_name not in self._nodes:
            raise ValueError(f"Node '{node_name}' not found")
        self._entry_point = node_name
        return self

    def add_reducer(self, key: str, reducer: Callable[[Any, Any], Any]) -> "StateGraph":
        """Add a reducer function for a state key.

        Reducers combine values from parallel branches.
        """
        self._reducers[key] = reducer
        return self

    def compile(self) -> "CompiledStateGraph":
        """Compile graph into executable form."""
        if not self._entry_point:
            raise ValueError("Entry point not set. Call set_entry_point() first.")

        # Validate all targets exist
        for edge in self._edges:
            if isinstance(edge.target, dict):
                for t in edge.target.values():
                    if t not in self._nodes and t != "__end__":
                        raise ValueError(f"Edge target '{t}' not found")
            elif edge.target not in self._nodes and edge.target != "__end__":
                raise ValueError(f"Edge target '{edge.target}' not found")

        return CompiledStateGraph(
            state_schema=self.state_schema,
            context_schema=self.context_schema,
            nodes=self._nodes,
            edges=self._edges,
            entry_point=self._entry_point,
            reducers=self._reducers,
        )

    def to_mermaid(self) -> str:
        """Generate Mermaid diagram for visualization."""
        lines = ["graph TD"]
        for edge in self._edges:
            if isinstance(edge.target, dict):
                for condition, target in edge.target.items():
                    lines.append(f"    {edge.source} -->|{condition}| {target}")
            else:
                if isinstance(edge.target, list):
                    for t in edge.target:
                        lines.append(f"    {edge.source} --> {t}")
                else:
                    lines.append(f"    {edge.source} --> {edge.target}")
        return "\n".join(lines)

    def to_dot(self) -> str:
        """Generate GraphViz DOT format."""
        lines = ["digraph G {"]
        for edge in self._edges:
            if isinstance(edge.target, dict):
                for condition, target in edge.target.items():
                    lines.append(f'    "{edge.source}" -> "{target}" [label="{condition}"];')
            else:
                if isinstance(edge.target, list):
                    for t in edge.target:
                        lines.append(f'    "{edge.source}" -> "{t}";')
                else:
                    lines.append(f'    "{edge.source}" -> "{edge.target}";')
        lines.append("}")
        return "\n".join(lines)


@dataclass
class CompiledStateGraph:
    """Executable compiled graph."""

    state_schema: type[BaseModel]
    context_schema: Optional[type[BaseModel]]
    nodes: dict[str, NodeDefinition]
    edges: list[EdgeDefinition]
    entry_point: str
    reducers: dict[str, Callable]

    _checkpointer: Optional[Any] = field(default=None, init=False)

    def with_checkpointer(self, checkpointer) -> "CompiledStateGraph":
        """Attach a checkpointer for persistence."""
        self._checkpointer = checkpointer
        return self

    async def ainvoke(
        self,
        initial_state: Union[BaseModel, dict],
        config: Optional[dict] = None,
    ) -> BaseModel:
        """Invoke graph asynchronously (single run)."""
        state = self.state_schema.model_validate(initial_state) if isinstance(initial_state, dict) else initial_state
        context = self.context_schema() if self.context_schema else None

        runner = GraphRunner(self, config)
        final_state = await runner.run(state, context)
        return final_state

    async def astream(
        self,
        initial_state: Union[BaseModel, dict],
        config: Optional[dict] = None,
        stream_mode: str = "values",
    ) -> AsyncIterator[Union[BaseModel, dict]]:
        """Stream graph execution.

        Modes:
        - "values": Yield full state after each node
        - "updates": Yield only changed keys
        - "messages": Yield message events
        - "debug": Yield everything
        """
        state = self.state_schema.model_validate(initial_state) if isinstance(initial_state, dict) else initial_state
        context = self.context_schema() if self.context_schema else None

        runner = GraphRunner(self, config)

        if stream_mode == "values":
            async for s in runner.stream_values(state, context):
                yield s
        elif stream_mode == "updates":
            async for update in runner.stream_updates(state, context):
                yield update
        elif stream_mode == "debug":
            async for event in runner.stream_debug(state, context):
                yield event
        else:
            raise ValueError(f"Unknown stream_mode: {stream_mode}")

    async def astream_log(
        self,
        initial_state: Union[BaseModel, dict],
        config: Optional[dict] = None,
        include_types: Optional[list[str]] = None,
    ) -> AsyncIterator[dict]:
        """Stream detailed execution logs (JSONPatch format)."""
        state = self.state_schema.model_validate(initial_state) if isinstance(initial_state, dict) else initial_state
        context = self.context_schema() if self.context_schema else None

        runner = GraphRunner(self, config)
        async for log in runner.stream_logs(state, context, include_types):
            yield log

    def get_graph(self) -> "StateGraph":
        """Reconstruct StateGraph for visualization."""
        graph = StateGraph(state_schema=self.state_schema)
        graph._nodes = self.nodes
        graph._edges = self.edges
        graph._entry_point = self.entry_point
        graph._reducers = self.reducers
        return graph


class GraphRunner:
    """Executes compiled graph with checkpointing and streaming."""

    def __init__(self, graph: CompiledStateGraph, config: Optional[dict] = None):
        self.graph = graph
        self.config = config or {}
        self._state = None
        self._context = None
        self._history: list[dict] = []
        self._checkpointer = graph._checkpointer
        self._thread_id = config.get("configurable", {}).get("thread_id") if config else None

    async def run(self, initial_state: BaseModel, context: Optional[BaseModel]) -> BaseModel:
        """Execute graph to completion."""
        self._state = initial_state
        # context_schema không cấu hình → context rỗng (dict), không None — node
        # func gọi context.get() sẽ không crash.
        self._context = context if context is not None else {}

        # Load checkpoint if available
        if self._checkpointer and self._thread_id:
            checkpoint = await self._checkpointer.get(self._thread_id)
            if checkpoint:
                self._state = checkpoint.state
                self._history = checkpoint.history

        current_node = self.graph.entry_point

        while current_node and current_node != "__end__":
            node_def = self.graph.nodes[current_node]

            # Execute node with retries
            result = await self._execute_node(node_def)

            # Apply state updates
            if result.updates:
                self._apply_updates(result.updates)

            # Record history
            self._history.append({
                "node": current_node,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "updates": result.updates,
            })

            # Determine next node
            current_node = self._get_next_node(current_node)

            # Save checkpoint
            if self._checkpointer and self._thread_id:
                await self._checkpointer.put(self._thread_id, self._state, self._history)

        return self._state

    async def _execute_node(self, node_def: NodeDefinition) -> NodeResult:
        """Execute a single node with retries."""
        last_error = None

        for attempt in range(node_def.retries + 1):
            try:
                if node_def.is_async:
                    result = await asyncio.wait_for(
                        node_def.func(self._state, self._context),
                        timeout=node_def.timeout,
                    )
                else:
                    result = await asyncio.to_thread(
                        node_def.func, self._state, self._context
                    )

                # Validate result is a dict (partial state update)
                if not isinstance(result, dict):
                    raise ValueError(f"Node {node_def.name} must return dict, got {type(result)}")

                return NodeResult(updates=result)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e
                if attempt < node_def.retries:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise RuntimeError(f"Node {node_def.name} failed after {node_def.retries + 1} attempts: {last_error}") from last_error

    def _apply_updates(self, updates: dict) -> None:
        """Apply state updates with reducers."""
        for key, value in updates.items():
            if key in self.graph.reducers and hasattr(self._state, key):
                reducer = self.graph.reducers[key]
                current = getattr(self._state, key)
                try:
                    setattr(self._state, key, reducer(current, value))
                except Exception:
                    setattr(self._state, key, value)  # Fallback: overwrite
            else:
                setattr(self._state, key, value)

    def _get_next_node(self, current_node: str) -> Optional[str]:
        """Determine next node based on edges."""
        for edge in self.graph.edges:
            if edge.source != current_node:
                continue

            if isinstance(edge.target, str):
                # Direct edge
                return edge.target
            elif isinstance(edge.target, dict):
                # Conditional edge
                condition_fn = edge.edge.condition
                try:
                    condition_result = condition_fn(self._state)
                    if isinstance(condition_result, str):
                        return edge.target.get(condition_result)
                    elif isinstance(condition_result, dict):
                        # Return first matching condition
                        for cond, target in edge.target.items():
                            if cond in condition_result:
                                return target
                except Exception:
                    pass
            elif isinstance(edge.target, list):
                # Fan-out - handled by parallel execution
                pass

        return None  # End of graph


@dataclass
class NodeResult:
    updates: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)