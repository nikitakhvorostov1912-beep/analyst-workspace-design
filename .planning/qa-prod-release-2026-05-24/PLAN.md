# QA Pre-Production Test Plan — 1С Аналитик v1.4.1

> **Дата:** 2026-05-24
> **Релиз:** v1.4.1 (после bump 1.3.0 → 1.4.0 → 1.4.1)
> **Окружение:** Electron 33 + Next.js 15 + FastAPI + SQLite + NVIDIA NIM + MCP Streamable HTTP
> **Цель:** проверить готовность к prod-выпуску — пройти все сценарии аналитика 1С от первого запуска до ежедневного использования.

---

## 0. Методология (research summary)

### Источники
1. [Testomat — Web App Testing Checklist 2026](https://testomat.io/blog/complete-web-application-testing-checklist/) — 100+ пунктов по 6 категориям, base reference
2. [Next.js Production Checklist](https://nextjs.org/docs/app/guides/production-checklist) — performance, security, observability
3. [Gatling — Load testing LLM API](https://gatling.io/blog/load-testing-an-llm-api) — 429/503/timeout scenarios, streaming
4. [Electron Production Checklist (forasoft)](https://www.forasoft.com/blog/article/electron-desktop-app-development-guide-for-business) — pre-release smoke + security
5. [Steve Kinney — Playwright vs Chrome DevTools MCP](https://stevekinney.com/writing/driving-vs-debugging-the-browser) — когда что использовать
6. [Mozilla QA/Test Plan Template](https://wiki.mozilla.org/QA/Test_Plan_Template) — структура IEEE 829-style
7. [BugHerd — Website QA Testing 2026](https://bugherd.com/blog/website-qa-testing-complete-guide-to-quality-assurance) — UAT методология
8. [Marker.io — Website Test Plan Template](https://marker.io/blog/test-plan-template) — primary deliverables
9. [ApiDog — SSE LLM streaming](https://apidog.com/blog/stream-llm-responses-using-sse/) — fragmentation patterns
10. [Test-Lab — Chrome DevTools MCP vs Playwright MCP](https://www.test-lab.ai/blog/chrome-devtools-mcp-vs-playwright-mcp-cli) — runtime tools choice

### Best practices по фазам
- **Smoke** (10 мин) — основные пути живы: запуск → главный экран → один полный chat → close
- **Functional** (1-2 ч) — все features работают как описано
- **Edge cases** (1-2 ч) — пустые состояния, ошибки сети, длинные тексты, спецсимволы
- **Performance** — TTI < 3 сек, memory не растёт > 200 МБ в long-session
- **Security** — XSS in chat input, CSP, нет API key в DevTools / Network / localStorage
- **UAT** — реальный аналитик задаёт реальные вопросы реальной 1С базе

### Tooling decision
| Случай | Инструмент |
|---|---|
| Бо́льшая часть прогона | **Claude in Chrome MCP** (текущая сессия, manual exploration, видит logged-in state) |
| Финальный regression | Playwright (если будет CI) — позже, не в этой сессии |
| Performance deep-dive | Chrome DevTools (вручную, F12) |

В этом прогоне — **Claude in Chrome MCP** (быстро, без CI setup, документирует findings).

---

## 1. Test scope

### In scope
- Web UI на `http://localhost:3010` (dev mode + prod build)
- Backend API на `http://localhost:8010`
- MCP integration (если есть запущенный MCP Toolkit на :6010 — иначе ограничиваемся mock'ами)
- LLM NVIDIA NIM (с env-ключом из `embedded.env`)
- Full user journey: первый запуск → onboarding → создание сессии → чат → trace → удаление → новая сессия

### Out of scope (этот прогон)
- Electron installer на чистой Win11 VM (требует отдельную VM)
- 1С реальные базы (требует доступ к боевому контуру)
- Light theme (отдельно — после dark прогона)
- Cross-browser (только Chrome — Electron WebView2 = Chromium)
- Локализация (только русский)

---

## 2. Test scenarios — 60+ кейсов

### Категории

| Cat | Описание | Сценариев |
|---|---|---|
| **SMOKE** | Базовая жизнеспособность | 6 |
| **ONBOARD** | Первый запуск, wizard | 8 |
| **CHAT** | Создание сессии, отправка, стриминг | 10 |
| **CONN** | Подключения 1С (CRUD + ping) | 7 |
| **LLM** | Модель ИИ (CRUD, тест, переключение) | 8 |
| **SESSION** | Управление сессиями (list, delete, undo, navigate) | 6 |
| **TRACE** | Tool trace (TraceSummary + JSON) | 4 |
| **SETTINGS** | Настройки + Memory + Insights + Skills | 5 |
| **STATUS** | Diagnostics page | 3 |
| **NAV** | Header, sidebar, navigation, theme | 5 |
| **ERROR** | Backend down, MCP down, LLM 401/429 | 5 |
| **A11Y** | Keyboard, focus-ring, aria | 4 |
| **SEC** | XSS, CSP, API key leaks | 3 |

### Severity
- **P0** — release-blocker (приложение неюзабельно если падает)
- **P1** — high (есть workaround, но ломает основной flow)
- **P2** — medium (косметика, edge case)
- **P3** — nice-to-have

---

### SMOKE (6 сценариев)

**SMOKE-01 (P0)** — Frontend поднимается на :3010.
- Шаги: `curl http://localhost:3010` → ожидаемо 200
- Expected: HTML response, заголовок «1С Аналитик»

**SMOKE-02 (P0)** — Backend health endpoint.
- Шаги: `curl http://localhost:8010/health` → 200 JSON
- Expected: `{version, db: "ok"}`

**SMOKE-03 (P0)** — Главная страница рендерится без crash.
- Шаги: открыть http://localhost:3010 в Chrome → дождаться React mount
- Expected: видны Header + Sidebar + ComposerHub или Empty state

**SMOKE-04 (P0)** — Settings страница доступна.
- Шаги: GET /settings → 200, видна форма «Базы 1С» + «Модель ИИ» + «Дополнительно»
- Expected: 3 секции, унифицированный padding

**SMOKE-05 (P0)** — Status страница доступна.
- Шаги: GET /status → 200, видны 3 high-level cards
- Expected: «Базы 1С / Модель ИИ / Серверная часть» + details collapsible

**SMOKE-06 (P1)** — No console errors на главной.
- Шаги: открыть `/`, ждать 5 сек, DevTools console
- Expected: 0 ошибок «Uncaught», 0 ошибок 4xx/5xx в Network

---

### ONBOARD (8 сценариев) — первый запуск

**ONBOARD-01 (P0)** — Onboarding появляется при первом запуске.
- Pre: `localStorage.clear()`, очистить SQLite (`/admin/cleanup`)
- Шаги: открыть /
- Expected: модал OnboardingDialog шаг 1 «Подключите вашу базу 1С»

**ONBOARD-02 (P1)** — Persist прогресса.
- Шаги: дойти до шага 2, F5
- Expected: открывается на шаге 2, не сбрасывается

**ONBOARD-03 (P0)** — Skip с шага 1 закрывает onboarding.
- Шаги: «Пропустить»
- Expected: модал закрылся, видна welcome screen (даже без конфига)

**ONBOARD-04 (P0)** — Создание Embedded подключения.
- Шаги: заполнить «Моя база» → host=localhost port=6010 → Сохранить
- Expected: подключение создано, ping выполнен (если 6010 живой → ✓, иначе ошибка)

**ONBOARD-05 (P1)** — Создание Proxy подключения через Advanced.
- Шаги: открыть «Расширенные настройки» → kind=proxy → ввести proxyBase + channel
- Expected: endpoint собирается корректно

**ONBOARD-06 (P0)** — Кнопка «Далее» disabled пока нет успешного ping.
- Шаги: ввести битый адрес → нажать Сохранить
- Expected: Далее всё ещё disabled, есть error toast

**ONBOARD-07 (P1)** — LLM шаг с дефолтной NVIDIA моделью.
- Шаги: выбрать DeepSeek V4 Flash → Test → Сохранить
- Expected: 200 ok, чип success рядом с кнопкой

**ONBOARD-08 (P1)** — Quick-start вопрос на step 4 создаёт сессию.
- Шаги: на step 4 кликнуть «Расскажи про базу — какая конфигурация и сколько объектов»
- Expected: сессия создана + auto-send происходит + redirect на /sessions/{id}

---

### CHAT (10 сценариев)

**CHAT-01 (P0)** — ComposerHub отображается на главной.
- Pre: hasConfig=true, нет активной сессии
- Шаги: открыть /
- Expected: eyebrow «БАЗА 1С · {имя}», title «О чём спросим базу?», composer, 6 chips шаблонов

**CHAT-02 (P0)** — Отправка сообщения из welcome composer.
- Шаги: написать «привет», нажать Enter
- Expected: создаётся сессия, redirect /sessions/{id}, сообщение появляется в thread, начинается стриминг

**CHAT-03 (P0)** — SSE streaming показывает stages.
- Pre: открыта сессия, отправлено сообщение
- Expected: видны streaming stages «Анализирую → Вызываю → Формирую», stagger animation, в конце assistant message

**CHAT-04 (P1)** — Click на template chip заполняет composer.
- Шаги: на welcome → клик «Найти контрагента по ИНН»
- Expected: text вставлен в textarea, courier в конце, можно дописать ИНН

**CHAT-05 (P0)** — Длинное сообщение (>4000 chars) обрезается / показывает counter.
- Шаги: вставить 5000 символов
- Expected: counter 5000/4000 красным или textarea обрезает

**CHAT-06 (P1)** — Спецсимволы в input (HTML, кавычки, emoji).
- Шаги: `<script>alert('xss')</script> "тест" 🚀`
- Expected: НЕ выполняется JS, экранируется в message bubble

**CHAT-07 (P1)** — Markdown в assistant message.
- Шаги: вернётся ответ с **bold**, `code`, lists
- Expected: рендерится правильно

**CHAT-08 (P1)** — Inline cards (table/object/log) рендерятся.
- Шаги: запрос «Покажи 5 контрагентов» → возврат с table card
- Expected: TableCard виден, virtual scroll работает для > 100 rows

**CHAT-09 (P1)** — Кнопка Stop прерывает streaming.
- Шаги: задать долгий запрос → click Stop
- Expected: streaming останавливается, частичный ответ сохраняется

**CHAT-10 (P0)** — Send button spring press (M04).
- Шаги: клик Send
- Expected: scale 1 → 0.94 → 1.04 → 1 за 240ms, message появляется с fade-up

---

### CONN (7 сценариев) — подключения 1С

**CONN-01 (P0)** — Settings → Базы 1С → видны подключения.
- Expected: список подключений в одной карточке p-5 rounded-lg

**CONN-02 (P1)** — Edit подключения сохраняет изменения.
- Шаги: «Изменить» → поменять name → Сохранить
- Expected: name обновился в списке, в header ChannelSelector тоже

**CONN-03 (P0)** — Удаление подключения.
- Шаги: «Удалить» → confirm dialog → Подтвердить
- Expected: подключение удалено, если оно было активным — auto-select следующего

**CONN-04 (P1)** — Тест подключения LiveTestResult chip.
- Шаги: «Тест»
- Expected: чип «Проверяю...» → «Готово · {ms} мс · {N} инструментов» либо «Не удалось»

**CONN-05 (P0)** — Channel selector в header показывает enriched info.
- Шаги: click ChannelSelector
- Expected: dropdown с config_type chip, мета-строкой «N объектов · N инструментов · обновлено N мин назад»

**CONN-06 (P0)** — Переключение активного канала.
- Шаги: клик на другую базу в dropdown
- Expected: ChannelSelector trigger обновляется, dispatchEvent `active-channel-changed`, header chips перечитываются

**CONN-07 (P1)** — Offline база показывает «↻ Перепроверить».
- Pre: добавить подключение с битым URL
- Expected: в dropdown красная точка + строка «ОФЛАЙН · последняя связь N назад», hover → кнопка retry

---

### LLM (8 сценариев)

**LLM-01 (P0)** — Все 9 NVIDIA моделей доступны в каталоге.
- Шаги: Settings → Модель ИИ → раскрыть Select
- Expected: видны DeepSeek V4 Flash/Pro, GLM-5.1, Qwen3 Coder Plus/480B, MiniMax M2.7, Nemotron 3, Llama 4 Scout, Mistral Large 3

**LLM-02 (P0)** — Сохранение NVIDIA модели без локального ключа.
- Pre: clear localStorage `llm_api_key`
- Шаги: выбрать DeepSeek V4 Flash → Сохранить
- Expected: сохраняется без ошибки (env-key используется), `clearLLMApiKey()` вызван если был storedKey

**LLM-03 (P0)** — ModelBadge в header обновляется после save.
- Шаги: в Settings сменить модель → Сохранить → не перезагружая страницу глянуть header
- Expected: ModelBadge показывает новую модель (event `llm-config-updated`)

**LLM-04 (P0)** — Переключение модели через ModelBadge popover.
- Шаги: click ModelBadge → выбрать другую модель
- Expected: модель меняется через PATCH /llm-config, toast «Модель переключена», badge обновляется

**LLM-05 (P0)** — Чат использует актуальную модель.
- Шаги: сменить модель → создать новую сессию → отправить сообщение
- Expected: backend log показывает новую модель, ответ приходит

**LLM-06 (P1)** — Тест LLM показывает inline result.
- Шаги: Settings → Тест
- Expected: LiveTestResult чип «Готово · N мс · {model name}»

**LLM-07 (P1)** — Удаление LLM config через AlertDialog.
- Шаги: Удалить → подтвердить
- Expected: config удалён, localStorage очищен, toast

**LLM-08 (P0)** — Cloud.ru — provider с compliance badge.
- Шаги: открыть Select → найти Cloud.ru Foundation Models
- Expected: chip «РФ-ДЦ» / «152-ФЗ» рядом с provider label

---

### SESSION (6 сценариев)

**SESSION-01 (P0)** — Список сессий в Sidebar группируется.
- Pre: создать 3+ сессии за разные дни (если есть)
- Expected: видны группы «СЕГОДНЯ — N», «ВЧЕРА — N», «НА ЭТОЙ НЕДЕЛЕ»

**SESSION-02 (P0)** — Удаление через UndoToast (НЕ confirm).
- Шаги: hover на session → click trash icon
- Expected: сессия исчезает мгновенно, внизу появляется UndoToast «Чат удалён · #XXXX · ↺ Отменить · progress bar», через 5 сек реальный DELETE

**SESSION-03 (P1)** — Click «↺ Отменить» возвращает сессию.
- Шаги: удалить → нажать Отменить в течение 5 сек
- Expected: сессия возвращается в sidebar, DELETE не делается

**SESSION-04 (P1)** — Hover на UndoToast пауза progress.
- Шаги: удалить → hover на toast
- Expected: progress bar animation-play-state paused, через 5 сек НЕ commit (если hover держится)

**SESSION-05 (P0)** — Открытие сессии загружает сообщения.
- Шаги: click на session → загрузка
- Expected: messages thread заполнен, исторический контекст виден

**SESSION-06 (P1)** — Sidebar collapse 260 → 56px.
- Шаги: click toggle button
- Expected: ширина анимируется, content fade-out, button «↻» виден

---

### TRACE (4 сценария)

**TRACE-01 (P0)** — Trace отображается под assistant message.
- Pre: сообщение с tool_calls > 0
- Expected: «N инструментов · {duration}», по клику раскрывается

**TRACE-02 (P0)** — TraceSummary показывает human-readable заголовки.
- Шаги: раскрыть trace
- Expected: «01 Запрос к 1С — «...» · ✓ 24 записи · 380 мс», не raw JSON

**TRACE-03 (P1)** — Click «JSON» раскрывает raw view.
- Шаги: на шаге → click «JSON»
- Expected: видны «Параметры» + «Результат» с JsonTree, цвета по syntax tokens

**TRACE-04 (P1)** — Кнопка curl в JSON-блоке копирует команду.
- Шаги: «JSON» → click «curl»
- Expected: clipboard содержит `curl -X POST ...`, toast «Скопировано»

---

### SETTINGS (5 сценариев)

**SETTINGS-01 (P0)** — Унифицированные секции (HIGH-3).
- Шаги: Settings page
- Expected: все главные блоки rounded-lg border-bd-2 bg-bg-1 p-5, single visual layer

**SETTINGS-02 (P0)** — Секция «Дополнительно» grid 3-col.
- Шаги: Settings → scroll вниз
- Expected: eyebrow «ДОПОЛНИТЕЛЬНО», 3 карточки Memory / Insights / Skills

**SETTINGS-03 (P1)** — Skeleton при loading.
- Pre: backend медленный или offline
- Шаги: открыть Settings
- Expected: skeleton shimmer вместо «Загрузка...»

**SETTINGS-04 (P1)** — Memory page (Постоянная память).
- Шаги: click «Постоянная память» card
- Expected: открывается /settings/memory, видны заметки если есть

**SETTINGS-05 (P1)** — Insights page (Аналитика).
- Шаги: click «Аналитика»
- Expected: открывается /insights, sparkline charts, sessions/tools/errors metrics

---

### STATUS (3 сценария)

**STATUS-01 (P0)** — High-level cards 3-col.
- Шаги: открыть /status
- Expected: 3 carved-out cards: «Базы 1С — N из M», «Модель ИИ — {model}», «Серверная часть — v1.4.1»

**STATUS-02 (P1)** — Technical details раскрываются.
- Шаги: click «> Технические подробности»
- Expected: раскрывается CheckRow + EnvSection + LogSection

**STATUS-03 (P1)** — Перепроверить обновляет все checks.
- Шаги: click «Обновить»
- Expected: skeleton → новые данные, иконка спин

---

### NAV (5 сценариев)

**NAV-01 (P0)** — Header sticky на всех страницах.
- Шаги: scroll вниз на /sessions/{id}
- Expected: header остаётся видимым

**NAV-02 (P1)** — Theme toggle переключает dark/light.
- Шаги: click theme toggle
- Expected: html data-theme="light", цвета меняются, persist в localStorage

**NAV-03 (P1)** — Page enter animation (M08).
- Шаги: navigate /settings → /status → /
- Expected: main контент с fade-up каждый раз

**NAV-04 (P1)** — Cmd+K открывает CommandPalette.
- Шаги: press Ctrl+K
- Expected: модал поиска открывается

**NAV-05 (P2)** — Иконки в header → /status, /guide, /about, /settings.
- Шаги: hover каждую
- Expected: title tooltip, click → navigate

---

### ERROR (5 сценариев)

**ERROR-01 (P0)** — Backend недоступен — BackendDownBanner.
- Pre: kill backend
- Шаги: F5
- Expected: top-banner «Серверная часть не отвечает», retry button + Диагностика →

**ERROR-02 (P0)** — Retry в BackendDownBanner.
- Шаги: с банером → click «Повторить» → запустить backend
- Expected: banner исчезает после успешного health

**ERROR-03 (P1)** — MCP недоступен — ConnectionStatusBanner.
- Pre: подключение есть, ping failing
- Expected: в чате видна ошибка соединения с MCP

**ERROR-04 (P0)** — LLM 401 (битый ключ).
- Pre: подставить битый api_key в localStorage
- Шаги: отправить сообщение
- Expected: error message «LLM не настроен» или translation 401

**ERROR-05 (P1)** — Network timeout / abort.
- Шаги: при streaming прервать сетку
- Expected: graceful error, нет crash

---

### A11Y (4 сценария)

**A11Y-01 (P1)** — Tab navigation проходит по всем интерактивным.
- Шаги: Tab от верха страницы
- Expected: focus-ring 2px accent + offset виден везде

**A11Y-02 (P1)** — Enter activates focused button.
- Шаги: Tab до Send → Enter
- Expected: submit triggers

**A11Y-03 (P2)** — aria-live на streaming stages.
- Шаги: inspect StreamingStages
- Expected: role=status aria-live=polite

**A11Y-04 (P2)** — aria-label / role на header chips.
- Expected: AnonymizationStatus role=status, ModelBadge button с aria-label

---

### SEC (3 сценария)

**SEC-01 (P0)** — XSS в chat input не выполняется.
- Шаги: отправить `<img src=x onerror=alert(1)>`
- Expected: не выполняется, экранируется в bubble

**SEC-02 (P0)** — API key НЕ виден в DOM / Network.
- Шаги: inspect localStorage / Network headers
- Expected: key либо в sessionStorage либо отсутствует (env-key)

**SEC-03 (P1)** — CSP headers в prod build.
- Шаги: production build → response headers
- Expected: Content-Security-Policy с strict directives (только в prod)

---

## 3. Definition of Done — Release Checklist

Перед merge в main / release:
- [ ] Все P0 сценарии — PASS
- [ ] P1 сценариев — PASS ≥90% (документировать любые ≤10% отложенные)
- [ ] vitest 320+/320+ green
- [ ] tsc --noEmit без ошибок
- [ ] next build clean
- [ ] electron-builder --win --x64 успешно собирает .exe
- [ ] Manual smoke на dev-сервере (Chrome) — ВЫПОЛНЕН и задокументирован
- [ ] Нет критических багов в FINDINGS.md без owner / ETA
- [ ] Release notes написаны (или TBD с placeholder)
- [ ] Bump версии в desktop/package.json
- [ ] Push в remote

---

## 4. Прогон — порядок и owner

| Этап | Длительность | Owner | Tools |
|---|---|---|---|
| SMOKE 01-06 | 5 мин | Claude в Chrome MCP | navigate + read_page + screenshot |
| ONBOARD 01-08 | 15 мин | Claude в Chrome MCP | + form_input |
| CHAT 01-10 | 20 мин | Claude в Chrome MCP | + computer (type, click) |
| CONN 01-07 | 10 мин | Claude в Chrome MCP | navigate |
| LLM 01-08 | 10 мин | Claude в Chrome MCP | navigate + form_input |
| Остальные | 30 мин | Claude в Chrome MCP | mix |
| Документирование FINDINGS | 10 мин | Claude | Write |

**Total: ~1.5 ч прогона + 10 мин отчёта.**

---

## 5. Где документируется

- **Этот файл** — plan (живой документ)
- `FINDINGS.md` — список найденных багов с severity / repro / screenshot path
- `RUN-LOG.md` — chronological log прогона (что и когда сделано)
- `SUMMARY.md` — итог: PASS/FAIL по каждой категории + recommendation для release
