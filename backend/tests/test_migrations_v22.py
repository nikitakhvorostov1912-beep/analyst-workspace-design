"""Тесты миграции v22 (M-K4 ИТС-KB Hybrid): FTS5 для its_chunks + bsp_chunks.

Покрытие:
- v22 создаёт its_chunks_fts + bsp_chunks_fts + 6 триггеров; версия >= 22
- INSERT/UPDATE/DELETE триггеры синхронизируют FTS (BM25-матч находит/теряет)
"""

from __future__ import annotations

import aiosqlite
import pytest

from app.storage.migrations import CURRENT_VERSION, apply_migrations


@pytest.mark.asyncio
async def test_v22_creates_fts_tables_and_triggers():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)

        cur = await conn.execute("SELECT MAX(version) FROM schema_version")
        version = (await cur.fetchone())[0]
        assert version == CURRENT_VERSION
        assert version >= 22

        cur = await conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE name IN ('its_chunks_fts', 'bsp_chunks_fts') ORDER BY name"
        )
        assert [r[0] for r in await cur.fetchall()] == ["bsp_chunks_fts", "its_chunks_fts"]

        cur = await conn.execute(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='trigger' AND name LIKE '%chunks_fts%'"
        )
        assert (await cur.fetchone())[0] == 6  # 3 (its) + 3 (bsp)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_v22_its_triggers_sync_fts():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)

        # INSERT trigger → FTS наполняется
        await conn.execute(
            "INSERT INTO its_chunks(object_path,doc_id,chunk_index,title,section_title,"
            "content,category,source_path,char_count,chunk_hash) "
            "VALUES('its:t#0','t',0,'Длительные операции',NULL,"
            "'Как запустить ВыполнитьФункцию в фоне','std','x',10,'h')"
        )
        cur = await conn.execute(
            "SELECT object_path FROM its_chunks_fts WHERE its_chunks_fts MATCH ?",
            ('"выполнитьфункцию"',),
        )
        assert [r[0] for r in await cur.fetchall()] == ["its:t#0"]

        # UPDATE trigger → старый термин уходит, новый появляется
        await conn.execute(
            "UPDATE its_chunks SET content = 'другой текст про транзакцию' WHERE object_path = 'its:t#0'"
        )
        cur = await conn.execute(
            "SELECT object_path FROM its_chunks_fts WHERE its_chunks_fts MATCH ?",
            ('"транзакцию"',),
        )
        assert [r[0] for r in await cur.fetchall()] == ["its:t#0"]
        cur = await conn.execute(
            "SELECT object_path FROM its_chunks_fts WHERE its_chunks_fts MATCH ?",
            ('"выполнитьфункцию"',),
        )
        assert await cur.fetchall() == []

        # DELETE trigger → строка уходит из FTS
        await conn.execute("DELETE FROM its_chunks WHERE object_path = 'its:t#0'")
        cur = await conn.execute(
            "SELECT object_path FROM its_chunks_fts WHERE its_chunks_fts MATCH ?",
            ('"транзакцию"',),
        )
        assert await cur.fetchall() == []
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_v22_bsp_trigger_syncs_fts_by_method_name():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await conn.execute(
            "INSERT INTO bsp_chunks(object_path,module_name,method_name,method_kind,signature,"
            "doc_comment,content,version,source_path,char_count,chunk_hash) "
            "VALUES('bsp:3.2:ОбщегоНазначения.ЗначениеРеквизитаОбъекта','ОбщегоНазначения',"
            "'ЗначениеРеквизитаОбъекта','Функция',"
            "'Функция ЗначениеРеквизитаОбъекта(Ссылка, ИмяРеквизита, Тип)',"
            "'Возвращает значение реквизита объекта','doc + sig','3.2','x',20,'h')"
        )
        cur = await conn.execute(
            "SELECT object_path FROM bsp_chunks_fts WHERE bsp_chunks_fts MATCH ?",
            ('"значениереквизитаобъекта"',),
        )
        assert len(await cur.fetchall()) == 1
    finally:
        await conn.close()
