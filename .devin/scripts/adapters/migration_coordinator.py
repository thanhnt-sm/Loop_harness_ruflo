#!/usr/bin/env python3
"""MigrationCoordinator — Saga orchestrator for dual-write migration.

Ensures atomicity across heterogeneous stores using saga pattern with
compensating transactions.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"


@dataclass
class SagaStep:
    """Single step in a saga."""
    name: str
    forward: Callable[[], Any]  # Forward action
    backward: Callable[[], Any]  # Compensating action
    status: StepStatus = StepStatus.PENDING
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class SagaExecution(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    saga_id: str
    steps: list[SagaStep] = field(default_factory=list)
    current_step: int = 0
    status: StepStatus = StepStatus.PENDING
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class MigrationCoordinator:
    """Orchestrates dual-write migrations using saga pattern.

    Ensures atomicity across heterogeneous stores by executing
    forward actions and compensating on failure.
    """

    def __init__(self):
        self._sagas: dict[str, SagaExecution] = {}
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger("migration_coordinator")

    @asynccontextmanager
    async def saga(self, saga_id: str):
        """Context manager for executing a saga."""
        async with self._lock:
            if saga_id in self._sagas:
                raise ValueError(f"Saga {saga_id} already exists")
            execution = SagaExecution(saga_id=saga_id)
            self._sagas[saga_id] = execution

        try:
            yield execution
            execution.status = StepStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            execution.status = StepStatus.FAILED
            execution.error = str(e)
            # Execute compensating transactions
            await self._compensate(execution)
            raise
        finally:
            async with self._lock:
                self._sagas.pop(saga_id, None)

    def add_step(
        self,
        execution: SagaExecution,
        name: str,
        forward: Callable[[], Any],
        backward: Callable[[], Any],
    ) -> None:
        """Add a step to the saga."""
        execution.steps.append(SagaStep(name=name, forward=forward, backward=backward))

    async def _compensate(self, execution: SagaExecution) -> None:
        """Execute compensating transactions in reverse order."""
        self._logger.warning(f"Compensating saga {execution.saga_id}")
        for step in reversed(execution.steps):
            if step.status == StepStatus.COMPLETED:
                step.status = StepStatus.COMPENSATED
                try:
                    if asyncio.iscoroutinefunction(step.backward):
                        await step.backward()
                    else:
                        step.backward()
                    self._logger.info(f"Compensated step: {step.name}")
                except Exception as e:
                    self._logger.error(f"Compensation failed for {step.name}: {e}")
                    # Continue compensating other steps


class DualWriteCoordinator:
    """Coordinates dual-write operations with saga pattern.

    Ensures atomic writes across primary and secondary stores.
    """

    def __init__(self, coordinator: MigrationCoordinator):
        self._coordinator = coordinator
        self._logger = logging.getLogger("dual_write_coordinator")

    async def execute(
        self,
        saga_id: str,
        primary_write: Callable[[], Any],
        secondary_write: Callable[[], Any],
        primary_rollback: Callable[[], Any],
        secondary_rollback: Callable[[], Any],
    ) -> None:
        """Execute dual-write with saga compensation.

        Args:
            saga_id: Unique identifier for this dual-write operation
            primary_write: Write to primary store (EventStore)
            secondary_write: Write to secondary store (legacy)
            primary_rollback: Rollback primary store
            secondary_rollback: Rollback secondary store
        """
        async with self._coordinator.saga(saga_id) as saga:
            # Step 1: Write to primary
            self._coordinator.add_step(
                saga,
                "primary_write",
                primary_write,
                primary_rollback,
            )
            if asyncio.iscoroutinefunction(primary_write):
                await primary_write()
            else:
                primary_write()

            # Step 2: Write to secondary
            self._coordinator.add_step(
                saga,
                "secondary_write",
                secondary_write,
                secondary_rollback,
            )
            if asyncio.iscoroutinefunction(secondary_write):
                await secondary_write()
            else:
                secondary_write()

            # If we reach here, both writes succeeded
            saga.status = StepStatus.COMPLETED


# --- Adapter Base Classes ---

class DualWriteAdapter:
    """Base adapter for dual-write pattern with saga support."""

    def __init__(self, dual_write_coordinator: DualWriteCoordinator):
        self._coordinator = dual_write_coordinator
        self._logger = logging.getLogger(f"adapter.{self.__class__.__name__}")

    async def dual_write(
        self,
        saga_id: str,
        primary_fn: Callable[[], Any],
        secondary_fn: Callable[[], Any],
        primary_rollback: Callable[[], Any],
        secondary_rollback: Callable[[], Any],
    ) -> None:
        """Execute dual-write with saga compensation."""
        await self._coordinator.execute(
            saga_id,
            primary_fn,
            secondary_fn,
            primary_rollback,
            secondary_rollback,
        )

    def _generate_saga_id(self, prefix: str, key: str) -> str:
        """Generate unique saga ID."""
        import uuid
        return f"{prefix}-{key}-{uuid.uuid4().hex[:8]}"

import uuid