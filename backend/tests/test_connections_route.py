"""Тесты CRUD /connections."""

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# GET /connections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_connections_empty(client: AsyncClient):
    """GET /connections с пустой БД → {connections: []}."""
    response = await client.get("/connections")
    assert response.status_code == 200
    data = response.json()
    assert data == {"connections": []}


# ---------------------------------------------------------------------------
# POST /connections
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_connection_success(client: AsyncClient):
    """POST /connections → 201, UUID id, last_seen_at=null."""
    response = await client.post(
        "/connections",
        json={"name": "Транзит", "endpoint": "http://localhost:6010/mcp", "channel": "prod"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Транзит"
    assert data["endpoint"] == "http://localhost:6010/mcp"
    assert data["channel"] == "prod"
    assert data["anon_enabled"] is False
    assert data["last_seen_at"] is None
    assert "created_at" in data
    # UUID4 format: 8-4-4-4-12 символов
    parts = data["id"].split("-")
    assert len(parts) == 5


@pytest.mark.asyncio
async def test_create_connection_invalid_endpoint(client: AsyncClient):
    """POST /connections с endpoint без http:// → 422."""
    response = await client.post(
        "/connections",
        json={"name": "Test", "endpoint": "not-a-url"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_connection_empty_name(client: AsyncClient):
    """POST /connections с пустым name → 422."""
    response = await client.post(
        "/connections",
        json={"name": "", "endpoint": "http://localhost:6010/mcp"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# SEC-1: SSRF guard integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_connection_blocks_aws_metadata(client: AsyncClient):
    """SEC-1: POST с AWS metadata IP должен вернуть 400 (link-local blocked)."""
    response = await client.post(
        "/connections",
        json={
            "name": "Pwn me",
            "endpoint": "http://169.254.169.254/latest/meta-data/",
        },
    )
    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error_code"] == "unsafe_endpoint"
    # Сообщение должно ссылаться на link-local / небезопасный IP.
    msg = payload["detail"]["message"].lower()
    assert "link-local" in msg or "небезопасн" in msg or "169.254" in msg


@pytest.mark.asyncio
async def test_create_connection_blocks_private_ip(client: AsyncClient):
    """SEC-1: POST с private IP (192.168.x) должен вернуть 400."""
    response = await client.post(
        "/connections",
        json={
            "name": "Router",
            "endpoint": "http://192.168.1.1/",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "unsafe_endpoint"


@pytest.mark.asyncio
async def test_create_connection_blocks_localhost_redis(client: AsyncClient):
    """SEC-1: 127.0.0.1 разрешён (whitelist), даже если порт Redis.

    Это намеренно: для аналитика legitimate use-case — MCP Toolkit EPF на
    той же машине. Защита уровня «не давать атаковать чужие сети», а не
    «не давать стрелять себе в ногу».
    """
    response = await client.post(
        "/connections",
        json={
            "name": "Local MCP",
            "endpoint": "http://127.0.0.1:6379/",  # Redis port, но localhost
        },
    )
    # 201 потому что localhost — whitelist
    # (если хочется блокировать opasные порты, нужен отдельный port-list).
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_connection_blocks_file_scheme(client: AsyncClient):
    """SEC-1: file:// URL должен быть отклонён."""
    response = await client.post(
        "/connections",
        json={
            "name": "evil",
            "endpoint": "file:///etc/passwd",
        },
    )
    # 422 (Pydantic) ИЛИ 400 (SSRF guard) — оба валидны.
    # Pydantic должен поймать первым потому что не http/https.
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_update_connection_blocks_unsafe_endpoint(client: AsyncClient):
    """SEC-1: PUT с unsafe endpoint должен вернуть 400."""
    # Сначала создаём валидное.
    create_resp = await client.post(
        "/connections",
        json={"name": "Test", "endpoint": "http://localhost:6010/mcp"},
    )
    assert create_resp.status_code == 201
    conn_id = create_resp.json()["id"]

    # Пытаемся подменить на unsafe.
    update_resp = await client.put(
        f"/connections/{conn_id}",
        json={"endpoint": "http://10.0.0.1/admin"},
    )
    assert update_resp.status_code == 400
    assert update_resp.json()["detail"]["error_code"] == "unsafe_endpoint"


@pytest.mark.asyncio
async def test_list_connections_after_create(client: AsyncClient):
    """GET /connections после POST → возвращает 1 connection."""
    await client.post(
        "/connections",
        json={"name": "База 1", "endpoint": "https://example.com/mcp"},
    )
    response = await client.get("/connections")
    assert response.status_code == 200
    data = response.json()
    assert len(data["connections"]) == 1
    assert data["connections"][0]["name"] == "База 1"


# ---------------------------------------------------------------------------
# PUT /connections/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_connection_partial(client: AsyncClient):
    """PUT /connections/{id} с {anon_enabled: true} → 200, остальные поля сохранены."""
    create_resp = await client.post(
        "/connections",
        json={"name": "МояБаза", "endpoint": "http://localhost:6010/mcp"},
    )
    conn_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/connections/{conn_id}",
        json={"anon_enabled": True},
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["anon_enabled"] is True
    assert data["name"] == "МояБаза"
    assert data["endpoint"] == "http://localhost:6010/mcp"


@pytest.mark.asyncio
async def test_update_connection_not_found(client: AsyncClient):
    """PUT /connections/{nonexistent} → 404."""
    response = await client.put(
        "/connections/nonexistent-id",
        json={"name": "Новое имя"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /connections/{id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_connection(client: AsyncClient):
    """DELETE /connections/{id} → 204; повторно → 404."""
    create_resp = await client.post(
        "/connections",
        json={"name": "ДляУдаления", "endpoint": "http://localhost:6010/mcp"},
    )
    conn_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/connections/{conn_id}")
    assert delete_resp.status_code == 204

    delete_again = await client.delete(f"/connections/{conn_id}")
    assert delete_again.status_code == 404


# ---------------------------------------------------------------------------
# POST /connections/{id}/ping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ping_connection_success(client: AsyncClient, monkeypatch):
    """POST /connections/{id}/ping с мокнутым MCPClient → 200 + обновляет last_seen_at."""
    import app.routes.connections as conn_module
    from app.clients.mcp import MCPSession

    class StubMCPClient:
        def __init__(self, *_a, **_kw) -> None:
            pass

        async def initialize(self) -> MCPSession:
            return MCPSession(
                session_id="stub-ping-session",
                mcp_version="2025-03-26",
                server_name="stub",
                tools=[],
            )

        async def list_tools(self) -> list[dict]:
            return [{"name": "execute_query"}, {"name": "get_metadata"}]

        async def close(self) -> None:
            pass

        async def __aenter__(self) -> "StubMCPClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(conn_module, "MCPClient", StubMCPClient)

    create_resp = await client.post(
        "/connections",
        json={"name": "ПингБаза", "endpoint": "http://localhost:6010/mcp"},
    )
    assert create_resp.status_code == 201
    conn_id = create_resp.json()["id"]

    # last_seen_at до пинга — null
    assert create_resp.json()["last_seen_at"] is None

    ping_resp = await client.post(f"/connections/{conn_id}/ping")
    assert ping_resp.status_code == 200
    data = ping_resp.json()
    assert data["tool_count"] == 2
    assert data["session_id"] == "stub-ping-session"
    assert data["mcp_version"] == "2025-03-26"
    assert "duration_ms" in data
    assert data["last_seen_at"] is not None


@pytest.mark.asyncio
async def test_ping_connection_mcp_error(client: AsyncClient, monkeypatch):
    """POST /connections/{id}/ping при ошибке MCPClient → 502, last_seen_at не обновляется."""
    import app.routes.connections as conn_module

    class FailingMCPClient:
        def __init__(self, *_a, **_kw) -> None:
            pass

        async def initialize(self) -> None:
            raise ConnectionError("MCP сервер недоступен")

        async def close(self) -> None:
            pass

        async def __aenter__(self) -> "FailingMCPClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            pass

    monkeypatch.setattr(conn_module, "MCPClient", FailingMCPClient)

    create_resp = await client.post(
        "/connections",
        json={"name": "НедоступнаяБаза", "endpoint": "http://localhost:9999/mcp"},
    )
    conn_id = create_resp.json()["id"]

    ping_resp = await client.post(f"/connections/{conn_id}/ping")
    assert ping_resp.status_code == 502

    # last_seen_at должен оставаться null
    get_resp = await client.get("/connections")
    conns = get_resp.json()["connections"]
    target = next(c for c in conns if c["id"] == conn_id)
    assert target["last_seen_at"] is None


@pytest.mark.asyncio
async def test_ping_connection_not_found(client: AsyncClient):
    """POST /connections/{id}/ping с несуществующим id → 404."""
    response = await client.post("/connections/does-not-exist/ping")
    assert response.status_code == 404
