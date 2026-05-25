"""Capability matrix — 23 feature flags для Multi-MCP + EPF/CFE delivery.

G10 (M-K0.10): создан как pre-flight для M-K1.

Источник истины: ADR-004 (Capability Discovery), M6 Phase 12,
INTEGRATION-DECISIONS.md §accepted #3.

23 capabilities = 8 base + 3 conditional + 12 CFE extended.

**Naming convention** (Q1 resolved): namespace `<source>.<feature>`:
- `mcp.*` — базовые MCP Toolkit tools (всегда есть в любом канале)
- `tools_ui.*` — опциональный tools_ui_1c (если установлен)
- `cfe.*` — CFE-only фичи через подсистему `АналитикПлюс`
- `epf.*` — EPF-specific (когда EPF, capability response явный)

**Использование:**
- Backend: `Capability` Literal type для validation incoming capability lists
  из MCP `experimental.analyst-1c.features`
- Backend: `CAPABILITIES_BASE/CONDITIONAL/CFE` sets для feature gating per
  request
- Frontend: tooling/lib/capabilities.ts (TS const enum) ZERO-DUP source
  (этот файл — single source of truth)

**Расширение:**
Новые capabilities добавляются в `_ALL_CAPABILITIES` + соответствующий set.
Synchroniseать с frontend через `pnpm gen:capabilities` (генератор M-K1.10).
"""

from __future__ import annotations

from typing import Literal, Final

# ---------------------------------------------------------------------------
# Base capabilities (8) — всегда доступны при любом MCP канале
# ---------------------------------------------------------------------------

CapabilityBase = Literal[
    "mcp.execute_query",       # SELECT-only queries to 1С
    "mcp.get_metadata",        # Metadata tree / object structure
    "mcp.get_object",          # Object by navigation link
    "mcp.get_link_of_object",  # Reverse
    "mcp.find_references",     # Where object is used
    "mcp.get_access_rights",   # Role / user permissions
    "mcp.get_event_log",       # Журнал регистрации (15 фильтров)
    "mcp.get_bsl_syntax_help", # Built-in BSL functions help
]

CAPABILITIES_BASE: Final[frozenset[CapabilityBase]] = frozenset({
    "mcp.execute_query",
    "mcp.get_metadata",
    "mcp.get_object",
    "mcp.get_link_of_object",
    "mcp.find_references",
    "mcp.get_access_rights",
    "mcp.get_event_log",
    "mcp.get_bsl_syntax_help",
})

# ---------------------------------------------------------------------------
# Conditional capabilities (3) — зависят от установленных расширений
# ---------------------------------------------------------------------------

CapabilityConditional = Literal[
    "tools_ui.query_console",       # ⛕ если установлен tools_ui_1c (GPL-3.0 opt-in)
    "mcp.execute_code",             # ⛕ если канал даёт execute_code (опасно)
    "mcp.submit_for_deanonymization", # ⛕ если анонимизация активна
]

CAPABILITIES_CONDITIONAL: Final[frozenset[CapabilityConditional]] = frozenset({
    "tools_ui.query_console",
    "mcp.execute_code",
    "mcp.submit_for_deanonymization",
})

# ---------------------------------------------------------------------------
# CFE extended capabilities (12) — только при подключении CFE АналитикПлюс
# ---------------------------------------------------------------------------

CapabilityCFE = Literal[
    "cfe.activity_stream",       # Real-time events через подписки
    "cfe.posting_trace",         # Per-document trace при ПередЗаписью
    "cfe.bsl_diagnostics",       # BSL LS через CFE (Phase 15)
    "cfe.method_overrides",      # Перехват методов типовых
    "cfe.hmac_sso",              # HMAC SSO между EPF и CFE
    "cfe.refactor_planner",      # L5-5 refactor predictions
    "cfe.compliance_check",      # L5-4 ИТС compliance
    "cfe.knowledge_graph",       # L2 graph через CFE accessors
    "cfe.rls_tracer",            # RLS-tracer use case
    "cfe.deadlock_tracer",       # L4-4 deadlock analysis
    "cfe.posting_explainer",     # «почему документ записался» L4
    "cfe.subsystem_metadata",    # Метаданные подсистемы АналитикПлюс
]

CAPABILITIES_CFE: Final[frozenset[CapabilityCFE]] = frozenset({
    "cfe.activity_stream",
    "cfe.posting_trace",
    "cfe.bsl_diagnostics",
    "cfe.method_overrides",
    "cfe.hmac_sso",
    "cfe.refactor_planner",
    "cfe.compliance_check",
    "cfe.knowledge_graph",
    "cfe.rls_tracer",
    "cfe.deadlock_tracer",
    "cfe.posting_explainer",
    "cfe.subsystem_metadata",
})

# ---------------------------------------------------------------------------
# Union — для типизации API ответов
# ---------------------------------------------------------------------------

Capability = Literal[
    # base
    "mcp.execute_query",
    "mcp.get_metadata",
    "mcp.get_object",
    "mcp.get_link_of_object",
    "mcp.find_references",
    "mcp.get_access_rights",
    "mcp.get_event_log",
    "mcp.get_bsl_syntax_help",
    # conditional
    "tools_ui.query_console",
    "mcp.execute_code",
    "mcp.submit_for_deanonymization",
    # cfe
    "cfe.activity_stream",
    "cfe.posting_trace",
    "cfe.bsl_diagnostics",
    "cfe.method_overrides",
    "cfe.hmac_sso",
    "cfe.refactor_planner",
    "cfe.compliance_check",
    "cfe.knowledge_graph",
    "cfe.rls_tracer",
    "cfe.deadlock_tracer",
    "cfe.posting_explainer",
    "cfe.subsystem_metadata",
]

ALL_CAPABILITIES: Final[frozenset[Capability]] = (
    CAPABILITIES_BASE | CAPABILITIES_CONDITIONAL | CAPABILITIES_CFE
)

# Sanity check at import time
assert len(ALL_CAPABILITIES) == 23, (
    f"Expected 23 capabilities, got {len(ALL_CAPABILITIES)}"
)


# ---------------------------------------------------------------------------
# Channel modes — связаны с capability discovery (ADR-004)
# ---------------------------------------------------------------------------

ChannelMode = Literal[
    "mcp_only",   # Raw 1C MCP Toolkit без расширения (8 base only)
    "epf",        # АналитикLite.epf (8 base + capability response без CFE-only)
    "cfe",        # АналитикПлюс.cfe (full 23, требует BSL 3.1+)
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def filter_capabilities_for_mode(mode: ChannelMode) -> frozenset[Capability]:
    """Возвращает набор capabilities ожидаемый для данного режима канала.

    Используется в backend authorization layer:
    - `cfe.*` отвергается если mode != "cfe"
    - `tools_ui.*` опционально для всех режимов

    NB: это **expected** set, реальный список приходит от MCP сервера через
    `experimental.analyst-1c.features` (ADR-004). Это лишь sanity check для
    UI / typing.
    """
    if mode == "mcp_only":
        return CAPABILITIES_BASE
    if mode == "epf":
        return CAPABILITIES_BASE | CAPABILITIES_CONDITIONAL
    if mode == "cfe":
        return ALL_CAPABILITIES
    raise ValueError(f"Unknown channel mode: {mode}")


def validate_capability_list(caps: list[str]) -> list[Capability]:
    """Фильтрует list of strings до valid Capability, отбрасывает unknown.

    Используется при parsing `experimental.analyst-1c.features` — внешний
    MCP сервер может вернуть unknown capability (forward-compat), мы их
    логируем как warning и игнорируем для UI.
    """
    valid: list[Capability] = []
    for cap in caps:
        if cap in ALL_CAPABILITIES:
            valid.append(cap)  # type: ignore[arg-type]
    return valid
