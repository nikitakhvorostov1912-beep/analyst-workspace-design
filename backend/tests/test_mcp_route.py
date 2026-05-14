"""Тесты POST /mcp/{conn_id}/ping."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ping_missing_endpoint_returns_400(client: AsyncClient):
    """POST /mcp/test/ping без endpoint → 400."""
    response = await client.post("/mcp/test/ping")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_ping_returns_tool_count(client: AsyncClient, monkeypatch):
    """POST /mcp/test/ping с заглушкой MCPClient → 200 с tool_count и session_id."""
    import app.routes.mcp as mcp_module
    from app.clients.mcp import MCPSession

    class StubMCPClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        async def initialize(self) -> MCPSession:
            return MCPSession(
                session_id="stub-session",
                mcp_version="2025-03-26",
                server_name="stub-server",
                tools=[],
            )

        async def list_tools(self) -> list[dict]:
            return [
                {"name": "execute_query", "description": "Запрос 1С"},
                {"name": "get_metadata", "description": "Метаданные"},
                {"name": "get_event_log", "description": "Журнал"},
            ]

        async def close(self) -> None:
            pass

        async def __aenter__(self) -> "StubMCPClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(mcp_module, "MCPClient", StubMCPClient)

    response = await client.post(
        "/mcp/test/ping",
        headers={"X-MCP-Endpoint": "http://mock/mcp"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tool_count"] == 3
    assert data["session_id"] == "stub-session"
    assert data["mcp_version"] == "2025-03-26"
    assert "duration_ms" in data


@pytest.mark.asyncio
async def test_ping_accepts_endpoint_query_param(client: AsyncClient, monkeypatch):
    """POST /mcp/test/ping принимает endpoint через query параметр."""
    import app.routes.mcp as mcp_module
    from app.clients.mcp import MCPSession

    class StubMCPClient:
        def __init__(self, endpoint: str, *_a, **_kw) -> None:
            self._endpoint = endpoint

        async def initialize(self) -> MCPSession:
            return MCPSession(
                session_id="qp-session",
                mcp_version="2025-03-26",
                server_name="qp-server",
            )

        async def list_tools(self) -> list[dict]:
            return []

        async def close(self) -> None:
            pass

        async def __aenter__(self) -> "StubMCPClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(mcp_module, "MCPClient", StubMCPClient)

    response = await client.post(
        "/mcp/test/ping",
        params={"endpoint": "http://via-query/mcp"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "qp-session"
