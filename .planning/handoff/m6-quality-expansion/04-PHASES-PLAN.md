# 04 — 8 фаз M6 с декомпозицией

## Обзор зависимостей

```
Phase 12 (Multi-MCP + Capabilities) ─┬──> Phase 13a (EPF) ──┬──> Phase 13b (CFE)
                                     │                       │
                                     └──> Phase 14 (RAG) ────┴──> Phase 17 (Cards+Gates)
                                                                  │
Phase 12 ──────────────────────────────> Phase 15 (BSL LS) ──────┤
                                                                  │
Phase 12 ──────────────────────────────> Phase 16 (MetaVision) ──┤
                                                                  │
                                                                  ├──> Phase 17b (Activity Stream/Posting Trace)
                                                                  │
                                                                  └──> Phase 18 (Distribution)
```

**Критический путь:** 12 → 13b → 17 → 18 (8 + 15 + 14 + 7 = 44 дня).
**С параллелизацией 13b+14, 16+17, 17b+15:** ~80 рабочих дней = 16 недель.

---

## Phase 12 — Multi-MCP Orchestration + Capability Discovery

**Срок:** 10-14 дней | **Сложность:** средняя | **Риск:** низкий

### Цель
LLM работает с 5 MCP параллельно. Backend знает capabilities каждого. Frontend показывает соответствующий UI.

### Atomic tasks (≤ 1 день каждая)

#### 12.1 — Backend модель `MCPConnection` (1 день)
**Файл:** `backend/app/models/connection.py`
- Добавить поля: `mode`, `configuration`, `platform_version`, `extension_version`, `capabilities`, `last_handshake_at`, `last_error`
- Alembic миграция `add_capability_fields_to_connection`
- Тесты: создание, обновление, сериализация

#### 12.2 — Capability discovery service (1.5 дня)
**Файл:** `backend/app/services/capability_discovery.py`
- Функция `parse_capabilities(initialize_response) → ConnectionMetadata`
- Legacy mode detection (если нет `experimental.analyst-1c`)
- Heuristics для inferring features из tools (для backwards compat)
- Тесты: 5+ типов ответов (EPF, CFE, external, legacy, malformed)

#### 12.3 — MCP Orchestrator (2 дня)
**Файл:** `backend/app/services/mcp_orchestrator.py`
- Класс `MCPOrchestrator` с регистром MCP клиентов
- Метод `unified_tool_registry()` — с префиксами
- Метод `route_tool_call(name, args)` — диспатч по префиксу
- Тесты: маршрутизация, конфликт имён, fallback

#### 12.4 — Existing MCP clients refactor (1.5 дня)
**Файлы:** `backend/app/services/mcp_clients/{http,stdio,base}.py`
- Базовый класс `MCPClient` (abstract)
- `HTTPMCPClient` (для :6010, :6002, :8770)
- `StdioMCPClient` (для bsl-context, METR)
- Capability discovery integration
- Тесты: connection lifecycle, error handling

#### 12.5 — Endpoint обновления capabilities (0.5 дня)
**Файл:** `backend/app/api/connections.py`
- `POST /connections/{id}/refresh-capabilities`
- `GET /connections/{id}/capabilities`
- Тесты: успех, MCP unreachable, malformed response

#### 12.6 — LLM Orchestrator интеграция (1 день)
**Файл:** `backend/app/services/llm_orchestrator.py` (существующий)
- `build_tools_for_session()` использует Orchestrator
- Tools с префиксами в LLM payload
- Tool call dispatcher через Orchestrator
- Тесты: multi-MCP вызовы в одной session

#### 12.7 — Frontend `useCapability` hook (0.5 дня)
**Файлы:** `frontend/lib/capabilities.ts`, `frontend/hooks/useCapability.ts`
- Define `Capability` type (23 значения)
- `useCapability(...required)` hook
- `useEnabledModules()` hook
- Tests: vitest на mocked connections

#### 12.8 — SourceSelector рефакторинг (1 день)
**Файлы:** `frontend/components/SourceSelector.tsx` (бывший ChannelSelector)
- Группировка по типу (Базы 1С / Знания / Инструменты)
- Multi-select для парапаллельного использования
- Badge mode для каждого подключения (EPF/CFE/EXT)
- E2E тест: выбор multiple sources

#### 12.9 — Connection settings UI с capability inspector (1 день)
**Файл:** `frontend/components/settings/ConnectionDetails.tsx`
- Detail view с capabilities list (свернуто по умолчанию)
- "Обновить" кнопка → POST /connections/{id}/refresh-capabilities
- Active modules list (из useEnabledModules)
- Visual indicators (mode badge, status dot)

#### 12.10 — Seed для 5 default подключений (0.5 дня)
**Файл:** `backend/app/db/seed.py`
- Транзит (MCP Toolkit на :6010)
- ИТС + Напарник (1c-buddy :6002)
- Синтаксис платформы (mcp-bsl-context stdio)
- Запуск тестов (METR stdio) — disabled by default
- EDT workspace (EDT-MCP :8770) — disabled by default

#### 12.11 — E2E smoke test для Multi-MCP (1 день)
**Файл:** `frontend/tests/e2e/multi-mcp.spec.ts`
- Запустить с 3 активными MCP
- Задать 3 разных вопроса (требующих разных MCP)
- Проверить trace что каждый ушёл в свой MCP
- Проверить что UI badge корректен для каждого

#### 12.12 — Migration script для legacy connections (0.5 дня)
- Существующие подключения в БД получают `mode="legacy"`, `capabilities=[]`
- При первом запуске после обновления — auto-handshake
- Update connections.last_handshake_at

### Acceptance criteria
- [ ] Подключаешь все 5 MCP одновременно — работают
- [ ] При выборе SourceSelector "Запросы по базе + Поиск в ИТС" — LLM использует оба
- [ ] Capability inspector показывает корректные данные
- [ ] Legacy MCP (без experimental.analyst-1c) — работает в базовом режиме
- [ ] Tests: 95%+ coverage на новый код

### Артефакты
- 12 новых файлов backend
- 8 новых файлов frontend
- 1 alembic migration
- 25+ новых tests
- Обновлённый ARCHITECTURE.md

---

## Phase 13a — Аналитик Lite (EPF)

**Срок:** 10-14 дней | **Сложность:** средняя (1С разработка) | **Риск:** средний

### Цель
Один файл `АналитикLite.epf` (~3 MB), который аналитик открывает двойным кликом и сразу работает с базой 1С через веб-приложение.

### Atomic tasks

#### 13a.1 — Создать EPF scaffold (1 день)
- Скачать MCP_Toolkit_v1.7.0.epf → разобрать в XML
- Создать новую обработку АналитикLite через cc-1c-skills:
  - `/epf-init` → scaffold
  - `/epf-add-form ОсновнаяФорма`
  - `/epf-add-form НастройкиToken`
- Подсистема "АналитикПлюс"

#### 13a.2 — Внедрить MCP Toolkit код (2 дня)
- Скопировать общие модули из MCP_Toolkit:
  - `MCPServerHTTP` → `АП_MCPServerHTTP`
  - Изменить пути регистрации (использовать префикс АП_)
- Тестировать что сервер запускается на :6010 и отвечает initialize

#### 13a.3 — Внедрить Connector (1 день)
- Из `tools/Connector/src/exts/Connector/Ext/ObjectModule.bsl` скопировать функции в `АП_HTTPКоннектор`
- Лицензия: MIT — указать в Module header (атрибуция)
- Adapt to BSL standards (ssl_3_2 patterns)

#### 13a.4 — Capability response (1 день)
- Общий модуль `АП_CapabilityResponse`
- Функция `ПолучитьCapabilities()` возвращает 8 features для EPF
- Включает в `initialize` ответ под `experimental.analyst-1c`

#### 13a.5 — Launcher form (ОсновнаяФорма) (2 дня)
- UI как в [03-DELIVERY-MODES.md](./03-DELIVERY-MODES.md) sketch
- Кнопки: Запустить сервер / Остановить / Открыть веб-приложение
- Поля: Порт, HMAC секрет
- Status indicator (зелёный/красный круг)
- Кнопка "Сгенерировать секрет"
- Кнопка "Установить CFE-расширение" (ссылка на инструкцию)

#### 13a.6 — HMAC token generation + paste flow (1 день)
- Генерация секрета 32 байта (через `Криптография.Случайные`)
- Сохранение в `ХранилищеНастроекДанныхФорм` (per-user)
- Copy to clipboard
- Frontend в Electron — protocol handler `analyst://configure?secret=...`

#### 13a.7 — Embedded launcher logic (1 день)
- Кнопка "Открыть веб-приложение"
- Если Electron не запущен → запускает через `Файловая Система.ЗапуститьПриложение`
- Если запущен → отправляет HTTP запрос на 127.0.0.1:8010/api/external/launch
- Передаёт endpoint MCP + HMAC секрет через query параметры

#### 13a.8 — EPF compile + validate (0.5 дня)
- `/epf-build` → собрать .epf файл
- `/epf-validate` → проверить корректность
- Загрузить в тестовую базу
- Smoke test: открыть форму, запустить сервер, проверить :6010

#### 13a.9 — Integration test с Electron app (1 день)
- В Electron — обновить protocol handler `analyst://`
- E2E: запустить EPF → запустить Electron → авто-подключение → smoke test
- Проверить что capabilities = 8 features
- Проверить что UI правильно ограничен (нет CFE-only модулей)

#### 13a.10 — Документация для аналитика (0.5 дня)
- `docs/INSTALL-EPF.md` — пошаговая инструкция установки EPF
- Скриншоты
- Troubleshooting (порт занят, фаервол, и т.д.)

### Acceptance criteria
- [ ] EPF файл собирается (`/epf-validate` PASS)
- [ ] Двойной клик на .epf → форма открывается
- [ ] Сервер запускается на :6010, отвечает initialize с 8 capabilities
- [ ] Веб-приложение подключается, mode="epf"
- [ ] Все 8 capabilities работают (тестируем 1 запрос на каждую)
- [ ] При закрытии формы — сервер останавливается с warning
- [ ] EPF работает на УТ 11.5, ERP 2.5, КА 2.5 (тестируем на 3 базах)

### Артефакты
- `АналитикLite.epf` (~3 MB)
- `docs/INSTALL-EPF.md`
- Integration tests

---

## Phase 13b — АналитикПлюс (CFE)

**Срок:** 15-21 день | **Сложность:** высокая (1С разработка + 1С админ) | **Риск:** высокий

### Цель
Расширение конфигурации `АналитикПлюс.cfe` с 23 capabilities, постоянным HTTP-сервисом, подписками на события, регламентными заданиями, HMAC SSO.

### Phase разделена на 4 sub-фазы:

### 13b.1 — Базовая CFE структура (3-4 дня)

#### 13b.1.1 — CFE scaffold через cc-1c-skills (0.5 дня)
- `/cfe-init` → scaffold
- Подсистема АналитикПлюс
- Префикс АП_

#### 13b.1.2 — Заимствование MCP Toolkit + Connector (1 день)
- Перенос общих модулей из EPF Phase 13a
- HTTP-сервис вместо HTTP-сервера на форме
- `АналитикПлюсHTTP` HTTP-service с эндпоинтами /mcp, /events, /health

#### 13b.1.3 — Базовый capability response (0.5 дня)
- 11 базовых capabilities (mcp.* + connector.*)
- Без CFE-only пока

#### 13b.1.4 — Tools UI 1C integration (2 дня)
- Из `tools/tools_ui_1c/` импортировать 6 обработок:
  - КонсольЗапросов
  - КонсольКода
  - HTTPИнструменты
  - JSONРедактор
  - ПоискДубликатов
  - СериализаторДанных
- Перевести в `Обработки.АП_*`
- Лицензия: GPL-3.0 → указать в каждом модуле

### 13b.2 — Event subscriptions + Activity Stream (3-4 дня)

#### 13b.2.1 — Регистр МониторингАктивности (0.5 дня)
- Измерения: Объект (Тип = Любая ссылка), Пользователь, ТипСобытия
- Ресурсы: Сообщение (Строка), Данные (Структура → JSON)
- Периодичность: ВПределахСекунды

#### 13b.2.2 — Подписки на события (2 дня)
- АП_ПриЗаписиОбъекта (Object.Write для всех справочников + документов)
- АП_ПриУдаленииОбъекта
- АП_ПриЗаписиНаСервере (для документов — более точный момент)
- Для каждой — запись в регистр МониторингАктивности
- Performance: фильтр по белому списку объектов (configurable)

#### 13b.2.3 — Activity Stream HTTP endpoint (1 день)
- `/АналитикПлюсHTTP/events?since=<timestamp>` — возвращает события с момента
- WebSocket-like polling (т.к. HTTP-сервис 1С не поддерживает WS нативно)
- В будущем v3 — переход на real WebSocket через external addin

#### 13b.2.4 — Capability `cfe.activity_stream` (0.5 дня)
- Добавить в capability response
- Документация endpoint

### 13b.3 — Method overrides + Posting Trace (3-4 дня)

#### 13b.3.1 — Заимствование типовых документов (1 день)
- Заимствовать в расширение базовые документы УТ (РеализацияТоваровУслуг, ПриобретениеТоваровУслуг, ...)
- Список configurable в настройках расширения

#### 13b.3.2 — Перехват ОбработкаПроведения (2 дня)
- `&Перед("ОбработкаПроведения")` — capture before-state регистров
- `&После("ОбработкаПроведения")` — capture after-state
- Сохранение diff в регистр АП_PostingTrace
- Тяжело по performance — нужны фильтры (по умолчанию отключено, включается per document type)

#### 13b.3.3 — Posting Trace HTTP endpoint (1 день)
- `/АналитикПлюсHTTP/posting-trace?doc_ref=<URL>` — возвращает before/after
- Visualization data для PostingTraceCard

### 13b.4 — HMAC SSO + Persistent HTTP + Final polish (3-4 дня)

#### 13b.4.1 — HMAC SSO (1.5 дня)
- Общий модуль АП_AuthHMAC
- Параметр сеанса АП_ТекущийАналитик
- Endpoint /АналитикПлюсHTTP/auth/handshake — возвращает HMAC токен с username + base_id + expires
- Backend проверяет токен → создаёт сессию

#### 13b.4.2 — Persistent HTTP service (1 день)
- Регламентное задание АП_ИнициализацияMCPСервиса (запуск раз в 5 мин, idempotent)
- Auto-restart если упал
- Healthcheck endpoint
- Параметр `cfe.persistent_http = true`

#### 13b.4.3 — Регламентные задания (1 день)
- АП_АвтоЭкспортОтчётов (configurable schedule)
- АП_МониторингСвободногоМеста (daily)
- АП_АктуализацияКеша (hourly)
- Capability `cfe.scheduled_jobs`

#### 13b.4.4 — Settings storage + Hot reload metadata (0.5 дня)
- Использование ХранилищеНастроекДанныхФорм для per-user settings
- Detection изменений метаданных через `ПолучитьСтруктуруХраненияБазыДанных().УникальныйИдентификатор`
- Capability `cfe.settings_storage`, `cfe.hot_reload_metadata`

### 13b.5 — Installer + tests (2 дня)

#### 13b.5.1 — PowerShell installer (1 день)
- `Install-АналитикПлюс.ps1` (см. [03-DELIVERY-MODES.md](./03-DELIVERY-MODES.md))
- Поддержка файловой и серверной базы
- Откат при ошибке

#### 13b.5.2 — Smoke tests on 3 typical (1 день)
- Тестируем на УТ 11.5
- Тестируем на ERP 2.5
- Тестируем на КА 2.5
- Проверяем что не конфликтует с типовой
- Проверяем что 23 capabilities активны

### Acceptance criteria для Phase 13b
- [ ] CFE собирается через `/cfe-validate` PASS
- [ ] Installer работает на УТ 11.5 / ERP 2.5 / КА 2.5
- [ ] HTTP-сервис стартует автоматически после перезапуска платформы
- [ ] 23 capabilities активны
- [ ] HMAC SSO работает (auto-login без ввода токена)
- [ ] Activity Stream показывает realtime события
- [ ] Posting Trace работает на 1 документе УТ
- [ ] Регламентные задания запускаются
- [ ] Migration с EPF на CFE работает (одна и та же история сессий)

### Артефакты Phase 13b
- `АналитикПлюс.cfe` (~8 MB)
- `Install-АналитикПлюс.ps1`
- `docs/INSTALL-CFE.md`
- 3 успешных smoke на типовых

---

## Phase 14 — Тройной RAG (v8std + БСП API + .hbk)

**Срок:** 15-21 день | **Сложность:** высокая | **Риск:** средний

### Цель
LLM получает релевантные стандарты + БСП API + справку платформы из 3 RAG-источников в каждом ответе с кодом.

### Sub-фазы

### 14.1 — Infrastructure (2-3 дня)

#### 14.1.1 — sqlite-vec setup (1 день)
- Добавить `sqlite-vec` extension в backend
- Миграция БД для нового файла `rag.db`
- Базовая обёртка над `sqlite-vec`

#### 14.1.2 — Embeddings service (1 день)
- OpenAI text-embedding-3-small (или MiMo-compatible если есть)
- Batch API для cost optimization
- Кэширование вокруг embeddings (sqlite)

#### 14.1.3 — Generic RAG service (1 день)
- `app/services/rag/base.py` — IndexerBase, RetrieverBase
- Метод `index_source(name, docs)`, `search(name, query, top_k)`
- Тесты на toy datasets

### 14.2 — v8std источник (3-4 дня)

#### 14.2.1 — Парсер v8std (1.5 дня)
- Загрузка из `tools/v8std/content/*.md`
- Парсинг frontmatter (если есть)
- Разбивка на чанки (метод + diagnostics + примеры)
- Извлечение reference IDs (СтРД-XXX)

#### 14.2.2 — Индексация (1 день)
- 317 документов → ~500-700 чанков
- Embeddings: $13
- Сохранение в sqlite-vec collection `v8std`

#### 14.2.3 — Retriever + citation формат (1 день)
- `rag.search("v8std", query, top_k=3)` → List[V8StdCitation]
- Каждая citation: {id, title, severity, snippet, full_url}
- Тесты с типовыми BSL-вопросами

#### 14.2.4 — UI блок StandardsCitationBlock (0.5 дня)
- Под CodeCard collapsible раздел
- Цвета по severity (BLOCKER red, CRITICAL orange, MAJOR yellow, MINOR blue)
- Клик на ID → модальное окно с полным текстом

### 14.3 — БСП API источник (4-5 дней)

#### 14.3.1 — Парсер БСП исходников (2 дня)
- Сканирование `tools/ssl_3_2/src/CommonModules/*/Ext/Module.bsl`
- Извлечение экспортных процедур/функций
- Парсинг JSDoc-комментариев (документация в `// Параметры:`)
- Извлечение примеров из комментариев

#### 14.3.2 — Сложности парсера (1 день)
- Мульти-строчные комментарии
- БСП standards форматирование
- Параметры с типами

#### 14.3.3 — Индексация (1 день)
- ~3000 методов → embeddings
- Stoимость: ~$60
- Сохранение в sqlite-vec collection `ssl_api`

#### 14.3.4 — Retriever + citation (0.5 дня)
- `rag.search("ssl_api", query, top_k=5)` → List[BSPMethodCitation]
- BSPMethodCard для отображения

### 14.4 — .hbk файл платформы (5-7 дней)

#### 14.4.1 — Локализация .hbk файла (0.5 дня)
- Поиск `C:\Program Files\1cv8\8.3.27.1989\1ceBsl.hbk` (или другой версии)
- Если несколько версий — выбрать актуальную
- Settings UI для override пути

#### 14.4.2 — Парсер .hbk (3-5 дней) — **САМЫЙ СЛОЖНЫЙ ТАСК**
- .hbk — бинарный формат
- Опции:
  - **Использовать onec_dtools** (Python, github.com/Infactum/onec_dtools) — но он Alpha и заброшен с 2017
  - **Собственный парсер** через analysis формата (есть статьи на habr)
  - **Wrapper над bsl-language-server** (он умеет читать .hbk внутри)
- **Fallback:** если не получится за 5 дней — пропускаем .hbk, оставляем v8std + ssl_api

#### 14.4.3 — Индексация (1 день, если получится)
- ~5000 entries → $150 embeddings
- sqlite-vec collection `platform_hbk`

#### 14.4.4 — Retriever + citation (0.5 дня)
- PlatformHelpCard

### 14.5 — Orchestrator integration (2-3 дня)

#### 14.5.1 — Merge with priorities (1 день)
- Веса по источнику: v8std=1.2, ssl_api=1.0, platform_hbk=0.8
- Top-K дедупликация
- Реrank через cross-encoder (опц.)

#### 14.5.2 — Injection в system prompt (0.5 дня)
- При BSL-вопросах LLM получает 5-10 citations в system message
- Tag формат: `<retrieved_standard id="..." />`

#### 14.5.3 — Citations в LLM response → frontend cards (1 день)
- LLM возвращает code с inline citations: `// СтРД-783: транзакции`
- Backend парсит citations → передаёт в frontend как metadata
- CodeCard рендерит citations под кодом

#### 14.5.4 — RAG status в Settings (0.5 дня)
- Статус каждого RAG-источника (ok / not indexed / outdated)
- Кнопка "Переиндексировать" с прогресс-баром

### Acceptance criteria для Phase 14
- [ ] v8std: 317 документов проиндексированы
- [ ] ssl_api: ~3000 методов проиндексированы
- [ ] platform_hbk: ~5000 entries (если получилось)
- [ ] При запросе "как настроить регистр" — LLM получает релевантные стандарты + методы БСП
- [ ] StandardsCitationBlock корректно рендерит цитаты с severity цветами
- [ ] Re-indexing работает по кнопке
- [ ] Cost: ≤ $250 на полную индексацию

### Артефакты Phase 14
- `backend/app/services/rag/`
- `backend/data/rag.db` (sqlite-vec, ~50 MB)
- `frontend/components/rag/`
- Документация процесса индексации

---

## Phase 15 — BSL LS + streaming diagnostics

**Срок:** 10-14 дней | **Сложность:** средняя | **Риск:** средний

### Цель
Автопроверка BSL кода через BSL LS в реальном времени по мере написания LLM.

### Atomic tasks

#### 15.1 — Bundle BSL LS jar в backend (1 день)
- Положить jar в `backend/bin/bsl-language-server-0.30.0-rc.2-exec.jar`
- Альтернатива: download postinstall (113 MB не bundling)
- Settings option: использовать external jar

#### 15.2 — Bundle JRE 17 для Electron (1 день)
- Liberica JRE 17 (или Microsoft OpenJDK 17)
- ~80 MB extra в installer
- Path detection с fallback на system JRE

#### 15.3 — Subprocess runner (2 дня)
- `backend/app/services/bsl_lint/runner.py`
- Async subprocess через `asyncio.create_subprocess_exec`
- `--analyze --reporter=json` режим BSL LS
- Timeout 10 сек
- Error handling (JRE не найден, BSL LS crashed)

#### 15.4 — JSON парсер diagnostics (1 день)
- `backend/app/services/bsl_lint/parser.py`
- Парсинг JSON-отчёта BSL LS
- Конвертация в `BSLDiagnostic { line, column, severity, code, message }`
- Mapping `code` к v8std-стандартам (где возможно)

#### 15.5 — SHA256 cache (1 день)
- `backend/app/services/bsl_lint/cache.py`
- Key: SHA256(code) + version of BSL LS
- TTL: бесконечно (инвалидация при upgrade BSL LS)
- Hit ratio metric

#### 15.6 — REST endpoint (0.5 дня)
- `POST /lint/bsl` { code } → diagnostics list
- Используется по требованию (не автоматически)

#### 15.7 — Streaming via WebSocket (3-4 дня) — **САМОЕ СЛОЖНОЕ**
- WebSocket endpoint `/ws/lint/{session_id}`
- LLM stream → debounce 500ms → BSL LS на накопленные строки
- Push diagnostics в WS
- Frontend: live highlighting в CodeCard

#### 15.8 — BSLDiagnosticsCard компонент (2 дня)
- `frontend/components/lint/BSLDiagnosticsCard.tsx`
- Pill над CodeCard: `🔴 3 errors  🟡 5 warnings`
- Collapsible детали с line numbers
- Клик на diagnostic → highlight строки в код-блоке
- Link на v8std статью (если есть mapping)

#### 15.9 — Settings toggle (0.5 дня)
- "Проверять BSL через Language Server" — default ON
- Per-session override

#### 15.10 — E2E test (1 день)
- Сгенерировать код с антипаттерном (тернарник, ТекущаяДата без Сеанса)
- Проверить что diagnostic появляется
- Проверить кэш (повторный — мгновенно)

### Acceptance criteria для Phase 15
- [ ] BSL LS работает: можно прогнать любой BSL код
- [ ] Diagnostics появляются за ≤ 2 сек
- [ ] Cache работает (повторный ≤ 100ms)
- [ ] Streaming diagnostics во время LLM stream (debounced)
- [ ] BSLDiagnosticsCard рендерится в CodeCard
- [ ] Связь с v8std citations (где доступно)
- [ ] Toggle в Settings работает

### Артефакты Phase 15
- `backend/app/services/bsl_lint/`
- `backend/bin/bsl-language-server-0.30.0-rc.2-exec.jar`
- `frontend/components/lint/`
- WebSocket endpoint

---

## Phase 16 — MetaVision граф (форк + CLI + D3)

**Срок:** 20-28 дней | **Сложность:** высокая (Java + D3 + integration) | **Риск:** высокий

### Sub-фазы

### 16.1 — MetaVision fork + CLI режим (5-7 дней)

#### 16.1.1 — Форк репозитория (0.5 дня)
- Fork `AndreyHhh/MetaVision` → `nikitakhvorostov1912-beep/MetaVision`
- Local clone в `tools/MetaVision/` уже есть, обновить remote

#### 16.1.2 — Анализ Java кода (1-2 дня)
- Понять структуру: где GUI код, где analyzer code
- Найти точку входа `com.lycurg.metavisionfor1c.Application_MetaVision`
- Identify Core analyzer без GUI dependency

#### 16.1.3 — CLI mode добавить (3-4 дня)
- Новый main class `com.lycurg.metavisionfor1c.CLI`
- Args: `--src=<path> --output=<json> [--format=json|sarif]`
- Запускать analyzer без JavaFX (только модули `javafx.base` если нужны для types)
- Output структура:
```json
{
  "configuration": {"name": "Транзит", "objects": 47, "modules": 234},
  "graph": {
    "nodes": [{"id": "Module.A.method1", "type": "Function", "complexity": 5, "warnings": 2}],
    "edges": [{"from": "Module.A.method1", "to": "ОбщегоНазначения.X"}]
  },
  "antipatterns": [
    {"type": "RCE", "location": "Module.B.method3", "severity": "blocker"}
  ],
  "statistics": {"total_functions": 1543, "warnings_total": 87}
}
```

#### 16.1.4 — Тестирование CLI (0.5 дня)
- На реальной выгрузке конфигурации УТ
- Сравнение результата с GUI режимом
- Performance benchmark

#### 16.1.5 — Submit PR в upstream (опц., 0.5 дня)
- Возможно автор AndreyHhh примет PR
- Если нет — используем свой fork

### 16.2 — Backend integration (3-4 дня)

#### 16.2.1 — Java subprocess wrapper (1 день)
- `backend/app/services/metavision/runner.py`
- `java -jar MetaVision.jar --cli --src=... --output=...`
- Timeout 5 минут (большие конфигурации)
- Error handling

#### 16.2.2 — JSON parser (1 день)
- `backend/app/services/metavision/parser.py`
- Pydantic модели для graph
- Validation

#### 16.2.3 — REST endpoint (1 день)
- `POST /analyze/configuration` (multipart ZIP upload)
- Распаковка в temp dir
- Запуск MetaVision CLI
- Возврат JSON
- Cleanup temp

#### 16.2.4 — Capability service.metavision (0.5 дня)
- Активна если MetaVision jar найден

### 16.3 — Frontend D3 graph (8-10 дней)

#### 16.3.1 — Choice of library (0.5 дня)
- D3.js force-directed для < 1000 узлов
- sigma.js или react-force-graph для 1000-5000 узлов
- Для 5000+ — Cytoscape.js с WebGL renderer

#### 16.3.2 — MetaVisionGraphCard skeleton (1 день)
- Базовая структура компонента
- Layout: граф 70% + side panel 30%

#### 16.3.3 — Force-directed render (2-3 дня)
- Узлы — функции, размер по complexity
- Цвет: server (синий), client (зелёный), mixed (фиолетовый)
- Связи — вызовы, толщина по частоте
- Anti-pattern узлы — обводка red
- Tooltip с метриками

#### 16.3.4 — Поиск + фильтры (1.5 дня)
- Search box (fuzzy)
- Фильтры: только проблемные, только серверные, только новые в CFE
- Highlight связей при hover

#### 16.3.5 — Side panel — детали узла (1.5 дня)
- При клике на узел — детали:
  - Имя, путь
  - Тип (server/client/...)
  - Complexity, warnings count
  - Применимые v8std стандарты (через RAG)
  - Кнопка "Открыть код" → CodeCard в чате

#### 16.3.6 — Export (1 день)
- PNG export (через html2canvas)
- SVG export (D3 native)
- GraphML для импорта в Gephi

#### 16.3.7 — Performance optimization (1 день)
- Virtualization при 5000+ узлов
- Web Worker для force simulation

### 16.4 — Upload UI + UX (2-3 дня)

#### 16.4.1 — File upload компонент (1 день)
- Drag-and-drop ZIP конфигурации
- Progress bar
- Validation (это действительно конфигурация 1С?)

#### 16.4.2 — Прогресс анализа (1 день)
- SSE для streaming прогресса от backend (parsing → analyzing → building graph)
- Иконки stages

#### 16.4.3 — Caching результатов (0.5 дня)
- По хэшу ZIP файла
- Re-analyze кнопка

#### 16.4.4 — E2E test (0.5 дня)
- Загрузка тестовой конфигурации
- Проверка что граф рендерится
- Проверка что клики работают

### Acceptance criteria для Phase 16
- [ ] MetaVision CLI работает с тестовой конфигурацией
- [ ] Backend endpoint возвращает корректный JSON
- [ ] Frontend рендерит граф 1000+ узлов плавно
- [ ] Поиск, фильтры работают
- [ ] Клик на узел показывает детали + кнопку открыть код
- [ ] Export PNG/SVG работает
- [ ] Связь с v8std через RAG (узел показывает применимые стандарты)

### Артефакты Phase 16
- Fork `nikitakhvorostov1912-beep/MetaVision` с CLI
- `backend/app/services/metavision/`
- `frontend/components/analysis/MetaVisionGraphCard.tsx`
- Documentation для пользователя

---

## Phase 17 — Cards + UX + feature gates

**Срок:** 10-14 дней | **Сложность:** средняя | **Риск:** низкий

### Цель
Свести все новые источники в когерентный UX. Никаких новых экранов, всё через cards.

### Atomic tasks

#### 17.1 — UpgradeCTA компонент (1 день)
- Универсальный компонент для disabled фич
- Props: feature, currentMode, requires, description, benefits, cta
- Brand-compliant дизайн (Stencil/Mono)

#### 17.2 — Feature module registry (1 день)
- Регистр в `frontend/lib/feature-modules.ts`
- Dynamic imports
- Lazy loading components

#### 17.3 — Card type registry rebuild (1 день)
- Динамическая регистрация cards по capabilities
- Обновление CardRenderer для использования registry

#### 17.4 — ITSArticleCard компонент (1 день)
- Для результатов `buddy.fetch_its`
- Полноценный article view (rich text)
- Bookmarking

#### 17.5 — BSPMethodCard компонент (1 день)
- Для результатов RAG ssl_api
- Сигнатура + параметры + примеры
- Кнопка "Открыть в исходнике БСП"

#### 17.6 — PlatformHelpCard компонент (1 день)
- Для результатов RAG platform_hbk
- Аналогично BSPMethodCard но для платформы

#### 17.7 — AntipatternCard компонент (1 день)
- Когда MetaVision/BSL LS нашёл проблему
- Severity, описание, как исправить (LLM)
- Link на v8std стандарт

#### 17.8 — MetricsCard компонент (1 день)
- Статистика конфигурации
- Используется и в чате, и в Settings

#### 17.9 — Source chips под сообщениями LLM (1 день)
- Каждое сообщение → chips: "База: Транзит", "ИТС: 2 статьи", "Стандарты: 3"
- Клик на chip — фильтрует cards/citations

#### 17.10 — Cross-card references (1 день)
- Клик на standard в StandardsCitationBlock → открывает полный текст в модалке
- Клик на узел в MetaVisionGraph → открывает CodeCard этой функции
- Клик на ИТС-статью → fetch_its + ITSArticleCard

#### 17.11 — Streaming stages обновление (0.5 дня)
- Новые stages: "Ищу в ИТС + БСП + Стандартах", "Проверяю BSL LS"
- Visual transitions

#### 17.12 — Brand audit (0.5 дня)
- Все новые компоненты по Stencil/Mono
- Signal #FF6A3D для primary
- JetBrains Mono для метаданных
- Проверить design-bans.md

#### 17.13 — Accessibility (1 день)
- Keyboard navigation для графа
- ARIA labels
- Contrast check (Stencil dark theme)

### Acceptance criteria для Phase 17
- [ ] 8 новых типов cards: BSLDiagnostics, StandardsCitation, ITSArticle, BSPMethod, PlatformHelp, MetaVisionGraph, Antipattern, Metrics
- [ ] UpgradeCTA на disabled фичах вместо скрытия
- [ ] Source chips работают
- [ ] Cross-card references работают
- [ ] Brand compliance — все компоненты по Stencil/Mono
- [ ] Vitest tests на компоненты
- [ ] Playwright E2E на full chat flow с разными cards

### Артефакты Phase 17
- 8 новых .tsx файлов
- Обновлённый CardRenderer
- Vitest tests
- Playwright tests

---

## Phase 17b — Activity Stream + Posting Trace (CFE-only)

**Срок:** 5-7 дней | **Сложность:** средняя | **Риск:** низкий

Может идти параллельно с Phase 17.

### Atomic tasks

#### 17b.1 — Activity Stream sidebar компонент (2 дня)
- Right sidebar (только в CFE mode)
- Polling `/АналитикПлюсHTTP/events?since=...` каждые 2 сек
- Список событий с фильтрами
- Click → детали в модалке или CodeCard

#### 17b.2 — Activity event card (1 день)
- Inline в чате когда LLM упоминает событие
- Полноценное отображение события

#### 17b.3 — PostingTraceCard компонент (2 дня)
- Visualization before/after регистров
- Diff highlight
- Связь с документом

#### 17b.4 — E2E tests (1 день)
- Создать документ в 1С → проверить что появилось в Activity Stream
- Провести документ → проверить Posting Trace

#### 17b.5 — Performance optimization (1 день)
- Pagination для Activity Stream
- Limit на 100 событий показывать одновременно
- Старые — в архив

### Acceptance criteria
- [ ] Activity Stream показывает realtime события из 1С
- [ ] Posting Trace показывает diff до/после проведения
- [ ] Только в CFE mode (capability gate работает)
- [ ] Performance: 1000+ событий не лагают UI

---

## Phase 18 — Distribution v2.0

**Срок:** 7-10 дней | **Сложность:** средняя | **Риск:** средний

### Цель
Production-ready installers для конечных аналитиков. Auto-update.

### Atomic tasks

#### 18.1 — Electron installer rebuild (2 дня)
- Bundled: backend + frontend + JRE 17 (~250 MB total)
- Postinstall: download BSL LS jar (113 MB), MetaVision jar (50 MB)
- Auto-index v8std + ssl_api при первом запуске (15 мин)

#### 18.2 — CFE installer signing (1 день)
- Code-signing certificate (если есть)
- SmartScreen prevention

#### 18.3 — Update mechanism (1 день)
- electron-updater (уже используется)
- Components versions API: BSL LS / MetaVision / RAG / Electron
- Granular updates: можно обновлять BSL LS без переустановки всего

#### 18.4 — First-run wizard improvements (2 дня)
- Skip onboarding если установка из CFE с auto-token
- Прогресс: "Скачиваем BSL LS (113 MB)... Индексируем стандарты..."
- Cancel/retry option

#### 18.5 — Release notes v2.0 (0.5 дня)
- Все 8 фаз summary
- Скриншоты новых фич
- Migration guide для v1.4.x пользователей

#### 18.6 — Smoke checklist (1 день)
- Полный e2e на чистой VM
- УТ 11.5 / ERP 2.5 / КА 2.5
- Файловая и серверная базы

#### 18.7 — Distribution через GitHub Releases (0.5 дня)
- 3 артефакта: `.exe`, `.epf`, `.cfe`
- + `Install-АналитикПлюс.ps1`
- + checksum SHA256

#### 18.8 — Auto-update protocol (1 день)
- На каждом старте — проверка GitHub Releases API
- Если есть новая версия — предложение обновиться
- Backward compat checks

### Acceptance criteria
- [ ] Installer 250 MB загружается без ошибок
- [ ] Первый запуск ~20 мин включая RAG индексацию
- [ ] Auto-update работает (тестируем на 2.0.0 → 2.0.1)
- [ ] Smoke на 3 типовых конфигурациях
- [ ] CFE installer на 3 базах (файл, серверная PG, серверная MS)
- [ ] SmartScreen не ругается (если есть signing)
