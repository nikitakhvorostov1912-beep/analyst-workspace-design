"""Тесты GET /connections/{channel_id}/metadata-suggest endpoint."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_metadata_suggest_404_unknown_channel(client):
    """404 если channel_id не найден в mcp_connections."""
    resp = await client.get("/connections/nonexistent-channel-id/metadata-suggest?q=Д")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_metadata_suggest_cache_hit_returns_cached(client):
    """Свежий кеш → возвращает cached=true без обращения к MCP."""
    # Создаём соединение
    r = await client.post(
        "/connections",
        json={"name": "test", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    # Заполняем кеш напрямую через db в lifespan
    from app.main import app

    db = app.state.db
    await db.execute(
        """
        INSERT INTO metadata_cache (channel_id, object_path, object_type, name, presentation, fetched_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (ch_id, "Документ.ОПП", "Документ", "ОПП", "Оформление перевозки"),
    )
    await db.commit()

    # Запрашиваем — должен вернуть из кеша
    resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=ОПП")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is True
    assert data["stale"] is False
    assert len(data["items"]) >= 1
    assert data["items"][0]["name"] == "ОПП"


@pytest.mark.asyncio
async def test_metadata_suggest_cache_miss_refreshes_via_mcp(client):
    """При отсутствии кеша — обращается к MCP get_metadata и заполняет кеш."""
    r = await client.post(
        "/connections",
        json={"name": "test-refresh", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    mock_session = MagicMock()
    mock_session.mcp_version = "2025-03-26"
    mock_session.session_id = "test-session"

    mock_tools = [
        {"name": "get_metadata", "description": ""},
        {"name": "execute_query", "description": ""},
    ]

    mock_result = [
        {"name": "ОПП", "object_type": "Документ", "full_path": "Документ.ОПП"},
        {"name": "Контрагенты", "object_type": "Справочник", "full_path": "Справочник.Контрагенты"},
    ]

    with patch("app.routes.connections.MCPClient") as MockMCP:
        mock_client = AsyncMock()
        mock_client.initialize = AsyncMock(return_value=mock_session)
        mock_client.list_tools = AsyncMock(return_value=mock_tools)
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockMCP.return_value = mock_client

        resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=ОПП")

    assert resp.status_code == 200
    data = resp.json()
    assert data["cached"] is True
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_metadata_suggest_cache_stale_refreshes(client):
    """Устаревший кеш (старше TTL) → обновляется через MCP."""
    r = await client.post(
        "/connections",
        json={"name": "stale-test", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    from app.main import app

    db = app.state.db
    # Вставляем устаревшую запись (2 часа назад)
    stale_time = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        """
        INSERT INTO metadata_cache (channel_id, object_path, object_type, name, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ch_id, "Справочник.Старый", "Справочник", "Старый", stale_time),
    )
    await db.commit()

    mock_session = MagicMock()
    mock_session.mcp_version = "2025-03-26"
    mock_session.session_id = "sess"

    mock_tools = [{"name": "get_metadata"}]
    mock_result = [
        {"name": "Новый", "object_type": "Справочник", "full_path": "Справочник.Новый"}
    ]

    with patch("app.routes.connections.MCPClient") as MockMCP:
        mock_client = AsyncMock()
        mock_client.initialize = AsyncMock(return_value=mock_session)
        mock_client.list_tools = AsyncMock(return_value=mock_tools)
        mock_client.call_tool = AsyncMock(return_value=mock_result)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockMCP.return_value = mock_client

        resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=Н")

    assert resp.status_code == 200
    data = resp.json()
    # После refresh stale=False
    assert data["stale"] is False


@pytest.mark.asyncio
async def test_metadata_suggest_filter_by_q_prefix(client):
    """Фильтр q=Д находит объекты начинающиеся с Д."""
    r = await client.post(
        "/connections",
        json={"name": "filter-prefix", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    from app.main import app

    db = app.state.db
    for name, path, otype in [
        ("ОПП", "Документ.ОПП", "Документ"),
        ("Контрагенты", "Справочник.Контрагенты", "Справочник"),
        ("Договоры", "Документ.Договоры", "Документ"),
    ]:
        await db.execute(
            """
            INSERT INTO metadata_cache (channel_id, object_path, object_type, name, fetched_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (ch_id, path, otype, name),
        )
    await db.commit()

    resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=Д")
    assert resp.status_code == 200
    data = resp.json()
    names = [item["name"] for item in data["items"]]
    assert "Договоры" in names


@pytest.mark.asyncio
async def test_metadata_suggest_filter_by_q_substring(client):
    """Фильтр q=онтраг (подстрока) находит Контрагенты."""
    r = await client.post(
        "/connections",
        json={"name": "filter-substr", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    from app.main import app

    db = app.state.db
    await db.execute(
        """
        INSERT INTO metadata_cache (channel_id, object_path, object_type, name, fetched_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (ch_id, "Справочник.Контрагенты", "Справочник", "Контрагенты"),
    )
    await db.commit()

    resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=онтраг")
    assert resp.status_code == 200
    data = resp.json()
    names = [item["name"] for item in data["items"]]
    # substring match через LIKE %онтраг%
    assert "Контрагенты" in names


@pytest.mark.asyncio
async def test_metadata_suggest_limit_respected(client):
    """Параметр limit ограничивает количество результатов."""
    r = await client.post(
        "/connections",
        json={"name": "limit-test", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    from app.main import app

    db = app.state.db
    # Вставляем 10 записей
    for i in range(10):
        await db.execute(
            """
            INSERT INTO metadata_cache (channel_id, object_path, object_type, name, fetched_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (ch_id, f"Справочник.Имя{i}", "Справочник", f"Имя{i}"),
        )
    await db.commit()

    resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=Имя&limit=3")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 3


@pytest.mark.asyncio
async def test_metadata_suggest_mcp_fails_returns_stale_with_flag(client):
    """MCP недоступен + есть устаревший кеш → stale=true."""
    r = await client.post(
        "/connections",
        json={"name": "stale-fallback", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    from app.main import app

    db = app.state.db
    stale_time = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
    await db.execute(
        """
        INSERT INTO metadata_cache (channel_id, object_path, object_type, name, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (ch_id, "Справочник.Старый", "Справочник", "Старый", stale_time),
    )
    await db.commit()

    with patch("app.routes.connections.MCPClient") as MockMCP:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.initialize = AsyncMock(side_effect=Exception("Connection refused"))
        MockMCP.return_value = mock_client

        resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=С")

    assert resp.status_code == 200
    data = resp.json()
    assert data["stale"] is True


@pytest.mark.asyncio
async def test_metadata_suggest_mcp_fails_cache_empty_returns_502(client):
    """MCP недоступен + кеш пуст → 502."""
    r = await client.post(
        "/connections",
        json={"name": "empty-cache-fail", "endpoint": "http://localhost:6010/mcp"},
    )
    ch_id = r.json()["id"]

    with patch("app.routes.connections.MCPClient") as MockMCP:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.initialize = AsyncMock(side_effect=Exception("Connection refused"))
        MockMCP.return_value = mock_client

        resp = await client.get(f"/connections/{ch_id}/metadata-suggest?q=Д")

    assert resp.status_code == 502


@pytest.mark.asyncio
async def test_metadata_suggest_strict_extra_field_rejected(client):
    """MetadataSuggestResponse — extra fields forbidden в модели."""
    from app.models import MetadataSuggestResponse, MetadataSuggestItem
    import pytest

    # Попытка создать с лишним полем — должна упасть
    with pytest.raises(Exception):
        MetadataSuggestResponse(
            items=[],
            cached=True,
            stale=False,
            extra_field="forbidden",  # type: ignore
        )
