# 1С Аналитик — чат с MCP

> Веб-приложение: чат-консоль для бизнес-аналитиков 1С, работающих с живыми базами клиентов через MCP Toolkit. LLM (Xiaomi MiMo, OpenAI-compatible) orchestrates tool calls автоматически. Multi-tenant через channel selector.

## Концепция (одной фразой)

**Аналог ChatGPT/Claude.ai/Perplexity**, но специализированный под 1С: аналитик пишет вопрос на естественном языке («покажи 32 ОПП за 30.04 без шапки»), LLM сама выбирает MCP-tool, формирует параметры, получает ответ, форматирует с inline-карточкой (таблица / объект / журнал / метрика / ссылки / код).

**Аналитик НЕ знает про get_metadata/execute_query/get_event_log** — это работа LLM. Но может развернуть trace для проверки.

## Стек

| Слой | Технологии |
|------|-----------|
| **Frontend** | Next.js 15 (App Router) + React 19 + shadcn/ui + Tailwind 4 |
| **Backend** | FastAPI + Pydantic v2 + SSE streaming |
| **LLM Client** | OpenAI-compatible HTTP client (для Xiaomi MiMo / других) |
| **MCP Client** | HTTP streaming к `localhost:6010/mcp` или `:6003/mcp` |
| **Storage** | SQLite (sessions, messages, MCP connections, settings) |
| **Шрифты** | IBM Plex Sans + IBM Plex Mono |
| **Тема** | Тёмная by default |
| **Язык** | Русский UI, имена tools (`get_metadata`, `execute_query`) остаются англ. в trace |

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│ Browser (Next.js)                                            │
│  ├─ Chat UI (SSE stream)                                     │
│  ├─ Channel selector (multi-tenant)                          │
│  ├─ Settings modal (LLM endpoint + key + model)              │
│  └─ Trace panel (collapsible, raw tool calls)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/SSE
┌──────────────────────────▼──────────────────────────────────┐
│ FastAPI Backend                                              │
│  ├─ /chat (SSE orchestrator)                                 │
│  │   └─ tool_calling loop: NL → LLM → tool_call → MCP →     │
│  │      result → LLM → response                              │
│  ├─ /sessions (CRUD)                                         │
│  ├─ /connections (MCP endpoints)                             │
│  ├─ /settings (LLM provider config)                          │
│  └─ SQLite                                                   │
└──────────┬──────────────────────────────────┬───────────────┘
           │                                  │
   ┌───────▼─────────┐              ┌────────▼──────────┐
   │ Xiaomi MiMo     │              │ 1С MCP Toolkit    │
   │ (OpenAI-compat) │              │ (EPF на :6010)    │
   └─────────────────┘              └────────┬──────────┘
                                             │
                                    ┌────────▼──────────┐
                                    │ База 1С клиента   │
                                    └───────────────────┘
```

## MCP Tools (под капотом)

10 операций 1С MCP Toolkit v1.7.0 — детали в `docs/00b-mcp-capability-map.md`:
1. `get_metadata` — структура базы (5 режимов)
2. `execute_query` — запросы 1С
3. `execute_code` — BSL код
4. `get_object_by_link` — объект по навигационной ссылке
5. `get_link_of_object` — обратное
6. `find_references_to_object` — где используется
7. `get_access_rights` — права роли/юзера
8. `get_event_log` — журнал регистрации (15 фильтров)
9. `get_bsl_syntax_help` — справочник BSL
10. `submit_for_deanonymization` — для анонимизированных сессий

## Правила разработки

- **Brutal honesty** в обе стороны
- **MCP — это всё.** Никаких абстракций «work-modes», «Object-IDE» сверху MCP (это были провальные итерации v0)
- **NL → LLM → tool_calls → результат** — единственный workflow
- **Channel selector** — multi-tenant base 1
- **Анонимизация** — toggle, активирует `submit_for_deanonymization`
- **Streaming через SSE** — статусы видны live: «Анализирую → Вызываю tool → Формирую ответ»
- **GSD methodology** — Get Shit Done, фазы / roadmap / explicit verification
- **3 итерации без прогресса** → STOP, перепроверить spec

## Workflow одного запроса (как должно работать)

```
1. Аналитик: «Покажи 32 ОПП за 30.04 без шапки»
2. Frontend → POST /chat { message, sessionId, channelId }
3. Backend orchestrator:
   a. Берёт MCP tools schema для channel
   b. Формирует LLM payload (system + history + message + tools)
   c. Streams к LLM
4. LLM решает: «Нужен execute_query»
5. Backend: вызывает MCP execute_query(...) через HTTP
6. MCP → 1С → результат (32 строки)
7. Backend → LLM (с результатом): «Сформируй ответ человеку»
8. LLM streams: текст + inline-таблица + trace
9. Frontend отображает: TL;DR + Table card + свёрнутый trace
```

## Что НЕ делаем (явные баны после провальных итераций)

- ❌ «Work-modes» Discovery/Triage/Investigate/Mapping/Knowledge — это was v0 mistake
- ❌ Object-centric IDE с tree метаданных слева — was v0 mistake
- ❌ Workflow editor с карточками MCP-операций (юзер собирает руками) — was v0b mistake
- ❌ AI right-rail с «инсайтами» / «магическими» подсказками
- ❌ Inter font, purple-cyan gradients, glass morphism, decorative emoji
- ❌ Mobile-first вёрстка (desktop only, ≥ 1280px)
- ❌ Светлая тема как опция

## Структура проекта

```
analyst-workspace-design/
├── CLAUDE.md                ← этот файл
├── PROJECT.md               ← vision (для GSD)
├── ARCHITECTURE.md          ← топология
├── REQUIREMENTS.md          ← FR/NFR
├── ROADMAP.md               ← фазы реализации
├── .planning/               ← GSD state
│   ├── PROJECT.md
│   ├── ROADMAP.md
│   ├── intel/               ← codebase analysis
│   └── phases/              ← phase plans + executions
├── docs/
│   ├── 00b-mcp-capability-map.md   ← actual (backend reference)
│   └── _archive-v0-object-ide/     ← historical, не трогать
├── frontend/                ← Next.js 15 app (будет создан)
├── backend/                 ← FastAPI app (будет создан)
└── mockups/
    └── _legacy/v0-object-ide/      ← historical
```

## GitHub

Отдельный репозиторий `analyst-workspace-design` (не часть Cloude_PR workspace).
HTTPS + PAT (см. `github_account.md` в memory). Account: `nikitakhvorostov1912-beep`.
