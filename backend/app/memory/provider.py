"""Memory provider abstraction (port of Hermes `agent/memory_provider.py`).

Lifecycle (called by MemoryManager):
    initialize()            — connect, create resources, warm up
    system_prompt_block()   — static text for the system prompt
    prefetch(query)         — background recall before each turn
    sync_turn(user, asst)   — async write after each turn
    get_tool_schemas()      — tool schemas exposed to the model
    handle_tool_call()      — dispatch tool call
    shutdown()              — clean exit

Только ОДИН external provider может быть зарегистрирован одновременно —
против tool schema bloat. Local providers (MarkdownStore) — без ограничений.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MemoryProvider(ABC):
    """Abstract base for memory providers.

    Subclasses set `name` (unique id) and `is_external` (True for cloud-based
    providers like Honcho/Mem0). MemoryManager rejects a second external
    provider with a warning.
    """

    name: str = ""
    is_external: bool = False

    @abstractmethod
    def initialize(self) -> None:
        """Connect, create resources, warm up. Called once at MemoryManager.add_provider."""
        raise NotImplementedError

    def system_prompt_block(self) -> str:
        """Static text injected into the system prompt. Default: empty."""
        return ""

    def prefetch(self, query: str) -> dict[str, Any]:
        """Pre-turn recall. Returns arbitrary context dict. Default: empty.

        Called BEFORE the LLM sees the user message. Use to inject
        provider-specific context (semantic search, etc.).
        """
        return {}

    def sync_turn(self, user_msg: str, assistant_msg: str) -> None:
        """Post-turn async write. Called AFTER the assistant reply is delivered.

        Use to extract facts and persist them. Should be best-effort —
        failures logged but not raised.
        """

    def get_tool_schemas(self) -> list[dict]:
        """Tool schemas exposed to the model. Default: no tools."""
        return []

    def handle_tool_call(self, name: str, args: dict) -> Any:
        """Dispatch a tool call. Raises ValueError for unknown tool."""
        raise ValueError(f"{self.name}: unknown tool {name!r}")

    def shutdown(self) -> None:
        """Clean exit. Close connections, flush buffers, etc."""
