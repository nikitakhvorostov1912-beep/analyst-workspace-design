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
async def test_migrations_v18_v19_idempotent():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        # Применить второй раз — без падений
        await apply_migrations(conn)
        cursor = await conn.execute("SELECT MAX(version) FROM schema_version")
        v = await cursor.fetchone()
        # v19 (M-K2.5.9.2) — текущая верхняя миграция (is_mock колонка)
        assert v[0] == 19
    finally:
        await conn.close()


# ─── Migration v19 — Mock isolation (M-K2.5.9.2) ──────────────────────


@pytest.mark.asyncio
async def test_migration_v19_creates_is_mock_column():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute("PRAGMA table_info(typical_object_cards)")
        cols = await cursor.fetchall()
        col_names = {c[1] for c in cols}
        assert "is_mock" in col_names
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v19_creates_is_mock_index():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name = 'idx_typical_cards_is_mock'"
        )
        row = await cursor.fetchone()
        assert row is not None


    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v19_backfills_mock_for_mock_generator_v1():
    """v19 должна пометить is_mock=1 для всех существующих карточек с
    llm_model='mock-generator-v1'. Защита 63 197 карточек в production pilot.db.
    """
    # Эмулируем pre-v19 БД: применяем миграции v1..v18, потом INSERT карточек
    # с mock-моделью, потом запускаем v19 (полный apply_migrations).
    conn = await aiosqlite.connect(":memory:")
    try:
        # Дотягиваемся до v18 руками (без apply_migrations, который сразу v19)
        from app.storage.migrations import (  # noqa: PLC0415
            DDL_STATEMENTS,
            MIGRATIONS_V2,
            MIGRATIONS_V3,
            MIGRATIONS_V4,
            MIGRATIONS_V5,
            MIGRATIONS_V6,
            MIGRATIONS_V7,
            MIGRATIONS_V8,
            MIGRATIONS_V9,
            MIGRATIONS_V10,
            MIGRATIONS_V11,
            MIGRATIONS_V12,
            MIGRATIONS_V13,
            MIGRATIONS_V14,
            MIGRATIONS_V15,
            MIGRATIONS_V16,
            MIGRATIONS_V17,
            MIGRATIONS_V18,
        )
        all_pre_v19 = [
            DDL_STATEMENTS[0],
            *DDL_STATEMENTS[1:],
            *MIGRATIONS_V2,
            *MIGRATIONS_V3,
            *MIGRATIONS_V4,
            *MIGRATIONS_V5,
            *MIGRATIONS_V6,
            *MIGRATIONS_V7,
            *MIGRATIONS_V8,
            *MIGRATIONS_V9,
            *MIGRATIONS_V10,
            *MIGRATIONS_V11,
            *MIGRATIONS_V12,
            *MIGRATIONS_V13,
            *MIGRATIONS_V14,
            *MIGRATIONS_V15,
            *MIGRATIONS_V16,
            *MIGRATIONS_V17,
            *MIGRATIONS_V18,
        ]
        for stmt in all_pre_v19:
            await conn.execute(stmt)
        await conn.execute(
            "INSERT INTO schema_version (version) VALUES (1), (2), (3), (4), (5), (6), (7), (8), (9), "
            "(10), (11), (12), (13), (14), (15), (16), (17), (18)"
        )
        # INSERT карточек — две mock, одна реальная
        for qname, model in [
            ("Document.A", "mock-generator-v1"),
            ("Document.B", "mock-generator-v1"),
            ("Document.C", "gpt-4o-mini"),
        ]:
            await conn.execute(
                """
                INSERT INTO typical_object_cards (
                    channel_id, object_qualified_name, object_kind,
                    card_payload, source_hash, prompt_version, llm_model, status
                ) VALUES (?, ?, ?, '{}', 'h', 'v1', ?, 'generated')
                """,
                ("_test_", qname, "Document", model),
            )
        await conn.commit()

        # Apply v19 — backfill is_mock
        await apply_migrations(conn)

        cursor = await conn.execute(
            "SELECT object_qualified_name, is_mock FROM typical_object_cards ORDER BY object_qualified_name"
        )
        rows = await cursor.fetchall()
        assert rows == [
            ("Document.A", 1),
            ("Document.B", 1),
            ("Document.C", 0),
        ]
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


# ─── Hard limits (M-K2.5.9.3) ─────────────────────────────────────────


class TestHardLimits:
    """Pydantic Field max_length блокирует LLM overshoot.

    Лимиты — см. константы MAX_* в card_models.py.
    """

    def test_summary_overlimit_raises_validation_error(self):
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_SUMMARY_LEN  # noqa: PLC0415

        with pytest.raises(ValidationError):
            TypicalObjectCard(
                object_qualified_name="Document.X",
                object_kind="Document",
                channel_id="_test_",
                summary="x" * (MAX_SUMMARY_LEN + 1),
            )

    def test_purpose_overlimit_raises_validation_error(self):
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_PURPOSE_LEN  # noqa: PLC0415

        with pytest.raises(ValidationError):
            TypicalObjectCard(
                object_qualified_name="Document.X",
                object_kind="Document",
                channel_id="_test_",
                purpose="y" * (MAX_PURPOSE_LEN + 1),
            )

    def test_key_attributes_overlimit_raises(self):
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_KEY_ATTRIBUTES  # noqa: PLC0415

        too_many = tuple(CardAttribute(name=f"A{i}") for i in range(MAX_KEY_ATTRIBUTES + 1))
        with pytest.raises(ValidationError):
            TypicalObjectCard(
                object_qualified_name="Document.X",
                object_kind="Document",
                channel_id="_test_",
                key_attributes=too_many,
            )

    def test_movements_overlimit_raises(self):
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_MOVEMENTS  # noqa: PLC0415

        too_many = tuple(CardMovement(register=f"R{i}") for i in range(MAX_MOVEMENTS + 1))
        with pytest.raises(ValidationError):
            TypicalObjectCard(
                object_qualified_name="Document.X",
                object_kind="Document",
                channel_id="_test_",
                movements=too_many,
            )

    def test_posting_flow_overlimit_count_raises(self):
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_POSTING_FLOW  # noqa: PLC0415

        too_many = tuple(f"step-{i}" for i in range(MAX_POSTING_FLOW + 1))
        with pytest.raises(ValidationError):
            TypicalObjectCard(
                object_qualified_name="Document.X",
                object_kind="Document",
                channel_id="_test_",
                posting_flow=too_many,
            )

    def test_posting_step_string_overlimit_raises(self):
        """Per-element string length лимит работает для tuple[Annotated[str, ...]]."""
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_POSTING_STEP_LEN  # noqa: PLC0415

        too_long_step = "x" * (MAX_POSTING_STEP_LEN + 1)
        with pytest.raises(ValidationError):
            TypicalObjectCard(
                object_qualified_name="Document.X",
                object_kind="Document",
                channel_id="_test_",
                posting_flow=(too_long_step,),
            )

    def test_attr_role_overlimit_raises(self):
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_ATTR_ROLE_LEN  # noqa: PLC0415

        with pytest.raises(ValidationError):
            CardAttribute(name="X", role="r" * (MAX_ATTR_ROLE_LEN + 1))

    def test_movement_condition_overlimit_raises(self):
        from pydantic import ValidationError  # noqa: PLC0415

        from app.knowledge.typical.card_models import MAX_MOVEMENT_CONDITION_LEN  # noqa: PLC0415

        with pytest.raises(ValidationError):
            CardMovement(
                register="R", direction="приход",
                condition="x" * (MAX_MOVEMENT_CONDITION_LEN + 1),
            )

    def test_from_payload_json_truncates_overshoot_for_backward_compat(self):
        """Legacy payload длиннее лимитов — обрезается ДО валидации.

        Защита 63 197 существующих карточек: даже если в БД где-то окажется
        overshoot (legacy bug), мы загружаем без падения, обрезанным.
        """
        import json  # noqa: PLC0415

        from app.knowledge.typical.card_models import (  # noqa: PLC0415
            MAX_POSTING_FLOW,
            MAX_POSTING_STEP_LEN,
            MAX_SUMMARY_LEN,
        )

        legacy = {
            "summary": "L" * (MAX_SUMMARY_LEN + 200),
            "posting_flow": [f"step-{i}" for i in range(MAX_POSTING_FLOW + 5)],
            "preconditions": ["x" * (MAX_POSTING_STEP_LEN + 50)],
        }
        c = TypicalObjectCard.from_payload_json(
            channel_id="_test_",
            object_qualified_name="Document.X",
            object_kind="Document",
            payload_json=json.dumps(legacy),
        )
        assert len(c.summary) == MAX_SUMMARY_LEN
        assert len(c.posting_flow) == MAX_POSTING_FLOW
        # каждый precondition тоже усечён до лимита по длине
        assert all(len(p) <= 200 for p in c.preconditions)

    def test_at_limit_passes(self):
        """Значение точно на лимите — валидно (boundary check)."""
        from app.knowledge.typical.card_models import MAX_SUMMARY_LEN  # noqa: PLC0415

        c = TypicalObjectCard(
            object_qualified_name="Document.X",
            object_kind="Document",
            channel_id="_test_",
            summary="x" * MAX_SUMMARY_LEN,
        )
        assert len(c.summary) == MAX_SUMMARY_LEN


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


# ─── is_mock flag (M-K2.5.9.2) ────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_card_with_is_mock_true(db_ready):
    """is_mock=True сохраняется и читается обратно."""
    card = _make_card()
    await upsert_card(
        db_ready, card=card, source_hash="h",
        llm_model="mock-generator-v1", is_mock=True,
    )
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    assert rec is not None
    assert rec.is_mock is True


@pytest.mark.asyncio
async def test_upsert_card_default_is_mock_false(db_ready):
    """По умолчанию is_mock=False (реальные карточки не помечаются)."""
    card = _make_card()
    await upsert_card(db_ready, card=card, source_hash="h", llm_model="gpt-4o-mini")
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.Заказ",
    )
    assert rec is not None
    assert rec.is_mock is False


@pytest.mark.asyncio
async def test_list_cards_exclude_mock(db_ready):
    """exclude_mock=True отфильтровывает mock-карточки."""
    await upsert_card(
        db_ready, card=_make_card("Document.A"), source_hash="h1",
        llm_model="mock-generator-v1", is_mock=True,
    )
    await upsert_card(
        db_ready, card=_make_card("Document.B"), source_hash="h2",
        llm_model="mock-generator-v1", is_mock=True,
    )
    await upsert_card(
        db_ready, card=_make_card("Document.C"), source_hash="h3",
        llm_model="gpt-4o-mini", is_mock=False,
    )

    all_cards = await list_cards_by_channel(db_ready, channel_id="_test_")
    assert len(all_cards) == 3

    verified_only = await list_cards_by_channel(
        db_ready, channel_id="_test_", exclude_mock=True,
    )
    assert len(verified_only) == 1
    assert verified_only[0].object_qualified_name == "Document.C"
    assert verified_only[0].is_mock is False


@pytest.mark.asyncio
async def test_count_mock_cards_by_channel(db_ready):
    """Helper для UI-визуализации mock-ratio."""
    from app.knowledge.typical.card_storage import (  # noqa: PLC0415
        count_mock_cards_by_channel,
    )

    await upsert_card(
        db_ready, card=_make_card("Document.A"), source_hash="h1", is_mock=True,
    )
    await upsert_card(
        db_ready, card=_make_card("Document.B"), source_hash="h2", is_mock=True,
    )
    await upsert_card(
        db_ready, card=_make_card("Document.C"), source_hash="h3", is_mock=False,
    )

    counts = await count_mock_cards_by_channel(db_ready, "_test_")
    assert counts == {"mock": 2, "verified": 1}


@pytest.mark.asyncio
async def test_count_mock_cards_empty_channel(db_ready):
    """Пустой канал возвращает нули по обеим категориям."""
    from app.knowledge.typical.card_storage import (  # noqa: PLC0415
        count_mock_cards_by_channel,
    )

    counts = await count_mock_cards_by_channel(db_ready, "_empty_")
    assert counts == {"mock": 0, "verified": 0}


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
