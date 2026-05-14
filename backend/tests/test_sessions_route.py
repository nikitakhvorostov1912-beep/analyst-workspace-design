"""Тесты sessions CRUD endpoints (Plan 2.3)."""

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def client():
    """AsyncClient с lifespan и изолированной in-memory БД."""
    import os

    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["APP_VERSION"] = "0.1.0-test"
    os.environ["CORS_ORIGINS"] = "http://localhost:3010"

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        async with app.router.lifespan_context(app):
            yield ac


class TestPostSessions:
    async def test_create_session_ok(self, client: AsyncClient):
        resp = await client.post("/sessions", json={"channel_id": "ch-x"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        # UUID4 формат
        uuid.UUID(data["id"], version=4)
        assert data["channel_id"] == "ch-x"
        assert data["title"] is None
        assert "created_at" in data
        assert "updated_at" in data

    async def test_create_session_with_title(self, client: AsyncClient):
        resp = await client.post("/sessions", json={"channel_id": "ch-x", "title": "Тест"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Тест"

    async def test_create_session_no_channel_id(self, client: AsyncClient):
        resp = await client.post("/sessions", json={})
        assert resp.status_code == 422

    async def test_create_session_empty_channel_id(self, client: AsyncClient):
        resp = await client.post("/sessions", json={"channel_id": ""})
        assert resp.status_code == 422


class TestGetSessionsList:
    async def test_empty_db(self, client: AsyncClient):
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data == {"today": [], "yesterday": [], "this_week": [], "earlier": []}

    async def test_grouping_by_date(self, client: AsyncClient):
        """4 сессии с разными updated_at попадают в правильные группы."""
        now = datetime.now()

        s1 = (await client.post("/sessions", json={"channel_id": "ch"})).json()["id"]
        s2 = (await client.post("/sessions", json={"channel_id": "ch"})).json()["id"]
        s3 = (await client.post("/sessions", json={"channel_id": "ch"})).json()["id"]
        s4 = (await client.post("/sessions", json={"channel_id": "ch"})).json()["id"]

        # Подключаемся к той же БД через app state
        from app.main import app

        db = app.state.db
        # s1 — сегодня (только что создан, updated_at = now — не трогаем)
        # s2 — вчера
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        # s3 — 3 дня назад (this_week)
        three_days = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        # s4 — 30 дней назад (earlier)
        thirty_days = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

        await db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (yesterday, s2))
        await db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (three_days, s3))
        await db.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (thirty_days, s4))
        await db.commit()

        resp = await client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()

        today_ids = [s["id"] for s in data["today"]]
        yesterday_ids = [s["id"] for s in data["yesterday"]]
        this_week_ids = [s["id"] for s in data["this_week"]]
        earlier_ids = [s["id"] for s in data["earlier"]]

        assert s1 in today_ids
        assert s2 in yesterday_ids
        assert s3 in this_week_ids
        assert s4 in earlier_ids

    async def test_channel_id_filter(self, client: AsyncClient):
        """Фильтр по channel_id возвращает только сессии из нужного канала."""
        await client.post("/sessions", json={"channel_id": "ch-A"})
        await client.post("/sessions", json={"channel_id": "ch-A"})
        await client.post("/sessions", json={"channel_id": "ch-B"})

        resp = await client.get("/sessions?channel_id=ch-A")
        assert resp.status_code == 200
        data = resp.json()
        all_sessions = (
            data["today"] + data["yesterday"] + data["this_week"] + data["earlier"]
        )
        assert len(all_sessions) == 2
        for s in all_sessions:
            assert s["channel_id"] == "ch-A"


class TestGetSessionDetail:
    async def test_get_existing(self, client: AsyncClient):
        created = (await client.post("/sessions", json={"channel_id": "ch"})).json()
        resp = await client.get(f"/sessions/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    async def test_get_not_found(self, client: AsyncClient):
        resp = await client.get("/sessions/nonexistent-id")
        assert resp.status_code == 404


class TestGetSessionMessages:
    async def test_messages_with_tool_calls(self, client: AsyncClient):
        """GET /sessions/{id}/messages парсит JSON tool_calls и cards."""
        import json

        # Создаём сессию
        s = (await client.post("/sessions", json={"channel_id": "ch"})).json()
        sid = s["id"]

        # Вставляем 3 сообщения напрямую
        from app.main import app

        db = app.state.db
        import uuid as _uuid

        msg1_id = str(_uuid.uuid4())
        msg2_id = str(_uuid.uuid4())
        msg3_id = str(_uuid.uuid4())

        tool_calls_data = json.dumps([{"id": "tc1", "name": "execute_query", "args": {}}])
        cards_data = json.dumps([{"type": "table", "payload": {"columns": [], "rows": [], "total": 0, "meta": {}}}])

        await db.execute(
            "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, 'user', 'Привет', CURRENT_TIMESTAMP)",
            (msg1_id, sid),
        )
        await db.execute(
            "INSERT INTO messages (id, session_id, role, content, tool_calls, cards, duration_ms, created_at) "
            "VALUES (?, ?, 'assistant', 'Ответ', ?, ?, 500, CURRENT_TIMESTAMP)",
            (msg2_id, sid, tool_calls_data, cards_data),
        )
        await db.execute(
            "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, 'user', 'Второй', CURRENT_TIMESTAMP)",
            (msg3_id, sid),
        )
        await db.commit()

        resp = await client.get(f"/sessions/{sid}/messages")
        assert resp.status_code == 200
        msgs = resp.json()["messages"]
        assert len(msgs) == 3
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        # tool_calls десериализованы из JSON
        assert isinstance(msgs[1]["tool_calls"], list)
        assert len(msgs[1]["tool_calls"]) == 1
        assert isinstance(msgs[1]["cards"], list)
        assert msgs[2]["role"] == "user"

    async def test_messages_not_found(self, client: AsyncClient):
        resp = await client.get("/sessions/nonexistent/messages")
        assert resp.status_code == 404


class TestDeleteSession:
    async def test_delete_existing(self, client: AsyncClient):
        s = (await client.post("/sessions", json={"channel_id": "ch"})).json()
        resp = await client.delete(f"/sessions/{s['id']}")
        assert resp.status_code == 204

    async def test_delete_twice(self, client: AsyncClient):
        s = (await client.post("/sessions", json={"channel_id": "ch"})).json()
        await client.delete(f"/sessions/{s['id']}")
        resp = await client.delete(f"/sessions/{s['id']}")
        assert resp.status_code == 404

    async def test_delete_not_found(self, client: AsyncClient):
        resp = await client.delete("/sessions/nonexistent")
        assert resp.status_code == 404


class TestPatchSession:
    async def test_rename(self, client: AsyncClient):
        s = (await client.post("/sessions", json={"channel_id": "ch"})).json()
        sid = s["id"]

        resp = await client.patch(f"/sessions/{sid}", json={"title": "Новый заголовок"})
        assert resp.status_code == 200
        assert resp.json()["title"] == "Новый заголовок"

        # Проверяем что GET тоже возвращает новый title
        resp2 = await client.get(f"/sessions/{sid}")
        assert resp2.json()["title"] == "Новый заголовок"

    async def test_rename_not_found(self, client: AsyncClient):
        resp = await client.patch("/sessions/nonexistent", json={"title": "Что-то"})
        assert resp.status_code == 404

    async def test_rename_empty_title(self, client: AsyncClient):
        s = (await client.post("/sessions", json={"channel_id": "ch"})).json()
        resp = await client.patch(f"/sessions/{s['id']}", json={"title": ""})
        assert resp.status_code == 422
