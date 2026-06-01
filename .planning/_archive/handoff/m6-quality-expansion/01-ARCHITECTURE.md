# 01 — Architecture: двухрежимная capability-based архитектура

## Big picture

```
┌──────────────────────────────────────────────────────────────────────┐
│  ELECTRON DESKTOP APP "1С Аналитик v2.0"                             │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │ Frontend (Next.js 15)                                          │  │
│  │  • Chat UI                                                     │  │
│  │  • 8 типов cards (Code/Table/Object/Log/Metric/References/     │  │
│  │    BSLDiagnostics/StandardsCitation/MetaVisionGraph/           │  │
│  │    ActivityEvent/PostingTrace)                                  │  │
│  │  • Source selector (multi-MCP + multi-base)                    │  │
│  │  • Feature gates per capability                                │  │
│  │  • RAG citations прямо в коде                                  │  │
│  │  • Streaming stages + WebSocket для live BSL LS diagnostics    │  │
│  └────────────────────────┬───────────────────────────────────────┘  │
│                           │ HTTP + SSE + WS                          │
│  ┌────────────────────────▼───────────────────────────────────────┐  │
│  │ Backend (FastAPI)                                              │  │
│  │  • MCP Orchestrator — роутит к нужному MCP                     │  │
│  │  • Capability Discovery — парсит initialize + кэширует         │  │
│  │  • RAG Service — sqlite-vec + 3 источника                      │  │
│  │  • BSL LS subprocess — Java + кэш по SHA256                    │  │
│  │  • MetaVision subprocess — Java CLI + JSON parser              │  │
│  │  • SQLite + sqlite-vec                                         │  │
│  └─┬────────┬──────────┬──────────┬──────────────────────────────┘  │
└────┼────────┼──────────┼──────────┼─────────────────────────────────┘
     │        │          │          │
     │ HTTP   │ HTTP     │ stdio    │ stdio
     ▼        ▼          ▼          ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────────────────────────┐
│1c-buddy │ │mcp-bsl- │ │ METR    │ │ ЕДИНОЕ CFE-РАСШИРЕНИЕ       │
│:6002    │ │context  │ │ tests   │ │ или EPF-обработка           │
│         │ │         │ │         │ │ в базе клиента              │
│Напарник │ │Синтаксис│ │YAxUnit  │ │ ────────────────────────    │
│+ ИТС    │ │платформы│ │check    │ │ EPF/CFE содержит:           │
│         │ │         │ │         │ │  • MCP Toolkit (наш)        │
│ 8 tools │ │ 5 tools │ │11 tools │ │  • tools_ui_1c (опц.)       │
└─────────┘ └─────────┘ └─────────┘ │  • Connector (embedded)     │
                                    │  • Launcher с HMAC auth     │
                                    │  • Capability response      │
                                    │    через initialize         │
                                    └─────────────────────────────┘
```

## Архитектурные принципы

### 1. Multi-MCP Orchestration (Phase 12)

LLM имеет доступ к **всем** инструментам всех подключённых MCP через **единый** unified tool registry. Каждое имя инструмента имеет префикс MCP-источника:

```python
unified_tools = {
    "toolkit.execute_query": <schema>,
    "toolkit.execute_code": <schema>,
    "toolkit.get_metadata": <schema>,
    # ... 7 tools от MCP Toolkit
    "buddy.ask_1c_ai": <schema>,
    "buddy.search_its": <schema>,
    "buddy.fetch_its": <schema>,
    # ... 5 tools от 1c-buddy
    "context.search": <schema>,
    "context.info": <schema>,
    # ... 5 tools от mcp-bsl-context
    "metr.run_tests": <schema>,
    # ... 11 tools от METR
}
```

LLM получает их все в одном `tools` массиве OpenAI API. Сама выбирает что вызвать.

**Преимущества:**
- Префикс исключает конфликты имён
- LLM понимает источник по префиксу
- Trace панель показывает к какому MCP пошёл запрос

**Risk mitigation:** в system prompt — явные правила маршрутизации ("для вопросов по ИТС — используй `buddy.search_its`, для синтаксиса BSL — `context.search`").

### 2. Capability-based UI (Phase 12 + 17)

Frontend модули **активируются по capabilities**, а не жёстко зашиты.

```
Connection.capabilities = ["mcp.execute_query", "cfe.activity_stream", ...]
                                  ↓
                          FEATURE_MODULES registry
                                  ↓
              UI рендерит только те модули, у которых
              все capabilities совпадают
```

При смене канала (`onActiveConnectionChange`) — frontend перерисовывает UI с другим набором модулей.

### 3. Дуальная доставка в 1С (Phase 13a + 13b)

Один и тот же функционал предлагается в двух формах:

**EPF (внешняя обработка):**
- Один файл `АналитикLite.epf` (~3 MB)
- Запускается через "Файл → Открыть" в Предприятии
- Работает пока форма открыта
- Не меняет конфигурацию
- Mode = "epf", 8 capabilities

**CFE (расширение конфигурации):**
- Файл `АналитикПлюс.cfe` (~8 MB) + PowerShell installer
- Подключается через LoadConfigFromFiles в DESIGNER
- Постоянный HTTP-сервис (не требует открытой формы)
- Подписки на события + регламентные задания
- Mode = "cfe", 23 capabilities

**Migration EPF→CFE и обратно** — поддерживается, история сессий сохраняется.

### 4. Тройной RAG (Phase 14)

Три параллельных источника знаний для LLM:

```
Question → Embeddings → sqlite-vec parallel search
                              ↓        ↓        ↓
                          v8std    ssl_api   platform_hbk
                          317      ~3000     ~5000
                          docs     methods   entries
                              ↓        ↓        ↓
                          merge with priorities
                              ↓
                          top-K (3 per source)
                              ↓
                          inject into LLM system prompt
                          + show citations in CodeCard
```

### 5. Code quality pipeline (Phase 15)

Параллельно с LLM stream работает BSL LS:

```
LLM streams BSL code → debounce 500ms → BSL LS subprocess
                                              ↓
                                       JSON diagnostics
                                              ↓
                                       WebSocket to frontend
                                              ↓
                                       Highlight in CodeCard realtime
```

С кэшем по SHA256(code) — повторные вызовы ≤ 100ms.

### 6. Visual architecture analysis (Phase 16)

MetaVision интегрирован как Java subprocess:

```
User uploads CF/CFE → backend extracts to temp
                              ↓
                       MetaVision CLI fork
                       --src=<temp> --output=<json>
                              ↓
                       MetaVisionGraph { nodes, edges, antipatterns }
                              ↓
                       MetaVisionGraphCard в чате
                       D3.js force-directed
                       (или sigma.js для 5000+ узлов)
```

## Capability Matrix (полная)

### Base (8) — доступно в EPF и CFE

| ID | Что даёт | UI компонент |
|----|----------|--------------|
| `mcp.execute_query` | Чтение данных через запросы 1С | TableCard |
| `mcp.execute_code` | Выполнение BSL (с confirm dialog) | CodeCard + ConfirmDialog |
| `mcp.get_metadata` | Структура базы (5 режимов) | ObjectCard |
| `mcp.get_event_log` | Журнал регистрации (15 фильтров) | LogCard |
| `mcp.find_references` | Поиск использования объекта | ReferencesCard |
| `mcp.get_access_rights` | Анализ прав роли/юзера | ObjectCard |
| `mcp.bsl_syntax_help` | Справочник BSL встроенный | inline в Code |
| `connector.http_request` | HTTP-вызовы из 1С (через Connector) | inline через execute_code |

### Optional in EPF / Builtin in CFE (3)

| ID | EPF | CFE | Что даёт |
|----|-----|-----|----------|
| `tools_ui.query_console` | ⚠️ доп. установка | ✅ встроено | Консоль запросов |
| `tools_ui.code_console` | ⚠️ доп. установка | ✅ встроено | Консоль кода (Monaco) |
| `tools_ui.dedup_finder` | ⚠️ доп. установка | ✅ встроено | Поиск дубликатов |

### Extended (12) — только CFE

| ID | Что даёт | UI компонент |
|----|----------|--------------|
| `cfe.persistent_http` | Сервер работает 24/7 без открытой формы | StatusDot в Header |
| `cfe.event_subscriptions` | Подписки на ПриЗаписи/ПриУдалении/ПриЗаписиНаСервере | feeds Activity Stream |
| `cfe.method_overrides` | Перехват методов типовых (для трассировки) | feeds Posting Trace |
| `cfe.privileged_mode` | Чтение защищённых данных (требует роли) | inline в queries |
| `cfe.monitoring_register` | Кастомный регистр МониторингАктивности | feeds Activity Stream |
| `cfe.activity_stream` | Realtime поток событий 1С | ActivityStreamSidebar |
| `cfe.posting_trace` | Детальная трассировка ОбработкаПроведения "до/после" | PostingTraceCard |
| `cfe.scheduled_jobs` | Регламентные задания (auto-export, alerts) | SchedulerCard |
| `cfe.custom_commands` | Кастомные команды в подсистемах УТ/ERP | inline в base 1С |
| `cfe.settings_storage` | Сохранение настроек в ХранилищеНастроек | SettingsPane |
| `cfe.hot_reload_metadata` | Без перезагрузки видит изменения в кешах | StatusDot |
| `auth.hmac_session` | SSO от 1С-пользователя | автоматически в onboarding |

**Итого:** EPF=8(+3 опц.)=11, CFE=8+3+12=**23 capabilities**.

## Backend модель

```python
# backend/app/models/connection.py

from sqlmodel import SQLModel, Field, Column, JSON
from typing import Literal
from datetime import datetime
from uuid import UUID, uuid4


class MCPConnection(SQLModel, table=True):
    """Подключение к MCP-серверу (1С-база или вспомогательный MCP)."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str  # "Транзит" / "ИТС + Напарник" / "Синтаксис платформы"
    endpoint: str  # "http://localhost:6010/mcp" или stdio path
    transport: Literal["http", "stdio"] = "http"

    # Capability discovery
    mode: Literal["epf", "cfe", "external"] | None = None
    configuration: str | None = None  # "УТ_11.5" / "ERP_2.5" / null для external
    platform_version: str | None = None  # "8.3.27.1989"
    extension_version: str | None = None  # "2.0.5"
    capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Lifecycle
    is_active: bool = True
    last_handshake_at: datetime | None = None
    last_error: str | None = None

    # UX hints
    color: str | None = None  # для badge в UI
    icon: str | None = None
```

## Что не делаем (явные не-цели M6)

- ❌ Не делаем мобильную версию (десктоп-only)
- ❌ Не делаем web hosted (только Electron desktop)
- ❌ Не делаем поддержку 8.3 < 27 (минимальная платформа — 8.3.27)
- ❌ Не делаем поддержку файловых баз > 30 GB (рекомендуем серверные)
- ❌ Не делаем работу с типовыми < УТ 11.5 (минимум УТ 11.5 / ERP 2.5 / КА 2.5)
- ❌ Не делаем мультиязычность UI (только русский)
- ❌ Не делаем светлую тему (пока — только тёмная, Stencil brand)

## Совместимость

### Что должно остаться работать (zero breaking changes)

- Существующие сессии v1.4.x открываются
- Backend API endpoints не ломаются
- Connection без capabilities (legacy) — работает в "legacy mode" с базовым набором tools

### Что меняется (с миграцией)

- `MCPConnection` получает 5 новых полей — миграция SQLAlchemy (alembic)
- Frontend `ChannelSelector` → `SourceSelector` (рефакторинг, не rename)
- Onboarding получает 1.5 шаг (выбор EPF/CFE)
