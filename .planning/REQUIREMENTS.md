# Requirements: 1С Аналитик — чат с MCP

**Defined:** 2026-05-13
**Core Value:** Аналитик пишет вопрос на NL → LLM сама дёргает MCP → ответ с inline-карточкой за ≤30 сек

## v1 Requirements

Требования для первого релиза. Каждое маппится на фазу roadmap.

### Connections

- [ ] **CONN-01**: Аналитик может добавить MCP endpoint своей базы 1С (URL + channel + имя) через Settings → Connections, статус ping = green
- [ ] **CONN-02**: Аналитик может подключить LLM provider (endpoint + API key + model + temperature) через Settings → LLM; ключ хранится в localStorage браузера
- [ ] **CONN-03**: Channel selector в header переключает контекст между подключёнными базами; новый чат использует tools активной базы
- [ ] **CONN-04**: Backend проверяет ping/health конкретного MCP подключения через `/mcp/{id}/ping`

### Chat

- [ ] **CHAT-01**: Аналитик пишет вопрос на русском в textarea → получает ответ ≤30 сек для типовых запросов
- [ ] **CHAT-02**: LLM автономно выбирает и вызывает нужные MCP tools (через function calling) — аналитик не указывает tool руками
- [ ] **CHAT-03**: Streaming ответа через SSE: первый chunk ≤500 мс, статусы видны live («Анализирую → Вызываю execute_query → Формирую ответ»)
- [ ] **CHAT-04**: Tool calling loop поддерживает множественные tool calls в одном ответе (LLM может вызвать 2-3 tools последовательно)
- [ ] **CHAT-05**: Ответ ассистента содержит TL;DR markdown + 0..N inline-карточек + collapsed trace

### Cards

- [ ] **CARD-01**: TableCard — рендер результата execute_query с пагинацией, сортировкой колонок, экспортом в CSV
- [ ] **CARD-02**: ObjectCard — рендер карточки объекта из get_metadata(detail) / get_object_by_link: реквизиты / ТЧ / формы / макеты
- [ ] **CARD-03**: LogCard — рендер get_event_log: таймлайн записей с уровнями, цветовая разметка Error/Warning, курсор-пагинация

### Sessions

- [ ] **HIST-01**: Sidebar показывает список сессий grouped by date (Сегодня / Вчера / На этой неделе / Раньше)
- [ ] **HIST-02**: Auto-title сессии генерится из первого user message (через LLM или эвристикой)
- [ ] **HIST-03**: Сессии персистятся в SQLite; после refresh страницы все session messages видны
- [ ] **HIST-04**: «+ Новый чат» создаёт сессию в текущем channel; меняется в URL `/sessions/{id}`

### Trace

- [ ] **TRACE-01**: Под каждым ответом ассистента есть collapsed строка `▸ LLM вызвала N tool'ов за X мс`; click разворачивает
- [ ] **TRACE-02**: Развёрнутый trace показывает для каждого tool call: name, input params (JSON tree), output (collapsed by default), duration_ms, error если был
- [ ] **TRACE-03**: Кнопка «Скопировать как curl» формирует HTTP-запрос для воспроизведения через REST API MCP

### States

- [ ] **STATE-01**: Empty state когда нет MCP-подключений: hero + кнопка «Настроить подключение» → Settings
- [ ] **STATE-02**: MCP disconnected: красный баннер вверху чата + кнопка «Повторить»; input disabled до восстановления
- [ ] **STATE-03**: LLM error (rate limit / invalid key / etc): readable error, не stack trace; respect `Retry-After` header

## v2 Requirements

Отложено до post-MVP. Tracked, но не в текущем roadmap.

### Anonymization

- **ANON-01**: Toggle анонимизации в header; при ON активирует MCP anon mode
- **ANON-02**: Ответы содержат токены `[ORG-001]`, `[INN-001]`, `[PER-001]` визуально подсвеченные
- **ANON-03**: Кнопка «Раскрыть реальные значения» в карточке → вызывает submit_for_deanonymization

### Advanced Cards

- **CARD-04**: MetricCard — одно большое число + sparkline + подпись (для агрегатов execute_query)
- **CARD-05**: ReferencesCard — список «где используется» из find_references_to_object
- **CARD-06**: CodeCard — BSL-фрагмент с подсветкой синтаксиса (для execute_code результатов и snippets)

### Productivity

- **PROD-01**: Quick prompts (chips над input): «Обзор базы», «Ошибки за сутки», «Сводка по типам документов»
- **PROD-02**: Slash-команды: `/sql`, `/journal`, `/find`, `/audit`, `/clear`
- **PROD-03**: @-mentions объектов 1С: `@Документ.ОПП` — подсказчик из metadata cache
- **PROD-04**: Cmd-K — поиск по сессиям и messages
- **PROD-05**: Экспорт ответа: Copy markdown / CSV / PDF

### Security

- **SEC-01**: Confirm dialog перед `execute_code` с dangerous keywords (Удалить, Записать, etc)
- **SEC-02**: CSP headers (script-src, connect-src)
- **SEC-03**: Pydantic strict validation на всех endpoints
- **SEC-04**: CORS lockdown — только configurable list origins

### DevX

- **DEVX-01**: Unit tests orchestrator/MCP client/LLM client (coverage ≥80% backend)
- **DEVX-02**: E2E Playwright tests для 3 ключевых flow
- **DEVX-03**: GitHub Actions CI: lint + test + build on PR
- **DEVX-04**: docker-compose.yml для one-command setup
- **DEVX-05**: USER.md гид для новых аналитиков

## Out of Scope

Явно исключено. Документировано чтобы не возвращалось.

| Feature | Reason |
|---------|--------|
| Mobile / tablet UI | Desktop only (≥1280px) — аналитик работает за компом |
| Multi-user / real-time collaboration | Single-user tool; sharing через Telegram остаётся |
| Light theme | Только тёмная; глаза болят за 6-7 ч работы |
| Voice input | Отдельная фича позже, не в MVP |
| TTS для ответов LLM | Отдельная фича позже |
| Direct 1С data editing через UI | Только просмотр; write — через confirm execute_code |
| Управление 1С базами (deploy, restart) | Это для админа, не для аналитика |
| Vector search / RAG over metadata | Отдельная итерация после MVP |
| Готовые «work-modes» (Discovery/Triage/...) | Провал v0 — лишний слой абстракции поверх MCP |
| Workflow editor c карточками операций | Провал v0b — юзер не собирает MCP вызовы вручную |
| OAuth / SSO для приложения | Local-first MVP, single-user |
| Email notifications | Не нужны для интерактивного tool |
| Theming light/custom colors | Только dark + brand colors |

## Traceability

Маппинг требований на фазы roadmap.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONN-01 | Phase 1 | Pending |
| CONN-02 | Phase 1 | Pending |
| CONN-03 | Phase 2 | Pending |
| CONN-04 | Phase 1 | Pending |
| CHAT-01 | Phase 2 | Pending |
| CHAT-02 | Phase 2 | Pending |
| CHAT-03 | Phase 2 | Pending |
| CHAT-04 | Phase 2 | Pending |
| CHAT-05 | Phase 2 | Pending |
| CARD-01 | Phase 2 | Pending |
| CARD-02 | Phase 2 | Pending |
| CARD-03 | Phase 2 | Pending |
| HIST-01 | Phase 2 | Pending |
| HIST-02 | Phase 2 | Pending |
| HIST-03 | Phase 2 | Pending |
| HIST-04 | Phase 2 | Pending |
| TRACE-01 | Phase 2 | Pending |
| TRACE-02 | Phase 2 | Pending |
| TRACE-03 | Phase 3 | Pending |
| STATE-01 | Phase 1 | Pending |
| STATE-02 | Phase 3 | Pending |
| STATE-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-13*
*Last updated: 2026-05-13 after initial GSD initialization*
