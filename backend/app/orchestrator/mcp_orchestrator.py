"""MCP Orchestrator — unified registry для нескольких MCP клиентов.

M-K1.8 (M6 Phase 12.3 + INTEGRATION-DECISIONS.md §accepted #7).

Аналитик в одном чате может одновременно использовать tools от:
- 1С MCP Toolkit (`:6010/mcp`) — основной канал к базе
- 1С:Напарник `1c-buddy` (`:6002/mcp`) — ИТС/БСП документация
- mcp-bsl-context — справочник API платформы 1С
- METR (опционально) — test runner
- EDT-MCP (опционально) — Eclipse-based 1С IDE

LLM видит **один объединённый список tools** с префиксами:
- `toolkit.execute_query`, `toolkit.get_metadata`
- `buddy.search_its`, `buddy.fetch_its`
- `context.search`, `context.info`, `context.getMembers`

При `call_tool('toolkit.execute_query', args)` — orchestrator splits
namespace, роутит к зарегистрированному клиенту с этим namespace.

**Не реализует:**
- Реальное создание MCP клиентов (это делает factory в M-K1.15 Seed)
- HTTP transport details (используется существующий MCPClient)
- Healthcheck / circuit breaker (M-K1.7 для capability, M-K1.15 для здоровья)

**Контракт:**
- Любой объект с методами `list_tools() / call_tool(name, args) / aclose()`
  может быть зарегистрирован — Protocol (PEP 544) duck typing
- Имена tools от внутреннего MCP client используются БЕЗ префикса —
  префикс добавляется/убирается ТОЛЬКО на границе orchestrator
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol — что должен уметь MCP-like клиент
# ---------------------------------------------------------------------------


@runtime_checkable
class MCPClientProtocol(Protocol):
    """Минимальный контракт MCP-клиента для orchestrator.

    Реальный `app.clients.mcp.MCPClient` его удовлетворяет автоматически.
    Тесты могут подсунуть mock — `isinstance(obj, MCPClientProtocol)` работает
    благодаря `@runtime_checkable`.
    """

    async def list_tools(self) -> list[dict]:
        """Возвращает schemas tools без namespace prefix.

        Каждый dict содержит как минимум `name: str`. Доп. поля (description,
        inputSchema) передаются как есть в LLM payload.
        """
        ...

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Вызывает tool по имени (без namespace prefix).

        Возвращает результат MCP `tools/call` response (содержит content array).
        """
        ...

    async def aclose(self) -> None:
        """Закрывает HTTP-клиент / транспорт."""
        ...


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class MCPOrchestratorError(RuntimeError):
    """Базовая ошибка orchestrator (некорректное имя tool, unknown namespace)."""


class UnknownNamespaceError(MCPOrchestratorError):
    """Запрошенный namespace не зарегистрирован."""


class InvalidToolNameError(MCPOrchestratorError):
    """Имя tool не содержит namespace.* префикса."""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Разделитель namespace и имени tool. Точка — стандартное соглашение MCP
# (см. ADR-004 и `app.types.capabilities` namespaces).
_NS_SEPARATOR = "."

# Известные namespaces — для логирования / валидации.
# Не использовать как whitelist (forward-compat: новые namespaces должны
# работать без code change), только для warning при unusual использовании.
_KNOWN_NAMESPACES: frozenset[str] = frozenset({
    "toolkit",  # 1С MCP Toolkit
    "buddy",    # 1С:Напарник (1c-buddy)
    "context",  # mcp-bsl-context (BSL syntax help)
    "metr",     # METR test runner (опционально)
    "edt",      # EDT-MCP (опционально)
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class MCPOrchestrator:
    """Unified registry для нескольких MCP клиентов с namespace routing.

    Не thread-safe — рассчитан на использование в asyncio event loop одного
    request handler. Для долгоживущих instance'ов (e.g. attached к
    `app.state`) — Это OK при single-process backend.

    **Не async-friendly при mutation:** `register()` / `unregister()` —
    sync методы. Все I/O (list_tools, call_tool, close_all) — async.
    """

    def __init__(self) -> None:
        # namespace → client
        self._clients: dict[str, MCPClientProtocol] = {}

    # ---------- Registration ----------

    def register(self, namespace: str, client: MCPClientProtocol) -> None:
        """Регистрирует клиента под namespace.

        Args:
            namespace: e.g. 'toolkit', 'buddy', 'context'. Должен быть
                непустой ASCII identifier (lowercase, без точки).
            client: объект с list_tools/call_tool/aclose (Protocol).

        Raises:
            ValueError: namespace пустой / содержит '.' / non-ASCII
            MCPOrchestratorError: namespace уже занят (используйте
                unregister + register для замены)
        """
        ns = namespace.strip().lower()
        if not ns:
            raise ValueError("namespace cannot be empty")
        if _NS_SEPARATOR in ns:
            raise ValueError(
                f"namespace cannot contain {_NS_SEPARATOR!r}: {namespace!r}"
            )
        if not ns.isascii():
            raise ValueError(f"namespace must be ASCII: {namespace!r}")
        if ns in self._clients:
            raise MCPOrchestratorError(
                f"namespace {ns!r} already registered; unregister first"
            )

        if ns not in _KNOWN_NAMESPACES:
            logger.info(
                "Registering unknown namespace %r — known: %s",
                ns,
                sorted(_KNOWN_NAMESPACES),
            )
        self._clients[ns] = client

    def unregister(self, namespace: str) -> MCPClientProtocol | None:
        """Удаляет клиента из registry. Возвращает удалённого или None."""
        ns = namespace.strip().lower()
        return self._clients.pop(ns, None)

    def namespaces(self) -> tuple[str, ...]:
        """Возвращает sorted tuple зарегистрированных namespaces."""
        return tuple(sorted(self._clients.keys()))

    def has_namespace(self, namespace: str) -> bool:
        return namespace.strip().lower() in self._clients

    # ---------- Public API: list_tools (aggregated) ----------

    async def list_tools(self) -> list[dict]:
        """Возвращает объединённый список tools от всех клиентов.

        Каждый tool['name'] префиксируется с namespace:
            'execute_query' → 'toolkit.execute_query'

        Если один клиент падает на list_tools — orchestrator логирует
        warning и продолжает (degraded mode, не блокирует остальные).
        Это критично т.к. падение buddy MCP не должно лишать пользователя
        toolkit tools.

        Returns:
            list of dicts с обогащённым `name` (и сохранёнными остальными
            полями оригинала).
        """
        result: list[dict] = []
        for ns, client in self._clients.items():
            try:
                tools = await client.list_tools()
            except Exception as exc:
                logger.warning(
                    "MCPOrchestrator: list_tools failed for namespace %r: %s",
                    ns,
                    exc,
                )
                continue
            for tool in tools:
                original_name = str(tool.get("name", "")).strip()
                if not original_name:
                    logger.warning(
                        "MCPOrchestrator: tool без name в namespace %r: %r",
                        ns,
                        tool,
                    )
                    continue
                # Не мутируем оригинал — копия с обновлённым name
                prefixed = dict(tool)
                prefixed["name"] = f"{ns}{_NS_SEPARATOR}{original_name}"
                result.append(prefixed)
        return result

    # ---------- Public API: call_tool (routing) ----------

    async def call_tool(self, prefixed_name: str, arguments: dict) -> dict:
        """Вызывает tool по prefixed имени, роутит к нужному клиенту.

        Args:
            prefixed_name: e.g. 'toolkit.execute_query' или 'buddy.search_its'.
                Должен содержать ровно одну точку (namespace.tool).
                Tool name может содержать дальнейшие точки (e.g.
                'toolkit.metadata.get_object') — splits только по ПЕРВОЙ.
            arguments: передаются как есть к client.call_tool.

        Returns:
            результат от client.call_tool (MCP `tools/call` response).

        Raises:
            InvalidToolNameError: name без префикса
            UnknownNamespaceError: namespace не зарегистрирован
        """
        if _NS_SEPARATOR not in prefixed_name:
            raise InvalidToolNameError(
                f"Tool name must contain namespace: {prefixed_name!r} "
                f"(expected format: '<namespace>{_NS_SEPARATOR}<tool>')"
            )
        ns, _, tool_name = prefixed_name.partition(_NS_SEPARATOR)
        ns = ns.strip().lower()
        if not tool_name:
            raise InvalidToolNameError(
                f"Tool name is empty after namespace: {prefixed_name!r}"
            )
        client = self._clients.get(ns)
        if client is None:
            raise UnknownNamespaceError(
                f"Namespace {ns!r} not registered. "
                f"Available: {sorted(self._clients.keys())}"
            )
        return await client.call_tool(tool_name, arguments)

    # ---------- Public API: lifecycle ----------

    async def close_all(self) -> None:
        """Асинхронно закрывает всех клиентов.

        Каждый client.aclose() выполняется отдельно — падение одного
        не блокирует закрытие остальных.

        После вызова clients dict пустой.
        """
        clients = list(self._clients.values())
        self._clients.clear()
        for client in clients:
            try:
                await client.aclose()
            except Exception as exc:
                logger.warning(
                    "MCPOrchestrator: aclose() failed for client %r: %s",
                    client,
                    exc,
                )

    def __repr__(self) -> str:
        return (
            f"<MCPOrchestrator namespaces={self.namespaces()} "
            f"count={len(self._clients)}>"
        )

    # ---------- Internal — для тестов / диагностики ----------

    def _get_client(self, namespace: str) -> MCPClientProtocol | None:
        """Только для тестов / диагностики. Возвращает зарегистрированный
        клиент или None.
        """
        return self._clients.get(namespace.strip().lower())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def split_prefixed_name(prefixed_name: str) -> tuple[str, str]:
    """Парсит 'namespace.tool' → ('namespace', 'tool').

    Helper для использования снаружи MCPOrchestrator (e.g. в loop.py
    для логирования какому MCP роутится конкретный tool call).

    Raises:
        InvalidToolNameError: если нет '.' или namespace/tool пустой.
    """
    if _NS_SEPARATOR not in prefixed_name:
        raise InvalidToolNameError(
            f"Tool name must contain namespace: {prefixed_name!r}"
        )
    ns, _, tool = prefixed_name.partition(_NS_SEPARATOR)
    ns = ns.strip().lower()
    tool = tool.strip()
    if not ns or not tool:
        raise InvalidToolNameError(
            f"namespace or tool name empty in {prefixed_name!r}"
        )
    return ns, tool
