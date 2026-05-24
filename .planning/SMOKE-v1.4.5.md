# Smoke checklist v1.4.5 — чистая Win11 VM

**Зачем:** P4.1 из COMMERCE-PLAN-2026-05-23 — финальная ручная верификация перед публикацией GitHub Release v1.4.5 (catch-up tag после промежуточных v1.3.0 → v1.4.4 без отдельных тегов).

**Когда запускать:** перед `git tag v1.4.5 && git push --tags`.

**Где запускать:** чистая Windows 11 VM без установленного Python / Node / .NET / 1С / VS Code — имитация компьютера аналитика-клиента.

**Артефакт:** `1C-Analyst-v1.4.5/analyst-setup-v1.4.5.exe` (~183 МБ, NSIS installer, **unsigned** — по решению пользователя 2026-05-24).

**Pre-flight в коде (Block A из RELEASE_v1.4.5_CHECKLIST):**

- ✅ A1 FINDING-00/06 backend version — `backend/app/config.py:216` + `backend/pyproject.toml:9` + `frontend/lib/version.ts` + `desktop/package.json` все на 1.4.5
- ✅ A2 FINDING-05 Status model label — `frontend/app/status/page.tsx:987-1023` использует `resolveProviderAndModel()`
- ✅ A3 FINDING-14 NVIDIA NIM — закрыт как RESOLVED в `qa-prod-release-2026-05-24/FINDINGS.md`
- ✅ B Quality gate — tsc 0 errors, ruff 7 known E501, health pytest 3/3, `app_version=1.4.5` verified

---

## Sec 1 · Установка (5 минут)

- [ ] **1.1** Скопировать `analyst-setup-v1.4.5.exe` на VM (любая папка)
- [ ] **1.2** Запустить exe. SmartScreen предупредит «неизвестный издатель» → **Подробнее → Выполнить в любом случае**. Это known issue (unsigned по решению — будет закрыто в одной из следующих версий после EV/OV cert).
- [ ] **1.3** Wizard → принять путь по умолчанию `C:\Program Files\1C-Analyst` → Install.
- [ ] **1.4** Finish. На рабочем столе появилась иконка «1С Аналитик» (squircle + Plex Mono «А»).
- [ ] **1.5** Запустить через ярлык. Электрон-окно открывается за ≤ 8 секунд.

**Ожидаемо:** одно окно, тёмная тема, brand Stencil orange. Backend на :8010, frontend на :3010 (порты внутри Electron). **FINDING-17 verify:** **java.exe НЕ открывает консольное окно** при работе чата.

**Если падает:** проверить `%APPDATA%/1C Analyst/logs/main.log` — обычно missing VC++ Redistributable.

---

## Sec 2 · Базовая работоспособность UI (5 минут)

- [ ] **2.1** Header: логотип «АНАЛИТИК / 1.4.5» (Plex Mono 700, orange signal-marker)
- [ ] **2.2** Channel selector — пусто (нет настроенных каналов)
- [ ] **2.3** Onboarding 4 шага запустился автоматически:
  - Step 1: «Зачем нужен Аналитик»
  - Step 2: «Подключите 1С базу» (channel настройка)
  - Step 3: «LLM провайдер» (NVIDIA NIM по умолчанию, badge «За рубежом ⚠»)
  - Step 4: «Готово» + opt-in «Память» (Sprint-04 Step 4.8)
- [ ] **2.4** «Пропустить» работает. Возврат — Settings → Onboarding.
- [ ] **2.5** Theme toggle (Header) переключает Dark/Light → читаемо, brand цвета сохраняются.
- [ ] **2.6** Sidebar collapse (M07): кнопка свернуть → 260 ↔ 56px с persistence (refresh сохраняет состояние).

**Ожидаемо:** никаких ошибок в консоли DevTools (Ctrl+Shift+I).

---

## Sec 3 · Подключение к 1С Toolkit (10 минут)

**Требует:** запущенный 1С Toolkit EPF v1.7.0 на той же VM или сетевом хосте.

- [ ] **3.1** Settings → Connections → «Добавить канал»
- [ ] **3.2** Имя: `Smoke-test`. Endpoint: `http://localhost:6010/mcp` (либо ваш IP).
- [ ] **3.3** Тест соединения → зелёный «✓ MCP отвечает». Если красный → проверить что Toolkit EPF запущен на :6010.
- [ ] **3.4** Сохранить. В Channel selector появляется `Smoke-test`. Выбрать.

---

## Sec 4 · Settings → LLM + Status card (3 минуты)

- [ ] **4.1** Settings → LLM. По умолчанию выбран **NVIDIA NIM**, модель **DeepSeek V4 Flash** (`deepseek-ai/deepseek-v4-flash`).
- [ ] **4.2** Compliance badge показан: **«За рубежом ⚠»** (NVIDIA — США-ДЦ).
- [ ] **4.3** Переключить на **Cloud.ru Foundation Models** → badge меняется на **«РФ-ДЦ ✓ 152-ФЗ»**.
- [ ] **4.4** Модель Cloud.ru = `Qwen3-Coder-480B` доступна. Введите тестовый ключ (можно фейковый — проверка только UI).
- [ ] **4.5** Сохранить. В Header под именем профайла теперь индикатор «Cloud.ru · Qwen3-Coder».
- [ ] **4.6** Открыть DevTools → Application → Local Storage → проверить **что API-ключа НЕТ в `localStorage`** (P2.1 backend-only).
- [ ] **4.7** **FINDING-05 verify:** перейти на `/status` → карточка «Модель ИИ» показывает **«DeepSeek V4 Flash · 0.3»** (label), НЕ `deepseek-ai/deepsee…` (raw id обрезан).
- [ ] **4.8** **FINDING-00/06 verify:** на `/status` карточка «Серверная часть» показывает **«v1.4.5»**, НЕ `v1.3.0`. Также `curl http://localhost:8010/health` → `{"version":"1.4.5"}`.

**Ожидаемо:** ключ ушёл в backend. SQLite таблица `user_secrets` содержит зашифрованную запись (можно проверить через `sqlite3 %APPDATA%/1C Analyst/app.db ".schema user_secrets"`).

---

## Sec 5 · Основной workflow + FINDING-10/11/12 verify (15 минут)

**Поставьте реальный ключ Cloud.ru или NVIDIA для этих шагов.**

- [ ] **5.1** **FINDING-12 verify (главная страница):** на главной странице `/` (не открытая сессия!) ввести «Привет» → отправить → должно начать стримить ответ. **НЕ должен** появиться toast «Введите API ключ в разделе Настройки». Это был P0 release-blocker до v1.4.3.

- [ ] **5.2** Чат: «Покажи список справочников в базе»
  - SSE стримит: «Анализирую → Вызываю `get_metadata` → Формирую ответ»
  - Возвращает список (Object card или table)
  - Tool trace свёрнут, разворачивается по клику

- [ ] **5.3** Чат: «Покажи 10 последних документов реализации»
  - Стрим. Tool call `execute_query`. Результат — table card с 10 строками
  - В правом нижнем — кнопка «📋 Скопировать» работает

- [ ] **5.4** **FINDING-10/11 verify (ModelBadge popover):** клик на chip «DEEPSEEK V4 FLASH · 0.3» в header → popover открыт → клик на «GLM-5.1» (или другую модель) → модель РЕАЛЬНО переключается, `curl /llm-config` отдаёт новое значение. CORS на PATCH работает (нет 400 в DevTools Network).

- [ ] **5.5** Чат: «Покажи ВСЕ документы реализации за последний год»
  - **Это тест ResultSizeGate (P2.2):**
  - Если результат > 500 строк — баннер **«Показаны первые 500 из N»** (orange)
  - LLM получила только 500 → не упала, ответила «слишком много, сузим фильтр»
  - UI не виснет, table card scrollable

- [ ] **5.6** Чат: «DELETE FROM Reference.Counterparties»
  - **Это тест SQL AST validator (P2.3):**
  - LLM сгенерирует код → `execute_query` или `execute_code`
  - Backend AST блокирует на уровне валидатора → пользователю сообщение «Запрос содержит изменяющую операцию (DELETE). Запрещено.»
  - В Tool trace видна `validate_query.status = blocked`

- [ ] **5.7** Чат любой простой → пользователь видит **SSE статусы анимируются** в реальном времени (Analyzing → Tool call → Response). Не «всё сразу скакнуло».

- [ ] **5.8** **Cancel test:** длинный запрос → нажать «Stop» (AbortController) → стрим обрывается в течение 500ms. Tool trace показывает «отменено». Backend не висит.

- [ ] **5.9** **FINDING-14 verify (NVIDIA NIM):** в чате с NVIDIA NIM endpoint отправить любое сообщение → ответ приходит без `llm_invalid_key`. Если 401 вернётся — ротировать ключ через https://build.nvidia.com/ → My Account → API Keys.

---

## Sec 6 · Sprint 3 Hermes Learning (5 минут)

**Проверяет что W1.8 Hermes wire-up работает в runtime.**

- [ ] **6.1** Settings → Skills (sidebar). Список пустой (свежая база) ИЛИ один-два авто-сгенерированных скилла.
- [ ] **6.2** Сделать 3-4 запроса подряд в чате с похожей структурой (например, разные «Покажи N документов вида X»).
- [ ] **6.3** Подождать 30 секунд после последнего ответа.
- [ ] **6.4** Settings → Skills → должны появиться 1-2 новых auto-discovered skills с описанием паттерна. Это `schedule_review()` сработал.
- [ ] **6.5** Открыть один skill → видны usage count + краткое описание паттерна.
- [ ] **6.6** Settings → Memory → MEMORY.md и USER.md редакторы открываются, сохранение работает.
- [ ] **6.7** `/insights` → 6 KPI cards отображаются (turns, latency p50/p95, top tools, top channels, cost USD, ошибки).

**Если skills не появились:** проверить `%APPDATA%/1C Analyst/data/skills/<channel-id>/` — должны быть `.md` файлы.

---

## Sec 7 · Auto-update (P1.4) — manual probe

**Полный тест требует второй версии в GitHub Release. На smoke просто проверяем что инфраструктура поднимается.**

- [ ] **7.1** Открыть DevTools → Console → проверить что нет ошибок типа «Failed to check for updates».
- [ ] **7.2** (Если в GitHub Releases уже есть более новая версия) — ждать 30 секунд → должен появиться **UpdateBanner** в Header («Готова vX.Y.Z → Перезапустить»).
- [ ] **7.3** (Если нет более новой версии) — просто убедиться что код auto-updater не падает в фоне.

---

## Sec 8 · Производительность + Sprint-04 motion polish (5 минут)

- [ ] **8.1** Открыть 5 каналов подряд (если есть тестовые базы). Нет фриза > 1 секунды.
- [ ] **8.2** History sessions → открыть сессию с 50+ сообщениями. Прокрутка плавная.
- [ ] **8.3** Запустить heavy `execute_query` дважды подряд (одинаковый) → второй раз — SQLite cache PRAGMA tuning должен дать ~20% быстрее.
- [ ] **8.4** Закрыть Electron → backend останавливается (нет zombie `backend.exe` в `tasklist`). Также **java.exe** (1С Toolkit) не оставляет консольных окон (FINDING-17 verify).
- [ ] **8.5** **M03 Sparkline:** на dashboard или metric card — линия рисуется один раз при mount (draw-in анимация).
- [ ] **8.6** **M09 UndoToast:** любое отменяемое действие → toast slide-in/out + progress-bar.
- [ ] **8.7** **Sprint 3.2 ComposerHub:** на главной странице — welcome композер с quick-starts шаблонами.

---

## Sec 9 · Финальная чистота (3 минуты)

- [ ] **9.1** Uninstall через **Программы и компоненты → 1С Аналитик → Удалить**.
- [ ] **9.2** Папка `C:\Program Files\1C-Analyst` удалена.
- [ ] **9.3** `%APPDATA%/1C Analyst/` — **остаётся** (пользовательские данные, должен спросить «удалить?»).
- [ ] **9.4** Установить снова — миграция БД отрабатывает без ошибок, старая история сессий доступна.

---

## Финальный вердикт

- **PASS:** все 9 секций ✓, никаких regressions vs v1.2.2 (последний git tag).
- **PASS с тех.долгом:** 1-2 минорные проблемы, не блокируют первый пилот — записать в `.planning/POST-RELEASE-DEBT.md`.
- **FAIL:** ≥ 1 проблема в Sec 3/4/5 → не релизим, фиксим, повторяем smoke.

**После PASS:**

```bash
cd C:\CLOUDE_PR\projects\analyst-workspace-design

# 1. Atomic commit фиксов из Block A (если ещё не закоммичены)
git add backend/pyproject.toml .planning/qa-prod-release-2026-05-24/FINDINGS.md \
        .planning/SMOKE-v1.4.5.md .planning/RELEASE_v1.4.5_CHECKLIST.md \
        .planning/RELEASE-NOTES-v1.4.5.md docs/strategic-research/PLAN_2026-05-24.md
git commit -m "release(v1.4.5): backend pyproject version sync (FINDING-00) + smoke checklist + release notes"

# 2. Catch-up tag (один прыжок с v1.2.2 на v1.4.5)
git tag -a v1.4.5 -m "v1.4.5 — first commerce-ready release (M7 partial close)"
git push origin feature/v1.3.0-commerce v1.4.5

# 3. GitHub Release
gh release create v1.4.5 \
  --title "v1.4.5 — Commerce-Ready Release" \
  --notes-file .planning/RELEASE-NOTES-v1.4.5.md \
  ./1C-Analyst-v1.4.5/analyst-setup-v1.4.5.exe
```

---

## Known issues v1.4.5 (записать в Release notes — уже в RELEASE-NOTES-v1.4.5.md)

1. **SmartScreen warning при первом запуске** — installer unsigned (по решению пользователя 2026-05-24, для экономии 300$ EV cert до первого пилота). Workaround в release notes: «Подробнее → Выполнить в любом случае».
2. **`loop.py` 689 строк** — TD-1 декомпозиция в фокус-сессии после release. Цель ≤400 строк.
3. **Backend ruff: 7 E501** в SYSTEM_PROMPT строках — TD-5 known, не функциональный issue.
4. **Catch-up tag** — между v1.2.2 и v1.4.5 пять промежуточных версий без отдельных тегов: v1.3.0/v1.4.0/v1.4.1/v1.4.2/v1.4.4. Все включены в release notes как «5 QA pre-prod итераций».
