"""Фабрики фейковых LLM/MCP ответов для тестов orchestrator."""

from collections.abc import AsyncIterator
from typing import Any


def stub_llm_stream(*chunks: dict) -> "AsyncIterator[dict]":
    """Создаёт async-генератор, имитирующий LLMClient.stream_chat_completion."""
    async def _gen() -> AsyncIterator[dict]:
        for chunk in chunks:
            yield chunk
    return _gen()


def make_text_chunk(content: str, finish_reason: str | None = None) -> dict:
    """Chunk с текстовым delta."""
    return {
        "delta": {"content": content},
        "finish_reason": finish_reason,
    }


def make_tool_call_chunk(
    index: int,
    call_id: str,
    name: str,
    arguments: str,
    finish_reason: str | None = None,
) -> dict:
    """Chunk с tool_call delta."""
    return {
        "delta": {
            "content": None,
            "tool_calls": [
                {
                    "index": index,
                    "id": call_id,
                    "function": {"name": name, "arguments": arguments},
                }
            ],
        },
        "finish_reason": finish_reason,
    }


def make_stop_chunk() -> dict:
    """Финальный chunk с finish_reason=stop."""
    return {"delta": {}, "finish_reason": "stop"}


def make_tool_calls_finish_chunk() -> dict:
    """Финальный chunk с finish_reason=tool_calls."""
    return {"delta": {}, "finish_reason": "tool_calls"}


class FakeMCPClient:
    """Фейковый MCPClient для тестов.

    tool_map: dict[str, dict | Exception] — имя инструмента → результат или исключение
    """

    def __init__(
        self,
        endpoint: str = "http://fake",
        tool_map: dict[str, Any] | None = None,
        tools: list[dict] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.tool_map = tool_map or {}
        self._tools = tools or [
            {"name": "execute_query", "description": "Запрос к 1С", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "get_metadata", "description": "Метаданные", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "get_event_log", "description": "Журнал", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "get_object_by_link", "description": "Объект по ссылке", "inputSchema": {"type": "object", "properties": {}}},
        ]
        self._call_count: dict[str, int] = {}

    async def initialize(self) -> None:
        pass

    async def list_tools(self) -> list[dict]:
        return self._tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        self._call_count[name] = self._call_count.get(name, 0) + 1
        result = self.tool_map.get(name)
        if result is None:
            return {"content": [{"type": "text", "text": "{}"}]}
        if isinstance(result, Exception):
            raise result
        return result

    async def aclose(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def __aenter__(self) -> "FakeMCPClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        pass
