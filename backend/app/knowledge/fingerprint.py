"""Configuration Fingerprint — стабильный идентификатор «уникальной» 1С-конфигурации.

M-K1.5 pre-flight skeleton + полная реализация compute_fingerprint.

**Назначение:**
Два канала могут указывать на УТ 11.5 на платформе 8.3.27 с теми же
расширениями — это **одна** «typed configuration» и должна делить
knowledge corpus. Иначе пользователь дублирует индексацию ИТС / БСП /
metadata для каждого канала.

Fingerprint вычисляется из стабильных характеристик инфобазы и
используется как **path slug** для `~/.analyst-1c/knowledge/<fp>/`.

**Алгоритм:** SHA-256 от канонической `Структура` следующих полей,
serialized JSON sorted_keys:
- `configuration_name` (e.g. "УправлениеТорговлей")
- `configuration_version` (e.g. "11.5.18.123")
- `platform_major_minor` (e.g. "8.3") — patch+build игнорируется
- `bsp_version_major_minor` (e.g. "3.1") — если известно
- `extension_uids` (sorted list of UUIDs of installed extensions)

Patch и build платформы намеренно опущены — иначе fingerprint менялся бы
после каждого обновления платформы (что dropped бы весь knowledge).
Минорные платформенные обновления — стабильность важнее точности.

Расширения важны: с разными расширениями платформа возвращает разные
объекты метаданных, что меняет дерево L1.

Длина итогового slug — 12 hex chars (collision risk negligible на масштабе
~10K каналов одного пользователя).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigurationFingerprint:
    """Стабильный fingerprint типовой конфигурации + платформы + расширений.

    Attrs:
        slug: Короткий hex (12 chars) — для path.
        full_hash: Полный SHA-256 (64 chars) — для audit / equality check.
        source_fields: Каноническая структура которая хешировалась
            (для отладки и логов).
    """

    slug: str
    full_hash: str
    source_fields: dict[str, object]

    def __str__(self) -> str:
        return self.slug


def _canonical_source(
    *,
    configuration_name: str,
    configuration_version: str,
    platform_version: str,
    bsp_version: str = "",
    extension_uids: tuple[str, ...] = (),
) -> dict[str, object]:
    """Каноническая форма для serialization.

    Все строки lowercase + trimmed чтобы 'УТ' и 'ут ' давали одинаковый
    fingerprint. UUID's sorted — нечувствительность к порядку.

    platform_version обрезается до major.minor (см. docstring).
    bsp_version обрезается до major.minor если задан.
    """
    plat = (platform_version or "").strip()
    if plat:
        parts = plat.split(".")
        plat_short = ".".join(parts[:2]) if len(parts) >= 2 else plat
    else:
        plat_short = ""

    bsp = (bsp_version or "").strip()
    if bsp:
        parts = bsp.split(".")
        bsp_short = ".".join(parts[:2]) if len(parts) >= 2 else bsp
    else:
        bsp_short = ""

    return {
        "configuration_name": (configuration_name or "").strip().lower(),
        "configuration_version": (configuration_version or "").strip().lower(),
        "platform_major_minor": plat_short,
        "bsp_version_major_minor": bsp_short,
        "extension_uids": sorted(
            (uid or "").strip().lower() for uid in extension_uids if uid
        ),
    }


def compute_fingerprint(
    *,
    configuration_name: str,
    configuration_version: str,
    platform_version: str,
    bsp_version: str = "",
    extension_uids: tuple[str, ...] = (),
) -> ConfigurationFingerprint:
    """Вычислить fingerprint типовой конфигурации.

    Использовать в `/connections/{id}/ping` handler чтобы вычислить slug
    после успешного MCP initialize.

    Args:
        configuration_name: "УправлениеТорговлей" / "ERPУправлениеПредприятием2"
        configuration_version: "11.5.18.123"
        platform_version: "8.3.27.1989" — обрежется до "8.3"
        bsp_version: "3.1.10.123" (опционально) — обрежется до "3.1"
        extension_uids: tuple UUID's установленных расширений

    Returns:
        ConfigurationFingerprint с slug (12 hex) + full_hash + source_fields.

    Raises:
        ValueError: если configuration_name пустой или platform_version
            не парсится (минимум "8.X").
    """
    if not (configuration_name or "").strip():
        raise ValueError("configuration_name is required for fingerprint")
    plat_clean = (platform_version or "").strip()
    if not plat_clean or "." not in plat_clean:
        raise ValueError(
            f"platform_version must contain at least major.minor: {plat_clean!r}"
        )

    source = _canonical_source(
        configuration_name=configuration_name,
        configuration_version=configuration_version,
        platform_version=platform_version,
        bsp_version=bsp_version,
        extension_uids=extension_uids,
    )
    canonical_json = json.dumps(source, sort_keys=True, ensure_ascii=False)
    full_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    slug = full_hash[:12]
    return ConfigurationFingerprint(
        slug=slug,
        full_hash=full_hash,
        source_fields=source,
    )


def fingerprint_from_string(raw: str) -> ConfigurationFingerprint:
    """Восстановить ConfigurationFingerprint из сохранённого slug.

    Используется когда мы знаем только slug (e.g. из БД `mcp_connections.fingerprint`)
    но не source_fields. source_fields будет пустой dict.

    Безопасно для чтения path / equality check.
    """
    cleaned = (raw or "").strip().lower()
    if not cleaned or len(cleaned) != 12:
        raise ValueError(
            f"fingerprint slug must be 12 hex chars, got: {raw!r}"
        )
    # Валидация что hex
    try:
        int(cleaned, 16)
    except ValueError as exc:
        raise ValueError(
            f"fingerprint slug must be hex: {raw!r}"
        ) from exc
    # full_hash неизвестен — нельзя восстановить только из slug
    return ConfigurationFingerprint(
        slug=cleaned,
        full_hash="",
        source_fields={},
    )
