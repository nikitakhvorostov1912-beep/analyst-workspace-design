"""Тесты для card_models + card_storage + migration v18 (M-K2.5.5)."""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.typical.card_models import (
    CardAttribute,
    CardMovement,
    CardStatus,
    TypicalObjectCard,
    TypicalObjectCardRecord,
)
from app.knowledge.typical.card_storage import (
    count_cards_by_channel,
    delete_cards_by_channel,
    get_card_by_qname,
    get_existing_source_hash,
    list_cards_by_channel,
    update_card_status,
    upsert_card,
)
from app.storage.migrations import apply_migrations


@pytest_asyncio.fixture
async def db_ready():
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


# ─── Migration v18 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_migration_v18_creates_typical_object_cards():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='typical_object_cards'"
        )
        row = await cursor.fetchone()
        assert row is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v18_creates_indexes():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name LIKE 'idx_typical_cards%'"
        )
        rows = await cursor.fetchall()
        names = {r[0] for r in rows}
        assert "idx_typical_cards_channel" in names
        assert "idx_typical_cards_kind" in names
        assert "idx_typical_cards_status" in names
        assert "idx_typical_cards_hash" in names
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v18_idempotent():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        # Применить второй раз — без падений
        await apply_migrations(conn)
        cursor = await conn.execute("SELECT MAX(version) FROM schema_version")
        v = await cursor.fetchone()
        assert v[0] == 18
    finally:
        await conn.close()


# ─── card_models ──────────────────────────────────────────────────────


class TestCardAttribute:
    def test_to_dict(self):
        a = CardAttribute(name="Контрагент", role="получатель")
        assert a.to_dict() == {"name": "Контрагент", "role": "получатель"}

    def test_default_role(self):
        a = CardAttribute(name="Х")
        assert a.role == ""

    def test_frozen(self):
        a = CardAttribute(name="Х")
        with pytest.raises((AttributeError, Exception)):
            a.name = "Y"


class TestCardMovement:
    def test_to_dict_full(self):
        m = CardMovement(
            register="РегистрНакопления.ТоварыНаСкладах",
            direction="расход",
            condition="при списании",
        )
        assert m.to_dict()["register"] == "РегистрНакопления.ТоварыНаСкладах"
        assert m.to_dict()["direction"] == "расход"


class TestTypicalObjectCard:
    def test_minimal(self):
        c = TypicalObjectCard(
            object_qualified_name="Document.Заказ",
            object_kind="Document",
            channel_id="_test_",
        )
        assert c.summary == ""
        assert c.embedding_text == ""

    def test_embedding_text_combines_fields(self):
        c = TypicalObjectCard(
            object_qualified_name="Document.X",
            object_kind="Document",
            channel_id="_test_",
            summary="Документ продажи.",
            purpose="Регистрирует факт реализации.",
            posting_flow=("Заполнение шапки", "Подбор товаров", "Запись движений"),
        )
        text = c.embedding_text
        assert "Документ продажи." in text
        assert "Регистрирует факт реализации." in text
        assert "Заполнение шапки → Подбор товаров → Запись движений" in text

    def test_embedding_text_limits_posting_flow_to_3(self):
        c = TypicalObjectCard(
            object_qualified_name="Document.X",
            object_kind="Document",
            channel_id="_test_",
            summary="S",
            posting_flow=("a", "b", "c", "d", "e"),
        )
        text = c.embedding_text
        assert "d" not in text  # 4-й шаг отрезан
        assert "a → b → c" in text

    def test_embedding_text_skips_empty_segments(self):
        c = TypicalObjectCard(
            object_qualified_name="Document.X",
            object_kind="Document",
            channel_id="_test_",
        )
        assert c.embedding_text == ""

    def test_to_payload_json_roundtrip(self):
        c1 = TypicalObjectCard(
            object_qualified_name="Document.X",
            object_kind="Document",
            channel_id="_test_",
            summary="S",
            purpose="P",
            key_attributes=(CardAttribute(name="A", role="r"),),
            movements=(CardMovement(register="R", direction="d", condition="c"),),
            posting_flow=("x",),
            related_objects=("Y",),
        )
        payload = c1.to_payload_json()
        c2 = TypicalObjectCard.from_payload_json(
            channel_id="_test_",
            object_qualified_name="Document.X",
            object_kind="Document",
            payload_json=payload,
        )
        assert c2.summary == "S"
        assert c2.purpose == "P"
        assert c2.key_attributes[0].name == "A"
        assert c2.movements[0].register == "R"
        assert c2.related_objects == ("Y",)

    def test_from_payload_json_empty(self):
        c = TypicalObjectCard.from_payload_json(
            channel_id="_test_",
            object_qualified_name="Document.X",
            object_kind="Document",
            payload_json="{}",
        )
        assert c.summary == ""
        assert c.key_attributes == ()


# ─── card_storage ─────────────────────────────────────────────────────


def _make_card(qname: str = "Document.Заказ") -> TypicalObjectCard:
    return TypicalObjectCard(
        object_qualified_name=qname,
        object_kind="Document",
        channel_id="_test_",
        summary="Тестовая карточка",
        purpose="Для проверки storage",
    )


@pytest.mark.asyncio
async def test_upsert_card_creates_new(db_ready):
    card = _make_card()
    card_id = await upsert_card(db_ready, card=card, source_hash="abc123")
    assert card_id > 0

    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    assert rec is not None
    assert rec.card.summary == "Тестовая карточка"
    assert rec.source_hash == "abc123"
    assert rec.status == CardStatus.GENERATED.value


@pytest.mark.asyncio
async def test_upsert_card_idempotent(db_ready):
    card = _make_card()
    id1 = await upsert_card(db_ready, card=card, source_hash="h1")
    id2 = await upsert_card(db_ready, card=card, source_hash="h1")
    assert id1 == id2  # тот же row, не дубль


@pytest.mark.asyncio
async def test_upsert_card_updates_payload(db_ready):
    card1 = _make_card()
    await upsert_card(db_ready, card=card1, source_hash="h1")

    card2 = TypicalObjectCard(
        object_qualified_name=card1.object_qualified_name,
        object_kind=card1.object_kind,
        channel_id=card1.channel_id,
        summary="Updated summary",
        purpose="Updated purpose",
    )
    await upsert_card(db_ready, card=card2, source_hash="h2")

    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    assert rec.card.summary == "Updated summary"
    assert rec.source_hash == "h2"


@pytest.mark.asyncio
async def test_upsert_card_with_llm_metadata(db_ready):
    card = _make_card()
    await upsert_card(
        db_ready, card=card, source_hash="h",
        llm_model="gpt-4o-mini", token_usage_in=500, token_usage_out=300,
    )
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    assert rec.llm_model == "gpt-4o-mini"
    assert rec.token_usage_in == 500
    assert rec.token_usage_out == 300


@pytest.mark.asyncio
async def test_get_card_by_qname_returns_none_when_missing(db_ready):
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.X",
    )
    assert rec is None


@pytest.mark.asyncio
async def test_get_existing_source_hash(db_ready):
    card = _make_card()
    await upsert_card(db_ready, card=card, source_hash="ABC")

    h = await get_existing_source_hash(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    assert h == "ABC"


@pytest.mark.asyncio
async def test_get_existing_source_hash_none_when_missing(db_ready):
    h = await get_existing_source_hash(
        db_ready, channel_id="_test_", object_qualified_name="Document.X",
    )
    assert h is None


@pytest.mark.asyncio
async def test_list_cards_by_channel(db_ready):
    await upsert_card(db_ready, card=_make_card("Document.A"), source_hash="h1")
    await upsert_card(db_ready, card=_make_card("Document.B"), source_hash="h2")
    await upsert_card(db_ready, card=_make_card("Document.C"), source_hash="h3")

    cards = await list_cards_by_channel(db_ready, channel_id="_test_")
    assert len(cards) == 3
    names = [c.object_qualified_name for c in cards]
    assert names == sorted(names)  # ORDER BY qualified_name


@pytest.mark.asyncio
async def test_list_cards_filter_by_kind(db_ready):
    await upsert_card(db_ready, card=_make_card("Document.A"), source_hash="h1")
    catalog_card = TypicalObjectCard(
        object_qualified_name="Catalog.Контрагенты",
        object_kind="Catalog",
        channel_id="_test_",
    )
    await upsert_card(db_ready, card=catalog_card, source_hash="h2")

    docs = await list_cards_by_channel(db_ready, channel_id="_test_", object_kind="Document")
    assert len(docs) == 1
    assert docs[0].object_kind == "Document"


@pytest.mark.asyncio
async def test_list_cards_filter_by_status(db_ready):
    await upsert_card(
        db_ready, card=_make_card("Document.A"), source_hash="h1",
        status=CardStatus.GENERATED,
    )
    await upsert_card(
        db_ready, card=_make_card("Document.B"), source_hash="h2",
        status=CardStatus.FAILED, error="Test error",
    )

    failed = await list_cards_by_channel(db_ready, channel_id="_test_", status=CardStatus.FAILED)
    assert len(failed) == 1
    assert failed[0].error == "Test error"


@pytest.mark.asyncio
async def test_update_card_status_lifecycle(db_ready):
    card = _make_card()
    await upsert_card(db_ready, card=card, source_hash="h", status=CardStatus.PENDING)

    ok = await update_card_status(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
        status=CardStatus.EMBEDDED, embedding_model="text-embedding-3-small",
        embedding_dim=1536,
    )
    assert ok is True

    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    assert rec.status == CardStatus.EMBEDDED.value
    assert rec.embedding_model == "text-embedding-3-small"
    assert rec.embedding_dim == 1536


@pytest.mark.asyncio
async def test_update_card_status_missing_returns_false(db_ready):
    ok = await update_card_status(
        db_ready, channel_id="_test_", object_qualified_name="Document.Unknown",
        status=CardStatus.GENERATED,
    )
    assert ok is False


@pytest.mark.asyncio
async def test_delete_cards_by_channel(db_ready):
    await upsert_card(db_ready, card=_make_card("Document.A"), source_hash="h1")
    await upsert_card(db_ready, card=_make_card("Document.B"), source_hash="h2")

    other_card = TypicalObjectCard(
        object_qualified_name="Document.X",
        object_kind="Document",
        channel_id="_other_",
    )
    await upsert_card(db_ready, card=other_card, source_hash="h3")

    deleted = await delete_cards_by_channel(db_ready, "_test_")
    assert deleted == 2

    remaining = await list_cards_by_channel(db_ready, channel_id="_other_")
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_delete_cards_returns_0_when_empty(db_ready):
    deleted = await delete_cards_by_channel(db_ready, "_test_")
    assert deleted == 0


@pytest.mark.asyncio
async def test_count_cards_by_channel(db_ready):
    await upsert_card(
        db_ready, card=_make_card("Document.A"), source_hash="h1",
        status=CardStatus.GENERATED,
    )
    await upsert_card(
        db_ready, card=_make_card("Document.B"), source_hash="h2",
        status=CardStatus.GENERATED,
    )
    await upsert_card(
        db_ready, card=_make_card("Document.C"), source_hash="h3",
        status=CardStatus.FAILED, error="x",
    )

    counts = await count_cards_by_channel(db_ready, "_test_")
    assert counts == {"generated": 2, "failed": 1}


@pytest.mark.asyncio
async def test_upsert_card_with_empty_qname_raises(db_ready):
    card = TypicalObjectCard(
        object_qualified_name="",
        object_kind="Document",
        channel_id="_test_",
    )
    with pytest.raises(ValueError):
        await upsert_card(db_ready, card=card, source_hash="h")


@pytest.mark.asyncio
async def test_upsert_card_with_empty_channel_raises(db_ready):
    card = TypicalObjectCard(
        object_qualified_name="Document.X",
        object_kind="Document",
        channel_id="",
    )
    with pytest.raises(ValueError):
        await upsert_card(db_ready, card=card, source_hash="h")


@pytest.mark.asyncio
async def test_to_dict_record(db_ready):
    card = _make_card()
    await upsert_card(db_ready, card=card, source_hash="h")
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    d = rec.to_dict()
    assert d["channel_id"] == "_test_"
    assert d["card"]["summary"] == "Тестовая карточка"
    assert d["source_hash"] == "h"
