# 02 — Capability Discovery Protocol + Frontend Feature Flags

## MCP Capability Discovery Protocol

### Зачем

MCP-стандарт (spec 2024-11-05) описывает `initialize` ответ с `serverInfo` и `capabilities.tools`. Этого недостаточно — нужна **семантика** что именно умеет данный сервер, чтобы frontend мог понять какие UI модули включать.

### Решение: `experimental.analyst-1c.features`

Расширяем стандартный `initialize` через `experimental` namespace (это allowed по MCP spec):

### Полный ответ MCP `initialize` для EPF режима

```json
{
  "protocolVersion": "2024-11-05",
  "serverInfo": {
    "name": "Аналитик Lite",
    "version": "2.0.0"
  },
  "capabilities": {
    "tools": {},
    "experimental": {
      "analyst-1c": {
        "mode": "epf",
        "configuration": "УТ_11.5",
        "platform": "8.3.27.1989",
        "extensionVersion": null,
        "epfVersion": "2.0.0",
        "host": "ut_rt_copy",
        "features": [
          "mcp.execute_query",
          "mcp.execute_code",
          "mcp.get_metadata",
          "mcp.get_event_log",
          "mcp.find_references",
          "mcp.get_access_rights",
          "mcp.bsl_syntax_help",
          "connector.http_request"
        ]
      }
    }
  }
}
```

### Полный ответ для CFE режима

```json
{
  "protocolVersion": "2024-11-05",
  "serverInfo": {
    "name": "АналитикПлюс",
    "version": "2.0.0"
  },
  "capabilities": {
    "tools": {},
    "experimental": {
      "analyst-1c": {
        "mode": "cfe",
        "configuration": "УТ_11.5",
        "platform": "8.3.27.1989",
        "extensionVersion": "2.0.5",
        "epfVersion": null,
        "host": "ut_rt_copy",
        "ssl_version": "3.1.12",
        "features": [
          "mcp.execute_query",
          "mcp.execute_code",
          "mcp.get_metadata",
          "mcp.get_event_log",
          "mcp.find_references",
          "mcp.get_access_rights",
          "mcp.bsl_syntax_help",
          "connector.http_request",
          "tools_ui.query_console",
          "tools_ui.code_console",
          "tools_ui.dedup_finder",
          "cfe.persistent_http",
          "cfe.event_subscriptions",
          "cfe.method_overrides",
          "cfe.privileged_mode",
          "cfe.monitoring_register",
          "cfe.activity_stream",
          "cfe.posting_trace",
          "cfe.scheduled_jobs",
          "cfe.custom_commands",
          "cfe.settings_storage",
          "cfe.hot_reload_metadata",
          "auth.hmac_session"
        ]
      }
    }
  }
}
```

### Для external MCP (1c-buddy, mcp-bsl-context, METR, EDT-MCP)

```json
{
  "protocolVersion": "2024-11-05",
  "serverInfo": {
    "name": "1C.ai Gateway MCP",
    "version": "1.0.0"
  },
  "capabilities": {
    "tools": {},
    "experimental": {
      "analyst-1c": {
        "mode": "external",
        "type": "knowledge",
        "features": [
          "external.its_search",
          "external.its_fetch",
          "external.platform_search",
          "external.code_review",
          "external.documentation_diff"
        ]
      }
    }
  }
}
```

### Backwards compatibility

Если MCP отвечает **без** `experimental.analyst-1c` (например, старый MCP Toolkit v1.6) — backend применяет **legacy mode**:

```python
def parse_capabilities(initialize_response: dict) -> ConnectionMetadata:
    exp = initialize_response.get("capabilities", {}).get("experimental", {})
    analyst = exp.get("analyst-1c")

    if not analyst:
        # Legacy MCP — assume basic capabilities based on advertised tools
        tools = initialize_response.get("capabilities", {}).get("tools", {})
        return ConnectionMetadata(
            mode="legacy",
            features=_infer_features_from_tools(tools),
            warnings=["Сервер не сообщает capabilities, используется базовый режим"],
        )

    return ConnectionMetadata(
        mode=analyst["mode"],
        configuration=analyst.get("configuration"),
        platform=analyst.get("platform"),
        extension_version=analyst.get("extensionVersion"),
        features=analyst["features"],
    )
```

## Backend поток

### `app/services/capability_discovery.py`

```python
from app.services.mcp_clients.base import MCPClient
from app.models.connection import MCPConnection


async def discover_capabilities(connection: MCPConnection) -> None:
    """Опрашивает MCP на capabilities, обновляет в БД."""
    client = MCPClient.from_connection(connection)

    try:
        init_response = await client.initialize()
        metadata = parse_capabilities(init_response)

        connection.mode = metadata.mode
        connection.configuration = metadata.configuration
        connection.platform_version = metadata.platform
        connection.extension_version = metadata.extension_version
        connection.capabilities = metadata.features
        connection.last_handshake_at = datetime.utcnow()
        connection.last_error = None

    except Exception as e:
        connection.last_error = str(e)
        connection.is_active = False

    await db.commit(connection)
```

### Когда вызывается

1. **При создании MCP подключения** (POST /connections)
2. **При reactivate** (если был ошибочный)
3. **Каждые 60 секунд** (heartbeat) — проверка что capabilities не изменились
4. **По кнопке "Обновить"** в Settings → MCP

### `app/services/llm_orchestrator.py` — фильтрация tools

```python
async def build_tools_for_session(session: Session) -> list[Tool]:
    """Возвращает только tools для capabilities активных подключений."""
    active_connections = await get_active_connections(session.workspace_id)
    all_tools = []

    for conn in active_connections:
        if conn.mode == "legacy":
            tools = await conn.list_tools()
        else:
            tools = filter_tools_by_capabilities(
                await conn.list_tools(),
                conn.capabilities
            )

        # Добавляем префикс к именам tools чтобы избежать конфликтов
        for tool in tools:
            tool.name = f"{conn.short_name}.{tool.name}"
            all_tools.append(tool)

    return all_tools
```

## Frontend Feature Flags

### `lib/capabilities.ts`

```typescript
// Все возможные capabilities в системе
export const ALL_CAPABILITIES = {
  // base mcp
  'mcp.execute_query': 'Чтение данных запросами',
  'mcp.execute_code': 'Выполнение BSL кода',
  'mcp.get_metadata': 'Структура базы',
  'mcp.get_event_log': 'Журнал регистрации',
  'mcp.find_references': 'Поиск использования',
  'mcp.get_access_rights': 'Анализ прав',
  'mcp.bsl_syntax_help': 'Справочник BSL',
  'connector.http_request': 'HTTP-вызовы из 1С',

  // tools_ui (EPF: optional, CFE: builtin)
  'tools_ui.query_console': 'Консоль запросов',
  'tools_ui.code_console': 'Консоль кода',
  'tools_ui.dedup_finder': 'Поиск дубликатов',

  // CFE-only
  'cfe.persistent_http': '24/7 сервер без открытой формы',
  'cfe.event_subscriptions': 'Подписки на события',
  'cfe.method_overrides': 'Перехват типовых методов',
  'cfe.privileged_mode': 'Привилегированный режим',
  'cfe.monitoring_register': 'Регистр мониторинга',
  'cfe.activity_stream': 'Поток активности',
  'cfe.posting_trace': 'Трассировка проведения',
  'cfe.scheduled_jobs': 'Регламентные задания',
  'cfe.custom_commands': 'Кастомные команды',
  'cfe.settings_storage': 'Хранилище настроек',
  'cfe.hot_reload_metadata': 'Hot reload кеша метаданных',
  'auth.hmac_session': 'HMAC SSO от 1С',

  // external MCP
  'external.its_search': 'Поиск по ИТС',
  'external.its_fetch': 'Получение статей ИТС',
  'external.platform_search': 'Поиск по справке платформы',
  'external.code_review': 'Code review через AI',
  'external.documentation_diff': 'Сравнение версий документации',

  // backend services
  'service.rag_v8std': 'RAG по 317 стандартам',
  'service.rag_ssl': 'RAG по БСП API',
  'service.rag_platform': 'RAG по справке платформы',
  'service.bsl_ls': 'BSL Language Server',
  'service.metavision': 'MetaVision граф',
} as const;

export type Capability = keyof typeof ALL_CAPABILITIES;
```

### `lib/feature-modules.ts`

```typescript
export const FEATURE_MODULES = {
  // Sidebar модули
  activity_stream: {
    requires: ['cfe.activity_stream'],
    component: () => import('@/components/cfe/ActivityStreamSidebar'),
    placement: 'sidebar',
    name: 'Поток активности',
    description: 'Realtime-события в базе 1С',
    cfe_only: true,
  },

  // Card типы
  posting_trace_card: {
    requires: ['cfe.posting_trace'],
    cardType: 'PostingTraceCard',
    component: () => import('@/components/cfe/PostingTraceCard'),
    cfe_only: true,
  },

  bsl_diagnostics_card: {
    requires: ['service.bsl_ls'],
    cardType: 'BSLDiagnosticsCard',
    component: () => import('@/components/lint/BSLDiagnosticsCard'),
    enhances: ['CodeCard'],  // расширяет существующую
  },

  standards_citation_block: {
    requires: ['service.rag_v8std'],
    component: () => import('@/components/rag/StandardsCitationBlock'),
    enhances: ['CodeCard'],
  },

  metavision_graph_card: {
    requires: ['service.metavision'],
    cardType: 'MetaVisionGraphCard',
    component: () => import('@/components/analysis/MetaVisionGraphCard'),
  },

  // Header indicators
  hot_reload_status: {
    requires: ['cfe.hot_reload_metadata'],
    component: () => import('@/components/cfe/HotReloadStatusDot'),
    placement: 'header',
  },

  hmac_sso_badge: {
    requires: ['auth.hmac_session'],
    component: () => import('@/components/cfe/HMACSSOBadge'),
    placement: 'header',
  },

  // Onboarding шаги (conditional)
  hmac_onboarding_step: {
    requires: ['auth.hmac_session'],
    component: () => import('@/components/onboarding/HMACSetupStep'),
    placement: 'onboarding',
  },
} as const;

export type FeatureModule = keyof typeof FEATURE_MODULES;
```

### `hooks/useCapability.ts`

```typescript
import { useActiveConnection } from '@/stores/connections';

export function useCapability(...required: Capability[]): boolean {
  const conn = useActiveConnection();
  if (!conn || !conn.capabilities) return false;
  return required.every(cap => conn.capabilities.includes(cap));
}

export function useEnabledModules(): FeatureModule[] {
  const conn = useActiveConnection();
  if (!conn?.capabilities) return [];

  return Object.entries(FEATURE_MODULES)
    .filter(([_, mod]) => mod.requires.every(cap => conn.capabilities.includes(cap)))
    .map(([name]) => name as FeatureModule);
}

export function useDisabledModules(): { module: FeatureModule; missing: Capability[] }[] {
  const conn = useActiveConnection();
  if (!conn?.capabilities) return [];

  return Object.entries(FEATURE_MODULES)
    .map(([name, mod]) => ({
      module: name as FeatureModule,
      missing: mod.requires.filter(cap => !conn.capabilities.includes(cap)),
    }))
    .filter(({ missing }) => missing.length > 0);
}
```

### Использование в компонентах

```tsx
// components/cfe/ActivityStreamSidebar.tsx
'use client';

import { useCapability } from '@/hooks/useCapability';
import { UpgradeCTA } from '@/components/upgrade/UpgradeCTA';

export function ActivityStreamSidebar() {
  const enabled = useCapability('cfe.activity_stream');

  if (!enabled) {
    return (
      <UpgradeCTA
        feature="Поток активности"
        currentMode="epf"
        requires={['cfe.activity_stream']}
        description="Реалтайм-поток создания, изменения, проведения объектов 1С"
        benefits={[
          'Видеть что происходит в базе live',
          'Алерты на критичные события',
          'История событий за сессию',
        ]}
        cta={{
          label: 'Установить CFE-расширение',
          href: '/docs/install-cfe',
        }}
      />
    );
  }

  // ... full component
  return <ActualActivityStream />;
}
```

### Card type registry (динамическая регистрация)

```typescript
// lib/card-registry.ts
import { FEATURE_MODULES } from './feature-modules';

export async function buildCardRegistry(capabilities: Capability[]) {
  const registry: Record<string, ComponentType> = {
    // Always available
    CodeCard: (await import('@/components/core/CodeCard')).default,
    TableCard: (await import('@/components/core/TableCard')).default,
    ObjectCard: (await import('@/components/core/ObjectCard')).default,
    LogCard: (await import('@/components/core/LogCard')).default,
    MetricCard: (await import('@/components/core/MetricCard')).default,
    ReferencesCard: (await import('@/components/core/ReferencesCard')).default,
  };

  // Conditional based on capabilities
  for (const [name, mod] of Object.entries(FEATURE_MODULES)) {
    if (!mod.cardType) continue;
    if (mod.requires.every(cap => capabilities.includes(cap))) {
      const Component = (await mod.component()).default;
      registry[mod.cardType] = Component;
    }
  }

  return registry;
}
```

### Visual indicators

```tsx
// components/header/ChannelBadge.tsx
export function ChannelBadge({ connection }: { connection: MCPConnection }) {
  const modeColors = {
    epf: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
    cfe: 'bg-signal/15 text-signal border-signal/30',
    external: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
    legacy: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  };

  const modeLabels = {
    epf: 'EPF',
    cfe: 'CFE',
    external: 'EXT',
    legacy: 'LEGACY',
  };

  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 text-xs font-mono uppercase tracking-wider border rounded',
      modeColors[connection.mode || 'legacy']
    )}>
      {modeLabels[connection.mode || 'legacy']}
    </span>
  );
}
```

### Settings — capability inspector

В Settings → MCP → детали подключения:

```
┌─────────────────────────────────────────────────┐
│ Транзит ⚡ CFE                                   │
│ URL: http://localhost:6010/mcp                  │
│ ─────────────────────────────────────────────── │
│ Конфигурация: УТ 11.5                          │
│ Платформа: 8.3.27.1989                         │
│ Расширение: АналитикПлюс v2.0.5                │
│ ─────────────────────────────────────────────── │
│ Capabilities: 23 of 23                          │
│   ✅ mcp.execute_query                          │
│   ✅ mcp.execute_code                           │
│   ✅ cfe.activity_stream                        │
│   ✅ cfe.posting_trace                          │
│   ... (раскрываемый список)                     │
│ ─────────────────────────────────────────────── │
│ Активные модули UI: 12                          │
│   ✅ Поток активности                           │
│   ✅ Трассировка проведения                     │
│   ... (раскрываемый список)                     │
│ ─────────────────────────────────────────────── │
│ [🔄 Обновить capabilities]  [⚙️ Изменить URL]   │
└─────────────────────────────────────────────────┘
```

## Безопасность

### Tool whitelist

LLM **не должна** видеть tools которых нет в capabilities активного подключения. Это enforced на backend:

```python
async def get_llm_tools(workspace_id: UUID) -> list[Tool]:
    conns = await db.query(MCPConnection).filter_by(
        workspace_id=workspace_id, is_active=True
    ).all()

    all_tools = []
    for conn in conns:
        # Получаем реальные tools от MCP
        raw_tools = await conn.list_tools()

        # Фильтруем по capabilities — некоторые MCP могут вернуть лишнее
        allowed_tools = [
            t for t in raw_tools
            if any(t.name.startswith(f"{prefix}.") for prefix in conn.capability_tool_prefixes)
        ]

        all_tools.extend(allowed_tools)

    return all_tools
```

### Capability spoofing protection

EPF/CFE сами сообщают свои capabilities — что если злонамеренная EPF заявит `cfe.privileged_mode` которого нет?

**Защита:** backend проверяет соответствие реальной функциональности:
- Если `cfe.persistent_http` заявлен, но MCP запущен из EPF контекста (не HTTP-сервис) — пометить как inconsistent
- Trace отслеживает реальные вызовы — расхождения логируются

Это не критическая защита (всё локально), но даёт визуальный indicator пользователю.
