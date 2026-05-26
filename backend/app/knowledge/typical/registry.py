"""Typical Configurations Registry — kinds, namespaces, version parsing.

Per ADR-003 (D2): каждой типовой выдаётся фиксированный channel_id с
префиксом `_<kind><minor>_<patch>`, например `_ut115_18_193` для
УТ 11.5.18.193. Реальные MCP-каналы используют UUID v4, никогда не
начинаются с `_` — namespace гарантированно безопасен.

Зарезервированные namespace согласно прецеденту M-K2: `_its` (ИТС),
`_bsp` (БСП). Этот модуль расширяет список префиксами для типовых.

## Поддерживаемые конфигурации

| Kind | Префикс channel | Релизная линейка |
|---|---|---|
| UT_115 | `_ut115_` | Управление торговлей 11.5.x |
| ERP_25 | `_erp25_` | ERP Управление предприятием 2.5.x |
| KA_2 | `_ka2_` | Комплексная автоматизация 2.5.x |
| BP_30 | `_bp30_` | Бухгалтерия предприятия 3.0.x |
| ZUP_31 | `_zup31_` | Зарплата и управление персоналом 3.1.x |
| USO_25 | `_uso25_` | Управление строительной организацией 2.5.x |
| DOCFLOW_3 | `_docflow3_` | 1С:Документооборот 3.x |
"""

from __future__ import annotations

from enum import Enum


class TypicalConfigKind(str, Enum):
    """Тип типовой конфигурации 1С.

    Значение enum'а совпадает с config_kind колонкой БД и используется
    как ключ в RESERVED_PREFIXES / DISPLAY_NAMES.
    """

    UT_115 = "UT_115"
    ERP_25 = "ERP_25"
    KA_2 = "KA_2"
    BP_30 = "BP_30"
    ZUP_31 = "ZUP_31"
    USO_25 = "USO_25"
    DOCFLOW_3 = "DOCFLOW_3"


# Зарезервированные channel_id префиксы для каждой конфигурации.
# Полный channel_id формируется как `<prefix><minor>_<patch>`
# (например `_ut115_` + `18_193` = `_ut115_18_193`).
RESERVED_PREFIXES: dict[TypicalConfigKind, str] = {
    TypicalConfigKind.UT_115: "_ut115_",
    TypicalConfigKind.ERP_25: "_erp25_",
    TypicalConfigKind.KA_2: "_ka2_",
    TypicalConfigKind.BP_30: "_bp30_",
    TypicalConfigKind.ZUP_31: "_zup31_",
    TypicalConfigKind.USO_25: "_uso25_",
    TypicalConfigKind.DOCFLOW_3: "_docflow3_",
}


# Человекочитаемые имена конфигураций. Используются для:
#   - display_name в БД (typical_configurations.display_name)
#   - UI селектор «Сравнить с УТ 11.5»
#   - LLM-промптах при генерации карточек
DISPLAY_NAMES: dict[TypicalConfigKind, str] = {
    TypicalConfigKind.UT_115: "Управление торговлей 11.5",
    TypicalConfigKind.ERP_25: "ERP Управление предприятием 2.5",
    TypicalConfigKind.KA_2: "Комплексная автоматизация 2.5",
    TypicalConfigKind.BP_30: "Бухгалтерия предприятия 3.0",
    TypicalConfigKind.ZUP_31: "Зарплата и управление персоналом 3.1",
    TypicalConfigKind.USO_25: "Управление строительной организацией 2.5",
    TypicalConfigKind.DOCFLOW_3: "1С:Документооборот 3",
}


def parse_version_tuple(version: str) -> tuple[int, ...]:
    """Парсит строку версии '11.5.18.193' в tuple (11, 5, 18, 193).

    Принимает любое количество компонентов, отделённых точками.
    Каждый компонент должен быть числом (без 'b1', 'rc2' и т.п.).
    Используется для:
      - сборки channel_id (берём последние 2 компонента — minor.patch)
      - сортировки по версии при fallback (закрытие D1 — ближайшая известная)

    >>> parse_version_tuple("11.5.18.193")
    (11, 5, 18, 193)
    >>> parse_version_tuple("3.0.158.18")
    (3, 0, 158, 18)
    >>> parse_version_tuple("invalid")
    Traceback (most recent call last):
        ...
    ValueError: Не удалось распарсить версию: 'invalid' (компонент 'invalid' не число)
    """
    if not version or not version.strip():
        raise ValueError(f"Не удалось распарсить версию: пустая строка")

    parts: list[int] = []
    for component in version.strip().split("."):
        try:
            parts.append(int(component))
        except ValueError as exc:
            raise ValueError(
                f"Не удалось распарсить версию: {version!r} "
                f"(компонент {component!r} не число)"
            ) from exc

    if not parts:
        raise ValueError(f"Не удалось распарсить версию: {version!r}")

    return tuple(parts)


def reserved_channel_id(kind: TypicalConfigKind, version: str) -> str:
    """Собирает channel_id из (kind, version).

    Берёт последние **два** компонента версии: minor + patch. Это даёт
    стабильный namespace per-release: УТ 11.5.18.193 → `_ut115_18_193`.

    Major-часть версии уже зашита в префикс (UT_115 → `_ut115_`
    означает «Управление торговлей **11.5**»).

    >>> reserved_channel_id(TypicalConfigKind.UT_115, "11.5.18.193")
    '_ut115_18_193'
    >>> reserved_channel_id(TypicalConfigKind.ERP_25, "2.5.18.245")
    '_erp25_18_245'
    >>> reserved_channel_id(TypicalConfigKind.BP_30, "3.0.158.18")
    '_bp30_158_18'

    Если версия короче двух компонентов — ValueError:
    >>> reserved_channel_id(TypicalConfigKind.UT_115, "11")
    Traceback (most recent call last):
        ...
    ValueError: Версия '11' слишком короткая — нужно минимум 2 компонента (minor.patch)
    """
    prefix = RESERVED_PREFIXES[kind]
    parts = parse_version_tuple(version)
    if len(parts) < 2:
        raise ValueError(
            f"Версия {version!r} слишком короткая — нужно минимум 2 компонента "
            f"(minor.patch)"
        )
    minor, patch = parts[-2], parts[-1]
    return f"{prefix}{minor}_{patch}"


def is_reserved_channel(channel_id: str) -> bool:
    """True если channel_id попадает в один из зарезервированных namespace'ов.

    Реальные MCP-каналы используют UUID v4 (никогда не начинаются с `_`),
    поэтому проверка по префиксу безопасна.
    """
    return any(
        channel_id.startswith(prefix) for prefix in RESERVED_PREFIXES.values()
    ) or channel_id in ("_its", "_bsp")
