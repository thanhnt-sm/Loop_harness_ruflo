#!/usr/bin/env python3
"""StreamAdapter — Unified streaming interface for SWE-1.7, GLM, Kimi executors."""
from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from pydantic import BaseModel, ConfigDict


class StreamChunk(BaseModel):
    """Single chunk from LLM stream."""
    model_config = ConfigDict(frozen=True)

    type: str  # "token" | "tool_call" | "tool_result" | "error" | "done"
    content: str = ""
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[str] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class LLMClient(ABC):
    """Abstract base for LLM streaming clients."""

    @abstractmethod
    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream response from LLM."""
        ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Non-streaming completion."""
        ...


class LightningExecutorClient(LLMClient):
    """SWE-1.7 Lightning executor client (paid, fast)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.getenv("SWE_LIGHTNING_API_KEY")
        self._base_url = base_url or os.getenv("SWE_LIGHTNING_BASE_URL", "https://api.swe-lightning.com/v1")
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120.0,
            )
        return self._client

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[StreamChunk]:
        client = await self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "swe-1.7-lightning",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        tool_calls = delta.get("tool_calls")
                        if content:
                            yield StreamChunk(type="token", content=content)
                        if tool_calls:
                            for tc in tool_calls:
                                yield StreamChunk(
                                    type="tool_call",
                                    tool_name=tc.get("function", {}).get("name", ""),
                                    tool_args=json.loads(tc.get("function", {}).get("arguments", "{}")),
                                )
                    except json.JSONDecodeError:
                        continue

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        result = []
        async for chunk in self.stream(prompt, system, temperature, max_tokens):
            if chunk.type == "token":
                result.append(chunk.content)
        return "".join(result)


class GLMExecutorClient(LLMClient):
    """GLM-5.2 executor client (free, high reasoning)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.getenv("GLM_API_KEY")
        self._base_url = base_url or os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120.0,
            )
        return self._client

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[StreamChunk]:
        client = await self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "glm-5.2",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield StreamChunk(type="token", content=content)
                    except json.JSONDecodeError:
                        continue

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        result = []
        async for chunk in self.stream(prompt, system, temperature, max_tokens):
            if chunk.type == "token":
                result.append(chunk.content)
        return "".join(result)


class KimiExecutorClient(LLMClient):
    """Kimi K2.7 executor client (free, open-source)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or os.getenv("KIMI_API_KEY")
        self._base_url = base_url or os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=120.0,
            )
        return self._client

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[StreamChunk]:
        client = await self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "kimi-k2.7",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with client.stream("POST", "/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or line == "data: [DONE]":
                    continue
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield StreamChunk(type="token", content=content)
                    except json.JSONDecodeError:
                        continue

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        result = []
        async for chunk in self.stream(prompt, system, temperature, max_tokens):
            if chunk.type == "token":
                result.append(chunk.content)
        return "".join(result)


class LocalLLMClient(LLMClient):
    """Local LLM via ollama or llama.cpp server."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self._base_url = base_url
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(base_url=self._base_url, timeout=120.0)
        return self._client

    async def stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[StreamChunk]:
        client = await self._get_client()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "llama3",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with client.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    message = data.get("message", {})
                    content = message.get("content", "")
                    if content:
                        yield StreamChunk(type="token", content=content)
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        result = []
        async for chunk in self.stream(prompt, system, temperature, max_tokens):
            if chunk.type == "token":
                result.append(chunk.content)
        return "".join(result)


class StreamAdapter:
    """Unified streaming interface for all executors.

    Usage:
        adapter = StreamAdapter()
        adapter.register("lightning", LightningExecutorClient())
        adapter.register("glm", GLMExecutorClient())
        adapter.register("kimi", KimiExecutorClient())

        async for chunk in adapter.stream("model_name", prompt, system="..."):
            print(chunk.content, end="", flush=True)
    """

    def __init__(self):
        self._clients: dict[str, LLMClient] = {}
        self._default_model: Optional[str] = None
        self._cost_optimizer = None

    def register(self, name: str, client: LLMClient, is_default: bool = False) -> None:
        self._clients[name] = client
        if is_default or self._default_model is None:
            self._default_model = name

    def set_cost_optimizer(self, optimizer) -> None:
        self._cost_optimizer = optimizer

    def select_model(self, required_capabilities: list[str] = None) -> str:
        if self._cost_optimizer and required_capabilities:
            return self._cost_optimizer.select_model(required_capabilities)
        return self._default_model or next(iter(self._clients))

    async def stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
    ) -> AsyncIterator[StreamChunk]:
        model_name = model or self.select_model()
        client = self._clients.get(model_name)
        if not client:
            raise ValueError(f"Unknown model: {model_name}")

        async for chunk in client.stream(prompt, system, temperature, max_tokens, tools):
            yield chunk

    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        result = []
        async for chunk in self.stream(prompt, model, system, temperature, max_tokens):
            if chunk.type == "token":
                result.append(chunk.content)
        return "".join(result)

    def list_models(self) -> list[str]:
        return list(self._clients.keys())