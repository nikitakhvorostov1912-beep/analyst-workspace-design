# REQUIREMENTS — 1С Аналитик

> FR / NFR / IR requirements with MoSCoW priority.

## Functional Requirements (FR)

### MUST (P0 — критично для MVP)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-1 | Аналитик подключает MCP endpoint своей базы 1С (URL + channel + название) | В Settings → Connections можно добавить ≥ 1 endpoint, статус ping = green |
| FR-2 | Аналитик подключает LLM provider (endpoint + API key + model) | В Settings → LLM можно сохранить и протестировать вызовом completion |
| FR-3 | Аналитик пишет вопрос на русском, получает ответ ≤ 30 сек для типовых запросов | Запрос «расскажи про базу» → корректный ответ + ≥ 1 inline card |
| FR-4 | LLM сама выбирает и вызывает MCP tools — аналитик НЕ указывает tool вручную | Из 3 тестовых вопросов в 100% случаев LLM выбирает релевантный tool |
| FR-5 | Ответ содержит inline-карточки минимум 3 типов: Table / Object / Log | Демо-prompts активируют 3 типа |
| FR-6 | Trace tool calls — collapsible, показывает имя tool / параметры / время | Click на trace разворачивает; видны имя tool + params JSON + duration_ms |
| FR-7 | Streaming: видно как LLM «думает» в реальном времени (статусы + текст) | SSE events приходят в ≤ 200 мс друг от друга; UI обновляется live |
| FR-8 | История чатов сохраняется в SQLite, доступна в sidebar (grouped: Today / Yesterday / Earlier) | После перезагрузки страницы все сессии видны |
| FR-9 | Channel selector в header переключает контекст между подключёнными базами | Click на selector → меняется active channel, новый чат использует новые tools |
| FR-10 | Empty state когда нет подключений: hero + кнопка «Настроить» → Settings | Свежая инсталляция показывает empty state, не пустой чат |

### SHOULD (P1 — важно, но можно после первого demo)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-11 | Анонимизация data toggle в header (header → активирует MCP anonymization mode) | При ON: ответы содержат токены `[ORG-N]`, кнопка «Раскрыть реальные значения» |
| FR-12 | Quick prompts (chips над input): «Обзор базы», «Ошибки за сутки», «Сводка по типам документов» | 3+ chips видны, click → подставляет в input + auto-submit |
| FR-13 | Slash-команды: `/sql`, `/journal`, `/find`, `/audit`, `/clear` | Type `/` → autocomplete dropdown с 5+ командами |
| FR-14 | @-mentions объектов 1С: `@Документ.ОПП` (подсказчик из metadata cache) | Type `@` → dropdown с подсказками из последних метаданных |
| FR-15 | Inline cards дополнительных типов: Metric / References / Code | Тестовые prompts активируют 5 типов всего |
| FR-16 | Поиск по истории чатов | Cmd-K → поиск по session titles + message content |
| FR-17 | Экспорт ответа: Copy markdown / CSV / PDF | На каждой карточке есть menu с экспортом |
| FR-18 | «Найти в KB похожее» — link на похожие сессии (по совпадению объектов) | По карточке Object с типом X — список других сессий где он встречался |

### COULD (P2 — после base feedback)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-19 | Multi-LLM switcher — несколько настроенных провайдеров | Дополнительные провайдеры в Settings + dropdown в header |
| FR-20 | Voice input через `getUserMedia` + Whisper API | Микрофон-кнопка в input area |
| FR-21 | Voice output — TTS для ответов LLM | Speaker-кнопка на каждом сообщении ассистента |
| FR-22 | Theming — кастомные accent colors (но dark only) | Settings → Appearance |
| FR-23 | Sharing — экспорт сессии как .html standalone (для отправки клиенту) | Кнопка Share → файл с inline данными |

### WON'T (out of scope для всего проекта или явно позже)

- Mobile / tablet UI (только desktop)
- Multi-user / collaboration в реальном времени
- Прямое редактирование данных в 1С через UI (только просмотр)
- Управление 1С базами (deploy, restart)
- Light theme

---

## Non-Functional Requirements (NFR)

### Производительность

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | First SSE byte после `/chat` POST | ≤ 500 мс |
| NFR-2 | Tool roundtrip (LLM → MCP → LLM next chunk) | ≤ 3 сек |
| NFR-3 | UI остаётся responsive (no jank) при streaming 50+ chunks/сек | 60 FPS |
| NFR-4 | Cold start backend | ≤ 2 сек до accepting requests |
| NFR-5 | SQLite read latency для recent sessions list | ≤ 50 мс |

### Безопасность

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-6 | LLM API keys не персистятся на backend | localStorage only + per-request header |
| NFR-7 | MCP endpoints с auth поддерживают custom headers | Header config в connection settings |
| NFR-8 | CORS allow только localhost в dev, configurable list в prod | Pydantic settings |
| NFR-9 | BSL `execute_code` requires user confirm в UI (dialog) | Перед вызовом — modal с подтверждением |
| NFR-10 | Никаких telemetry в облако без explicit opt-in | По умолчанию off, opt-in toggle в Settings |

### Reliability

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-11 | MCP disconnect — UI показывает баннер + retry button | Health check каждые 30 сек + on-demand |
| NFR-12 | LLM rate limit — show error + retry-after | Backend парсит `Retry-After` header |
| NFR-13 | SQLite corruption recovery | WAL mode + periodic backups |

### Usability

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-14 | Onboarding ≤ 3 шага: подключить MCP → ввести LLM key → задать первый вопрос | Empty state ведёт пользователя |
| NFR-15 | Тёмная тема by default, нет переключателя light в MVP | tailwind dark class on root |
| NFR-16 | Русский UI; имена tools и параметров остаются на английском (как в MCP spec) | i18n не нужен, фиксированно RU |
| NFR-17 | Keyboard-first: ⌘+Enter / ⌘+K / ⌘+N работают | Глобальные shortcuts |

### Maintainability

| ID | Requirement | Implementation |
|----|-------------|----------------|
| NFR-18 | Tests coverage ≥ 80% для orchestrator и storage | pytest --cov |
| NFR-19 | Frontend компоненты типизированы (no `any`) | tsc strict |
| NFR-20 | Каждый MCP tool wrapper тестируем независимо | unit tests с mocks |

---

## Integration Requirements (IR)

| ID | Requirement | Spec |
|----|-------------|------|
| IR-1 | OpenAI-compatible LLM API (Chat Completions + function calling) | Совместимость минимум с MiMo + DeepSeek + OpenAI |
| IR-2 | MCP Streamable HTTP transport | Совместимость с MCP Toolkit 1.7.0+ |
| IR-3 | MCP tool discovery via `tools/list` | Auto-detect доступных tools при подключении channel |
| IR-4 | MCP method `tools/call` для вызовов | Стандартный JSON-RPC 2.0 |
| IR-5 | Session ID для MCP Streamable HTTP (header `Mcp-Session-Id`) | Получаем при initialize, переиспользуем |
| IR-6 | SSE event format для frontend | Стандартный (data: ... \n\n), типизированные events |
| IR-7 | docker compose up должен поднимать всё локально | `docker-compose.yml` |

---

## Validation Strategy

- **MVP gate (FR-1..FR-10 + NFR-1..NFR-3)** — все P0 + базовая perf
- **Demo gate (+ FR-11..FR-15)** — расширенные cards и UX
- **Beta gate (+ NFR-6..NFR-13 + IR-1..IR-7)** — security + reliability + integration
- **Production gate (+ all NFR + tests)** — ready для self-host другими аналитиками
