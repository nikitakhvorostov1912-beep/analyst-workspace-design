# 1С Аналитик — чат с MCP

> Веб-консоль для бизнес-аналитиков 1С. Аналитик пишет вопрос на естественном языке, LLM (Xiaomi MiMo / любая OpenAI-совместимая) под капотом вызывает операции **1С MCP Toolkit**, форматирует ответ с inline-карточками (таблица / объект / журнал / метрика / ссылки / код). Multi-tenant: несколько баз клиентов через channel selector.

**Status:** 🚧 In development (M1 — Foundation). Не для продакшен использования.

---

## Demo concept

```
🧑 «Покажи 32 ОПП за 30.04 без шапки»
   ↓
🤖 LLM решает: нужен execute_query → вызов через MCP
   ↓
📊 Ответ: TL;DR + Table card (32 строки) + ▸ свёрнутый trace
```

## Стек

- **Frontend:** Next.js 15 + shadcn/ui + Tailwind 4 (тёмная тема, русский UI)
- **Backend:** FastAPI + Pydantic v2 + SSE streaming
- **LLM:** любой OpenAI-compatible (Xiaomi MiMo, DeepSeek, OpenAI, local llama.cpp)
- **MCP:** прямой HTTP к [1С MCP Toolkit](https://github.com/ROCTUP/1c-mcp-toolkit)
- **Storage:** SQLite (sessions / messages / connections)

## Архитектура (one diagram)

```
Browser (Next.js)  ⇄  FastAPI Backend  ⇄  LLM Provider  (Xiaomi MiMo)
                       │
                       └────────────────  1С MCP Toolkit  ⇄  База 1С
```

Полная топология — см. [ARCHITECTURE.md](./ARCHITECTURE.md).

## Quickstart (после M1)

```bash
# 1. Clone
git clone https://github.com/nikitakhvorostov1912-beep/analyst-workspace-design.git
cd analyst-workspace-design

# 2. Run
docker compose up

# 3. Open
# - Frontend: http://localhost:3010
# - Backend:  http://localhost:8010
# - Docs:     http://localhost:8010/docs (OpenAPI)

# 4. Setup (in browser)
# Settings → Connections → Add MCP endpoint (e.g. http://localhost:6010/mcp)
# Settings → LLM → endpoint + API key + model
# → начни писать в чат
```

> Требуется запущенный [1С MCP Toolkit](https://github.com/ROCTUP/1c-mcp-toolkit) — EPF-обработка в твоей 1С базе. Подробнее в [USER.md](./docs/USER.md) (TBD).

## Документация

| Документ | Содержание |
|---|---|
| [PROJECT.md](./PROJECT.md) | Vision, problem space, success criteria |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Топология, data flow, storage schema |
| [REQUIREMENTS.md](./REQUIREMENTS.md) | FR / NFR / IR с MoSCoW приоритизацией |
| [ROADMAP.md](./ROADMAP.md) | Phased roadmap (M1-M4) |
| [CLAUDE.md](./CLAUDE.md) | Внутренние правила разработки (для Claude Code) |
| [docs/00b-mcp-capability-map.md](./docs/00b-mcp-capability-map.md) | Паспорт 10 MCP операций (backend reference) |

## Какие проблемы решает

Бизнес-аналитик 1С (4-6 параллельных проектов УТ/КА/ERP/УСО):

- 🔍 **Discovery незнакомой базы клиента** — сейчас 3+ дня. Цель: 1 час
- 📊 **Drill-down цифры из отчёта руководству** — сейчас «через неделю когда разраб сделает». Цель: ответ в той же встрече
- 🐛 **Bug-triage** через журнал регистрации + поиск ссылок + чтение кода
- 📥 **Маппинг внешних данных** (CSV/API) в документы 1С с валидацией типов
- 📚 **Knowledge work** — knowledge graph по конфигурациям и ловушкам

## Почему не Claude Code / Cursor?

Эти инструменты — для разработчиков. Аналитик:
- Не пишет BSL руками
- Не знает про `get_metadata`/`execute_query`
- Работает с **несколькими базами клиентов** (channel selector)
- Хочет одну поверхность для всех проектов
- Не хочет ставить Claude Code / Cursor + конфигурировать MCP вручную

Этот инструмент — для них. Простой URL → подключил базу → задал вопрос.

## Развитие

См. [ROADMAP.md](./ROADMAP.md). 4 milestone'а:
- **M1 Foundation** — инфраструктура
- **M2 MVP Chat** — работающий чат от и до
- **M3 Production Ready** — надёжность + безопасность + тесты
- **M4 Demo & Refine** — feedback от реальных аналитиков

## Контакты

Автор: Никита Хворостов — nikita.khvorostov1912@gmail.com

## License

MIT (см. [LICENSE](./LICENSE) после добавления)
