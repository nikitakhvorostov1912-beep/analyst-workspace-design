"""Integration-тесты для backend/app/orchestrator/mentions_prefetch.py (M-K1.14).

Используют реальный in-memory aiosqlite + миграции (как metadata_cache test'ы)
для проверки end-to-end: парсинг → fetch from cache → cards + context_block.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
import aiosqlite

from app.knowledge.dossier import fill_cache_entry
from app.orchestrator.mentions_prefetch import (
    MentionPrefetchResult,
    prefetch_mentions,
)
from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def db_with_cache() -> aiosqlite.Connection:
    """In-memory SQLite с применёнными миграциями + одним cached dossier."""
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        # Заполняем metadata_cache одним объектом для тестов «found» path.
        await fill_cache_entry(
            conn,
            channel_id="ch-test",
            object_path="Документ.ОПП",
            object_type="Документ",
            name="ОПП",
            presentation="Отгрузка под перевозку",
        )
        yield conn
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_prefetch_no_mentions_returns_empty_result(db_with_cache):
    result = await prefetch_mentions(db_with_cache, "ch-test", "просто текст без mentions")
    assert isinstance(result, MentionPrefetchResult)
    assert result.cards == []
    assert result.context_block is None
    assert result.mentions == []
    assert result.found_count == 0
    assert result.not_found_count == 0


@pytest.mark.asyncio
async def test_prefetch_single_found_mention(db_with_cache):
    result = await prefetch_mentions(
        db_with_cache, "ch-test", "расскажи про @Документ.ОПП"
    )
    assert len(result.mentions) == 1
    assert result.found_count == 1
    assert result.not_found_count == 0
    assert len(result.cards) == 1
    card = result.cards[0]
    assert card["type"] == "object"
    assert card["payload"]["header"]["path"] == "Документ.ОПП"
    assert card["payload"]["header"]["name"] == "Отгрузка под перевозку"
    assert result.context_block is not None
    assert "Документ.ОПП" in result.context_block
    assert "паспорта переданы" in result.context_block


@pytest.mark.asyncio
async def test_prefetch_not_found_mention(db_with_cache):
    result = await prefetch_mentions(
        db_with_cache, "ch-test", "что такое @Документ.Несуществует"
    )
    assert result.found_count == 0
    assert result.not_found_count == 1
    assert result.cards == []
    assert result.context_block is not None
    assert "Документ.Несуществует" in result.context_block
    assert "metadata_cache" in result.context_block


@pytest.mark.asyncio
async def test_prefetch_mixed_found_and_not_found(db_with_cache):
    result = await prefetch_mentions(
        db_with_cache,
        "ch-test",
        "сравни @Документ.ОПП и @Документ.Неизвестный",
    )
    assert result.found_count == 1
    assert result.not_found_count == 1
    assert len(result.cards) == 1  # только found попадает в cards
    assert result.cards[0]["payload"]["header"]["path"] == "Документ.ОПП"
    assert result.context_block is not None
    assert "Документ.ОПП" in result.context_block
    assert "Документ.Неизвестный" in result.context_block


@pytest.mark.asyncio
async def test_prefetch_unknown_channel_returns_only_not_found(db_with_cache):
    """Канал без записей в metadata_cache — все mentions попадают в not_found."""
    result = await prefetch_mentions(
        db_with_cache, "ch-other", "про @Документ.ОПП"
    )
    assert result.found_count == 0
    assert result.not_found_count == 1
    assert result.cards == []


@pytest.mark.asyncio
async def test_prefetch_dedupes_repeated_mentions(db_with_cache):
    """Повторные mentions одного объекта генерируют ровно одну card."""
    result = await prefetch_mentions(
        db_with_cache,
        "ch-test",
        "@Документ.ОПП ещё раз @Документ.ОПП и ещё @Документ.ОПП",
    )
    assert len(result.mentions) == 1
    assert result.found_count == 1
    assert len(result.cards) == 1


@pytest.mark.asyncio
async def test_prefetch_empty_message_returns_empty(db_with_cache):
    result = await prefetch_mentions(db_with_cache, "ch-test", "")
    assert result.cards == []
    assert result.context_block is None
    assert result.found_count == 0
    assert result.not_found_count == 0


@pytest.mark.asyncio
async def test_prefetch_cards_validate_against_pydantic_card_event(db_with_cache):
    """Каждая card должна проходить app.orchestrator.events.CardEvent валидацию."""
    from app.orchestrator.events import CardEvent

    result = await prefetch_mentions(
        db_with_cache, "ch-test", "@Документ.ОПП"
    )
    assert len(result.cards) == 1
    # Должно не бросить ValidationError
    CardEvent.model_validate(result.cards[0])
