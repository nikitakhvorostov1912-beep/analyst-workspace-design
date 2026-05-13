# PROJECT — 1С Аналитик: чат-консоль с MCP

**Status:** Inception (новый проект, GSD methodology)
**Created:** 2026-05-13
**Owner:** Никита Хворостов (nikita.khvorostov1912@gmail.com)

---

## Vision (one paragraph)

Веб-приложение для бизнес-аналитиков 1С: аналитик пишет вопрос на естественном языке про любую подключённую базу 1С — LLM (Xiaomi MiMo через OpenAI-compatible API) под капотом вызывает нужные операции 1С MCP Toolkit, получает данные, форматирует ответ с inline-карточками (таблица / объект / журнал / метрика / ссылки / код). Аналитик не знает про API, SQL и BSL — он просто общается с экспертом, у которого есть доступ к его базам. Multi-tenant: аналитик переключается между базами клиентов через channel selector.

## Problem Space

**Кого решаем:** бизнес-аналитики 1С / внедренцы 1С — работают с базами клиентов, отвечают на вопросы руководства, разбирают баги, делают аудит конфигураций.

**Что болит:**
1. **Discovery незнакомой базы клиента** — 3+ дня на «понять что задействовано / что доработано» через Конфигуратор / EDT
2. **Drill-down цифры из отчёта руководству** — постановка разработчику + неделя ожидания на каждый раунд вопросов
3. **AI-инструменты галлюцинируют** — не знают методов платформы, путают типы, выдумывают реквизиты (правило 3 итераций Матакова)
4. **Telegram-чат с разработчиком — единственный канал** — контекст растворяется за неделю
5. **Параллельно 4-6 проектов** — постоянное переключение, контекст теряется

**Текущее решение пользователя:** Claude Code + 1С MCP Toolkit через CLI — работает, но (а) другие аналитики не могут себе позволить Claude Code, (б) нет multi-tenant, (в) нет UI для несведущих.

## Target Users

- **P1. Опытный 1С-аналитик** (как Никита) — 4+ лет опыта, работает с 4-6 проектами параллельно, читает BSL, не пишет руками. Уже использует AI-инструменты, но через CLI.
- **P2. Внедренец 1С** (франчайзи, 2-3 года опыта) — типовые конфигурации (УТ/КА/ERP/УСО), AI слабая, нужен low-friction onboarding в незнакомую базу клиента.

## Success Criteria (MVP)

- ✅ Аналитик подключает свою базу 1С через `localhost:6010/mcp` (или другой endpoint)
- ✅ Подключает свой LLM endpoint + API ключ (Xiaomi MiMo по умолчанию)
- ✅ Пишет вопрос на NL → получает ответ ≤ 30 сек
- ✅ Ответ содержит inline-карточку (таблица / объект / журнал — минимум 3 типа)
- ✅ Можно развернуть trace tool calls для проверки
- ✅ История чатов сохраняется (SQLite) и доступна в sidebar
- ✅ Переключение между ≥ 2 базами 1С через channel selector
- ✅ Состояния: MCP disconnected (понятный баннер с retry), LLM error (понятная ошибка), streaming (видно что происходит)
- ✅ Тёмная тема, русский UI

## Non-Goals (явно out of scope для MVP)

- ❌ Управление 1С базами на стороне MCP (deploy, restart) — это для админа
- ❌ Написание BSL-кода руками (это для разработчика)
- ❌ Real-time collaboration (multi-user в одной сессии)
- ❌ Mobile / tablet UI (desktop ≥ 1280px)
- ❌ Vector search / RAG над метаданными (потом, отдельная итерация)
- ❌ Voice input (нативный input через `getUserMedia` — потом)

## Tech Stack (locked)

- **Frontend:** Next.js 15 (App Router) + React 19 + shadcn/ui + Tailwind 4 + IBM Plex шрифты
- **Backend:** FastAPI + Pydantic v2 + httpx (для MCP и LLM) + SSE streaming
- **LLM Client:** `openai` SDK v1.x (compatible с любым OpenAI-совместимым endpoint)
- **MCP Client:** прямой HTTP к MCP Streamable HTTP endpoint
- **Storage:** SQLite (через `aiosqlite`)
- **Контейнеризация:** Docker Compose (`docker compose up` поднимает всё)
- **Тестирование:** pytest (backend) + Playwright (E2E, опц.)
- **CI/CD:** GitHub Actions (later)

## Constraints

- **OpenAI-compatible only** для LLM — упрощает интеграцию с разными провайдерами
- **MCP Streamable HTTP** transport — это единственный supported transport (не stdio)
- **Local-first** — приложение работает локально у аналитика. Опц. self-host позже
- **Без accounts / multi-user** в MVP — это инструмент для одного аналитика
- **API ключи** — только в localStorage браузера, никогда не в backend storage

## Inspirations / References

- **ChatGPT** — простой чат-интерфейс
- **Claude.ai** — inline-карточки (artifacts), trace tool use
- **Perplexity** — источники в ответах
- **NOT Linear, Cursor, Hex** — это про абстракции, нам нужна прозрачность операций

## Open Questions (будут решены через GSD discuss-phase)

1. **Tool calling format:** какой именно у Xiaomi MiMo (OpenAI native? Cohere-style?) — определит реализацию orchestrator'а
2. **Streaming protocol:** SSE или WebSocket? (SSE проще, но WebSocket bidirectional)
3. **MCP session lifecycle:** держим одну сессию на всё время или новая при каждом /chat?
4. **Cache metadata:** держать локально (SQLite) или re-fetch при каждом session start?
5. **Channel multiplexing:** одна MCP-обработка на много каналов или MCP-сервер на каждую базу?

## Related Resources

- 1С MCP Toolkit: `C:\CLOUDE_PR\tools\1c-mcp-toolkit-proxy\`
- MCP capability map: `docs/00b-mcp-capability-map.md`
- Claude Design макет: `https://claude.ai/design/p/019e2188-87ed-7ae9-a77a-362c234c33a3`
- Historical artifacts (v0/v0b провалы): `docs/_archive-v0-object-ide/`
