"""Тесты endpoint POST /sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize.

Plan 04-01 Task 1.
"""

import json
from unittest.mock import AsyncMock, patch

import aiosqlite
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.orchestrator.persistence import save_card_state
from app.routes.log_cards import get_app_db
from app.storage.migrations import apply_migrations


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def fresh_db():
    """Чистая in-memory БД с миграциями для каждого теста."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await apply_migrations(conn)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def client_with_db(fresh_db):
    """AsyncClient с ASGI-транспортом и переопределённой DB dependency."""
    from app.main import app

    async def override_db():
        yield fresh_db

    app.dependency_overrides[get_app_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        async with app.router.lifespan_context(app):
            yield ac, fresh_db

    app.dependency_overrides.pop(get_app_db, None)


async def _seed_card(
    db: aiosqlite.Connection,
    sid: str = "sess-001",
    mid: str = "msg-001",
    cid: str = "card-001",
    channel_id: str = "ch-001",
    anon_tokens: list[str] | None = None,
) -> None:
    """Создаёт session, mcp_connection и card_state для теста."""
    await db.execute(
        "INSERT OR IGNORE INTO sessions (id, title, channel_id) VALUES (?, ?, ?)",
        (sid, "Test Session", channel_id),
    )
    await db.execute(
        "INSERT OR IGNORE INTO mcp_connections (id, name, endpoint) VALUES (?, ?, ?)",
        (channel_id, "Test MCP", "http://localhost:6010/mcp"),
    )
    await db.commit()

    await save_card_state(
        db,
        card_id=cid,
        session_id=sid,
        message_id=mid,
        tool_name="execute_query",
        original_args={"query": "ВЫБРАТЬ * ИЗ Справочник.Контрагенты"},
        channel_id=channel_id,
        anon_tokens=anon_tokens,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deanonymize_200_returns_mapping(client_with_db):
    """POST /deanonymize → 200 с mapping от MCP."""
    client, db = client_with_db

    await _seed_card(db, anon_tokens=["[ORG-001]", "[INN-001]"])

    mcp_result = {
        "content": [
            {"type": "text", "text": json.dumps({"mapping": {"[ORG-001]": "ООО Ромашка", "[INN-001]": "7707123456"}})}
        ]
    }

    class FakeMCP:
        def __init__(self, *a, **kw):
            self.session_id = "fake"

        async def initialize(self):
            pass

        async def call_tool(self, name, args):
            return mcp_result

        async def aclose(self):
            pass

    with patch("app.routes.log_cards.MCPClient", FakeMCP):
        resp = await client.post(
            "/sessions/sess-001/messages/msg-001/cards/card-001/deanonymize",
            json={"tokens": ["[ORG-001]", "[INN-001]"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["mapping"]["[ORG-001]"] == "ООО Ромашка"
    assert data["mapping"]["[INN-001]"] == "7707123456"


@pytest.mark.asyncio
async def test_deanonymize_response_cache_control(client_with_db):
    """Ответ /deanonymize содержит Cache-Control: no-store."""
    client, db = client_with_db

    await _seed_card(db)

    class FakeMCP:
        def __init__(self, *a, **kw):
            pass

        async def initialize(self):
            pass

        async def call_tool(self, name, args):
            return {"mapping": {"[ORG-001]": "ООО Ромашка"}}

        async def aclose(self):
            pass

    with patch("app.routes.log_cards.MCPClient", FakeMCP):
        resp = await client.post(
            "/sessions/sess-001/messages/msg-001/cards/card-001/deanonymize",
            json={"tokens": ["[ORG-001]"]},
        )

    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("cache-control", "").lower()


# ---------------------------------------------------------------------------
# 404 cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deanonymize_404_card_not_found(client_with_db):
    """POST /deanonymize на несуществующий card → 404."""
    client, _ = client_with_db
    resp = await client.post(
        "/sessions/s1/messages/m1/cards/nonexistent/deanonymize",
        json={"tokens": ["[ORG-001]"]},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deanonymize_404_sid_mismatch(client_with_db):
    """POST /deanonymize с неверным sid → 404."""
    client, db = client_with_db

    await _seed_card(db, sid="real-session", mid="msg-001", cid="card-mismatch")

    resp = await client.post(
        "/sessions/wrong-session/messages/msg-001/cards/card-mismatch/deanonymize",
        json={"tokens": ["[ORG-001]"]},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_deanonymize_404_mid_mismatch(client_with_db):
    """POST /deanonymize с неверным mid → 404."""
    client, db = client_with_db

    await _seed_card(db, sid="sess-x", mid="real-msg", cid="card-midmm")

    resp = await client.post(
        "/sessions/sess-x/messages/wrong-msg/cards/card-midmm/deanonymize",
        json={"tokens": ["[ORG-001]"]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 422 validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deanonymize_422_invalid_token_format(client_with_db):
    """POST /deanonymize с невалидным токеном → 422."""
    client, db = client_with_db

    await _seed_card(db)

    resp = await client.post(
        "/sessions/sess-001/messages/msg-001/cards/card-001/deanonymize",
        json={"tokens": ["foo", "bar"]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_deanonymize_422_empty_tokens(client_with_db):
    """POST /deanonymize с пустым массивом токенов → 422."""
    client, db = client_with_db

    await _seed_card(db)

    resp = await client.post(
        "/sessions/sess-001/messages/msg-001/cards/card-001/deanonymize",
        json={"tokens": []},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_deanonymize_strict_mode_rejects_extra_field(client_with_db):
    """DeanonymizeRequest(extra=forbid) отклоняет лишние поля → 422."""
    client, db = client_with_db

    await _seed_card(db)

    resp = await client.post(
        "/sessions/sess-001/messages/msg-001/cards/card-001/deanonymize",
        json={"tokens": ["[ORG-001]"], "extra_field": "oops"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 502 MCP errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deanonymize_502_mcp_disconnected(client_with_db):
    """POST /deanonymize когда MCP недоступен → 502."""
    client, db = client_with_db

    await _seed_card(db)

    from app.clients.mcp import MCPDisconnectedError

    class FakeMCPDisconnected:
        def __init__(self, *a, **kw):
            pass

        async def initialize(self):
            raise MCPDisconnectedError("MCP недоступен")

        async def call_tool(self, name, args):
            pass

        async def aclose(self):
            pass

    with patch("app.routes.log_cards.MCPClient", FakeMCPDisconnected):
        resp = await client.post(
            "/sessions/sess-001/messages/msg-001/cards/card-001/deanonymize",
            json={"tokens": ["[ORG-001]"]},
        )

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_deanonymize_502_mcp_error(client_with_db):
    """POST /deanonymize когда MCP возвращает JSON-RPC ошибку → 502."""
    client, db = client_with_db

    await _seed_card(db)

    from app.clients.mcp import MCPError

    class FakeMCPError:
        def __init__(self, *a, **kw):
            pass

        async def initialize(self):
            pass

        async def call_tool(self, name, args):
            raise MCPError(-32000, "submit_for_deanonymization not available")

        async def aclose(self):
            pass

    with patch("app.routes.log_cards.MCPClient", FakeMCPError):
        resp = await client.post(
            "/sessions/sess-001/messages/msg-001/cards/card-001/deanonymize",
            json={"tokens": ["[ORG-001]"]},
        )

    assert resp.status_code == 502
