"""Routes edge cases — sessions DELETE 404, PATCH invalid, GET non-existent;
connections DELETE cascade; mcp backward compat Phase 1 query param.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    """AsyncClient с lifespan и изолированной in-memory БД."""
    import os

    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["APP_VERSION"] = "0.1.0-test"
    os.environ["BACKEND_ALLOWED_ORIGINS"] = "http://localhost:3010"

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        async with app.router.lifespan_context(app):
            yield ac


# ---------------------------------------------------------------------------
# sessions — DELETE 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sessions_delete_nonexistent_404(client: AsyncClient):
    """DELETE /sessions/{id} для несуществующей сессии → 404."""
    response = await client.delete("/sessions/no-such-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# sessions — PATCH 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sessions_patch_nonexistent_404(client: AsyncClient):
    """PATCH /sessions/{id} для несуществующей сессии → 404."""
    response = await client.patch("/sessions/no-such-id", json={"title": "Новый заголовок"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# sessions — PATCH с пустым title → 422 (min_length=1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sessions_patch_empty_title_422(client: AsyncClient):
    """PATCH /sessions/{id} с title='' → 422 (Pydantic min_length=1)."""
    response = await client.patch("/sessions/any-id", json={"title": ""})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# sessions — GET /sessions/{id}/messages для несуществующей → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sessions_get_messages_nonexistent_404(client: AsyncClient):
    """GET /sessions/{id}/messages для несуществующей сессии → 404."""
    response = await client.get("/sessions/no-such-id/messages")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# sessions — GET /sessions/{id} для несуществующей → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sessions_get_detail_nonexistent_404(client: AsyncClient):
    """GET /sessions/{id} для несуществующей сессии → 404."""
    response = await client.get("/sessions/no-such-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# connections — GET с пустой таблицей → {connections:[]}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connections_get_empty(client: AsyncClient):
    """GET /connections при пустой таблице → {"connections":[]}."""
    response = await client.get("/connections")
    assert response.status_code == 200
    assert response.json() == {"connections": []}


# ---------------------------------------------------------------------------
# connections — PUT /connections/{id} с ftp:// endpoint → 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connections_put_invalid_endpoint_422(client: AsyncClient):
    """PUT /connections/{id} с endpoint='ftp://x' → 422 (Pydantic validator)."""
    # Сначала создаём connection
    create_resp = await client.post(
        "/connections",
        json={"name": "Test", "endpoint": "http://localhost:6010/mcp"},
    )
    assert create_resp.status_code == 201
    conn_id = create_resp.json()["id"]

    # Пытаемся обновить с невалидным endpoint
    update_resp = await client.put(
        f"/connections/{conn_id}",
        json={"endpoint": "ftp://invalid"},
    )
    assert update_resp.status_code == 422


# ---------------------------------------------------------------------------
# connections — DELETE несуществующего → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connections_delete_nonexistent_404(client: AsyncClient):
    """DELETE /connections/{id} для несуществующего → 404."""
    response = await client.delete("/connections/no-such-conn-id")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# connections — ping unknown id → 404
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connections_ping_unknown_id_404(client: AsyncClient):
    """POST /connections/{id}/ping для несуществующего → 404."""
    response = await client.post("/connections/unknown-conn-id/ping")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# connections — ping MCP error → 502
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connections_ping_mcp_error_502(client: AsyncClient, monkeypatch):
    """POST /connections/{id}/ping когда MCP initialize() бросает → 502."""
    import app.routes.connections as connections_module

    class BrokenMCPClient:
        def __init__(self, *a, **kw): pass

        async def initialize(self):
            raise RuntimeError("Connection refused")

        async def list_tools(self):
            return []

        async def aclose(self): pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr(connections_module, "MCPClient", BrokenMCPClient)

    # Создаём connection
    create_resp = await client.post(
        "/connections",
        json={"name": "Broken", "endpoint": "http://broken:9999/mcp"},
    )
    assert create_resp.status_code == 201
    conn_id = create_resp.json()["id"]

    # Ping должен вернуть 502
    ping_resp = await client.post(f"/connections/{conn_id}/ping")
    assert ping_resp.status_code == 502


# ---------------------------------------------------------------------------
# mcp route — backward compat Phase 1 query param ?endpoint=
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_route_backward_compat_phase1_query_param(client: AsyncClient, monkeypatch):
    """POST /mcp/_/ping?endpoint=… → 200 (Phase 1 path)."""
    import app.routes.mcp as mcp_module
    from app.clients.mcp import MCPSession

    class FakeMCPClient:
        def __init__(self, *a, **kw): pass

        async def initialize(self):
            return MCPSession(
                session_id="fake-sid",
                mcp_version="2025-03-26",
                server_name="fake-server",
                tools=[],
            )

        async def list_tools(self):
            return [{"name": "tool1"}]

        async def aclose(self): pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr(mcp_module, "MCPClient", FakeMCPClient)

    # Phase 1 backward compat — endpoint через query param, conn_id = "_"
    response = await client.post("/mcp/_/ping?endpoint=http://localhost:6010/mcp")
    assert response.status_code == 200
    data = response.json()
    assert data["mcp_version"] == "2025-03-26"
    assert data["tool_count"] == 1
