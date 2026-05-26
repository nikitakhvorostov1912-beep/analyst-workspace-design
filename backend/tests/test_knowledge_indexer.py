"""Tests для backend/app/knowledge/indexer.py (M-K2.1).

Покрытие:
- _normalize_metadata_object — синонимы ключей, fallback, invalid
- parse_metadata_result — list / dict / str / MCP wrap content / nested
- write_cache_batch — full vs incremental + persisted строки
- bulk_refresh_metadata_cache — integration: monkeypatched MCP +
  aiosqlite + проверка IndexerProgress + content в metadata_cache

MCP замокан через monkeypatch — никаких настоящих HTTP-вызовов.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.indexer import (
    IndexerProgress,
    NormalizedMetadata,
    _normalize_metadata_object,
    bulk_refresh_metadata_cache,
    parse_metadata_result,
    write_cache_batch,
)
from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


# ---------- _normalize_metadata_object ----------


def test_normalize_basic_lowercase_keys():
    obj = {
        "name": "ОПП",
        "type": "Документ",
        "presentation": "Отгрузка под перевозку",
        "full_path": "Документ.ОПП",
    }
    result = _normalize_metadata_object(obj)
    assert result == NormalizedMetadata(
        object_path="Документ.ОПП",
        object_type="Документ",
        name="ОПП",
        presentation="Отгрузка под перевозку",
    )


def test_normalize_uppercase_synonyms():
    """Name / Type / Synonym — допустимые синонимы lowercase ключей."""
    obj = {"Name": "Контрагенты", "Type": "Справочник", "Synonym": "Контрагенты"}
    result = _normalize_metadata_object(obj)
    assert result is not None
    assert result.object_path == "Справочник.Контрагенты"
    assert result.presentation == "Контрагенты"


def test_normalize_full_path_explicit_overrides_construction():
    """Если в obj есть full_path — используем его без склейки type+name."""
    obj = {
        "name": "Х",
        "type": "Y",
        "full_path": "Custom.Path.X",
    }
    result = _normalize_metadata_object(obj)
    assert result is not None
    assert result.object_path == "Custom.Path.X"


def test_normalize_path_synonym():
    """path — синоним full_path."""
    obj = {"name": "Z", "type": "Q", "path": "Q.Z"}
    result = _normalize_metadata_object(obj)
    assert result is not None
    assert result.object_path == "Q.Z"


def test_normalize_constructs_path_when_missing():
    obj = {"name": "X", "type": "Y"}
    result = _normalize_metadata_object(obj)
    assert result is not None
    assert result.object_path == "Y.X"


def test_normalize_returns_none_when_no_name_and_no_type():
    obj = {"presentation": "только описание"}
    result = _normalize_metadata_object(obj)
    assert result is None


def test_normalize_handles_name_only_no_type():
    """Только name без type — fallback в object_path == name."""
    obj = {"name": "БезТипа"}
    result = _normalize_metadata_object(obj)
    assert result is not None
    assert result.object_path == "БезТипа"
    assert result.object_type == ""


def test_normalize_presentation_none_when_empty_string():
    obj = {"name": "A", "type": "B", "presentation": ""}
    result = _normalize_metadata_object(obj)
    assert result is not None
    assert result.presentation is None


def test_normalize_strips_whitespace():
    obj = {"name": "  ОПП  ", "type": "  Документ  "}
    result = _normalize_metadata_object(obj)
    assert result is not None
    assert result.name == "ОПП"
    assert result.object_type == "Документ"


# ---------- parse_metadata_result ----------


def test_parse_plain_list():
    raw = [
        {"name": "A", "type": "Документ"},
        {"name": "B", "type": "Справочник"},
    ]
    result = parse_metadata_result(raw)
    assert len(result) == 2
    assert result[0].object_path == "Документ.A"
    assert result[1].object_path == "Справочник.B"


def test_parse_dict_wrapped_in_objects():
    raw = {"objects": [{"name": "X", "type": "Y"}]}
    result = parse_metadata_result(raw)
    assert len(result) == 1
    assert result[0].object_path == "Y.X"


def test_parse_dict_wrapped_in_items():
    raw = {"items": [{"name": "X", "type": "Y"}]}
    result = parse_metadata_result(raw)
    assert len(result) == 1


def test_parse_dict_wrapped_in_result():
    raw = {"result": [{"name": "X", "type": "Y"}]}
    result = parse_metadata_result(raw)
    assert len(result) == 1


def test_parse_mcp_text_wrap_with_json():
    """MCP-формат {"content": [{"type":"text", "text": "<json>"}]} разворачивается."""
    payload = [{"name": "ОПП", "type": "Документ"}]
    raw = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    result = parse_metadata_result(raw)
    assert len(result) == 1
    assert result[0].object_path == "Документ.ОПП"


def test_parse_string_with_json():
    raw = json.dumps([{"name": "A", "type": "Документ"}])
    result = parse_metadata_result(raw)
    assert len(result) == 1


def test_parse_invalid_string_returns_empty():
    assert parse_metadata_result("not a json") == []


def test_parse_unknown_type_returns_empty():
    assert parse_metadata_result(42) == []
    assert parse_metadata_result(None) == []


def test_parse_filters_invalid_items():
    raw = [
        {"name": "A", "type": "Документ"},
        {"presentation": "Без name/type — должно быть пропущено"},
        "не dict",
        {"name": "B", "type": "Справочник"},
    ]
    result = parse_metadata_result(raw)
    assert len(result) == 2
    assert {r.name for r in result} == {"A", "B"}


# ---------- write_cache_batch ----------


@pytest.mark.asyncio
async def test_write_cache_batch_writes_rows(db):
    objects = [
        NormalizedMetadata("Документ.ОПП", "Документ", "ОПП", "Отгрузка"),
        NormalizedMetadata("Справочник.К", "Справочник", "К", None),
    ]
    written = await write_cache_batch(db, "ch-1", objects)
    assert written == 2

    cursor = await db.execute(
        "SELECT object_path, object_type, presentation FROM metadata_cache "
        "WHERE channel_id = ? ORDER BY object_path",
        ("ch-1",),
    )
    rows = await cursor.fetchall()
    assert rows == [
        ("Документ.ОПП", "Документ", "Отгрузка"),
        ("Справочник.К", "Справочник", None),
    ]


@pytest.mark.asyncio
async def test_write_cache_batch_replace_existing_clears_old(db):
    """replace_existing=True должен очистить старые записи для канала."""
    old = [NormalizedMetadata("Документ.Old", "Документ", "Old", None)]
    await write_cache_batch(db, "ch-1", old)

    new = [NormalizedMetadata("Документ.New", "Документ", "New", None)]
    await write_cache_batch(db, "ch-1", new, replace_existing=True)

    cursor = await db.execute(
        "SELECT object_path FROM metadata_cache WHERE channel_id = ?",
        ("ch-1",),
    )
    rows = await cursor.fetchall()
    assert rows == [("Документ.New",)]


@pytest.mark.asyncio
async def test_write_cache_batch_incremental_keeps_old_and_upserts(db):
    """replace_existing=False — старые остаются, дубликаты обновляются."""
    initial = [
        NormalizedMetadata("Документ.A", "Документ", "A", "v1"),
        NormalizedMetadata("Документ.B", "Документ", "B", None),
    ]
    await write_cache_batch(db, "ch-1", initial, replace_existing=False)

    update = [
        NormalizedMetadata("Документ.A", "Документ", "A", "v2"),  # обновляется
        NormalizedMetadata("Документ.C", "Документ", "C", None),  # добавляется
    ]
    await write_cache_batch(db, "ch-1", update, replace_existing=False)

    cursor = await db.execute(
        "SELECT object_path, presentation FROM metadata_cache "
        "WHERE channel_id = ? ORDER BY object_path",
        ("ch-1",),
    )
    rows = await cursor.fetchall()
    assert rows == [
        ("Документ.A", "v2"),  # обновлено
        ("Документ.B", None),  # сохранилось
        ("Документ.C", None),  # добавлено
    ]


@pytest.mark.asyncio
async def test_write_cache_batch_empty_is_noop(db):
    """Пустой список не должен ломать executemany."""
    written = await write_cache_batch(db, "ch-1", [], replace_existing=False)
    assert written == 0


@pytest.mark.asyncio
async def test_write_cache_batch_isolates_channels(db):
    """Запись в один канал не задевает другой."""
    await write_cache_batch(
        db, "ch-A", [NormalizedMetadata("Документ.X", "Документ", "X", None)]
    )
    await write_cache_batch(
        db, "ch-B", [NormalizedMetadata("Документ.Y", "Документ", "Y", None)]
    )

    cursor = await db.execute(
        "SELECT channel_id, object_path FROM metadata_cache ORDER BY channel_id"
    )
    rows = await cursor.fetchall()
    assert rows == [("ch-A", "Документ.X"), ("ch-B", "Документ.Y")]


# ---------- bulk_refresh_metadata_cache (integration с monkeypatched MCP) ----------


class _FakeMCPSession:
    def __init__(self, tools: list[dict], result: object):
        self._tools = tools
        self._result = result
        self.initialized = False

    async def initialize(self):
        self.initialized = True

    async def list_tools(self):
        return self._tools

    async def call_tool(self, name: str, arguments: dict):  # noqa: ARG002
        return self._result


def _patch_mcp(monkeypatch, *, tools: list[dict], result: object):
    """Подменяет `MCPClient` в indexer.py на async context manager fake."""

    fake = _FakeMCPSession(tools, result)

    @asynccontextmanager
    async def fake_client(endpoint: str, headers: dict[str, str] | None = None):  # noqa: ARG001
        yield fake

    monkeypatch.setattr("app.knowledge.indexer.MCPClient", fake_client)
    return fake


@pytest.mark.asyncio
async def test_bulk_refresh_happy_path(db, monkeypatch):
    payload = [
        {"name": "ОПП", "type": "Документ"},
        {"name": "Контрагенты", "type": "Справочник", "presentation": "Контрагенты"},
    ]
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}, {"name": "execute_query"}],
        result=payload,
    )

    progress = await bulk_refresh_metadata_cache(db, "ch-1", "http://fake/mcp")

    assert progress.status == "done"
    assert progress.is_success
    assert progress.objects_total == 2
    assert progress.objects_written == 2
    assert progress.error is None
    assert progress.channel_id == "ch-1"
    assert progress.duration_ms >= 0

    cursor = await db.execute(
        "SELECT object_path FROM metadata_cache WHERE channel_id = ? ORDER BY object_path",
        ("ch-1",),
    )
    rows = await cursor.fetchall()
    assert rows == [("Документ.ОПП",), ("Справочник.Контрагенты",)]


@pytest.mark.asyncio
async def test_bulk_refresh_returns_failed_when_get_metadata_missing(db, monkeypatch):
    """Если у MCP нет get_metadata — status=failed + понятный error."""
    _patch_mcp(monkeypatch, tools=[{"name": "execute_query"}], result=[])

    progress = await bulk_refresh_metadata_cache(db, "ch-1", "http://fake/mcp")

    assert progress.status == "failed"
    assert "get_metadata" in (progress.error or "")
    assert progress.objects_written == 0


@pytest.mark.asyncio
async def test_bulk_refresh_mcp_exception_returns_failed(db, monkeypatch):
    """Если MCP-вызов raises — IndexerProgress(failed) вместо raise."""

    class _ExplodingSession:
        async def initialize(self):
            raise RuntimeError("network down")

        async def list_tools(self):
            return []

        async def call_tool(self, name, arguments):  # noqa: ARG002
            return None

    @asynccontextmanager
    async def boom(endpoint: str, headers: dict[str, str] | None = None):  # noqa: ARG001
        yield _ExplodingSession()

    monkeypatch.setattr("app.knowledge.indexer.MCPClient", boom)

    progress = await bulk_refresh_metadata_cache(db, "ch-1", "http://fake/mcp")

    assert progress.status == "failed"
    assert "network down" in (progress.error or "")
    assert progress.objects_written == 0


@pytest.mark.asyncio
async def test_bulk_refresh_replaces_old_cache_entries(db, monkeypatch):
    """Full refresh должен затирать старые записи канала."""
    # Pre-seed старыми данными
    from app.knowledge.dossier import fill_cache_entry
    await fill_cache_entry(db, "ch-1", "Документ.OldOne", "Документ", "OldOne", None)

    payload = [{"name": "NewOne", "type": "Документ"}]
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}],
        result=payload,
    )

    progress = await bulk_refresh_metadata_cache(db, "ch-1", "http://fake/mcp")
    assert progress.status == "done"

    cursor = await db.execute(
        "SELECT object_path FROM metadata_cache WHERE channel_id = ?",
        ("ch-1",),
    )
    rows = await cursor.fetchall()
    assert rows == [("Документ.NewOne",)]


@pytest.mark.asyncio
async def test_bulk_refresh_handles_mcp_text_wrap(db, monkeypatch):
    """MCP wrap {"content": [{"type": "text", "text": "<json>"}]} разворачивается."""
    payload = [{"name": "X", "type": "Документ"}]
    wrapped: dict[str, Any] = {
        "content": [{"type": "text", "text": json.dumps(payload)}]
    }
    _patch_mcp(monkeypatch, tools=[{"name": "get_metadata"}], result=wrapped)

    progress = await bulk_refresh_metadata_cache(db, "ch-1", "http://fake/mcp")
    assert progress.status == "done"
    assert progress.objects_written == 1


@pytest.mark.asyncio
async def test_bulk_refresh_empty_payload_succeeds_with_zero_objects(db, monkeypatch):
    """Канал без объектов — это валидно, status=done, objects=0."""
    _patch_mcp(monkeypatch, tools=[{"name": "get_metadata"}], result=[])

    progress = await bulk_refresh_metadata_cache(db, "ch-1", "http://fake/mcp")
    assert progress.status == "done"
    assert progress.objects_total == 0
    assert progress.objects_written == 0
