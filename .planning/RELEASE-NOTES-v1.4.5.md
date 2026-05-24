# 1С Аналитик v1.4.5 — Commerce-Ready Release

**Дата:** 2026-05-24
**Статус:** First commerce-ready release (unsigned)
**Предыдущий tag:** v1.2.2 (2026-05-19)

> Этот release консолидирует 5 промежуточных итераций: **v1.3.0 → v1.4.5**.
> Промежуточные версии не имели отдельных тегов — они были QA pre-production rounds.
> Все фиксы из этих итераций включены в v1.4.5.

---

## 📦 Скачать

Скачайте `analyst-setup-v1.4.5.exe` (~183 МБ) из Assets ниже.

**⚠️ SmartScreen warning при установке:**

Этот релиз **не подписан** EV/OV сертификатом (планируется в следующих версиях). При первом запуске Windows покажет окно «Защитник Windows предотвратил запуск неопознанного приложения».

**Что делать:** нажмите **«Подробнее»** → **«Выполнить в любом случае»**.

Это безопасно — installer собран из открытого репозитория. После первого запуска система запомнит решение.

---

## 🎯 Главное

v1.4.5 — первая коммерчески-готовая версия:

- **Безопасность для корп-клиентов**: API-ключи на сервере (AES-256 GCM), SQL валидация через AST, защита от 100K-row crash'ей.
- **152-ФЗ из коробки**: РФ-ДЦ LLM по умолчанию (Cloud.ru Qwen3-Coder-480B), NVIDIA NIM как основной англоязычный провайдер.
- **Auto-update**: после установки одной из следующих версий — уведомление в Header «Готова vX.Y.Z — Перезапустить».
- **Самообучение в runtime**: Hermes Sprint 3 wired — Skills накапливаются per channel, инжектируются в system prompt автоматически.

---

## ✨ Что нового (с v1.2.2)

### 🧠 Hermes Memory & Learning (M6 milestone)

Полностью новый слой памяти и обучения, реализованный за 5 sprint'ов:

- **MEMORY.md / USER.md per-channel** — Markdown-память про клиента и пользователя. Видна в `/settings/memory`, редактируется руками или через `update_memory` tool.
- **Skills** — паттерны «как делать X» извлекаются автоматически из удачных turn'ов через aux LLM. Видны в `/settings/skills`, можно archive/unarchive, есть Curator для авто-чистки.
- **Insights dashboard** `/insights` — 6 KPI карт: turns, latency p50/p95, top tools, top channels, cost USD, ошибки. Период переключается (day/week/month).
- **Todo per session** — структурированные задачи, AI может добавить/закрыть через tool calls.
- **Clarify dialog** — multiple-choice вопросы AI пользователю когда не хватает контекста.
- **Stop button** — прерывание SSE стрима в любой момент.

### 🛡️ Безопасность (Commerce Readiness M7 Wave 1)

- **Keyword-scanner на execute_query** — DELETE/DROP/TRUNCATE блокируются с confirm dialog (раньше защищён был только execute_code).
- **MAX_TOOL_CALLS_PER_TURN** — лимит на runaway tool loops.
- **Rate-limit /chat** через slowapi.
- **XSS Prism CodeCard** — DOMPurify санитизация Markdown.
- **AbortController в useChatStream** — корректное прерывание fetch'а.
- **AES-256 GCM** для user_secrets (API-ключи на бэке, не в localStorage).
- **ResultSizeGate** — 500 row cap в TableCard с баннером «Показаны первые 500 из N».
- **SQL AST validator** через sqlparse — защита от bypass keyword-scanner'а через комментарии или encoded строки.

### 🤖 LLM провайдеры pivot

- **NVIDIA NIM (по умолчанию)** — один встроенный ключ покрывает 8-9 моделей: DeepSeek V4 Flash (default), DeepSeek R1, Qwen3-Coder 480B, Llama Nemotron Super 49B, Llama 3.3 70B, Mistral Large 3, Mistral Medium 3.5, Nemotron Nano 9B.
- **Cloud.ru Foundation Models** — добавлен как 152-ФЗ compliance альтернатива (РФ-ДЦ, данные не пересекают границу).
- **Compliance badges** в Настройках: «РФ-ДЦ ✓ 152-ФЗ» / «За рубежом — требует согласие».

### 🎨 Design v2 + Sprint-04 motion polish

- Brand Stencil/Mono — Signal #FF6A3D, IBM Plex Mono 700, обе темы (Dark/Light через `data-theme`).
- 12 новых компонентов: StatusDot, EmptyState, ErrorBanner, CardActionMenu, CardHeader, StreamingStages, CardSkeleton + 4 redesign'а.
- **Sidebar collapse** 260px ↔ 56px с persistence (M07).
- **UndoToast** slide-in/out + progress-bar (M09).
- **Sparkline** draw-in анимация (M03).
- **Stagger / spring / drag / page-enter** motion polish (M02+04+06+08).
- **ComposerHub welcome** с шаблонами quick-starts (Sprint 3.2).
- **ResumeBanner** + config warnings + quick-starts (O-2/O-3/O-5).

### 🔧 Стабильность и фиксы (v1.3.0 → v1.4.5)

- **v1.4.1**: ModelBadge sync с backend, анонимизация из 1С, NVIDIA-ключ cleanup.
- **v1.4.2**: ModelBadge popover клик работает (FINDING-10), Backend CORS PATCH разрешён (FINDING-11) — раньше смена модели и любые PATCH ломались.
- **v1.4.3**: Главная страница отправляет сообщения с env-ключом (FINDING-12 — раньше показывала «Введите API ключ» даже когда ключ был).
- **v1.4.4**: 8 NVIDIA-моделей рабочие «из коробки», главная отправляет.
- **v1.4.5**: java.exe больше не открывает консольное окно при работе чата (FINDING-17).

---

## 📊 Метрики качества

- Backend: **847/847 pytest passed**, coverage **88.1%** на критичных модулях (loop.py 81.9%, persistence.py 88.4%, sql_validator 89%, cards 93%).
- Frontend: **323/323 vitest passed**, TypeScript 0 errors, build clean.
- 7/7 ранее flaky тестов починены (encoding + migration setup + race timeout).
- 3 ранее skipped E2E specs unskipped.

---

## 🎁 Системные требования

- **OS:** Windows 10 / Windows 11 (64-bit)
- **RAM:** 4 GB минимум, 8 GB рекомендуется
- **Disk:** 500 MB для установки
- **Сеть:** интернет для LLM (NVIDIA NIM / Cloud.ru / DeepSeek), 1С MCP Toolkit локально на :6010

---

## 🚀 Установка и onboarding

1. Скачайте `analyst-setup-v1.4.5.exe`
2. Запустите → SmartScreen warning → «Подробнее» → «Выполнить в любом случае»
3. Установите в `%LOCALAPPDATA%\Programs\1C-Analyst` (по умолчанию)
4. Запустите ярлык «1С Аналитик» на рабочем столе
5. Пройдите 4-step onboarding:
   - Step 1: MCP — укажите endpoint вашей базы 1С (обычно `http://localhost:6010/mcp`)
   - Step 2: LLM — выберите провайдера (NVIDIA NIM рекомендуется, ключ встроен)
   - Step 3: Память — opt-in для self-learning (можно включить позже)
   - Step 4: Готово — задайте первый вопрос

**Демо-запросы для проверки:**
- «Расскажи про базу»
- «Покажи 10 последних документов реализации»
- «Что в журнале регистрации за сегодня»

---

## 📚 Документация

- **USER.md** — руководство аналитика (см. в установке `docs/USER.md`)
- **API.md** — REST endpoints
- **Demo script** — 15-минутный сценарий для презентации

---

## 🐛 Известные ограничения

- **Unsigned installer** — SmartScreen warning при первой установке (фикс — следующая версия с EV/OV cert).
- **loop.py 689 строк** — orchestrator всё ещё monolith, цель ≤400 в следующем релизе (TD-1 в работе).
- **macOS / Linux installers** не собираются — только Windows. По запросу первого Mac-клиента (TD-13).
- **Multi-user backend** — текущий installer = single-user desktop. Standalone server для нескольких клиентов — по enterprise запросу (TD-14).

---

## 🛣️ Что дальше — M8 Pilot Stabilization

После этого релиза начинается milestone M8:

1. **Первый платный пилот** — 2-3 аналитика франчайзи, символическая цена 15-30K ₽/мес
2. **TD-1 decompose loop.py** — 6-10h фокус-сессия, цель 689 → ≤400 строк
3. **Wave 2 commerce-blockers** — slash-команды, robust injection scan, Docker multi-stage
4. **Wave 3 polish** — A11y audit, lazy load, PRAGMA tuning
5. **Feedback-driven фичи** — на основе real usage от пилотных клиентов

---

## 🤝 Обратная связь

GitHub Issues: https://github.com/nikitakhvorostov1912-beep/analyst-workspace-design/issues

Email: nikita.khvorostov1912@gmail.com

---

## 📝 Полная история коммитов (v1.2.2 → v1.4.5)

```
1328b2e fix(v1.4.5): java.exe больше не открывает консольное окно (FINDING-17)
7cc605d fix(v1.4.4): чат «из коробки» — 8 NVIDIA-моделей рабочие
73a7e3a chore(release): bump v1.4.1 → v1.4.2 — QA pre-prod fixes round
c4b5067 fix(qa-prod): P0 finding-10/11 — ModelBadge switch + CORS PATCH
ff5dadd fix(v1.4.1): ModelBadge sync + анонимизация из 1С + NVIDIA-ключ cleanup
6cd8e96 chore(release): bump v1.3.0 → v1.4.0
... (полная история в git log)
```
