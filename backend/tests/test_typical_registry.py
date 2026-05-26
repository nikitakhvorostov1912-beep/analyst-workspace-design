"""Тесты для backend/app/knowledge/typical/registry.py (M-K2.5.0).

Покрытие:
- TypicalConfigKind enum
- RESERVED_PREFIXES и DISPLAY_NAMES маппинги
- parse_version_tuple: валидные / невалидные кейсы
- reserved_channel_id: 7 конфигураций + edge cases
- is_reserved_channel: префиксы + _its / _bsp + реальные UUID
"""

from __future__ import annotations

import pytest

from app.knowledge.typical.registry import (
    DISPLAY_NAMES,
    RESERVED_PREFIXES,
    TypicalConfigKind,
    is_reserved_channel,
    parse_version_tuple,
    reserved_channel_id,
)


# ---------- TypicalConfigKind enum ----------


def test_kind_enum_values_match_db_strings():
    """Значения enum'а используются как config_kind в БД (ADR-003 D2)."""
    assert TypicalConfigKind.UT_115.value == "UT_115"
    assert TypicalConfigKind.ERP_25.value == "ERP_25"
    assert TypicalConfigKind.KA_2.value == "KA_2"
    assert TypicalConfigKind.BP_30.value == "BP_30"
    assert TypicalConfigKind.ZUP_31.value == "ZUP_31"
    assert TypicalConfigKind.USO_25.value == "USO_25"
    assert TypicalConfigKind.DOCFLOW_3.value == "DOCFLOW_3"


def test_kind_enum_is_str_subclass():
    """Enum должен быть str-производным — для прямой записи в БД."""
    assert isinstance(TypicalConfigKind.UT_115, str)


def test_all_kinds_have_reserved_prefix():
    """Каждой Kind соответствует префикс в RESERVED_PREFIXES."""
    for kind in TypicalConfigKind:
        assert kind in RESERVED_PREFIXES, f"{kind} нет в RESERVED_PREFIXES"
        prefix = RESERVED_PREFIXES[kind]
        assert prefix.startswith("_"), f"Префикс {kind} должен начинаться с _"
        assert prefix.endswith("_"), f"Префикс {kind} должен оканчиваться на _"


def test_all_kinds_have_display_name():
    """Каждой Kind соответствует display_name на русском."""
    for kind in TypicalConfigKind:
        assert kind in DISPLAY_NAMES, f"{kind} нет в DISPLAY_NAMES"
        name = DISPLAY_NAMES[kind]
        assert name, f"Пустое имя для {kind}"
        # display_names на русском — проверка через кириллицу
        assert any("а" <= ch.lower() <= "я" for ch in name), (
            f"Имя {kind} не содержит русских букв: {name!r}"
        )


def test_reserved_prefixes_unique():
    """Префиксы не пересекаются — гарантирует уникальность namespace."""
    prefixes = list(RESERVED_PREFIXES.values())
    assert len(prefixes) == len(set(prefixes))


# ---------- parse_version_tuple ----------


@pytest.mark.parametrize(
    "version,expected",
    [
        ("11.5.18.193", (11, 5, 18, 193)),
        ("2.5.18.245", (2, 5, 18, 245)),
        ("3.0.158.18", (3, 0, 158, 18)),
        ("3", (3,)),
        ("11.5", (11, 5)),
        ("1.0.0.0.0", (1, 0, 0, 0, 0)),  # больше 4 компонентов
    ],
)
def test_parse_version_valid(version, expected):
    assert parse_version_tuple(version) == expected


@pytest.mark.parametrize(
    "bad_version",
    [
        "",
        "   ",
        "invalid",
        "11.5.abc.193",
        "11..5",  # пустой компонент посередине → fail на int("")
        "11.5.18.193-rc1",  # суффикс не число
    ],
)
def test_parse_version_invalid(bad_version):
    with pytest.raises(ValueError):
        parse_version_tuple(bad_version)


def test_parse_version_strips_whitespace():
    assert parse_version_tuple("  11.5.18.193  ") == (11, 5, 18, 193)


# ---------- reserved_channel_id ----------


@pytest.mark.parametrize(
    "kind,version,expected",
    [
        (TypicalConfigKind.UT_115, "11.5.18.193", "_ut115_18_193"),
        (TypicalConfigKind.UT_115, "11.5.20.5", "_ut115_20_5"),
        (TypicalConfigKind.ERP_25, "2.5.18.245", "_erp25_18_245"),
        (TypicalConfigKind.KA_2, "2.5.15.130", "_ka2_15_130"),
        (TypicalConfigKind.BP_30, "3.0.158.18", "_bp30_158_18"),
        (TypicalConfigKind.ZUP_31, "3.1.30.85", "_zup31_30_85"),
        (TypicalConfigKind.USO_25, "2.5.14.50", "_uso25_14_50"),
        (TypicalConfigKind.DOCFLOW_3, "3.0.13.5", "_docflow3_13_5"),
    ],
)
def test_reserved_channel_id_for_all_kinds(kind, version, expected):
    assert reserved_channel_id(kind, version) == expected


def test_reserved_channel_id_takes_last_two_components():
    """Major-часть зашита в префикс — берём последние 2 компонента версии."""
    assert reserved_channel_id(TypicalConfigKind.UT_115, "11.5.18.193") == "_ut115_18_193"


def test_reserved_channel_id_short_version_fails():
    """Версия < 2 компонентов не даёт собрать channel_id."""
    with pytest.raises(ValueError, match="слишком короткая"):
        reserved_channel_id(TypicalConfigKind.UT_115, "11")


def test_reserved_channel_id_two_component_version_works():
    """Минимальная версия — два компонента (minor.patch напрямую)."""
    assert reserved_channel_id(TypicalConfigKind.UT_115, "5.193") == "_ut115_5_193"


def test_reserved_channel_id_propagates_invalid_version_error():
    """Невалидная версия пробрасывает ValueError из parse_version_tuple."""
    with pytest.raises(ValueError):
        reserved_channel_id(TypicalConfigKind.UT_115, "abc.def")


# ---------- is_reserved_channel ----------


@pytest.mark.parametrize(
    "channel_id",
    [
        "_ut115_18_193",
        "_erp25_18_245",
        "_bp30_158_18",
        "_zup31_30_85",
        "_uso25_14_50",
        "_ka2_15_130",
        "_docflow3_13_5",
        "_its",
        "_bsp",
    ],
)
def test_is_reserved_channel_true(channel_id):
    assert is_reserved_channel(channel_id)


@pytest.mark.parametrize(
    "channel_id",
    [
        # UUID v4 каналов — никогда не зарезервированы
        "550e8400-e29b-41d4-a716-446655440000",
        "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        # Без подчёркивания
        "ut115_18_193",
        # Произвольная строка без префикса
        "channel-1",
        "",
    ],
)
def test_is_reserved_channel_false(channel_id):
    assert not is_reserved_channel(channel_id)


def test_namespace_isolation_from_real_channels():
    """Реальные MCP-каналы — UUID v4, никогда не начинаются с _."""
    import uuid

    for _ in range(20):
        uid = str(uuid.uuid4())
        assert not uid.startswith("_")
        assert not is_reserved_channel(uid)
