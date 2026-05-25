"""Capability Discovery Service — парсинг experimental.analyst-1c.* из MCP initialize.

M-K1.7 (M6 Phase 12.2 + ADR-004).

Принцип:
- MCP сервер при `initialize` может вернуть `experimental.analyst-1c.*` (см. ADR-004)
- Если вернул — мы знаем mode/configuration/platform/ext_version/capabilities
- Если нет (raw MCP Toolkit) — fallback: mode='mcp_only', остальные NULL,
  capabilities = базовые 8 (предполагается что MCP сервер реализует Toolkit-level
  tools)

Результат сохраняется в `mcp_connections` (миграция v11, M-K1.6) и используется:
- Frontend `useCapability(feature)` hook для feature gating (M-K1.10)
- Backend для authorization (отказывать в `cfe.*` если mode != 'cfe')
- Knowledge Layer — для роутинга к правильному per-config knowledge corpus
  через fingerprint

**Не блокирует** MCP initialize если capability discovery упала — возвращает
fallback значения, логирует warning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from app.clients.mcp import MCPSession
from app.knowledge.fingerprint import (
    ConfigurationFingerprint,
    compute_fingerprint,
)
from app.types.capabilities import (
    CAPABILITIES_BASE,
    Capability,
    ChannelMode,
    validate_capability_list,
)

logger = logging.getLogger(__name__)

# Namespace conventions для experimental fields (ADR-004)
_NS_FEATURES = "analyst-1c.features"
_NS_MODE = "analyst-1c.mode"
_NS_CONFIGURATION = "analyst-1c.configuration"
_NS_CONFIG_VERSION = "analyst-1c.configuration_version"
_NS_PLATFORM = "analyst-1c.platform"
_NS_BSP_VERSION = "analyst-1c.bsp_version"
_NS_EXT_VERSION = "analyst-1c.extension_version"
_NS_EXT_UIDS = "analyst-1c.extension_uids"


_VALID_MODES: tuple[ChannelMode, ...] = ("mcp_only", "epf", "cfe")


@dataclass(frozen=True)
class CapabilityDiscoveryResult:
    """Структурированный результат discovery.

    None для optional полей означает: сервер не сообщил эту информацию.
    Capabilities = базовые 8 (mcp.*) если experimental пустой.
    Fingerprint = None если configuration_name не известен (нельзя считать).
    """

    mode: ChannelMode
    configuration: str | None
    platform: str | None
    ext_version: str | None
    capabilities: list[Capability]
    fingerprint: ConfigurationFingerprint | None
    # Внутреннее — для логов / debug
    source: Literal["experimental", "fallback"]
    raw_experimental: dict[str, object] = field(default_factory=dict)

    @property
    def capability_strings(self) -> list[str]:
        """Plain list of capability names — для JSON serialization в БД."""
        return list(self.capabilities)


def _coerce_string(value: object) -> str | None:
    """Безопасное преобразование experimental field → string. None если пустое."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else None
    # Числа, etc. — приводим к str
    cleaned = str(value).strip()
    return cleaned if cleaned else None


def _coerce_mode(value: object) -> ChannelMode:
    """Парсит experimental.analyst-1c.mode, валидирует против ChannelMode.

    Unknown / missing → 'mcp_only' (graceful fallback, не блокирует initialize).
    """
    if value is None:
        return "mcp_only"
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _VALID_MODES:
            return normalized  # type: ignore[return-value]
        logger.warning(
            "Unknown analyst-1c.mode from MCP server: %r, defaulting to 'mcp_only'",
            value,
        )
    return "mcp_only"


def _coerce_capabilities(value: object) -> list[Capability]:
    """Парсит experimental.analyst-1c.features, фильтрует unknown через registry.

    Empty / non-list → пустой список.
    Unknown capabilities игнорируются с warning (forward-compat).
    """
    if not isinstance(value, list):
        if value is not None:
            logger.warning(
                "experimental.%s ожидался list, получено %s",
                _NS_FEATURES,
                type(value).__name__,
            )
        return []
    # Все элементы → str + filter unknowns
    string_caps = [str(item) for item in value if item is not None]
    return validate_capability_list(string_caps)


def _coerce_extension_uids(value: object) -> tuple[str, ...]:
    """Парсит experimental.analyst-1c.extension_uids → tuple of strings."""
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip().lower() for item in value if item)


def discover_capabilities(session: MCPSession) -> CapabilityDiscoveryResult:
    """Парсит experimental из MCP initialize result в structured form.

    Args:
        session: результат `MCPClient.initialize()` — содержит `experimental` dict
            который мог быть наполнен сервером (ADR-004).

    Returns:
        CapabilityDiscoveryResult со всеми полями + fingerprint если возможно
        вычислить (configuration_name + platform_version известны).

    Graceful fallback:
        - Если experimental пустой → mode='mcp_only', capabilities=базовые 8,
            всё остальное None. source='fallback'.
        - Если experimental есть но какое-то поле отсутствует → используем
            что есть, недостающее → None. source='experimental'.
    """
    exp = session.experimental or {}

    if not exp:
        # Полный fallback — сервер ничего не сообщил про себя.
        # Предполагаем raw 1C MCP Toolkit → 8 базовых capabilities.
        return CapabilityDiscoveryResult(
            mode="mcp_only",
            configuration=None,
            platform=None,
            ext_version=None,
            capabilities=list(CAPABILITIES_BASE),
            fingerprint=None,
            source="fallback",
            raw_experimental={},
        )

    mode = _coerce_mode(exp.get(_NS_MODE))
    configuration = _coerce_string(exp.get(_NS_CONFIGURATION))
    config_version = _coerce_string(exp.get(_NS_CONFIG_VERSION))
    platform = _coerce_string(exp.get(_NS_PLATFORM))
    bsp_version = _coerce_string(exp.get(_NS_BSP_VERSION))
    ext_version = _coerce_string(exp.get(_NS_EXT_VERSION))
    ext_uids = _coerce_extension_uids(exp.get(_NS_EXT_UIDS))
    capabilities = _coerce_capabilities(exp.get(_NS_FEATURES))

    # Если capabilities пустые но mode заявлен — используем expected set для mode
    if not capabilities:
        if mode == "mcp_only":
            capabilities = list(CAPABILITIES_BASE)
        # Для 'epf' / 'cfe' пустой capabilities оставляем как есть — пусть сервер
        # явно их перечисляет (иначе capability discovery бесполезна).

    # Fingerprint — только если configuration_name + platform известны
    fingerprint: ConfigurationFingerprint | None = None
    if configuration and platform:
        try:
            fingerprint = compute_fingerprint(
                configuration_name=configuration,
                configuration_version=config_version or "",
                platform_version=platform,
                bsp_version=bsp_version or "",
                extension_uids=ext_uids,
            )
        except ValueError as exc:
            logger.warning(
                "Не удалось вычислить fingerprint: %s (configuration=%r, platform=%r)",
                exc,
                configuration,
                platform,
            )

    return CapabilityDiscoveryResult(
        mode=mode,
        configuration=configuration,
        platform=platform,
        ext_version=ext_version,
        capabilities=capabilities,
        fingerprint=fingerprint,
        source="experimental",
        raw_experimental=exp,
    )
