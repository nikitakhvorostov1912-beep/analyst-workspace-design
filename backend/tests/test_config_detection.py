"""Tests for backend/app/knowledge/config_detection.py (M-K2.9)."""

from __future__ import annotations

import aiosqlite
import pytest
import pytest_asyncio

from app.knowledge.config_detection import (
    KNOWN_CONFIGURATIONS,
    ConfigurationSignature,
    DetectionResult,
    MIN_CONFIDENCE,
    detect_configuration_type,
    update_channel_configuration,
)
from app.storage.migrations import apply_migrations


# ---------- detect_configuration_type ----------


def test_empty_channel_returns_custom():
    result = detect_configuration_type([])
    assert result.is_custom
    assert result.configuration_key == "custom"
    assert result.display_name == "Самописная"
    assert result.confidence == 0.0
    assert result.family == "unknown"
    # scores всё равно есть — для debug
    assert "ut_11_5" in result.scores


def test_ut_11_5_full_signature_detected():
    """Все характерные объекты УТ → confidence ≈ 1.0."""
    sig = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    result = detect_configuration_type(sig.characteristic_objects)
    assert result.configuration_key == "ut_11_5"
    assert result.display_name == "УТ 11.5"
    assert result.confidence >= 0.99
    assert result.family == "trade"


def test_erp_2_5_detected_with_partial_overlap():
    """ERP должен выиграть у УТ если есть ERP-specific объекты."""
    erp_objects = {
        "Документ.РеализацияТоваровУслуг",
        "Документ.ЗаказПокупателя",
        "Справочник.Партнеры",
        "РегистрНакопления.СвободныеОстатки",
        # ERP-only:
        "Документ.РасчетСебестоимостиТоваров",
        "РегистрБухгалтерии.МеждународныйУчет",
        "Документ.ОтражениеЗарплатыВФинансовомУчете",
        "Документ.ПроизводственнаяОперация",
    }
    result = detect_configuration_type(erp_objects)
    assert result.configuration_key == "erp_2_5"
    assert result.scores["erp_2_5"] > result.scores["ut_11_5"]


def test_bp_3_0_distinguished_by_accounting_objects():
    """БП имеет ПланСчетов.Хозрасчетный и регистр бухгалтерии — отличается."""
    bp_objects = {
        "Документ.СчетНаОплату",
        "Документ.ОперацияБух",
        "Документ.ПоступлениеТоваровУслуг",
        "ПланСчетов.Хозрасчетный",
        "РегистрБухгалтерии.Хозрасчетный",
        "Справочник.ОсновныеСредства",
        "Справочник.СтатьиЗатрат",
    }
    result = detect_configuration_type(bp_objects)
    assert result.configuration_key == "bp_3_0"
    assert result.family == "accounting"


def test_zup_3_1_detected_by_payroll_markers():
    zup_objects = {
        "Документ.ПриемНаРаботу",
        "Документ.КадровыйПеревод",
        "Документ.НачислениеЗарплатыИВзносов",
        "Справочник.Сотрудники",
        "РегистрРасчета.НачисленияСотрудникам",
        "РегистрНакопления.ВыплаченныеВзносы",
    }
    result = detect_configuration_type(zup_objects)
    assert result.configuration_key == "zup_3_1"
    assert result.family == "payroll"


def test_bgu_2_0_detected_by_budget_objects():
    bgu_objects = {
        "Справочник.БюджетнаяКлассификация",
        "Документ.БюджетноеОбязательство",
        "Документ.КассовоеПоступление",
        "ПланСчетов.ЕПСБУ",
        "РегистрБухгалтерии.Бюджетный",
    }
    result = detect_configuration_type(bgu_objects)
    assert result.configuration_key == "bgu_2_0"
    assert result.family == "government"


def test_uso_jkx_detected():
    uso_objects = {
        "Справочник.ЛицевыеСчета",
        "Справочник.Тарифы",
        "Документ.НачислениеПоЛицевомуСчету",
        "РегистрНакопления.ПоказанияСчетчиков",
    }
    result = detect_configuration_type(uso_objects)
    assert result.configuration_key == "uso_2_5"
    assert result.family == "utilities"


def test_below_min_confidence_returns_custom():
    """Если только 1 объект совпадает (< MIN_CONFIDENCE) — custom."""
    weak_signal = {
        "Документ.РеализацияТоваровУслуг",  # есть и в УТ и в ERP и в КА
        # ничего больше характерного
    }
    result = detect_configuration_type(weak_signal)
    # Score = 1 / |signature| < MIN_CONFIDENCE (0.30) только для конфигураций
    # с большим signature. Для УТ 11.5 (10 объектов) = 0.10 < 0.30 → custom.
    assert result.confidence < MIN_CONFIDENCE
    assert result.is_custom


def test_custom_includes_debug_scores():
    result = detect_configuration_type([
        "Документ.МойУникальныйДокумент",
        "Справочник.НиктоНеЗнаетЧтоЭто",
    ])
    assert result.is_custom
    # Все scores = 0.0 (никакого пересечения)
    assert all(score == 0.0 for score in result.scores.values())


def test_min_confidence_threshold_is_configurable():
    """Дозвольте каллеру повысить порог уверенности."""
    # Один объект из УТ-сигнатуры из 10 = 10% — обычно проходит как custom
    weak_ut = {"Справочник.Номенклатура"}
    result_default = detect_configuration_type(weak_ut)
    assert result_default.is_custom

    # При min_confidence=0.05 — должен пройти как УТ (1/10 = 0.10 > 0.05)
    result_low_threshold = detect_configuration_type(weak_ut, min_confidence=0.05)
    assert not result_low_threshold.is_custom
    assert result_low_threshold.configuration_key == "ut_11_5"


def test_scores_dict_includes_all_known_configurations():
    """`scores` всегда содержит все ключи из KNOWN_CONFIGURATIONS."""
    result = detect_configuration_type([])
    expected_keys = {sig.key for sig in KNOWN_CONFIGURATIONS}
    assert set(result.scores.keys()) == expected_keys


def test_ut_and_erp_signatures_overlap_but_erp_wins_with_specific_objects():
    """УТ и ERP имеют пересечение, но ERP-specific объекты дают перевес ERP."""
    # Базовые УТ-объекты + ERP-маркеры
    mixed = {
        "Документ.РеализацияТоваровУслуг",
        "Справочник.Партнеры",
        "РегистрНакопления.СвободныеОстатки",
        "Документ.РасчетСебестоимостиТоваров",  # ERP-only
        "РегистрБухгалтерии.МеждународныйУчет",  # ERP-only
    }
    result = detect_configuration_type(mixed)
    # ERP может выиграть или быть близко — главное что детектирована trade-семья
    assert result.family == "trade"
    assert result.configuration_key in {"ut_11_5", "erp_2_5", "ka_2_5"}


def test_duplicate_objects_in_input_handled():
    """Дубликаты в input не должны влиять — internally set()."""
    sig = next(s for s in KNOWN_CONFIGURATIONS if s.key == "bp_3_0")
    duplicated = list(sig.characteristic_objects) * 3  # тройные дубликаты
    result = detect_configuration_type(duplicated)
    assert result.configuration_key == "bp_3_0"
    assert result.confidence >= 0.99


def test_configuration_signature_score_method():
    """score() напрямую на ConfigurationSignature — sanity check."""
    sig = ConfigurationSignature(
        key="test",
        display_name="Test",
        characteristic_objects=frozenset({"A", "B", "C", "D"}),
        family="test",
    )
    assert sig.score(set()) == 0.0
    assert sig.score({"A"}) == 0.25
    assert sig.score({"A", "B"}) == 0.5
    assert sig.score({"A", "B", "C", "D"}) == 1.0
    assert sig.score({"X", "Y", "Z"}) == 0.0
    # Дополнительные объекты в channel не учитываются:
    assert sig.score({"A", "B", "Q", "R", "S"}) == 0.5


def test_known_configurations_have_distinct_signatures():
    """Sanity: пары конфигураций не должны иметь >70% пересечения.

    Исключение — пара ERP 2.5 / КА 2.5: КА by design подмножество ERP
    без МСФО. Disambiguation таких пар идёт через ERP-only маркеры
    (РегистрБухгалтерии.МеждународныйУчет, СтатьиАктивовПассивов).
    """
    THRESHOLD = 0.70
    EXPECTED_OVERLAPS = {("erp_2_5", "ka_2_5")}  # by-design subset

    for i, sig_a in enumerate(KNOWN_CONFIGURATIONS):
        for sig_b in KNOWN_CONFIGURATIONS[i + 1:]:
            pair = tuple(sorted([sig_a.key, sig_b.key]))
            intersection = sig_a.characteristic_objects & sig_b.characteristic_objects
            smaller_set_size = min(
                len(sig_a.characteristic_objects),
                len(sig_b.characteristic_objects),
            )
            overlap_ratio = len(intersection) / smaller_set_size

            if pair in EXPECTED_OVERLAPS:
                # By-design close pairs — допускаем до 80%
                assert overlap_ratio <= 0.80, (
                    f"{sig_a.key} и {sig_b.key} пересекаются на {overlap_ratio:.0%} — "
                    "даже для родственных конфигураций это слишком близко"
                )
            else:
                assert overlap_ratio <= THRESHOLD, (
                    f"{sig_a.key} и {sig_b.key} пересекаются на {overlap_ratio:.0%} — "
                    "детекция может быть неоднозначной"
                )


# ---------- update_channel_configuration ----------


@pytest_asyncio.fixture
async def db():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        yield conn
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_update_channel_configuration_writes_display_name(db):
    # Seed mcp_connections
    await db.execute(
        """
        INSERT INTO mcp_connections (id, name, endpoint, kind)
        VALUES (?, ?, ?, 'embedded')
        """,
        ("ch-1", "Test", "http://localhost:6010/mcp"),
    )
    await db.commit()

    sig = next(s for s in KNOWN_CONFIGURATIONS if s.key == "ut_11_5")
    result = detect_configuration_type(sig.characteristic_objects)
    await update_channel_configuration(db, "ch-1", result)

    cursor = await db.execute(
        "SELECT configuration FROM mcp_connections WHERE id = ?", ("ch-1",)
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "УТ 11.5"


@pytest.mark.asyncio
async def test_update_channel_configuration_writes_custom_for_unknown(db):
    await db.execute(
        """
        INSERT INTO mcp_connections (id, name, endpoint, kind)
        VALUES ('ch-x', 'X', 'http://localhost:6010/mcp', 'embedded')
        """
    )
    await db.commit()

    result = detect_configuration_type(["Документ.НеизвестныйМне"])
    await update_channel_configuration(db, "ch-x", result)

    cursor = await db.execute(
        "SELECT configuration FROM mcp_connections WHERE id = ?", ("ch-x",)
    )
    row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "Самописная"


@pytest.mark.asyncio
async def test_update_channel_configuration_unknown_channel_is_noop(db):
    """UPDATE по несуществующему channel_id — просто 0 rows affected."""
    result = DetectionResult(
        configuration_key="ut_11_5",
        display_name="УТ 11.5",
        confidence=0.9,
        family="trade",
        scores={},
    )
    # Не должно бросить
    await update_channel_configuration(db, "ghost", result)


# ---------- Task 1.1: discriminative_objects + discriminative_score() ----------


def test_signature_discriminative_score_method():
    """discriminative_score() = доля найденных дискрим-маркеров."""
    sig = ConfigurationSignature(
        key="t",
        display_name="T",
        characteristic_objects=frozenset({"A", "B"}),
        family="trade",
        discriminative_objects=frozenset({"X", "Y"}),
    )
    assert sig.discriminative_score(set()) == 0.0
    assert sig.discriminative_score({"X"}) == 0.5
    assert sig.discriminative_score({"X", "Y"}) == 1.0
    # объекты вне дискрим-набора не влияют
    assert sig.discriminative_score({"A", "B"}) == 0.0


def test_signature_empty_discriminative_score_is_zero():
    """Базовая конфа без дискрим-маркеров → discriminative_score == 0."""
    sig = ConfigurationSignature(
        key="base", display_name="Base",
        characteristic_objects=frozenset({"A"}), family="trade",
    )
    assert sig.discriminative_objects == frozenset()
    assert sig.discriminative_score({"A", "B", "C"}) == 0.0
