"""Tests for app.knowledge.types (M-K1.3 skeleton)."""

from __future__ import annotations

import pytest

from app.knowledge.types import (
    KNOWLEDGE_SUBDIRS,
    KnowledgeSubdir,
    ObjectPath,
    PlatformVersion,
)


# ---------------------------------------------------------------------------
# ObjectPath
# ---------------------------------------------------------------------------


def test_object_path_parse_simple() -> None:
    p = ObjectPath.parse("Документ.ОПП")
    assert p.full == "Документ.ОПП"
    assert p.kind == "Документ"
    assert p.name == "ОПП"


def test_object_path_parse_nested() -> None:
    p = ObjectPath.parse("РегистрНакопления.ТоварыНаСкладах.Реквизиты.Партия")
    assert p.full == "РегистрНакопления.ТоварыНаСкладах.Реквизиты.Партия"
    assert p.kind == "РегистрНакопления"
    assert p.name == "Партия"


def test_object_path_strips_whitespace() -> None:
    p = ObjectPath.parse("  Справочник.Контрагенты  ")
    assert p.full == "Справочник.Контрагенты"


def test_object_path_str_returns_full() -> None:
    p = ObjectPath.parse("Документ.ОПП")
    assert str(p) == "Документ.ОПП"


def test_object_path_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        ObjectPath.parse("")
    with pytest.raises(ValueError, match="empty"):
        ObjectPath.parse("   ")


def test_object_path_no_dot_raises() -> None:
    with pytest.raises(ValueError, match="at least one dot"):
        ObjectPath.parse("invalidsingleword")


def test_object_path_frozen_immutable() -> None:
    """Dataclass(frozen=True) — нельзя мутировать."""
    p = ObjectPath.parse("Документ.ОПП")
    with pytest.raises(Exception):  # FrozenInstanceError
        p.name = "Другое"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PlatformVersion
# ---------------------------------------------------------------------------


def test_platform_version_parse() -> None:
    v = PlatformVersion.parse("8.3.27.1989")
    assert v.major == 8
    assert v.minor == 3
    assert v.patch == 27
    assert v.build == 1989
    assert v.full == "8.3.27.1989"


def test_platform_version_str() -> None:
    v = PlatformVersion.parse("8.3.27.1989")
    assert str(v) == "8.3.27.1989"


def test_platform_version_85_detection() -> None:
    """8.5.x — летом 2026 клиенты УТ начинают мигрировать (8.5-Ready)."""
    v_83 = PlatformVersion.parse("8.3.27.1989")
    assert v_83.is_85_or_above() is False

    v_85 = PlatformVersion.parse("8.5.1.123")
    assert v_85.is_85_or_above() is True

    v_854 = PlatformVersion.parse("8.5.4.5000")
    assert v_854.is_85_or_above() is True

    v_90 = PlatformVersion.parse("9.0.0.1")
    assert v_90.is_85_or_above() is True


def test_platform_version_invalid_format_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        PlatformVersion.parse("")
    with pytest.raises(ValueError, match="4 segments"):
        PlatformVersion.parse("8.3.27")
    with pytest.raises(ValueError, match="4 segments"):
        PlatformVersion.parse("8.3")
    with pytest.raises(ValueError, match="integers"):
        PlatformVersion.parse("8.3.27.abc")


# ---------------------------------------------------------------------------
# KNOWLEDGE_SUBDIRS
# ---------------------------------------------------------------------------


def test_knowledge_subdirs_constant() -> None:
    """5 subdirs: metadata/embeddings/graph/cache/logs (см. ADR + storage.py)."""
    assert KNOWLEDGE_SUBDIRS == ("metadata", "embeddings", "graph", "cache", "logs")
    assert len(KNOWLEDGE_SUBDIRS) == 5
