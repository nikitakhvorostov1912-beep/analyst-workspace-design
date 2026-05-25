"""Tests for app.orchestrator.mcp_orchestrator (M-K1.8)."""

from __future__ import annotations

from typing import Any

import pytest

from app.orchestrator.mcp_orchestrator import (
    InvalidToolNameError,
    MCPClientProtocol,
    MCPOrchestrator,
    MCPOrchestratorError,
    UnknownNamespaceError,
    split_prefixed_name,
)


# ---------------------------------------------------------------------------
# Fake клиент для тестов (не использует HTTP, не зависит от MCPClient)
# ---------------------------------------------------------------------------


class FakeMCPClient:
    """Минимальная реализация MCPClientProtocol для тестов.

    Хранит зарегистрированные tools + результаты вызовов.
    Позволяет имитировать сбои через raise_on_list / raise_on_call.
    """

    def __init__(
        self,
        tools: list[dict] | None = None,
        *,
        raise_on_list: Exception | None = None,
        raise_on_call: Exception | None = None,
    ) -> None:
        self._tools = list(tools or [])
        self._raise_on_list = raise_on_list
        self._raise_on_call = raise_on_call
        self.closed = False
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self) -> list[dict]:
        if self._raise_on_list:
            raise self._raise_on_list
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict) -> dict:
        if self._raise_on_call:
            raise self._raise_on_call
        self.calls.append((name, dict(arguments)))
        return {"result": f"fake-{name}", "args": arguments}

    async def aclose(self) -> None:
        self.closed = True


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_orchestrator_empty_on_init() -> None:
    orch = MCPOrchestrator()
    assert orch.namespaces() == ()
    assert orch.has_namespace("toolkit") is False


def test_orchestrator_register_known_namespace() -> None:
    orch = MCPOrchestrator()
    client = FakeMCPClient()
    orch.register("toolkit", client)
    assert orch.namespaces() == ("toolkit",)
    assert orch.has_namespace("toolkit") is True
    assert orch._get_client("toolkit") is client


def test_orchestrator_register_normalizes_casing() -> None:
    orch = MCPOrchestrator()
    orch.register("Toolkit", FakeMCPClient())
    assert orch.has_namespace("toolkit") is True
    assert orch.has_namespace("TOOLKIT") is True  # has_namespace тоже normalize


def test_orchestrator_register_multiple_namespaces() -> None:
    orch = MCPOrchestrator()
    orch.register("toolkit", FakeMCPClient())
    orch.register("buddy", FakeMCPClient())
    orch.register("context", FakeMCPClient())
    assert orch.namespaces() == ("buddy", "context", "toolkit")  # sorted


def test_orchestrator_register_duplicate_raises() -> None:
    orch = MCPOrchestrator()
    orch.register("toolkit", FakeMCPClient())
    with pytest.raises(MCPOrchestratorError, match="already registered"):
        orch.register("toolkit", FakeMCPClient())


def test_orchestrator_register_empty_namespace_raises() -> None:
    orch = MCPOrchestrator()
    with pytest.raises(ValueError, match="cannot be empty"):
        orch.register("", FakeMCPClient())
    with pytest.raises(ValueError, match="cannot be empty"):
        orch.register("   ", FakeMCPClient())


def test_orchestrator_register_namespace_with_dot_raises() -> None:
    orch = MCPOrchestrator()
    with pytest.raises(ValueError, match="cannot contain"):
        orch.register("tool.kit", FakeMCPClient())


def test_orchestrator_register_non_ascii_raises() -> None:
    orch = MCPOrchestrator()
    with pytest.raises(ValueError, match="ASCII"):
        orch.register("инструменты", FakeMCPClient())


def test_orchestrator_register_unknown_namespace_warns_but_works(caplog) -> None:
    """Unknown namespace регистрируется (forward-compat) с info-уровнем лога."""
    orch = MCPOrchestrator()
    orch.register("future_v99", FakeMCPClient())  # не в _KNOWN_NAMESPACES
    assert orch.has_namespace("future_v99")
    # Лог содержит info-уровень про unknown
    # (не проверяем точно — это implementation detail)


def test_orchestrator_unregister() -> None:
    orch = MCPOrchestrator()
    client = FakeMCPClient()
    orch.register("toolkit", client)
    removed = orch.unregister("toolkit")
    assert removed is client
    assert orch.has_namespace("toolkit") is False


def test_orchestrator_unregister_missing_returns_none() -> None:
    orch = MCPOrchestrator()
    assert orch.unregister("toolkit") is None


# ---------------------------------------------------------------------------
# list_tools — aggregation + prefix
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tools_empty_orchestrator_returns_empty() -> None:
    orch = MCPOrchestrator()
    assert await orch.list_tools() == []


@pytest.mark.asyncio
async def test_list_tools_prefixes_single_namespace() -> None:
    orch = MCPOrchestrator()
    orch.register(
        "toolkit",
        FakeMCPClient(tools=[
            {"name": "execute_query", "description": "Run SQL"},
            {"name": "get_metadata", "description": "Read meta"},
        ]),
    )
    tools = await orch.list_tools()
    names = [t["name"] for t in tools]
    assert names == ["toolkit.execute_query", "toolkit.get_metadata"]
    # Description сохранилась
    assert tools[0]["description"] == "Run SQL"


@pytest.mark.asyncio
async def test_list_tools_aggregates_multiple_namespaces() -> None:
    orch = MCPOrchestrator()
    orch.register(
        "toolkit",
        FakeMCPClient(tools=[{"name": "execute_query"}]),
    )
    orch.register(
        "buddy",
        FakeMCPClient(tools=[{"name": "search_its"}, {"name": "fetch_its"}]),
    )
    orch.register(
        "context",
        FakeMCPClient(tools=[{"name": "search"}, {"name": "info"}]),
    )
    tools = await orch.list_tools()
    names = sorted(t["name"] for t in tools)
    assert names == [
        "buddy.fetch_its",
        "buddy.search_its",
        "context.info",
        "context.search",
        "toolkit.execute_query",
    ]


@pytest.mark.asyncio
async def test_list_tools_one_namespace_fails_degraded_mode() -> None:
    """Падение одного клиента не блокирует остальные (degraded mode)."""
    orch = MCPOrchestrator()
    orch.register(
        "toolkit",
        FakeMCPClient(tools=[{"name": "execute_query"}]),
    )
    orch.register(
        "buddy",
        FakeMCPClient(raise_on_list=RuntimeError("Connection refused")),
    )
    tools = await orch.list_tools()
    # toolkit вернулся, buddy пропущен
    names = [t["name"] for t in tools]
    assert "toolkit.execute_query" in names
    assert not any(n.startswith("buddy.") for n in names)


@pytest.mark.asyncio
async def test_list_tools_skips_unnamed_tools() -> None:
    """Tool без name — пропускается с warning, не падаем."""
    orch = MCPOrchestrator()
    orch.register(
        "toolkit",
        FakeMCPClient(tools=[
            {"name": "execute_query"},
            {"name": ""},  # пустое
            {"description": "no name field"},  # name отсутствует
        ]),
    )
    tools = await orch.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "toolkit.execute_query"


@pytest.mark.asyncio
async def test_list_tools_does_not_mutate_originals() -> None:
    """Префиксирование — на копии, оригинал не меняется."""
    original = {"name": "execute_query", "description": "SQL"}
    client = FakeMCPClient(tools=[original])
    orch = MCPOrchestrator()
    orch.register("toolkit", client)
    await orch.list_tools()
    # Оригинал остался без префикса
    assert original["name"] == "execute_query"


# ---------------------------------------------------------------------------
# call_tool — routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_tool_routes_to_correct_namespace() -> None:
    orch = MCPOrchestrator()
    toolkit_client = FakeMCPClient()
    buddy_client = FakeMCPClient()
    orch.register("toolkit", toolkit_client)
    orch.register("buddy", buddy_client)

    result = await orch.call_tool("toolkit.execute_query", {"sql": "SELECT 1"})
    assert result == {"result": "fake-execute_query", "args": {"sql": "SELECT 1"}}
    assert toolkit_client.calls == [("execute_query", {"sql": "SELECT 1"})]
    assert buddy_client.calls == []  # не вызывался


@pytest.mark.asyncio
async def test_call_tool_strips_namespace_before_calling() -> None:
    orch = MCPOrchestrator()
    client = FakeMCPClient()
    orch.register("buddy", client)

    await orch.call_tool("buddy.search_its", {"q": "test"})
    # В client.call_tool ушло имя БЕЗ префикса
    assert client.calls[0][0] == "search_its"


@pytest.mark.asyncio
async def test_call_tool_no_namespace_raises() -> None:
    orch = MCPOrchestrator()
    orch.register("toolkit", FakeMCPClient())
    with pytest.raises(InvalidToolNameError, match="must contain namespace"):
        await orch.call_tool("execute_query", {})


@pytest.mark.asyncio
async def test_call_tool_unknown_namespace_raises() -> None:
    orch = MCPOrchestrator()
    orch.register("toolkit", FakeMCPClient())
    with pytest.raises(UnknownNamespaceError, match="not registered"):
        await orch.call_tool("nonexistent.foo", {})


@pytest.mark.asyncio
async def test_call_tool_empty_tool_after_namespace_raises() -> None:
    """'toolkit.' — namespace без tool — ошибка."""
    orch = MCPOrchestrator()
    orch.register("toolkit", FakeMCPClient())
    with pytest.raises(InvalidToolNameError, match="empty"):
        await orch.call_tool("toolkit.", {})


@pytest.mark.asyncio
async def test_call_tool_preserves_dots_in_tool_name() -> None:
    """split только по ПЕРВОЙ точке: 'toolkit.metadata.get' → 'metadata.get'."""
    orch = MCPOrchestrator()
    client = FakeMCPClient()
    orch.register("toolkit", client)
    await orch.call_tool("toolkit.metadata.get", {})
    assert client.calls[0][0] == "metadata.get"


# ---------------------------------------------------------------------------
# close_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_all_closes_every_client() -> None:
    orch = MCPOrchestrator()
    c1 = FakeMCPClient()
    c2 = FakeMCPClient()
    orch.register("toolkit", c1)
    orch.register("buddy", c2)

    await orch.close_all()

    assert c1.closed is True
    assert c2.closed is True
    assert orch.namespaces() == ()


@pytest.mark.asyncio
async def test_close_all_continues_on_individual_failure() -> None:
    """Если один client.aclose() падает — остальные всё равно закрываются."""
    orch = MCPOrchestrator()
    broken = FakeMCPClient()

    async def broken_close():
        raise RuntimeError("boom")
    broken.aclose = broken_close  # type: ignore[method-assign]
    good = FakeMCPClient()

    orch.register("toolkit", broken)
    orch.register("buddy", good)

    await orch.close_all()  # не должна выбросить
    assert good.closed is True
    assert orch.namespaces() == ()


# ---------------------------------------------------------------------------
# split_prefixed_name helper
# ---------------------------------------------------------------------------


def test_split_prefixed_name_basic() -> None:
    assert split_prefixed_name("toolkit.execute_query") == ("toolkit", "execute_query")
    assert split_prefixed_name("buddy.search_its") == ("buddy", "search_its")


def test_split_prefixed_name_preserves_dots_in_tool() -> None:
    assert split_prefixed_name("toolkit.meta.get") == ("toolkit", "meta.get")


def test_split_prefixed_name_normalizes_namespace() -> None:
    ns, tool = split_prefixed_name("ToolKit.execute_query")
    assert ns == "toolkit"


def test_split_prefixed_name_no_dot_raises() -> None:
    with pytest.raises(InvalidToolNameError, match="must contain namespace"):
        split_prefixed_name("execute_query")


def test_split_prefixed_name_empty_parts_raise() -> None:
    with pytest.raises(InvalidToolNameError, match="empty"):
        split_prefixed_name(".tool")
    with pytest.raises(InvalidToolNameError, match="empty"):
        split_prefixed_name("ns.")


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


def test_fake_client_satisfies_protocol() -> None:
    """Sanity: FakeMCPClient должен удовлетворять MCPClientProtocol."""
    client: Any = FakeMCPClient()
    # @runtime_checkable Protocol позволяет isinstance check
    assert isinstance(client, MCPClientProtocol)


def test_orchestrator_repr() -> None:
    orch = MCPOrchestrator()
    orch.register("toolkit", FakeMCPClient())
    s = repr(orch)
    assert "MCPOrchestrator" in s
    assert "toolkit" in s
