"""Базовые типы для Knowledge Layer.

M-K1.3 pre-flight. Используются модулями M-K1.4+ (storage, fingerprint,
dossier, vector_store).

Все типы:
- Immutable (`frozen=True` для dataclass) или Literal — нет mutation
- Pydantic-friendly (model_validator не нужен — простые structural types)
- Без зависимостей от backend.app.* (чтобы избежать circular imports)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ---------------------------------------------------------------------------
# Channel mode (re-export для consistency)
# ---------------------------------------------------------------------------

# Дублирует `app.types.capabilities.ChannelMode`. Дубль — намеренный, чтобы
# `app.knowledge.*` не зависел от `app.types.capabilities` (cap registry
# может ссылаться на knowledge через factory functions, обратное запрещено).
KnowledgeMode = Literal["mcp_only", "epf", "cfe"]


# ---------------------------------------------------------------------------
# Object identification
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObjectPath:
    """Полный путь к объекту 1С метаданных.

    Пример: `Документ.РеализацияТоваровУслуг`, `Справочник.Контрагенты`,
    `РегистрНакопления.ТоварыНаСкладах.Реквизиты.Партия`.

    Формат: `<Тип>.<Имя>[.<Подсекция>.<Имя>]*`. Сегменты разделены точкой.

    Attrs:
        full: Полный canonical путь (e.g. 'Документ.ОПП')
        kind: Тип верхнего уровня ('Документ', 'Справочник', 'Регистр*', ...)
        name: Имя объекта (последний сегмент)
    """

    full: str
    kind: str
    name: str

    @classmethod
    def parse(cls, raw: str) -> ObjectPath:
        """Парсит строку формата `Документ.X` или `Регистр.X.Реквизит.Y`.

        Raises:
            ValueError: если строка пустая или не содержит точки.
        """
        cleaned = (raw or "").strip()
        if not cleaned:
            raise ValueError("ObjectPath cannot be empty")
        if "." not in cleaned:
            raise ValueError(
                f"ObjectPath must contain at least one dot: {cleaned!r}"
            )
        parts = cleaned.split(".")
        return cls(full=cleaned, kind=parts[0], name=parts[-1])

    def __str__(self) -> str:
        return self.full


# ---------------------------------------------------------------------------
# Platform / configuration version
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PlatformVersion:
    """Версия платформы 1С.

    Формат source: `8.3.27.1989` → major=8, minor=3, patch=27, build=1989.

    Attrs:
        full: Исходная строка
        major: 8
        minor: 3
        patch: 27 (release)
        build: 1989 (build number)
    """

    full: str
    major: int
    minor: int
    patch: int
    build: int

    @classmethod
    def parse(cls, raw: str) -> PlatformVersion:
        """Парсит '8.3.27.1989' → PlatformVersion(...).

        Raises:
            ValueError: если строка не соответствует формату.
        """
        cleaned = (raw or "").strip()
        if not cleaned:
            raise ValueError("PlatformVersion cannot be empty")
        parts = cleaned.split(".")
        if len(parts) != 4:
            raise ValueError(
                f"PlatformVersion must have 4 segments: {cleaned!r}"
            )
        try:
            major, minor, patch, build = (int(p) for p in parts)
        except ValueError as exc:
            raise ValueError(
                f"PlatformVersion segments must be integers: {cleaned!r}"
            ) from exc
        return cls(full=cleaned, major=major, minor=minor, patch=patch, build=build)

    def __str__(self) -> str:
        return self.full

    def is_85_or_above(self) -> bool:
        """8.5.x вышел в конце 2025 — летом 2026 клиенты УТ начинают мигрировать."""
        return (self.major, self.minor) >= (8, 5)


# ---------------------------------------------------------------------------
# Knowledge subdirectories — fixed schema
# ---------------------------------------------------------------------------

KnowledgeSubdir = Literal["metadata", "embeddings", "graph", "cache", "logs"]

KNOWLEDGE_SUBDIRS: tuple[KnowledgeSubdir, ...] = (
    "metadata",   # L1 metadata_cache.json / dossier snapshots
    "embeddings", # L5 sqlite-vec (ADR-001) + corpora hashes
    "graph",      # L2 SQLite graph (ADR-002)
    "cache",      # temporary computation cache
    "logs",       # debug logs per-channel (NOT мерж с глобальным ЖР)
)
