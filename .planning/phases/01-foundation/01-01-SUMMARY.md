---
phase: 01-foundation
plan: 01
subsystem: backend
tags: [fastapi, pydantic-v2, sqlite, aiosqlite, llm-client, mcp-client, sse, docker]
dependency_graph:
  requires: []
  provides: [backend-skeleton, health-endpoint, llm-client, mcp-client, chat-sse, sqlite-schema]
  affects: [phase-2-orchestrator, phase-2-sessions, plan-02-frontend]
tech_stack:
  added:
    - FastAPI 0.115 + uvicorn[standard] 0.32
    - Pydantic v2 2.9 + pydantic-settings 2.6
    - httpx 0.27 (async HTTP client)
    - aiosqlite 0.20 (SQLite без ORM)
    - sse-starlette 2.1
    - pytest + pytest-asyncio + pytest-cov + ruff
  patterns:
    - Pydantic Settings с lru_cache для конфига
    - aiosqlite raw DDL (без ORM/Alembic), идемпотентные миграции через schema_version
    - Lifespan asynccontextmanager для init/close БД
    - Annotated[T, Depends(F)] вместо default Depends (ruff B008)
    - MockTransport + base_url для unit-тестов httpx-клиентов без реальных вызовов
    - monkeypatch в namespace роутера (не клиента) для замены зависимостей в тестах
key_files:
  created:
    - backend/pyproject.toml
    - backend/ruff.toml
    - backend/.env.example
    - backend/Dockerfile
    - backend/.dockerignore
    - backend/app/__init__.py
    - backend/app/main.py
    - backend/app/config.py
    - backend/app/models.py
    - backend/app/storage/__init__.py
    - backend/app/storage/db.py
    - backend/app/storage/migrations.py
    - backend/app/clients/__init__.py
    - backend/app/clients/llm.py
    - backend/app/clients/mcp.py
    - backend/app/routes/__init__.py
    - backend/app/routes/health.py
    - backend/app/routes/chat.py
    - backend/app/routes/mcp.py
    - backend/tests/conftest.py
    - backend/tests/test_health.py
    - backend/tests/test_db.py
    - backend/tests/test_llm_client.py
    - backend/tests/test_chat_route.py
    - backend/tests/test_mcp_client.py
    - backend/tests/test_mcp_route.py
    - docker-compose.yml
  modified: []
decisions:
  - "requires-python опущен до >=3.11 для совместимости с локальным окружением; Docker использует python:3.12-slim"
  - "monkeypatch в пространстве имён роутера (app.routes.chat.LLMClient), а не клиентского модуля — иначе уже импортированная ссылка не заменяется"
  - "Annotated[T, Depends(F)] вместо default parameter Depends() — исправление ruff B008"
  - "sqlite_path извлекается через strip sqlite+aiosqlite:/// (3 слеша) — корректно для :memory: и /data/app.db"
  - "LLM api_key не логируется нигде (T-01-01); event=error не содержит деталей исключения"
metrics:
  duration: "~35 мин"
  completed: "2026-05-14"
  tasks_completed: 3
  tasks_total: 3
  files_created: 27
  files_modified: 0
---

# Phase 01 Plan 01: Backend Skeleton + LLM/MCP Clients Summary

FastAPI backend с SQLite, OpenAI-совместимым LLM-клиентом (streaming SSE) и MCP Streamable HTTP-клиентом — полный скелет для Phase 2 orchestrator.

## Что сделано

### Task 1 — Скелет + health + SQLite (коммит `5083fc8`)
- `pyproject.toml` (pip, не poetry): FastAPI, Pydantic v2, httpx, aiosqlite, uvicorn, sse-starlette + dev deps
- `app/config.py` — Pydantic Settings с `get_settings()` + `lru_cache`; корректный парсинг `sqlite_path` для `:memory:` и `/data/app.db`
- `app/models.py` — ChatRequest, ChatSSEEvent, MCPPingResponse, HealthResponse, MCPConnection (все с `extra="forbid"`, T-01-08)
- `app/storage/migrations.py` — идемпотентные DDL через `schema_version`; 4 таблицы: sessions, messages, mcp_connections, llm_settings
- `app/storage/db.py` — init_db (WAL mode + миграции), close_db, get_db dependency
- `app/main.py` — FastAPI + lifespan + CORS (`http://localhost:3010`, T-01-02)
- `app/routes/health.py` — GET /health (DB SELECT 1), GET /
- `Dockerfile` (python:3.12-slim), `docker-compose.yml` (port 8010, volume ./data)
- 7 тестов: health 200+db=ok, root, migrations idempotency, table columns

### Task 2 — LLM-клиент + POST /chat SSE (коммит `c35b986`)
- `app/clients/llm.py` — LLMClient с `stream_chat_completion`: парсит SSE `data:` строки, yields `choices[0]` dict; остановка на `[DONE]`; не логирует Authorization
- `app/routes/chat.py` — POST /chat: `event: status` → `event: delta` × N → `event: done`; X-LLM-API-Key обязателен (400 иначе); X-LLM-Endpoint/Model опциональные override
- 6 тестов: SSE content parsing, tool_calls, api_key не в repr, 400 без ключа, SSE контракт, first event=status

### Task 3 — MCP-клиент + POST /mcp/{id}/ping (коммит `b81de9d`)
- `app/clients/mcp.py` — MCPClient: `initialize()` (JSON-RPC + Mcp-Session-Id из header), `list_tools()`, `call_tool()`; поддержка JSON и SSE ответов; MCPError для JSON-RPC errors
- `app/routes/mcp.py` — POST /mcp/{conn_id}/ping: endpoint из X-MCP-Endpoint header или ?endpoint= query; возвращает MCPPingResponse
- 7 тестов: session_id extraction, session_id reuse в headers, SSE parsing, MCPError, ping 400/200/query-param

## Итоги верификации

```
pytest -x -v  →  20 passed  (все 6 test файлов)
ruff check .  →  All checks passed!
```

Верифицировано локально на Python 3.11.9.

**Не верифицировано в sandbox:**
- `docker compose build backend` — Docker недоступен в sandbox; Dockerfile синтаксически валиден (FROM python:3.12-slim, WORKDIR, COPY, pip install, CMD uvicorn)
- `curl http://localhost:8010/health` — сервер не запускался в sandbox
- Реальный cold start ≤ 2 сек (NFR-4) — не измерено без Docker

## Отклонения от плана

### [Rule 3 - Blocking] setuptools.backends.legacy:build недоступен
- **Найдено при:** Task 1, попытка `pip install -e .`
- **Проблема:** `setuptools.backends.legacy:build` требует setuptools ≥ 72; установлена старая версия
- **Исправление:** `build-backend = "setuptools.build_meta"` — стандартный стабильный бэкенд
- **Файл:** `backend/pyproject.toml`

### [Rule 3 - Blocking] requires-python = ">=3.12" блокировало установку
- **Найдено при:** Task 1
- **Проблема:** локально Python 3.11.9, Docker 3.12; pip отказывался ставить пакет
- **Исправление:** `requires-python = ">=3.11"` — код совместим с 3.11 (union `|` с 3.10+); Docker всё равно использует 3.12-slim
- **Файл:** `backend/pyproject.toml`

### [Rule 1 - Bug] sqlite_path неверно извлекал :memory:
- **Найдено при:** Task 1, первый запуск тестов
- **Проблема:** `sqlite+aiosqlite:///:memory:` → после strip `sqlite+aiosqlite://` → `/:memory:` → `sqlite3.OperationalError: unable to open database file`
- **Исправление:** strip `sqlite+aiosqlite:///` (3 слеша), не `//` (2 слеша)
- **Файл:** `backend/app/config.py`

### [Rule 1 - Bug] monkeypatch на модуль клиента не работал для роутера
- **Найдено при:** Task 2, первый запуск `test_chat_returns_sse_with_status_and_delta`
- **Проблема:** `from app.clients.llm import LLMClient` в роутере создаёт локальную ссылку; `monkeypatch.setattr(llm_module, "LLMClient", ...)` не затрагивала её
- **Исправление:** `monkeypatch.setattr(chat_module, "LLMClient", ...)` — патчим в пространстве имён роутера
- **Файл:** `backend/tests/test_chat_route.py`, `backend/tests/test_mcp_route.py`

## Known Stubs

Нет. Все эндпоинты реализованы без заглушек, TODO и placeholder'ов.

## Threat Surface Scan

Новые security-поверхности совпадают с threat model в PLAN.md:
- `/chat` + `X-LLM-API-Key` форвардит к произвольному LLM endpoint (T-01-03: accepted)
- `/mcp/{id}/ping` + endpoint param принимает произвольный URL (T-01-03: accepted)
- Оба случая explicitly marked `accept` в threat register Phase 1 (allowlist — Phase 3)

## Self-Check: PASSED

- backend/app/clients/mcp.py — FOUND
- backend/app/routes/chat.py — FOUND
- backend/app/main.py — FOUND
- backend/tests/test_health.py — FOUND
- commit 5083fc8 — FOUND
- commit c35b986 — FOUND
- commit b81de9d — FOUND
