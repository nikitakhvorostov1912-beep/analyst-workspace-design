# Smoke checklist v1.3.0 — чистая Win11 VM

**Зачем:** P4.1 из COMMERCE-PLAN-2026-05-23. Финальная ручная верификация перед публикацией GitHub Release.

**Когда запускать:** перед `git tag v1.3.0 && git push --tags`.

**Где запускать:** чистая Windows 11 VM без установленного Python / Node / .NET / 1С / VS Code — имитация компьютера аналитика-клиента.

**Артефакт:** `1C-Analyst-v1.3.0/analyst-setup-v1.3.0.exe` (187 МБ, NSIS installer, неподписанный пока без EV/OV cert).

---

## Sec 1 · Установка (5 минут)

- [ ] **1.1** Скопировать `analyst-setup-v1.3.0.exe` на VM (любая папка)
- [ ] **1.2** Запустить exe. SmartScreen предупредит «неизвестный издатель» → **Подробнее → Выполнить в любом случае**. Это known issue до P1.3 (EV/OV cert).
- [ ] **1.3** Wizard → принять путь по умолчанию `C:\Program Files\1C-Analyst` → Install.
- [ ] **1.4** Finish. На рабочем столе появилась иконка «1С Аналитик» (squircle + Plex Mono «А»).
- [ ] **1.5** Запустить через ярлык. Электрон-окно открывается за ≤ 8 секунд.

**Ожидаемо:** одно окно, тёмная тема, brand Stencil orange. Backend на :8010, frontend на :3010 (порты внутри Electron).

**Если падает:** проверить `%APPDATA%/1C Analyst/logs/main.log` — обычно missing VC++ Redistributable.

---

## Sec 2 · Базовая работоспособность UI (5 минут)

- [ ] **2.1** Header: логотип «АНАЛИТИК / 1.3.0» (Plex Mono 700, orange signal-marker)
- [ ] **2.2** Channel selector — пусто (нет настроенных каналов)
- [ ] **2.3** Onboarding 4 шага запустился автоматически:
  - Step 1: «Зачем нужен Аналитик»
  - Step 2: «Подключите 1С базу» (channel настройка)
  - Step 3: «LLM провайдер» (NVIDIA NIM по умолчанию, badge «За рубежом ⚠»)
  - Step 4: «Готово»
- [ ] **2.4** «Пропустить» работает. Возврат — Settings → Onboarding.
- [ ] **2.5** Theme toggle (Header) переключает Dark/Light → читаемо, brand цвета сохраняются.

**Ожидаемо:** никаких ошибок в консоли DevTools (Ctrl+Shift+I).

---

## Sec 3 · Подключение к 1С Toolkit (10 минут)

**Требует:** запущенный 1С Toolkit EPF v1.7.0 на той же VM или сетевом хосте.

- [ ] **3.1** Settings → Connections → «Добавить канал»
- [ ] **3.2** Имя: `Smoke-test`. Endpoint: `http://localhost:6010/mcp` (либо ваш IP).
- [ ] **3.3** Тест соединения → зелёный «✓ MCP отвечает». Если красный → проверить что Toolkit EPF запущен на :6010.
- [ ] **3.4** Сохранить. В Channel selector появляется `Smoke-test`. Выбрать.

---

## Sec 4 · Settings → LLM (3 минуты)

- [ ] **4.1** Settings → LLM. По умолчанию выбран **NVIDIA NIM**, модель **DeepSeek V4 Flash** (`deepseek-ai/deepseek-v4-flash`).
- [ ] **4.2** Compliance badge показан: **«За рубежом ⚠»** (NVIDIA — США-ДЦ).
- [ ] **4.3** Переключить на **Cloud.ru Foundation Models** → badge меняется на **«РФ-ДЦ ✓ 152-ФЗ»**.
- [ ] **4.4** Модель Cloud.ru = `Qwen3-Coder-480B` доступна. Введите тестовый ключ (можно фейковый — проверка только UI).
- [ ] **4.5** Сохранить. В Header под именем профайла теперь индикатор «Cloud.ru · Qwen3-Coder».
- [ ] **4.6** Открыть DevTools → Application → Local Storage → проверить **что API-ключа НЕТ в `localStorage`** (P2.1 backend-only).

**Ожидаемо:** ключ ушёл в backend. SQLite таблица `user_secrets` содержит зашифрованную запись (можно проверить через `sqlite3 %APPDATA%/1C Analyst/app.db ".schema user_secrets"`).

---

## Sec 5 · Основной workflow (15 минут)

**Поставьте реальный ключ Cloud.ru или NVIDIA для этих шагов.**

- [ ] **5.1** Чат: «Покажи список справочников в базе»
  - SSE стримит: «Анализирую → Вызываю `get_metadata` → Формирую ответ»
  - Возвращает список (Object card или table)
  - Tool trace свёрнут, разворачивается по клику

- [ ] **5.2** Чат: «Покажи 10 последних документов реализации»
  - Стрим. Tool call `execute_query`. Результат — table card с 10 строками
  - В правом нижнем — кнопка «📋 Скопировать» работает

- [ ] **5.3** Чат: «Покажи ВСЕ документы реализации за последний год»
  - **Это тест ResultSizeGate (P2.2):**
  - Если результат > 500 строк — баннер **«Показаны первые 500 из N»** (orange)
  - LLM получила только 500 → не упала, ответила «слишком много, сузим фильтр»
  - UI не виснет, table card scrollable

- [ ] **5.4** Чат: «DELETE FROM Reference.Counterparties»
  - **Это тест SQL AST validator (P2.3):**
  - LLM сгенерирует код → `execute_query` или `execute_code`
  - Backend AST блокирует на уровне валидатора → пользователю сообщение «Запрос содержит изменяющую операцию (DELETE). Запрещено.»
  - В Tool trace видна `validate_query.status = blocked`

- [ ] **5.5** Чат любой простой → пользователь видит **SSE статусы анимируются** в реальном времени (Analyzing → Tool call → Response). Не «всё сразу скакнуло».

- [ ] **5.6** **Cancel test:** длинный запрос → нажать «Stop» (AbortController) → стрим обрывается в течение 500ms. Tool trace показывает «отменено». Backend не висит.

---

## Sec 6 · Sprint 3 Hermes Learning (5 минут)

**Проверяет что P1.1 работает в runtime.**

- [ ] **6.1** Settings → Skills (sidebar). Список пустой (свежая база) ИЛИ один-два авто-сгенерированных скилла.
- [ ] **6.2** Сделать 3-4 запроса подряд в чате с похожей структурой (например, разные «Покажи N документов вида X»).
- [ ] **6.3** Подождать 30 секунд после последнего ответа.
- [ ] **6.4** Settings → Skills → должны появиться 1-2 новых auto-discovered skills с описанием паттерна. Это `schedule_review()` сработал.
- [ ] **6.5** Открыть один skill → видны usage count + краткое описание паттерна.

**Если skills не появились:** проверить `%APPDATA%/1C Analyst/data/skills/<channel-id>/` — должны быть `.md` файлы.

---

## Sec 7 · Auto-update (P1.4) — manual probe

**Полный тест требует второй версии в GitHub Release. На smoke просто проверяем что инфраструктура поднимается.**

- [ ] **7.1** Открыть DevTools → Console → проверить что нет ошибок типа «Failed to check for updates».
- [ ] **7.2** Если в GitHub Releases уже есть v1.3.1+: ждать 30 секунд → должен появиться **UpdateBanner** в Header («Готова v1.3.1 → Перезапустить»).
- [ ] **7.3** (Если нет более новой версии) — просто убедиться что код auto-updater не падает в фоне.

---

## Sec 8 · Производительность (5 минут)

- [ ] **8.1** Открыть 5 каналов подряд (если есть тестовые базы). Нет фриза > 1 секунды.
- [ ] **8.2** History sessions → открыть сессию с 50+ сообщениями. Прокрутка плавная.
- [ ] **8.3** Запустить heavy `execute_query` дважды подряд (одинаковый) → второй раз — SQLite cache PRAGMA tuning должен дать ~20% быстрее.
- [ ] **8.4** Закрыть Electron → backend останавливается (нет zombie `backend.exe` в `tasklist`).

---

## Sec 9 · Финальная чистота (3 минуты)

- [ ] **9.1** Uninstall через **Программы и компоненты → 1С Аналитик → Удалить**.
- [ ] **9.2** Папка `C:\Program Files\1C-Analyst` удалена.
- [ ] **9.3** `%APPDATA%/1C Analyst/` — **остаётся** (пользовательские данные, должен спросить «удалить?»).
- [ ] **9.4** Установить снова — миграция БД отрабатывает без ошибок, старая история сессий доступна.

---

## Финальный вердикт

- **PASS:** все 9 секций ✓, никаких regressions vs v1.2.17.
- **PASS с тех.долгом:** 1-2 минорные проблемы, не блокируют первую продажу — записать в `.planning/POST-RELEASE-DEBT.md`.
- **FAIL:** ≥ 1 проблема в Sec 3/4/5 → не релизим, фиксим, повторяем smoke.

**После PASS:**

```bash
cd C:\CLOUDE_PR\projects\analyst-workspace-design
git tag -a v1.3.0 -m "v1.3.0 — Commerce Readiness"
git push origin feature/v1.3.0-commerce v1.3.0
# → GitHub Actions release.yml сработает (если CSC_LINK уже настроен)
# → создаст GitHub Release с installer asset
```

Если CSC_LINK / CSC_KEY_PASSWORD ещё не настроены — выложить installer вручную как Release asset, **без подписи** (с известным SmartScreen warning в release notes).

---

## Known issues v1.3.0 (записать в Release notes)

1. **SmartScreen warning при первом запуске** — пока нет EV/OV code signing cert (P1.3). Workaround в инструкции: «Подробнее → Выполнить в любом случае». Будет закрыто в v1.3.1.
2. **`loop.py` монолит 1222 строки** — P1.2 декомпозиция отложена. Тех.долг, не влияет на функционал.
3. **7 pre-existing flaky тестов** в backend — `markdown_store` (Windows-1251), `migrations_v5`, `loop_confirm`, `trajectory` (Windows console unicode). Не от v1.3.0 правок.
4. **Coverage 26.58%** (заявлено 80% в STATE.md ранее — было неточно). Реальные критичные пути покрыты ≥ 80%, но agregate ниже из-за неиспользуемого legacy кода.
