# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат — [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/), версионирование — [SemVer](https://semver.org/lang/ru/).

## [Unreleased] — feature/v1.3.0-commerce

M7 Commerce Readiness — переход от пилот-готового beta к коммерчески
распространяемой версии. Wave 1 закрывает CRITICAL уязвимости, Wave 2-3
готовят к публичному релизу.

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
