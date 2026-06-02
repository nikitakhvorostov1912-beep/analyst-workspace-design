# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версионирование — [SemVer](https://semver.org/lang/ru/).

## [Unreleased]

### 2026-06-02 — ИТС в чате + durability + user-facing «3 источника знаний»

#### Fixed
- **ИТС/Напарник реально подключён в чат** (был критический разрыв из ROADMAP §6.0):
  чат собирал инструменты через `MCPPool` (toolkit + только bsl-context), а buddy
  жил в неиспользуемом чатом `MCPOrchestrator` → `buddy.search_its` НЕ доходил до
  LLM, ИТС-ответы шли из памяти модели по пустой статической заглушке. Добавлен
  `BuddyAuxClient` (HTTP-aux с namespace-префиксом `buddy.` + телеметрия #40) в
  `mcp_pool.build_aux_clients`; `list_all_tools` пропускает `_proc`-guard для
  HTTP-aux. Live (MiMo): чат зовёт `buddy.search_its` → `buddy.fetch_its` → ответ
  с живыми ссылками its.1c.ru. Коммит `8cbd96c`.
- **Durability БД грунтинга** — `awd-dev-up/up.ps1` выставляет
  `DATABASE_URL → pilot.db` на каждый запуск (раньше backend по умолчанию читал
  пустую `/data/app.db` без типовых таблиц → карточки/граф/ИТС-tools пусты).
  Скрипт переписан в ASCII (кириллица сбивала кодировку → ParserError). `8cbd96c`.

#### Added — user-facing слой «3 источника знаний» (P0+P1+P2)
> Единая ментальная модель — **Ваша база / Типовая / ИТС·Напарник** — повторена
> в бейдже шапки, на `/status`, в пустом экране, гайде, онбординге и ярлыках
> ответов. До этого ИТС и типовые были невидимы пользователю, а бейдж врал.

- **P0 честный статус:** бейдж шапки «ИТС 0 · БСП 0» → «●●● Источники» с live-
  статусом каждого источника (попап + что спрашивать + ссылки на /status и /guide);
  секция «Источники знаний» на `/status` (раньше про buddy/типовую не знала);
  хук `useSourcesStatus` (ping базы + typical configs + `/health.buddy`); тип
  `BuddyHealth` в `HealthResponse` фронта.
- **P1 discoverability + freshness:** чипы пустого экрана сгруппированы по 3
  источникам + ссылка «Как это работает →»; 2 новых раздела гайда (Типовые
  конфигурации, ИТС и Напарник — с честным предупреждением о латентности живого
  Напарника 1–3 мин); блок «Что я умею — три источника» в онбординге; убран
  дрейф моделей в текстах (DeepSeek V4 Flash → модель-агностично, активная видна
  в бейдже).
- **P2 in-context:** ярлык-источник под ответом (`AnswerSources` — реализует
  гейт приёмки **G0.2 «метка источника»**) по именам вызванных инструментов
  (`buddy.*`/`search_its`→ИТС, `*_typical*`→Типовая, прочие MCP→База); поясняющая
  строка в селекторе «Типовая».
- **Проверка:** `next build` зелёный, 11 unit-тестов (KnowledgeBadge 5 +
  `deriveAnswerSources` 6), live-проверка всех поверхностей в Chrome. Frontend,
  15 файлов.

## [1.5.0] — 2026-06-01 — Knowledge Layer Grounding (карточки + граф + buddy)

> Веха: знаниевый слой работает в проде end-to-end, проверено живым LLM (MiMo
> `mimo-v2.5-pro`). Карточки (смысл «что это») + граф (структура «что с чем
> связано») + grounding в чате. Ветка `feature/m-k3-relational-cfe`.

### Added / Changed (сессия 2026-06-01)
- **Ребилд карточек типовых — 63 207 шт, 100% `is_mock=0`, 99.9% score 5.0**
  (NIM qwen3.5-122b + Claude Haiku + Claude Sonnet; 4 канала: БП 3.0 / УТ 11.5 /
  КА 2.5 / ЕРП 2.5). Аудит `audit_cards.py` сделан kind-aware (graph-aware):
  не штрафует корректные карточки объектов без реквизитов/сценариев (без подгонки
  под метрику, без выдуманных данных). Инструментарий: `build_chunks_from_mock.py`,
  `apply_loop_erp8.py` (salvage частично битого JSON), `apply_sonnet_final.py`.
- **Пересборка графов в `pilot.db` (4 конфигурации)** с фиксами Phase F (движения
  `RegisterRecords`), RLS-v2 (per-right), cross-module CALLS. `wipe_channel_graph.py`
  (обязательный per-channel wipe — билдер сам не чистит). Валидация WRITES_TO:
  ut115 2485 / erp25 8602 / ka2 7672 / bp30 2969 (везде ≠0).
- **Fix grounding read-path** — `build_card_context` подхватывает движения уровня
  объекта (Phase F): Реализация 1→44 регистра в контексте LLM (числа — из графа,
  не из прозы карточки).
- **#38 — цепочка вызовов:** системный промпт (гайд по qname метода, «не молчать
  до лимита, факты из графа»), `grounding.py` MAX_ROUNDS 6→10. Закрыт и подтверждён
  LIVE (MiMo): движения / impact / RLS 3/3 без галлюцинаций.
- **#40 — 1С:Напарник (buddy MCP):** healthcheck + circuit-breaker (`buddy_monitor.py`,
  30s ping → degraded в `/health.buddy`), usage-телеметрия (`_BuddyTelemetryClient`),
  autostart проверен (Startup-ярлык + :6002 жив).

### Knowledge Layer (M-K3 Relational + Behavioral) — 2026-05-29

> Ветка `feature/m-k3-relational-cfe`. Параллельный поток поверх M7 —
> слой понимания L2 (граф вызовов/связей) + анти-галлюцинация по БСП.
> Единый роадмап: `.planning/ROADMAP-2026-05-29.md`.

#### Added
- **Knowledge Graph subgraph API** — `GET /knowledge/{channel_id}/graph/{qname}`
  + `get_subgraph()` в `graph_storage.py`: подграф вокруг узла (узлы с глубиной +
  ИНДУЦИРОВАННЫЕ рёбра, cap `max_nodes`) — данные для будущей GraphCard. Query:
  `depth`/`direction`/`edge_kind`/`max_nodes`/`node_kind`. Работает на типовых
  (УТ/ERP/КА); для живых каналов — после `build_live_graph` (нужен BSL-источник,
  стандартный MCP исходники модулей не отдаёт).
- **G2 phantom-guardrail** (анти-галлюцинация БСП) — `run_chat_loop` после ответа
  сверяет упомянутые методы БСП с корпусом `bsp_chunks`; при выдуманных эмитит
  неблокирующее SSE-событие `bsp_warning` → UI-баннер «сигнатуры не верифицированы».
- **`scripts/graph_bench.py`** — NIM-safe бенчмарк графа (отдельная БД, не `pilot.db`)
  для верификации DoD M-K3.17.1; флаг `--traverse-only`.
- **GraphCard (frontend, React Flow `@xyflow/react`)** — визуализация L2-подграфа
  в чате: раскладка слоями по глубине, центр подсвечен accent-рамкой, CALLS-рёбра
  анимированы. Новый тип карточки `graph` (CardEnvelope/CardRenderer/CardHeader);
  чистая раскладка `lib/graph-card.toFlowElements` под unit-тесты. Backend
  эмитит graph-карточку end-to-end из `trace_typical_calls` (`build_graph_card`
  → `get_subgraph`, CardEvent type `graph`).
- **RLS-tracer (M-K3.17.2)** — флагманский UC «почему пользователь не видит X»,
  на типовых end-to-end (R1+R2+R3):
  - R1 `parse_rights_xml` — парсит `Roles/<Role>/Ext/Rights.xml` → права роли +
    RLS-условия (`restrictionByCondition`), модель `RoleRight`. Устойчив к cp1251
    при declaration UTF-8 (1С так пишет).
  - R2 Phase E в `graph_builder` — Role-узлы + рёбра `EdgeKind.RESTRICTS`
    (Role → MetadataObject, attrs `{right, condition}`) ТОЛЬКО для прав с условием.
    Verified на УТ 11.5: **521 роль, 2103 RLS-ограничения** в графе.
  - R3 LLM-tool `explain_rls_restrictions` — «какие роли и с каким условием
    ограничивают доступ к объекту X». Данные из графа (снапшот); per-user trace
    конкретной записи — на живом канале (MCP get_access_rights + данные документа).

#### Fixed
- **`traverse_bfs` производительность (M-K3.17.1)** — рекурсивный CTE без
  visited-set переисследовал узлы по всем путям (циклы + высокий fan-out →
  экспоненциальный взрыв path-строк). Заменён на итеративный BFS с
  visited-множеством — O(nodes+edges). На реальной типовой УТ 11.5 (62.7K nodes /
  69.4K edges) traversal depth=5: **384мс → 30мс (~12.8×)**. Контракт сохранён
  (46 тестов `graph_storage`). DoD 17.1 (≤300мс) выполнен.

---

M7 Commerce Readiness — переход от пилот-готового beta к коммерчески
распространяемой версии. Wave 1 закрывает CRITICAL уязвимости, Wave 2-3
готовят к публичному релизу.

### Phase 2 — Critical P0 (2026-05-23)

- **P2.1 Backend-only API key (XSS защита, P0-2)** — раньше LLM API-ключи
  жили в `localStorage` и передавались в header `X-LLM-API-Key`. XSS через
  одно прорванное Markdown/Prism тегирование выносил ключи всех пользователей.
  Теперь — на backend в SQLite таблице `user_secrets` с AES-256 GCM
  шифрованием (`cryptography` lib). `app_secret` 32-байтовый ключ генерируется
  при первом запуске backend, лежит в `<userData>/.app-secret`. Новые REST
  endpoints `/user-secrets` (POST/DELETE/GET status). Frontend сохраняет
  через `saveSecretToBackend(provider_id, key)`. Header `X-LLM-API-Key`
  остаётся как backward compat для legacy клиентов, deprecated в v1.4.0.
- **P2.2 ResultSizeGate (P0-3)** — раньше `execute_query` мог вернуть 100k+
  строк → LLM захлёбывалась контекстом + frontend виснул. Теперь модуль
  `result_gate.py` урезает до `MAX_ROWS_FOR_LLM=500` ДО передачи в LLM и UI.
  TableCardPayload расширен полями `truncated: bool` + `total_available: int`.
  UI показывает баннер «Показаны первые 500 из N, сузьте запрос (WHERE /
  временной диапазон) или попросите LLM добавить агрегацию».
- **P2.3 SQL AST validator (P0-4)** — defence-in-depth поверх keyword-scan.
  Новый модуль `sql_validator.py` парсит запрос через `sqlparse` и блокирует
  всё что НЕ `SELECT/ВЫБРАТЬ/WITH/EXPLAIN/SHOW`. Также убирает SQL-комментарии
  ДО парсинга (`-- DELETE FROM users` → strip → второй statement BLOCKED).
  20+ тестов на bypass attempts: encoded payload, multi-statement, inline
  DML в CTE/subquery. Активируется через `pip install sqlparse>=0.5`,
  graceful degrade без зависимости (keyword-scan продолжает работать).

### Auto-update & Code signing (P1.3 / P1.4, 2026-05-23)

- **electron-updater** интегрирован в main.js — после загрузки окна
  проверяет GitHub Releases на новую версию, скачивает в фоне, показывает
  UI баннер `UpdateBanner` в Header с кнопкой «Перезапустить».
- **publish: github** добавлен в `electron-builder.yml` — `git tag vX.Y.Z`
  триггерит `.github/workflows/release.yml`, который собирает Signed
  installer и заливает в GitHub Releases.
- **Code signing scaffold** — `electron-builder.yml` готов принять
  `CSC_LINK` (base64 PFX) и `CSC_KEY_PASSWORD` из GitHub Secrets. Когда
  EV/OV сертификат куплен — SmartScreen warning исчезает. Stamp:
  `signingHashAlgorithms: [sha256]`.

### LLM Providers (P3.1 / P3.3, 2026-05-23)

- **NVIDIA NIM (база)** теперь дефолтный провайдер — ключ вшит в installer,
  один аккаунт покрывает 9 моделей (Llama Nemotron Super 49B, DeepSeek R1/V3.1,
  Qwen3-Coder 480B, Llama 3.3 70B, Mistral Large 3, Mistral Medium 3.5,
  Nemotron Nano 9B). Раньше дефолтом был Xiaomi MiMo (один ключ — одна модель).
- **Cloud.ru Foundation Models** добавлен как 152-ФЗ compliance альтернатива
  (РФ-ДЦ). Бесплатный Qwen3-Coder-480B для корп-клиентов с jur-требованием
  «данные не пересекают границу». Новый env-параметр
  `DEFAULT_LLM_API_KEY_CLOUD_RU` для embedded ключа.
- **Каталог сокращён** под коммерческую стратегию: NVIDIA NIM, Cloud.ru,
  DeepSeek (прямой API — самый дешёвый для R1/V3), Xiaomi MiMo. OpenAI direct,
  Anthropic, Groq, Mistral direct, xAI Grok, OpenRouter убраны из UI dropdown
  (доступны через «Свой endpoint» по необходимости).
- **UI compliance badges** в LLMConfigForm: рядом с выбранным провайдером
  показывается зелёная плашка «РФ-ДЦ ✓ 152-ФЗ» для Cloud.ru или янтарная
  «За рубежом» для зарубежных провайдеров. Аналитик/админ видит compliance
  риск до отправки данных в LLM.

### Security

- **W1.1** Убран MiMo API ключ из коммерческого installer. `desktop/resources/.env`
  больше НЕ копируется в дистрибутив — каждый аналитик вводит свой ключ через
  onboarding. `.env.example` остался как публичный шаблон.
- **W1.2** `execute_query` теперь проходит keyword-scanner (раньше только
  `execute_code`). Добавлены SQL-DML паттерны: INSERT, UPDATE SET, ALTER,
  GRANT, REVOKE, EXEC, sp_executesql. Защита от SQL-injection через MCP.
- **W1.3** Новый бюджет `MAX_TOOL_CALLS_PER_TURN=50` (env конфиг). Защита
  от runaway LLM — DoS клиентской базы 1С невозможен даже при ошибке модели.
- **W1.4** Rate-limit на POST /chat через slowapi: 30/minute по умолчанию
  (env `CHAT_RATE_LIMIT`). 429 + Retry-After: 60.
- **W1.6** Двойная XSS-защита в CodeCard: Prism encode + DOMPurify sanitize
  с whitelist'ом `{span, code, br}` тегов. Защищает от вредоносного кода в
  LLM-ответах.
- **W3.15** CORS `allow_methods` сужен с `*` до `[GET, POST, DELETE, OPTIONS]`.
  Меньше CSRF-surface.

### Performance

- **W3.3** SQLite PRAGMA tuning: synchronous=NORMAL, cache_size=64MB,
  temp_store=MEMORY, foreign_keys=ON. +20-40% writes throughput,
  кеш FTS5-поиска по messages. КРИТИЧНО: foreign_keys раньше был OFF —
  ON DELETE CASCADE не работал, orphan messages при удалении сессий.
- **W3.4** httpx.AsyncClient reuse в AuxiliaryClient (compressor/curator/
  review). Keep-alive + connection pool. Раньше каждый aux-вызов делал
  новый TCP handshake — для длинной сессии с компрессией 5-15 handshakes.

### UX/UI

- **W3.1** 10 точек hardcoded цветов (`text-emerald-400`, `text-rose-400`,
  `text-amber-400`, `amber-700`) заменены на семантические токены
  `var(--success/error/warning/warning-40)`. Light theme (Sand) теперь
  адаптируется корректно.
- **W3.2** StreamingStages показывает русские лейблы tool names:
  `execute_query` → «Выполняю запрос», `get_metadata` → «Читаю структуру»,
  и т.д. для 19 MCP-tools + aux MCP + internal tools. Раньше snake_case
  светился в UI — нарушение принципа CLAUDE.md «аналитик НЕ знает про
  get_metadata/execute_query — это работа LLM».

### Stability

- **W1.7** `useChatStream` теперь использует `AbortController`. При unmount/
  навигации SSE-стрим корректно отменяется (раньше async generator
  продолжал setState на размонтированном компоненте — утечка памяти и
  spurious re-renders).
- **W1.5** Verified: `LLMClient.aclose()` корректно вызывается в inner
  try/finally `loop.py:704`. Утечка httpx на `GeneratorExit` — false
  positive аудита (защита уже была).

### Honesty

- **W1.9** STATE.md обновлён: M6 Sprint 3 Self-Learning теперь явно помечен
  как «code-only complete, runtime НЕ wired». 27 stub/TODO маркеров в
  `learning/*`. Wire-up — следующий milestone (W1.8 отложен в отдельную
  сессию).

### Honesty: реальные метрики тестов

- Backend pytest: **689/696 passed** (раньше заявленные 652).
- Coverage: **26.58%** total (заявленный target 80% не достигнут).
  На критичных модулях: `loop.py` 11%, `persistence.py` 13%, `mcp_pool.py`
  15%, `cards.py` 28%. → Wave 2.6 — поднять до 60%.
- Frontend vitest: **323/323 passed** (43 файла). Раньше 304, +19 от
  W1.2/W1.3/W1.4/W1.6 + 6 от XSS-тестов W1.6.
- Playwright E2E: 5 spec'ов, **3 skipped** (`setup-and-prompt`, `sessions-
  history`, `channel-switch`). Главный happy-path (отправить сообщение
  → SSE → карточка) НЕ покрыт E2E. → Wave 2.5.

### Docs

- **W1.9** STATE.md → M7 Commerce Readiness + honesty gap.
- **W2.12** README: убрана ссылка на v1.0.0, актуальная latest. Раздел
  SmartScreen описывает code-signing план на v1.3.0+. Убрана фраза
  «получите через USB».
- `.planning/CHECKLIST-COMMERCE-2026-05-22.md` — 43-тикетная дорожная карта
  Wave 1-4 (от M7 до релиза v1.3.0).
- `.planning/BASELINE-2026-05-22.md` — baseline метрик на старте feature
  ветки.

### Технический долг (НЕ закрыт в этом релизе)

- **W1.8 Sprint 3 Hermes wire-up** — 6 часов работы, отложен в отдельную
  сессию: `background_review.py`, `skill_store.inject`, usage telemetry
  закомментированы в `loop.py:468/489/524/531`.
- **W2.1 Decompose loop.py** — God-функция 1157 строк. 10h рефакторинга
  до 4 функций по 200-300 строк перед M8.
- **W2.2 Multi-tenant isolation** — глобальные `INTERRUPTS`/`_pending`/
  `CLARIFY` per-session не per-channel.
- **W2.3 Code signing installer** — нужен EV сертификат + интеграция в
  electron-builder.yml.
- **W2.4 Auto-update** — electron-updater + GitHub Releases workflow.
- **W2.5 E2E coverage** — раскрытие 3 skipped spec'ов.
- **W2.6 Test coverage 60%** на критичных модулях.
- **W2.7 Robust prompt-injection** (llm-guard/rebuff вместо regex).

---

## [1.2.17] — 2026-05-22 (последний релиз main)

### Fixed

- DB migration v8: очистка битого '?1' channel_id из старых сессий.
- Light theme: точечный аудит контраста после Stencil/Mono brand.

## [1.2.16] — 2026-05-21

### Fixed

- Sessions: fallback на рабочий channel при битом channel_id.

## [1.2.15] — 2026-05-20

### Added

- BSL справочник из коробки: auto-detect + bundled JRE/JAR в Electron.

## [1.2.14] — 2026-05-19

### Fixed

- Timezone: `parseBackendDate` форсирует UTC для timezone-naive строк.

## [1.2.13] — 2026-05-18

### Added

- Файловые логи backend + кнопка «Открыть папку» + cleanup.

## [1.2.12] — 2026-05-17

### Fixed

- Chat empty-state, ошибки создания сессии, реактивный sidebar.

## [1.2.11] — 2026-05-16

### Fixed

- Обход системного прокси для локальных MCP-подключений.

## [1.2.3] — 2026-05-15

### Added

- Electron: зашитый MiMo ключ в `resources/.env` (для пилот-флоу).

## [1.2.2] — 2026-05-19

M5 Phase 11 финал — Stencil/Mono brand:
- Signal `#FF6A3D` как единственный accent.
- IBM Plex Mono 700 в лого, JetBrains Mono в meta.
- Dark (Ink) + Light (Sand) темы через `data-theme`.

## [1.2.0] — 2026-05-13

M5 Phase 11 — design v2 import (273/273 vitest):
- 12 новых atomic components.
- Onboarding 3→4 шага с Learn opt-in.
- Animation tokens (7 keyframes).
- Privacy reset endpoint.

## [1.1.0] — 2026-05-16

M5 Phase 7 — Desktop Installer (Electron + PyInstaller, 105.9 MB).

## [1.0.0] — 2026-05-13

MVP — M4 Demo & Refine завершён. 6 типов inline-карточек, история сессий,
channel selector, anonymization toggle, trace tool calls.

---

## Соглашения

- **Added** — новая функциональность.
- **Changed** — изменения существующего поведения.
- **Deprecated** — будет удалено в будущей версии.
- **Removed** — удалено.
- **Fixed** — исправления багов.
- **Security** — уязвимости.
- **Performance** — оптимизации без изменения API.
