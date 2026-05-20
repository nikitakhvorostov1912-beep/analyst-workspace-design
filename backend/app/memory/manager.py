"""MemoryManager — orchestrates memory providers (port of Hermes pattern).

См. `agent/memory_manager.py` в Hermes. Тут — упрощённая версия для нашего
синхронного FastAPI обработчика. В Sprint 3 (background review) добавится
async prefetch queue.

Usage:
    manager = MemoryManager()
    manager.add_provider(MarkdownStore(root=Path("..."), channel_id="..."))

    # В loop:
    system_block = manager.build_system_prompt()  # инжект в SYSTEM
    context = manager.prefetch_all(user_message)  # pre-turn
    # ... LLM call ...
    manager.sync_all(user_msg, assistant_reply)   # post-turn
"""

from __future__ import annotations

import logging
from typing import Any

from .provider import MemoryProvider

logger = logging.getLogger(__name__)


class MemoryManager:
    """Orchestrator for memory providers.

    Only ONE external provider may be registered at a time. Attempting
    to add a second is rejected with a warning. Local providers
    (MarkdownStore etc.) have no limit.
    """

    def __init__(self) -> None:
        self._providers: list[MemoryProvider] = []

    def add_provider(self, provider: MemoryProvider) -> bool:
        """Register a provider. Returns True if accepted, False if rejected."""
        if provider.is_external and any(p.is_external for p in self._providers):
            logger.warning(
                "External memory provider %r rejected — already have %r",
                provider.name,
                next(p.name for p in self._providers if p.is_external),
            )
            return False
        try:
            provider.initialize()
        except Exception:
            logger.exception("MemoryProvider %r initialize() failed — not added", provider.name)
            return False
        self._providers.append(provider)
        logger.info("MemoryProvider %r registered", provider.name)
        return True

    def providers(self) -> list[MemoryProvider]:
        return list(self._providers)

    def build_system_prompt(self) -> str:
        """Aggregate system_prompt_block() из всех providers.

        Возвращает один блок (joined через двойной перевод строки) или ''.
        """
        blocks: list[str] = []
        for p in self._providers:
            try:
                block = p.system_prompt_block()
            except Exception:
                logger.exception("Provider %r system_prompt_block() failed", p.name)
                continue
            if block and block.strip():
                blocks.append(block.strip())
        return "\n\n".join(blocks)

    def prefetch_all(self, user_msg: str) -> dict[str, Any]:
        """Pre-turn recall. Returns dict {provider_name: context_dict}.

        Failures logged but not raised. Provider that fails gets empty dict.
        """
        result: dict[str, Any] = {}
        for p in self._providers:
            try:
                result[p.name] = p.prefetch(user_msg)
            except Exception:
                logger.exception("Provider %r prefetch() failed", p.name)
                result[p.name] = {}
        return result

    def sync_all(self, user_msg: str, assistant_msg: str) -> None:
        """Post-turn sync. Best-effort — failures logged, not raised."""
        for p in self._providers:
            try:
                p.sync_turn(user_msg, assistant_msg)
            except Exception:
                logger.exception("Provider %r sync_turn() failed", p.name)

    def get_tool_schemas(self) -> list[dict]:
        """Aggregate tool schemas from all providers."""
        schemas: list[dict] = []
        for p in self._providers:
            try:
                schemas.extend(p.get_tool_schemas())
            except Exception:
                logger.exception("Provider %r get_tool_schemas() failed", p.name)
        return schemas

    def handle_tool_call(self, name: str, args: dict) -> Any:
        """Dispatch tool call to the provider that owns this tool.

        Lookup is by tool name across all providers. Raises ValueError if
        no provider claims the tool.
        """
        for p in self._providers:
            schemas = p.get_tool_schemas()
            for s in schemas:
                tool_name = s.get("function", {}).get("name")
                if tool_name == name:
                    return p.handle_tool_call(name, args)
        raise ValueError(f"No provider handles memory tool {name!r}")

    def shutdown_all(self) -> None:
        """Shutdown all providers. Best-effort."""
        for p in self._providers:
            try:
                p.shutdown()
            except Exception:
                logger.exception("Provider %r shutdown() failed", p.name)
        self._providers.clear()
