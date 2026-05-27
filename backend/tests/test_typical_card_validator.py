"""Тесты для card_validator (M-K2.5.9.5).

GraphEval-стиль: карточка валидируется против семантического графа,
который считается ground truth.
"""

from __future__ import annotations

import json

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.graph_storage import (
    EdgeKind,
    NodeKind,
    insert_edge,
    insert_node,
)
from app.knowledge.typical.card_models import (
    CardAttribute,
    CardMovement,
    TypicalObjectCard,
)
from app.knowledge.typical.card_storage import upsert_card
from app.knowledge.typical.card_validator import (
    CardValidationIssue,
    CardValidationResult,
    save_validation_result,
    validate_card_against_graph,
)
from app.storage.migrations import apply_migrations


# ─── Fixtures ─────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db_ready():
    conn = await aiosqlite.connect(":memory:")
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


async def _setup_object_with_writes(
    db: aiosqlite.Connection,
    *,
    channel_id: str,
    object_qname: str,
    register_qnames: list[str] | None = None,
    reads_from_qnames: list[str] | None = None,
) -> int:
    """Создаёт в графе: объект → метод → WRITES_TO/READS_FROM регистры.

    Возвращает id объекта.
    """
    object_id = await insert_node(
        db,
        channel_id=channel_id,
        node_kind=NodeKind.METADATA_OBJECT.value,
        qualified_name=object_qname,
        source_path=None,
        attributes={"kind": object_qname.split(".", 1)[0]},
    )
    # method node, привязан к объекту через CONTAINS
    method_id = await insert_node(
        db,
        channel_id=channel_id,
        node_kind=NodeKind.METHOD.value,
        qualified_name=f"{object_qname}.ОбработкаПроведения",
        source_path=None,
        attributes={"is_handler": True},
    )
    await insert_edge(
        db,
        src_id=object_id,
        dst_id=method_id,
        edge_kind=EdgeKind.CONTAINS.value,
    )

    for reg_qname in (register_qnames or []):
        reg_id = await insert_node(
            db,
            channel_id=channel_id,
            node_kind=NodeKind.METADATA_OBJECT.value,
            qualified_name=reg_qname,
            source_path=None,
            attributes={"kind": reg_qname.split(".", 1)[0]},
        )
        await insert_edge(
            db,
            src_id=method_id,
            dst_id=reg_id,
            edge_kind=EdgeKind.WRITES_TO.value,
        )

    for reg_qname in (reads_from_qnames or []):
        reg_id = await insert_node(
            db,
            channel_id=channel_id,
            node_kind=NodeKind.METADATA_OBJECT.value,
            qualified_name=reg_qname,
            source_path=None,
            attributes={"kind": reg_qname.split(".", 1)[0]},
        )
        await insert_edge(
            db,
            src_id=method_id,
            dst_id=reg_id,
            edge_kind=EdgeKind.READS_FROM.value,
        )

    return object_id


def _make_card(
    qname: str = "Document.РеализацияТоваровУслуг",
    movements: tuple[CardMovement, ...] = (),
    related: tuple[str, ...] = (),
) -> TypicalObjectCard:
    return TypicalObjectCard(
        object_qualified_name=qname,
        object_kind="Document",
        channel_id="_test_",
        summary="Тестовая карточка",
        movements=movements,
        related_objects=related,
    )


# ─── object_not_in_graph ─────────────────────────────────────────────


class TestObjectNotInGraph:
    @pytest.mark.asyncio
    async def test_returns_object_not_in_graph_status(self, db_ready):
        card = _make_card(qname="Document.Phantom")
        result = await validate_card_against_graph(
            db_ready, channel_id="_test_", card=card,
        )
        assert result.status == "object_not_in_graph"
        assert result.error_count == 1
        assert result.issues[0].code == "object_not_in_graph"


# ─── Phantom movements ────────────────────────────────────────────────


class TestPhantomMovements:
    @pytest.mark.asyncio
    async def test_phantom_movement_detected_when_not_in_graph(self, db_ready):
        """Карточка ссылается на регистр которого нет в WRITES_TO графа."""
        await _setup_object_with_writes(
            db_ready, channel_id="_test_",
            object_qname="Document.X",
            register_qnames=["AccumulationRegister.RealOne"],
        )
        card = _make_card(
            qname="Document.X",
            movements=(
                CardMovement(register="AccumulationRegister.RealOne", direction="расход"),
                CardMovement(register="AccumulationRegister.PhantomMade", direction="расход"),
            ),
        )
        result = await validate_card_against_graph(
            db_ready, channel_id="_test_", card=card,
        )
        assert result.status == "issues_found"
        phantom_issues = [i for i in result.issues if i.code == "phantom_movement"]
        assert len(phantom_issues) == 1
        assert "PhantomMade" in phantom_issues[0].detail

    @pytest.mark.asyncio
    async def test_no_phantom_when_all_movements_in_graph(self, db_ready):
        await _setup_object_with_writes(
            db_ready, channel_id="_test_",
            object_qname="Document.X",
            register_qnames=["AccumulationRegister.Товары", "AccumulationRegister.Взаиморасчеты"],
        )
        card = _make_card(
            qname="Document.X",
            movements=(
                CardMovement(register="AccumulationRegister.Товары", direction="расход"),
                CardMovement(register="AccumulationRegister.Взаиморасчеты", direction="приход"),
            ),
        )
        result = await validate_card_against_graph(
            db_ready, channel_id="_test_", card=card,
        )
        # Status = 'valid' (нет issues по movements) ИЛИ 'issues_found' если есть info-уровня
        assert result.error_count == 0

    @pytest.mark.asyncio
    async def test_reads_from_register_in_card_movements_does_not_trigger_phantom(
        self, db_ready,
    ):
        """Если регистр в movements карточки соответствует READS_FROM в графе,
        это OK (карточка может описывать чтение как 'движение')."""
        await _setup_object_with_writes(
            db_ready, channel_id="_test_",
            object_qname="Document.X",
            register_qnames=[],
            reads_from_qnames=["AccumulationRegister.СвободныеОстатки"],
        )
        card = _make_card(
            qname="Document.X",
            movements=(
                CardMovement(register="AccumulationRegister.СвободныеОстатки", direction="приход/расход"),
            ),
        )
        result = await validate_card_against_graph(
            db_ready, channel_id="_test_", card=card,
        )
        phantom_issues = [i for i in result.issues if i.code == "phantom_movement"]
        assert len(phantom_issues) == 0


# ─── Missing movements (info severity) ────────────────────────────────


class TestMissingMovements:
    @pytest.mark.asyncio
    async def test_missing_movement_reported_as_info(self, db_ready):
        """В графе есть WRITES_TO, в карточке — нет. Это info, не error."""
        await _setup_object_with_writes(
            db_ready, channel_id="_test_",
            object_qname="Document.X",
            register_qnames=[
                "AccumulationRegister.Товары",
                "AccumulationRegister.Взаиморасчеты",  # missing in card
            ],
        )
        card = _make_card(
            qname="Document.X",
            movements=(
                CardMovement(register="AccumulationRegister.Товары", direction="расход"),
            ),
        )
        result = await validate_card_against_graph(
            db_ready, channel_id="_test_", card=card,
        )
        info_issues = [i for i in result.issues if i.code == "missing_movement"]
        assert len(info_issues) == 1
        assert info_issues[0].severity == "info"
        assert "Взаиморасчеты" in info_issues[0].detail
        assert result.error_count == 0  # info doesn't count as error


# ─── related_objects ──────────────────────────────────────────────────


class TestRelatedObjects:
    @pytest.mark.asyncio
    async def test_phantom_related_object_detected(self, db_ready):
        await _setup_object_with_writes(
            db_ready, channel_id="_test_", object_qname="Document.X",
        )
        # Создаём ещё один реальный объект чтобы проверить отрицательный кейс
        await insert_node(
            db_ready, channel_id="_test_",
            node_kind=NodeKind.METADATA_OBJECT.value,
            qualified_name="Document.RealRelated",
            source_path=None, attributes={},
        )
        card = _make_card(
            qname="Document.X",
            related=("Document.RealRelated", "Document.Phantom"),
        )
        result = await validate_card_against_graph(
            db_ready, channel_id="_test_", card=card,
        )
        phantom_issues = [i for i in result.issues if i.code == "phantom_related"]
        assert len(phantom_issues) == 1
        assert "Phantom" in phantom_issues[0].detail
        assert phantom_issues[0].severity == "warning"


# ─── CardValidationResult helpers ─────────────────────────────────────


class TestValidationResultDataClass:
    def test_to_dict_serializes_issues(self):
        result = CardValidationResult(
            status="issues_found",
            issues=(
                CardValidationIssue(
                    severity="error", code="phantom_movement",
                    field="movements", detail="X не в графе",
                ),
            ),
            validated_at="2026-05-27T10:00:00+00:00",
            object_qualified_name="Document.X",
            channel_id="_test_",
        )
        d = result.to_dict()
        assert d["status"] == "issues_found"
        assert len(d["issues"]) == 1
        assert d["issues"][0]["code"] == "phantom_movement"

    def test_to_json_roundtrip(self):
        result = CardValidationResult(
            status="valid",
            issues=(),
            validated_at="2026-05-27T10:00:00+00:00",
            object_qualified_name="Document.X",
            channel_id="_test_",
        )
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed["status"] == "valid"
        assert parsed["issues"] == []

    def test_error_count_counts_only_errors(self):
        result = CardValidationResult(
            status="issues_found",
            issues=(
                CardValidationIssue(severity="error", code="x", field=None, detail=""),
                CardValidationIssue(severity="warning", code="y", field=None, detail=""),
                CardValidationIssue(severity="info", code="z", field=None, detail=""),
                CardValidationIssue(severity="error", code="x2", field=None, detail=""),
            ),
            validated_at="2026-05-27T10:00:00+00:00",
            object_qualified_name="Document.X",
            channel_id="_test_",
        )
        assert result.error_count == 2
        assert result.warning_count == 1


# ─── save_validation_result ──────────────────────────────────────────


class TestSaveValidationResult:
    @pytest.mark.asyncio
    async def test_save_persists_result_to_card_row(self, db_ready):
        # Создаём карточку
        card = _make_card(qname="Document.X")
        await upsert_card(db_ready, card=card, source_hash="h")

        result = CardValidationResult(
            status="issues_found",
            issues=(
                CardValidationIssue(
                    severity="error", code="phantom_movement",
                    field="movements", detail="X выдумано",
                ),
            ),
            validated_at="2026-05-27T10:00:00+00:00",
            object_qualified_name="Document.X",
            channel_id="_test_",
        )
        ok = await save_validation_result(
            db_ready,
            channel_id="_test_",
            object_qualified_name="Document.X",
            result=result,
        )
        assert ok is True

        # Проверяем что записалось
        cursor = await db_ready.execute(
            "SELECT validation_status, validation_issues, validated_at "
            "FROM typical_object_cards WHERE object_qualified_name = ?",
            ("Document.X",),
        )
        row = await cursor.fetchone()
        assert row[0] == "issues_found"
        parsed = json.loads(row[1])
        assert len(parsed) == 1
        assert parsed[0]["code"] == "phantom_movement"
        assert row[2] == "2026-05-27T10:00:00+00:00"

    @pytest.mark.asyncio
    async def test_save_returns_false_for_missing_card(self, db_ready):
        result = CardValidationResult(
            status="valid", issues=(),
            validated_at="2026-05-27T10:00:00+00:00",
            object_qualified_name="Document.Missing", channel_id="_test_",
        )
        ok = await save_validation_result(
            db_ready,
            channel_id="_test_",
            object_qualified_name="Document.Missing",
            result=result,
        )
        assert ok is False


# ─── Integration: validate + save + read ──────────────────────────────


@pytest.mark.asyncio
async def test_full_validate_save_read_cycle(db_ready):
    """End-to-end: создать карточку, валидировать, сохранить, прочитать через
    get_card_by_qname — validation_status / validation_issues видны в record."""
    from app.knowledge.typical.card_storage import get_card_by_qname  # noqa: PLC0415

    # Setup граф: объект с одним registers
    await _setup_object_with_writes(
        db_ready, channel_id="_test_",
        object_qname="Document.X",
        register_qnames=["AccumulationRegister.Real"],
    )

    # Карточка с фантомным register
    card = _make_card(
        qname="Document.X",
        movements=(
            CardMovement(register="AccumulationRegister.Phantom"),
        ),
    )
    await upsert_card(db_ready, card=card, source_hash="h")

    # Валидируем
    result = await validate_card_against_graph(
        db_ready, channel_id="_test_", card=card,
    )
    assert result.status == "issues_found"
    assert result.error_count >= 1

    # Сохраняем
    await save_validation_result(
        db_ready, channel_id="_test_",
        object_qualified_name="Document.X", result=result,
    )

    # Читаем
    rec = await get_card_by_qname(
        db_ready, channel_id="_test_", object_qualified_name="Document.X",
    )
    assert rec is not None
    assert rec.validation_status == "issues_found"
    issues_data = json.loads(rec.validation_issues)
    assert any(i["code"] == "phantom_movement" for i in issues_data)
    assert rec.validated_at is not None
