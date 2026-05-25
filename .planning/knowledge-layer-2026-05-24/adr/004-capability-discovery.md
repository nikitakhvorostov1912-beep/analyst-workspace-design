# ADR-004: Capability Discovery — через MCP initialize experimental field

**Status:** Accepted
**Date:** 2026-05-25
**Deciders:** Никита, Claude
**Phase:** M-K1

## Context

После M6 handoff: фронту нужно знать **что умеет данный канал** до того как
рендерить UI. Например:
- Если канал = EPF (АналитикLite) → нет CFE-only фич (Activity Stream, Posting Trace)
- Если канал = чистый 1C MCP Toolkit без расширения → нет custom tools (только базовые 10)
- Если канал = CFE (АналитикПлюс) на УТ 11.5 БСП 3.1.10 → включить все 23 capabilities

Без этого фронт **угадывает** через try/catch при tool call → плохой UX (заглушки
появляются по факту ошибки).

23 capabilities matrix (см. INTEGRATION-DECISIONS.md §accepted #3):
- 8 base (mcp.execute_query, mcp.get_metadata, ...)
- 3 conditional (tools_ui.query_console если установлен tools_ui_1c, ...)
- 12 CFE extended (cfe.activity_stream, cfe.posting_trace, cfe.bsl_diagnostics, ...)

## Decision

Использовать **MCP `initialize` response, поле `experimental.analyst-1c.features`** —
сервер при handshake возвращает list of capability strings.

```jsonc
// MCP server initialize response:
{
  "protocolVersion": "2024-11-05",
  "capabilities": { "tools": {}, "resources": {} },
  "experimental": {
    "analyst-1c.features": [
      "mcp.execute_query",
      "mcp.get_metadata",
      "cfe.activity_stream",
      "cfe.posting_trace",
      "cfe.bsl_diagnostics"
    ],
    "analyst-1c.mode": "cfe",
    "analyst-1c.configuration": "УТ 11.5",
    "analyst-1c.platform": "8.3.27",
    "analyst-1c.bsp_version": "3.1.10",
    "analyst-1c.extension_version": "1.0.0"
  }
}
```

Backend кэширует это в `mcp_connections.capabilities` (JSON колонка, добавляется
DDL миграцией v11 — см. ADR-005). Frontend получает через `GET /connections/{id}`
и использует в hook `useCapability(feature)`.

## Consequences

### Положительные
- **MCP spec-compliant**: `experimental.*` зарезервировано стандартом для vendor extensions
- **No extra round-trip**: capability flag приходит при первом initialize (один HTTP)
- **Backward-compat**: старые MCP-сервера (Toolkit < 1.7.x) просто не возвращают
  experimental field → frontend получает empty list → показывает только базовый UX
- **Type-safe**: 23 capability имени фиксированы в `backend/app/types/capabilities.py`
  и `frontend/lib/capabilities.ts` (Python Literal + TS const enum)
- **Auditable**: один источник правды (initialize response), не разбросано по
  10 endpoints

### Отрицательные
- **Server должен явно вернуть list** — нашему EPF/CFE придётся имплементировать
  capability response в M-K3 Phase 13a.X (есть task в M-K3-PLAN)
- **Refresh при upgrade EPF/CFE**: пользователь обновил расширение → новые caps
  не появятся пока не перезайти / не сделать `/connections/{id}/ping` (нужен
  background refresh каждый N минут)
- **Frontend ловит initialize lag**: первый `useCapability` после connect может
  вернуть `false` пока capabilities не загрузились → нужен loading state

### Нейтральные
- Можно расширить additional fields в `experimental.analyst-1c.*` для будущих
  фич без breaking change

## Alternatives considered

| Alt | Verdict | Reason |
|---|---|---|
| **Отдельный `/capabilities` endpoint** | rejected | Extra round-trip на каждый коннект, не MCP-native |
| **Tool discovery (через list_tools)** | rejected | Только tools, нет place для metadata типа `configuration`, `bsp_version` |
| **Hardcoded matrix по channel.endpoint pattern** | rejected | Fragile (URL может измениться), не extensible |
| **Try/catch при каждом tool call** | rejected | Текущее behavior — даёт плохой UX (заглушки по факту ошибки) |
| **MCP `meta` namespace** | considered | Спорно — `experimental.*` более точный для нестандартных полей |

## References

- MCP spec experimental: https://modelcontextprotocol.io/specification/2024-11-05 §schema.experimental
- Будет в:
  - `backend/app/clients/mcp.py` (parsing experimental field) — M-K1.7
  - `backend/app/services/capability_discovery.py` (cache/refresh) — M-K1.7
  - `frontend/lib/capabilities.ts` (typed enum) — M-K1.10
  - `frontend/hooks/useCapability.ts` (React hook) — M-K1.10
- См. также ADR-005 (DDL миграция v11 для capabilities JSON column)
