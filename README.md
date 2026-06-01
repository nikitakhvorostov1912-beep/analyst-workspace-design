# 1С Аналитик — чат с MCP

Веб-приложение: чат-консоль для бизнес-аналитиков 1С через MCP Toolkit.
LLM сама вызывает MCP-инструменты — аналитик только пишет на русском.

> 🗺️ **Навигация по проекту и документам — [`PROJECT-INDEX.md`](PROJECT-INDEX.md)** (что где лежит, что актуально, что историческое).

## Возможности

- Чат с потоковым ответом (SSE), inline-карточки (Table / Object / Log / Metric / References / Code)
- Streaming pipeline с иконками: «Анализирую → Вызываю → Получил данные → Формирую ответ» (v1.2.0)
- История сессий, channel selector (multi-tenant, несколько баз 1С)
- Trace tool calls с кнопкой «Скопировать как curl»
- Confirm dialog для опасных execute_code
- Пагинация LogCard (load-more следующей страницы журнала)
- 4-шаговый Onboarding wizard с опт-ин обучения на сессиях (v1.2.0)
- Privacy escape hatch: сброс локальной базы через Settings → Локальные данные (v1.2.0)
- Анонимизация чувствительных данных (toggle в Header, amber pill когда ВКЛ)
- Тёмно-синий accent с 4 вариантами палитры (`data-accent="blue|clinical|indigo|orange"`, v1.2.0)

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | Next.js 15 + React 19 + Tailwind 4 + shadcn/ui + IBM Plex Sans/Mono |
| Backend | FastAPI + Pydantic v2 + SSE streaming + SQLite (через aiosqlite) |
| LLM | OpenAI-compatible HTTP (Xiaomi MiMo, GPT-4o, любой) |
| MCP | 1С MCP Toolkit v1.7.0 (EPF) на localhost:6010 или :6003 |
| Desktop | Electron 33 + PyInstaller (Windows installer, v1.1.0+) |
| Тесты | Vitest 4 (278 specs) + Pytest (321 specs) + Playwright |

## Скачать готовый Windows installer

Для аналитиков, которым не нужно настраивать dev-окружение:

1. Скачать `analyst-setup-vX.Y.Z.exe` из [GitHub Releases](https://github.com/nikitakhvorostov1912-beep/analyst-workspace-design/releases/latest) (~110 MB)
2. Двойной клик → пройти мастер установки на русском (без админских прав)
3. На Рабочем столе появится ярлык «1С Аналитик» → двойной клик запускает приложение
4. При первом запуске откроется onboarding wizard — указать MCP подключение к базе 1С + ввести свой LLM API-ключ

**Что внутри:** Electron + bundled Python backend (PyInstaller) + Next.js standalone frontend. Аналитику НЕ нужно ставить Python, Node.js, Docker, pnpm.

**SmartScreen:**
- v1.3.0+ установщики подписаны Code-Signing сертификатом — SmartScreen не должен ругаться.
- На старых сборках (v1.2.x и раньше) Windows покажет предупреждение «Windows защитил ваш ПК». Нажмите «Подробнее» → «Выполнить в любом случае».

**Auto-update:** v1.3.0+ проверяет наличие новых версий при старте и предлагает обновиться одним кликом (через electron-updater).

**Поддерживаемые системы:** Windows 10/11 x64. macOS и Linux — в roadmap v2.

---

## Быстрый старт

### 1. Запуск

```bash
git clone <repo-url> analyst-workspace-design
cd analyst-workspace-design
docker compose up
```

- Backend: http://localhost:8010
- Frontend: http://localhost:3010
- Swagger UI: http://localhost:8010/docs

### 2. Onboarding wizard (~90 секунд до первого ответа)

1. Открыть http://localhost:3010
2. Появится 3-шаговый onboarding wizard:
   - **Шаг 1 — MCP:** указать адрес MCP Toolkit вашей базы 1С (обычно `http://localhost:6010/mcp`) → «Сохранить» → «MCP подключён» → «Далее»
   - **Шаг 2 — LLM:** указать endpoint + модель + API ключ (OpenAI-совместимый сервис) → «Тест» → «Сохранить» → «Далее»
   - **Шаг 3 — Готово:** нажать «Начать работу»
3. Задать первый вопрос, например: «Расскажи про базу»
4. Наблюдать статус: «Анализирую...» → «Вызываю tool...» → ответ с inline-карточкой

**После onboarding:**
- Настройки MCP/LLM редактируются в `/settings` (кнопка «шестерёнка» в шапке)
- Добавить ещё одну базу 1С: `/settings` → «+ Добавить подключение»
- Channel selector в шапке переключает базу для нового чата

### 3. Запуск вручную (без Docker)

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8010
```

**Frontend:**

```bash
cd frontend
pnpm install
pnpm dev   # http://localhost:3010
```

### 4. Конфигурация

Backend `.env`:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
BACKEND_ALLOWED_ORIGINS=http://localhost:3010
LOG_LEVEL=INFO

# Дефолты сидятся в БД при первом запуске — после установки можно сразу
# зайти и протестировать, останется ввести только API-ключ через UI.
DEFAULT_LLM_ENDPOINT=https://api.xiaomimimo.com/v1
DEFAULT_LLM_MODEL=mimo-v2.5-pro
DEFAULT_LLM_TEMPERATURE=0.3

# Если задать — backend сам подставит ключ в LLM-вызовы как fallback, когда
# frontend не передал свой. UI узнаёт по флагу has_env_api_key и не требует
# ввода ключа в форме («прописал один раз — забыл навсегда»).
DEFAULT_LLM_API_KEY=sk-your-mimo-key

DEFAULT_MCP_NAME=Транзит
DEFAULT_MCP_ENDPOINT=http://localhost:6010/mcp
DEFAULT_MCP_KIND=embedded
# SEED_ON_STARTUP=false  # выключить seed (для тестов)
```

Frontend `.env.local`:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8010
```

## Тестирование

```bash
# Backend (unit + integration)
cd backend && pytest -v --cov-fail-under=80

# Frontend (unit vitest)
cd frontend && pnpm test

# E2E (Playwright, требует запущенного frontend)
cd frontend && pnpm exec playwright install --with-deps chromium && pnpm exec playwright test
```

## CI

GitHub Actions на каждый PR и push в main:
- Job `backend`: ruff check + pytest --cov-fail-under=80
- Job `frontend`: type-check + lint + build + vitest
- Job `e2e`: Playwright 3 flow (only on PR)

## Troubleshooting

| Проблема | Решение |
|----------|---------|
| Backend не стартует | Проверить порт 8010 свободен; права на `data/` для SQLite |
| MCP ping красный | Запущен ли EPF MCP Toolkit? Открыть `http://localhost:6010/health` |
| LLM 429 | rate-limited модель — ждать `retry-after` секунд из toast |
| Confirm dialog на безобидном коде | Regex чувствительный; см. docs/USER.md «Опасные команды» |
| Кнопка «Загрузить ещё» disabled | card_id отсутствует в старых сессиях (created до v3 миграции) |
| Build падает на Node < 22 | Обновить Node до 22 LTS |

## Демо для аналитика

Перед прогоном:

1. Запустить `docker compose up`
2. (Опционально) Заполнить демо-данными: `python scripts/seed-demo-data.py --clean`
   — создаёт 6 сессий с примерами всех 6 типов карточек (без живой 1С)
3. Открыть [docs/DEMO-SCRIPT.md](docs/DEMO-SCRIPT.md) — 15-минутный пошаговый сценарий

Во время демо:

- Наблюдатель ведёт [docs/DEMO-OBSERVER-CHECKLIST.md](docs/DEMO-OBSERVER-CHECKLIST.md)
- После — аналитик заполняет [docs/DEMO-FEEDBACK-TEMPLATE.md](docs/DEMO-FEEDBACK-TEMPLATE.md)

После демо — feedback → [.planning/BACKLOG-POST-MVP.md](.planning/BACKLOG-POST-MVP.md)

## Документация

- [docs/USER.md](docs/USER.md) — руководство аналитика
- [docs/API.md](docs/API.md) — REST API endpoints
- [docs/CURL.md](docs/CURL.md) — формат «Скопировать как curl»
- [ARCHITECTURE.md](ARCHITECTURE.md) — топология, SSE events, persistence

## Структура `.claude/` (project-local Claude Code routing, v1.2.0)

```
.claude/
├── CLAUDE.md          # автоматически подгружается при работе в проекте
│                        wrong-project guard + lazy-load memory map
├── skills/            # проектные скиллы (slash commands)
│   ├── awd-dev-up/                  # /awd-dev-up — поднять :8010 + :3010
│   ├── awd-quality-gate/            # /awd-quality-gate — pytest + vitest + build + playwright
│   └── awd-claude-design-handoff/   # /awd-claude-design-handoff — bundle для claude.ai/design
├── memory/            # проектная память (lazy-load по триггеру)
│   ├── MEMORY.md                              # индекс
│   ├── llm-providers.md                       # MiMo, OpenAI-compatible
│   ├── distribution.md                        # Electron + PyInstaller
│   ├── design-constraints.md                  # запреты дизайна verbatim
│   ├── pivot-history.md                       # v0/v0b/v1 lessons
│   ├── open-questions.md                      # неопределённости
│   └── requirements-stack-sessions-learn.md   # MSG #10 requirements
└── rules/             # извлечённые правила
    ├── design-bans.md           # запреты дизайна
    ├── tech-stack.md            # locked версии
    └── session-contract.md      # брутальная честность + workflow
```

Claude Code автоматически читает `.claude/CLAUDE.md` при работе в проекте.
Wrong-project guard защищает от случайной работы в других проектах workspace.

## v1.2.0 release notes

См. [.planning/phases/11-design-v2-import/RELEASE-NOTES.md](.planning/phases/11-design-v2-import/RELEASE-NOTES.md):

- Полная переработка визуального языка из Claude Design v2 handoff
- 12 новых atomic components (StatusDot, EmptyState, ErrorBanner, CardHeader, StreamingStages, etc.)
- Onboarding 3→4 шага с Learn opt-in (privacy-first)
- Тёмно-синий accent `#3b82f6` (blue-500) + 4 варианта
- 7 keyframes анимаций + animate-fade-up на mount cards
- Privacy reset endpoint + Settings UI (Phase 9)
- 599 automated tests (278 vitest + 321 pytest)
- Zero breaking changes в backend API

## Лицензия

MIT
