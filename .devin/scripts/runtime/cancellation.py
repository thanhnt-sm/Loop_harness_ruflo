#!/usr/bin/env python3
"""CancellationToken — Cooperative cancellation for async operations."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CancellationToken:
    """Cancellation token for cooperative cancellation.

    Usage:
        token = CancellationToken()

        # Pass to long-running operations
        await long_operation(token)

        # Cancel from another task
        token.cancel()

    In the operation:
        async def long_operation(token: CancellationToken):
            for item in items:
                token.throw_if_cancelled()  # Check at yield points
                await process(item)

            # Or wait for cancellation
            await token.wait()
    """

    _cancelled: bool = False
    _event: asyncio.Event = field(default_factory=asyncio.Event)
    _children: set["CancellationToken"] = field(default_factory=set)

    def cancel(self) -> None:
        """Signal cancellation to this token and all children."""
        if self._cancelled:
            return
        self._cancelled = True
        self._event.set()
        # Cascade to children
        for child in self._children:
            child.cancel()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    async def wait(self) -> None:
        """Wait until cancelled."""
        await self._event.wait()

    def throw_if_cancelled(self) -> None:
        """Raise CancelledError if cancelled."""
        if self._cancelled:
            raise asyncio.CancelledError("Operation cancelled")

    def child_token(self) -> "CancellationToken":
        """Create a child token that gets cancelled when parent cancels."""
        child = CancellationToken()
        self._children.add(child)
        return child

    def unlink_child(self, child: "CancellationToken") -> None:
        self._children.discard(child)

    def __enter__(self) -> "CancellationToken":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is asyncio.CancelledError:
            self.cancel()
        return False


class CancellationTokenSource:
    """Factory for linked cancellation tokens."""

    def __init__(self):
        self._token = CancellationToken()

    @property
    def token(self) -> CancellationToken:
        return self._token

    def cancel(self) -> None:
        self._token.cancel()

    def create_linked_token(self) -> CancellationToken:
        """Create a token linked to this source."""
        return self._token.child_token()

    def __enter__(self) -> "CancellationTokenSource":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is asyncio.CancelledError:
            self.cancel()
        return False


async def with_timeout(
    coro,
    timeout: float,
    token: Optional[CancellationToken] = None
) -> Any:
    """Run coroutine with timeout and optional cancellation token."""
    if token:
        async def wrapped():
            try:
                return await coro
            except asyncio.CancelledError:
                if token.cancelled:
                    raise
                raise

        return await asyncio.wait_for(wrapped(), timeout=timeout)
    else:
        return await asyncio.wait_for(coro, timeout=timeout)


def cancel_on(token: CancellationToken, *awaitables) -> asyncio.Task:
    """Cancel awaitables when token is cancelled."""
    async def cancel_watcher():
        await token.wait()
        for aw in awaitables:
            if hasattr(aw, "cancel"):
                aw.cancel()

    return asyncio.create_task(cancel_watcher())