"""Tests for admin endpoints — Phase 9.1 privacy escape hatches."""

import pytest


@pytest.mark.asyncio
async def test_reset_requires_confirm_header(client):
    """POST /admin/reset-local-db без X-Confirm-Reset → 422 (missing header)."""
    r = await client.post("/admin/reset-local-db")
    # FastAPI validation вернёт 422 при отсутствии required header
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_reset_wrong_confirm_value(client):
    """POST с X-Confirm-Reset='false' → 400 (защита от случайных вызовов)."""
    r = await client.post(
        "/admin/reset-local-db",
        headers={"X-Confirm-Reset": "false"},
    )
    assert r.status_code == 400
    assert "X-Confirm-Reset" in r.json()["detail"]


@pytest.mark.asyncio
async def test_reset_clears_sessions(client):
    """POST с X-Confirm-Reset='true' → 200 + удаляет sessions/messages."""
    # arrange: создаём session + message
    session_resp = await client.post(
        "/sessions",
        json={"title": "test", "channel_id": "test-channel"},
    )
    assert session_resp.status_code == 200
    session_id = session_resp.json()["id"]

    # act: reset
    reset_resp = await client.post(
        "/admin/reset-local-db",
        headers={"X-Confirm-Reset": "true"},
    )
    assert reset_resp.status_code == 200

    body = reset_resp.json()
    assert body["status"] == "ok"
    assert "sessions" in body["cleared"]
    assert "messages" in body["cleared"]

    # assert: session исчезла
    get_resp = await client.get(f"/sessions/{session_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_reset_preserves_connections(client):
    """Reset не удаляет mcp_connections (настройки подключений сохраняются)."""
    # arrange: создаём MCP connection
    create_resp = await client.post(
        "/connections",
        json={
            "name": "test-mcp",
            "endpoint": "http://localhost:6010/mcp",
            "channel": None,
            "anon_enabled": False,
        },
    )
    assert create_resp.status_code in (200, 201)

    # act: reset
    reset_resp = await client.post(
        "/admin/reset-local-db",
        headers={"X-Confirm-Reset": "true"},
    )
    assert reset_resp.status_code == 200

    # assert: connection всё ещё существует — нормализуем как list или dict.items
    list_resp = await client.get("/connections")
    assert list_resp.status_code == 200
    payload = list_resp.json()

    # /connections может возвращать либо list[dict], либо dict с ключом "connections"
    if isinstance(payload, dict):
        items = payload.get("connections") or payload.get("items") or list(payload.values())
    else:
        items = payload

    names = [c.get("name") for c in items if isinstance(c, dict)]
    assert "test-mcp" in names, f"test-mcp not found in {names}"


@pytest.mark.asyncio
async def test_reset_returns_only_existing_tables(client):
    """Reset возвращает в `cleared` только те таблицы, которые реально удалось очистить."""
    r = await client.post(
        "/admin/reset-local-db",
        headers={"X-Confirm-Reset": "true"},
    )
    assert r.status_code == 200

    cleared = r.json()["cleared"]
    # Все 4 RESET_TABLES должны быть успешно очищены в свежей DB
    assert "messages" in cleared
    assert "sessions" in cleared
    assert "card_states" in cleared
    assert "metadata_cache" in cleared

    # Не должны быть в cleared
    assert "mcp_connections" not in cleared
    assert "llm_settings" not in cleared
    assert "schema_version" not in cleared
