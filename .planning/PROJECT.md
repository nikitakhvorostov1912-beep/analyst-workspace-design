# 1С Аналитик — чат-консоль с MCP

## What This Is

Веб-приложение: чат-консоль для бизнес-аналитиков 1С, работающих с живыми базами клиентов. Аналитик пишет вопросы на естественном русском, LLM (Xiaomi MiMo через OpenAI-совместимый API) автономно вызывает операции 1С MCP Toolkit (10 tools) и форматирует ответы с inline-карточками (таблица / объект / журнал / метрика / ссылки / код). Multi-tenant через channel selector — несколько баз клиентов в одном UI.

## Core Value

**Любой 1С-аналитик получает то же что Никита имеет в Claude Code сейчас — но через веб-морду на своей LLM.** Если этот сценарий не работает (вопрос на NL → реальный ответ из живой базы с inline-карточкой), всё остальное не имеет смысла.

## Requirements

### Validated

(Ничего — новый проект, валидация только после ship)

### Active

- [ ] **CONN-01**: Аналитик подключает MCP endpoint своей базы 1С (URL + channel + название) через Settings → Connections
- [ ] **CONN-02**: Аналитик подключает LLM provider (endpoint + API key + model) через Settings → LLM, ключ в localStorage браузера
- [ ] **CONN-03**: Channel selector в header переключает контекст между подключёнными базами
- [ ] **CHAT-01**: Аналитик пишет вопрос на NL → получает ответ ≤ 30 сек для типовых запросов
- [ ] **CHAT-02**: LLM сама выбирает и вызывает MCP tools — аналитик не указывает tool вручную
- [ ] **CHAT-03**: Streaming ответа через SSE: статусы видны live («Анализирую → Вызываю → Формирую»)
- [ ] **CARD-01**: TableCard — для execute_query результатов (пагинация + экспорт CSV)
- [ ] **CARD-02**: ObjectCard — для get_metadata(detail) / get_object_by_link
- [ ] **CARD-03**: LogCard — для get_event_log с фильтрами
- [ ] **TRACE-01**: Collapsible trace под ответом — раскрывает имя tool, params (JSON), result, duration
- [ ] **HIST-01**: История чатов в SQLite, доступна в sidebar (grouped by date)
- [ ] **HIST-02**: Auto-title для сессии из первого сообщения
- [ ] **STATE-01**: Empty state когда нет подключений — hero + кнопка «Настроить»
- [ ] **STATE-02**: MCP disconnected — баннер с retry
- [ ] **STATE-03**: LLM error — readable error message, не stack trace

### Out of Scope

- **Mobile / tablet UI** — desktop only (≥1280px). Аналитик работает за компом
- **Multi-user / real-time collaboration** — single-user tool. Совместная работа через Telegram остаётся
- **Light theme** — только тёмная. Аналитик работает 6-7 часов, глаза болят
- **Voice input** — отдельная фича позже
- **Direct 1С data editing** через UI — только просмотр, на write-операции LLM требует confirm
- **Управление 1С базами** (deploy, restart, configuration) — это для админа
- **Vector search / RAG** над метаданными — отдельная итерация позже
- **Готовые «work-modes»** (Discovery/Triage/Investigate/...) — провал v0, заменён единым чатом
- **Workflow editor с карточками операций** — провал v0b, юзер не должен собирать MCP-вызовы руками

## Context

**Технический ландшафт:**
- 1С платформа 8.3.18+ / 8.5.x на горизонте
- 1С MCP Toolkit v1.7.0 (Streamable HTTP transport, 10 tools, EPF в 1С)
- Существующие сценарии работы пользователя: Claude Code + MCP через CLI (для одного аналитика, не для других)

**Pivot history (lessons learned):**
| Version | Подход | Почему отвергнут |
|---------|--------|------------------|
| v0 | Object-centric IDE (tree + карточка объекта + AI rail) | Слишком много абстракций. 6 «work-modes» поверх MCP |
| v0b | Workflow editor (карточки операций как steps Postman-style) | Юзер не должен собирать MCP-вызовы руками — это работа LLM |
| **v1** | **Chat-first (NL → LLM → tool_calls → cards)** | **Принят.** Аналог ChatGPT/Claude.ai/Perplexity |

**Целевые пользователи:**
- P1 — опытный 1С-аналитик (4+ лет, как Никита), работает с 4-6 проектами параллельно
- P2 — внедренец 1С (франчайзи, 2-3 года), типовые УТ/КА/ERP/УСО

**Reference:** Claude.ai (artifacts), ChatGPT (clean chat), Perplexity (sources in answers).

## Constraints

- **Tech stack:** Next.js 15 + shadcn/ui + Tailwind 4 (frontend), FastAPI + Pydantic v2 + SSE (backend). Не меняем.
- **LLM:** OpenAI-compatible HTTP API only. Поддерживаем Xiaomi MiMo как primary, любой совместимый — bonus.
- **MCP transport:** Streamable HTTP только (не stdio). Совместимость с MCP Toolkit 1.7.0+.
- **API keys:** только в localStorage браузера. Backend никогда не персистит — каждый /chat запрос содержит ключ в header `X-LLM-API-Key`.
- **Storage:** SQLite (single-file, embedded). Без отдельного DB сервера в MVP.
- **Local-first:** приложение работает локально (`docker compose up`). Без SaaS / multi-tenant accounts.
- **Language:** русский UI везде. Имена tools (`get_metadata`, `execute_query`) остаются на английском — это spec.
- **Theme:** только тёмная.
- **Min viewport:** 1280×800 (desktop).

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Chat-first UI (v1) после провалов v0/v0b | Юзер сравнил с Claude Code workflow — это natural metaphor. Object-IDE и Workflow editor добавляли абстракции там, где LLM сама справляется | — Pending validation |
| Xiaomi MiMo как primary LLM | У юзера есть ключ. OpenAI-compatible API → переключение на другой провайдер тривиально | — Pending |
| Single-file SQLite | MVP, single-user. Не нужен Postgres / отдельный DB сервер | — Pending |
| Multi-tenant через channel selector | Юзер выбрал option B (а не один MCP на сессию). MCP уже поддерживает `?channel=` | — Pending |
| API ключи только в localStorage браузера | Безопасность. Backend не персистит, ротация ключа = чистка localStorage | — Pending |
| SSE для streaming, не WebSocket | Чат unidirectional — SSE достаточно. WS оверкилл | — Pending |
| Coarse granularity (4 phase для GSD) | Pivot уже занял много времени, нужно быстро дойти до working MVP | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-13 after initial GSD initialization (post-pivot to chat-first v1)*
