"""Тесты для scripts/typical_cards_reembed.py (M-K2.5.9.6).

Проверяет:
- dry-run находит candidates но не пишет
- --confirm обновляет metadata
- filter by --channel-id / --from-version
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import aiosqlite
import pytest

from app.knowledge.typical.card_models import TypicalObjectCard
from app.knowledge.typical.card_storage import (
    get_card_by_qname,
    update_card_status,
    upsert_card,
)
from app.knowledge.typical.card_models import CardStatus
from app.storage.migrations import apply_migrations
from scripts.typical_cards_reembed import (
    find_candidates_for_reembed,
    reembed_cards,
)


def _make_card(qname: str, channel_id: str = "_test_") -> TypicalObjectCard:
    return TypicalObjectCard(
        object_qualified_name=qname,
        object_kind="Document",
        channel_id=channel_id,
        summary=f"Stub {qname}",
    )


async def _seed_cards(db_path: str) -> None:
    """Создаёт три карточки: 2 без version, 1 с version='v0.5'."""
    db = await aiosqlite.connect(db_path)
    try:
        await apply_migrations(db)
        for qname in ("Document.A", "Document.B"):
            await upsert_card(db, card=_make_card(qname), source_hash=f"h-{qname}")
        await upsert_card(db, card=_make_card("Document.C"), source_hash="h-C")
        await update_card_status(
            db, channel_id="_test_", object_qualified_name="Document.C",
            status=CardStatus.EMBEDDED,
            embedding_model="legacy-embeddings",
            embedding_dim=512,
            embedding_model_version="v0.5",
        )
    finally:
        await db.close()


@pytest.fixture
def tmp_db(tmp_path: Path) -> str:
    """Возвращает путь к временной БД (без миграций — их применит сам скрипт)."""
    db_path = tmp_path / "test_reembed.db"
    return str(db_path)


@pytest.mark.asyncio
async def test_find_candidates_returns_cards_without_version(tmp_db):
    await _seed_cards(tmp_db)
    db = await aiosqlite.connect(tmp_db)
    try:
        candidates = await find_candidates_for_reembed(
            db, channel_id="_test_", from_version=None,
        )
        # Document.A и Document.B — без version
        qnames = sorted(c[1] for c in candidates)
        assert qnames == ["Document.A", "Document.B"]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_find_candidates_filters_by_from_version(tmp_db):
    await _seed_cards(tmp_db)
    db = await aiosqlite.connect(tmp_db)
    try:
        candidates = await find_candidates_for_reembed(
            db, channel_id="_test_", from_version="v0.5",
        )
        qnames = sorted(c[1] for c in candidates)
        assert qnames == ["Document.C"]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_reembed_dry_run_finds_but_does_not_update(tmp_db):
    await _seed_cards(tmp_db)
    result = await reembed_cards(
        db_path=tmp_db,
        channel_id="_test_",
        from_version=None,  # карточки без version
        to_version="v1.0",
        model="text-embedding-3-small",
        confirm=False,
    )
    assert result["dry_run"] is True
    assert result["found"] == 2  # A + B
    assert result["updated"] == 0

    # Проверяем что в БД ничего не изменилось
    db = await aiosqlite.connect(tmp_db)
    try:
        rec = await get_card_by_qname(
            db, channel_id="_test_", object_qualified_name="Document.A",
        )
        assert rec.embedding_model_version is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_reembed_with_confirm_updates_metadata(tmp_db):
    await _seed_cards(tmp_db)
    result = await reembed_cards(
        db_path=tmp_db,
        channel_id="_test_",
        from_version=None,
        to_version="v1.0",
        model="text-embedding-3-small",
        confirm=True,
    )
    assert result["dry_run"] is False
    assert result["found"] == 2
    assert result["updated"] == 2
    assert result["errors"] == 0

    # Проверяем что A и B получили version='v1.0' + новую модель
    db = await aiosqlite.connect(tmp_db)
    try:
        for qname in ("Document.A", "Document.B"):
            rec = await get_card_by_qname(
                db, channel_id="_test_", object_qualified_name=qname,
            )
            assert rec.embedding_model == "text-embedding-3-small"
            assert rec.embedding_model_version == "v1.0"

        # C остался с v0.5 (не попал в фильтр from_version=None)
        rec_c = await get_card_by_qname(
            db, channel_id="_test_", object_qualified_name="Document.C",
        )
        assert rec_c.embedding_model_version == "v0.5"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_reembed_filters_by_channel_id(tmp_db):
    await _seed_cards(tmp_db)
    # Добавим карточку в _other_ канал
    db = await aiosqlite.connect(tmp_db)
    try:
        await upsert_card(
            db, card=_make_card("Document.X", channel_id="_other_"), source_hash="hx",
        )
    finally:
        await db.close()

    result = await reembed_cards(
        db_path=tmp_db,
        channel_id="_test_",  # только _test_
        from_version=None,
        to_version="v1.0",
        model="m",
        confirm=True,
    )
    # 2 карточки в _test_ (A, B) — _other_ не должна быть затронута
    assert result["updated"] == 2

    # Проверяем что _other_ не тронут
    db = await aiosqlite.connect(tmp_db)
    try:
        rec = await get_card_by_qname(
            db, channel_id="_other_", object_qualified_name="Document.X",
        )
        assert rec.embedding_model_version is None
    finally:
        await db.close()
