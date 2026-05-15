# 1С Аналитик — чат с MCP

Веб-приложение: чат-консоль для бизнес-аналитиков 1С через MCP Toolkit.
LLM сама вызывает MCP-инструменты — аналитик только пишет на русском.

## Возможности

- Чат с потоковым ответом (SSE), inline-карточки (Table / Object / Log)
- История сессий, channel selector (multi-tenant, несколько баз 1С)
- Trace tool calls с кнопкой «Скопировать как curl»
- Confirm dialog для опасных execute_code
- Пагинация LogCard (load-more следующей страницы журнала)

## Стек

| Слой | Технологии |
|------|-----------|
| Frontend | Next.js 15 + React 19 + Tailwind 4 + shadcn/ui |
| Backend | FastAPI + Pydantic v2 + SSE streaming + SQLite |
| LLM | OpenAI-compatible HTTP (Xiaomi MiMo, GPT-4o, любой) |
| MCP | 1С MCP Toolkit v1.7.0 (EPF) на localhost:6010 или :6003 |

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
DEFAULT_LLM_ENDPOINT=https://api.mimo.example/v1
DEFAULT_LLM_MODEL=mimo-32b
LOG_LEVEL=INFO
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

## Лицензия

MIT
