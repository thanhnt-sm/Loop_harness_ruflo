#!/usr/bin/env python3
"""BackpressureQueue — Bounded async queue with backpressure handling."""
from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Generic, Optional, TypeVar

T = TypeVar("T")


@dataclass
class BackpressureQueue(Generic[T]):
    """Bounded async queue with backpressure signaling.

    When queue is full, put() waits until space is available.
    Provides metrics for monitoring backpressure.
    """

    maxsize: int = 100
    _queue: deque = field(default_factory=deque)
    _put_waiters: int = field(default=0, init=False)
    _get_waiters: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _not_full: asyncio.Condition = field(default_factory=lambda: asyncio.Condition(), init=False)
    _not_empty: asyncio.Condition = field(default_factory=lambda: asyncio.Condition(), init=False)

    async def put(self, item: T, timeout: Optional[float] = None) -> None:
        """Put item with optional timeout.

        Args:
            item: Item to add
            timeout: Max seconds to wait for space. None = wait forever.

        Raises:
            asyncio.TimeoutError: If timeout expires before space available.
        """
        async with self._not_full:
            if self.maxsize > 0:
                while len(self._queue) >= self.maxsize:
                    self._put_waiters += 1
                    try:
                        await asyncio.wait_for(self._not_full.wait(), timeout=timeout)
                    except asyncio.TimeoutError:
                        self._put_waiters -= 1
                        raise
                    finally:
                        if not self._cancelled:
                            self._put_waiters -= 1

            self._queue.append(item)
            self._not_empty.notify()

    def put_nowait(self, item: T) -> None:
        """Put item without blocking. Raises QueueFull if full."""
        if self.maxsize > 0 and len(self._queue) >= self.maxsize:
            raise asyncio.QueueFull
        self._queue.append(item)
        self._not_empty.notify()

    async def get(self, timeout: Optional[float] = None) -> T:
        """Get item with optional timeout.

        Args:
            timeout: Max seconds to wait for item. None = wait forever.

        Returns:
            Next item in queue.

        Raises:
            asyncio.TimeoutError: If timeout expires before item available.
        """
        async with self._not_empty:
            while not self._queue:
                self._get_waiters += 1
                try:
                    await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    self._get_waiters -= 1
                    raise
                finally:
                    if not self._cancelled:
                        self._get_waiters -= 1

            item = self._queue.popleft()
            self._not_full.notify()
            return item

    def get_nowait(self) -> T:
        """Get item without blocking. Raises QueueEmpty if empty."""
        if not self._queue:
            raise asyncio.QueueEmpty
        item = self._queue.popleft()
        self._not_full.notify()
        return item

    def qsize(self) -> int:
        return len(self._queue)

    def empty(self) -> bool:
        return not self._queue

    def full(self) -> bool:
        return self.maxsize > 0 and len(self._queue) >= self.maxsize

    def put_waiters(self) -> int:
        return self._put_waiters

    def get_waiters(self) -> int:
        return self._get_waiters

    def backpressure_ratio(self) -> float:
        """Return ratio of current size to max size (0.0 to 1.0)."""
        if self.maxsize <= 0:
            return 0.0
        return len(self._queue) / self.maxsize

    async def __aiter__(self) -> AsyncIterator[T]:
        while True:
            yield await self.get()

    def __len__(self) -> int:
        return len(self._queue)


@dataclass
class PriorityBackpressureQueue(Generic[T]):
    """Backpressure queue with priority levels.

    Items with lower priority number are dequeued first.
    """

    maxsize: int = 100
    _queues: dict[int, deque] = field(default_factory=dict, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _not_empty: asyncio.Condition = field(default_factory=lambda: asyncio.Condition(), init=False)

    def __post_init__(self):
        self._queues[0] = deque()  # Default priority

    async def put(self, item: T, priority: int = 0, timeout: Optional[float] = None) -> None:
        async with self._not_empty:
            while self.qsize() >= self.maxsize:
                await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)

            async with self._lock:
                if priority not in self._queues:
                    self._queues[priority] = deque()
                self._queues[priority].append(item)

            self._not_empty.notify()

    async def get(self, timeout: Optional[float] = None) -> T:
        async with self._not_empty:
            while self.qsize() == 0:
                await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)

            async with self._lock:
                # Find highest priority non-empty queue
                for priority in sorted(self._queues.keys()):
                    if self._queues[priority]:
                        item = self._queues[priority].popleft()
                        self._not_empty.notify()
                        return item
                # Should not reach here if qsize() > 0
                raise RuntimeError("Queue inconsistent state")

    def qsize(self) -> int:
        return sum(len(q) for q in self._queues.values())

    def empty(self) -> bool:
        return self.qsize() == 0

    def full(self) -> bool:
        return self.maxsize > 0 and self.qsize() >= self.maxsize