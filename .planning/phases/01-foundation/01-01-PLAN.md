---
phase: 01-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
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
  - docker-compose.yml
autonomous: true
requirements:
  - FR-1
  - FR-2
  - FR-7
  - NFR-1
  - NFR-4
  - NFR-8
  - NFR-18
  - IR-1
  - IR-2
  - IR-5
  - IR-6
  - IR-7
must_haves:
  truths:
    - "docker compose up backend поднимает контейнер за ≤ 2 сек до accepting requests"
    - "GET /health возвращает 200 с JSON {status: ok, version, db: ok}"
    - "POST /chat принимает {message, sessionId?, channelId?} и стримит SSE с content-chunks"
    - "POST /mcp/{conn_id}/ping выполняет MCP initialize + tools/list и возвращает {mcp_version, tool_count, session_id}"
    - "SQLite БД создаётся при старте; миграции прогоняются идемпотентно"
    - "LLM-клиент пробрасывает X-LLM-API-Key из request-header в Authorization Bearer к LLM endpoint и не персистит ключ"
    - "MCP-клиент сохраняет Mcp-Session-Id после initialize и переиспользует в последующих вызовах"
    - "pytest проходит зелёным, ruff не находит нарушений"
  artifacts:
    - path: "backend/pyproject.toml"
      provides: "Зависимости проекта (FastAPI, Pydantic v2, httpx, aiosqlite, pytest, ruff), entry-point uvicorn"
      contains: "fastapi, pydantic, httpx, aiosqlite, pytest, ruff"
    - path: "backend/app/main.py"
      provides: "FastAPI app instance, CORS, lifespan для init/close DB, регистрация роутеров"
      exports: ["app"]
    - path: "backend/app/config.py"
      provides: "Pydantic Settings: DATABASE_URL, CORS_ORIGINS, LLM endpoint defaults, log level"
      exports: ["Settings", "get_settings"]
    - path: "backend/app/models.py"
      provides: "Pydantic v2 модели: ChatRequest, ChatSSEEvent, MCPPingResponse, HealthResponse, MCPConnection"
      exports: ["ChatRequest", "ChatSSEEvent", "MCPPingResponse", "HealthResponse"]
    - path: "backend/app/storage/db.py"
      provides: "aiosqlite соединение, init/close, get_db() dependency"
      exports: ["init_db", "close_db", "get_db"]
    - path: "backend/app/storage/migrations.py"
      provides: "DDL для sessions/messages/mcp_connections/llm_settings (см. ARCHITECTURE.md), идемпотентный apply()"
      exports: ["apply_migrations"]
    - path: "backend/app/clients/llm.py"
      provides: "OpenAI-compat httpx AsyncClient: stream_chat_completion(messages, tools, api_key) → async iterator chunks, parser tool_calls"
      exports: ["LLMClient", "stream_chat_completion"]
    - path: "backend/app/clients/mcp.py"
      provides: "MCP Streamable HTTP клиент: initialize(), list_tools(), call_tool(), хранение Mcp-Session-Id"
      exports: ["MCPClient", "MCPSession"]
    - path: "backend/app/routes/health.py"
      provides: "GET /health (проверяет DB connection) и GET / (root)"
      exports: ["router"]
    - path: "backend/app/routes/chat.py"
      provides: "POST /chat → StreamingResponse media_type=text/event-stream, форматирует SSE events"
      exports: ["router"]
    - path: "backend/app/routes/mcp.py"
      provides: "POST /mcp/{conn_id}/ping → инициализирует MCP сессию и возвращает count tools"
      exports: ["router"]
    - path: "backend/Dockerfile"
      provides: "Python 3.12-slim, COPY pyproject, pip install, CMD uvicorn"
      contains: "FROM python:3.12-slim"
    - path: "docker-compose.yml"
      provides: "Service backend: build ./backend, port 8010:8010, volume ./data:/data для SQLite"
      contains: "services:"
  key_links:
    - from: "backend/app/main.py"
      to: "backend/app/routes/{health,chat,mcp}.py"
      via: "app.include_router(router)"
      pattern: "include_router"
    - from: "backend/app/main.py"
      to: "backend/app/storage/db.py"
      via: "lifespan startup → init_db + apply_migrations"
      pattern: "lifespan|asynccontextmanager"
    - from: "backend/app/routes/chat.py"
      to: "backend/app/clients/llm.py"
      via: "stream_chat_completion в SSE generator"
      pattern: "stream_chat_completion"
    - from: "backend/app/routes/mcp.py"
      to: "backend/app/clients/mcp.py"
      via: "MCPClient.initialize() + list_tools()"
      pattern: "MCPClient|initialize"
    - from: "docker-compose.yml"
      to: "backend/Dockerfile"
      via: "build: ./backend"
      pattern: "build:"
---

<objective>
Заложить весь backend-стек проекта «1С Аналитик»: FastAPI приложение (порт 8010), SQLite через aiosqlite, OpenAI-совместимый LLM-клиент со streaming, MCP Streamable HTTP клиент с управлением Mcp-Session-Id, контейнеризация через Dockerfile + docker-compose. Без бизнес-логики оркестратора чата (это Phase 2) — только инфраструктура и smoke-эндпоинты.

Purpose: backend готов принимать запросы, поднимается одной командой `docker compose up backend`, отдаёт `/health` за ≤ 2 сек после cold start, имеет работающие smoke-эндпоинты `/chat` (минимальный SSE без MCP) и `/mcp/{id}/ping` (initialize + tools/list). Это фундамент для Phase 2 orchestrator.

Output: скелет backend (~25 файлов), docker-compose.yml, прохождение pytest + ruff.
</objective>

<execution_context>
@C:/CLOUDE_PR/.claude/get-shit-done/workflows/execute-plan.md
@C:/CLOUDE_PR/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@PROJECT.md
@REQUIREMENTS.md
@ARCHITECTURE.md
@.planning/intel/STACK.md
@.planning/intel/MCP_INTEGRATION.md
@.planning/intel/TOOL_CALLING.md

<interfaces>
<!-- Контракты, на которые будет опираться Phase 2 orchestrator и Plan 02 (frontend). -->
<!-- Executor должен реализовать ровно эти сигнатуры. -->

# SSE event types (см. ARCHITECTURE.md data flow)
event=status     data={"stage": "thinking" | "calling_tool" | "responding"}
event=delta      data={"content": "<text chunk>"}
event=tool_call  data={"name": "execute_query", "args": {...}, "call_id": "..."}
event=tool_result data={"call_id": "...", "result": {...}, "duration_ms": 134}
event=card       data={"type": "table" | "object" | "log", "payload": {...}}
event=done       data={}
event=error      data={"message": "...", "code": "llm_rate_limit" | "mcp_disconnected" | ...}

# ChatRequest (Pydantic v2)
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    channel_id: str | None = None
    # api key пробрасывается через header X-LLM-API-Key, в теле НЕ передаётся

# MCPPingResponse
class MCPPingResponse(BaseModel):
    mcp_version: str
    tool_count: int
    session_id: str
    duration_ms: int

# HealthResponse
class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    db: Literal["ok", "error"]

# MCP Streamable HTTP протокол (см. .planning/intel/MCP_INTEGRATION.md)
POST {endpoint} body={"jsonrpc":"2.0","id":1,"method":"initialize","params":{...}}
  ← response header Mcp-Session-Id: <uuid>
  ← body {"result": {"protocolVersion": "...", "serverInfo": {...}}}
POST {endpoint} header Mcp-Session-Id body={"jsonrpc":"2.0","id":2,"method":"tools/list"}
  ← body {"result": {"tools": [{"name", "description", "inputSchema"}, ...]}}
POST {endpoint} header Mcp-Session-Id body={"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name","arguments"}}

# OpenAI-compat streaming (см. .planning/intel/TOOL_CALLING.md)
POST {endpoint}/chat/completions stream=true tools=[...]
  ← SSE chunks: choices[0].delta.content | choices[0].delta.tool_calls[...]
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Скелет проекта + Dockerfile + docker-compose + health check</name>
  <files>backend/pyproject.toml, backend/ruff.toml, backend/.env.example, backend/Dockerfile, backend/.dockerignore, backend/app/__init__.py, backend/app/main.py, backend/app/config.py, backend/app/models.py, backend/app/storage/__init__.py, backend/app/storage/db.py, backend/app/storage/migrations.py, backend/app/routes/__init__.py, backend/app/routes/health.py, backend/tests/conftest.py, backend/tests/test_health.py, backend/tests/test_db.py, docker-compose.yml</files>
  <action>
Создать структуру проекта backend/ согласно ARCHITECTURE.md "Module Layout". Технологии — точно по PROJECT.md: Python 3.12, FastAPI, Pydantic v2, httpx, aiosqlite, pytest, ruff (никаких других веб-фреймворков, никаких ORM).

1. backend/pyproject.toml — pip-проект (НЕ poetry): зависимости fastapi>=0.115, pydantic>=2.9, pydantic-settings>=2.6, httpx>=0.27, aiosqlite>=0.20, uvicorn[standard]>=0.32, sse-starlette>=2.1. Dev: pytest, pytest-asyncio, pytest-cov, ruff, httpx (для тестов). Конфиг ruff в backend/ruff.toml (line-length 120, target py312, select E,F,W,I,UP,B). pytest config внутри pyproject.toml [tool.pytest.ini_options]: asyncio_mode=auto, testpaths=tests.

2. backend/.env.example — DATABASE_URL=sqlite+aiosqlite:////data/app.db, CORS_ORIGINS=http://localhost:3010, LOG_LEVEL=INFO, DEFAULT_LLM_ENDPOINT=https://api.openai.com/v1, APP_VERSION=0.1.0.

3. backend/app/config.py — класс Settings(BaseSettings) из pydantic-settings, читает .env, поля по списку выше. Функция get_settings() с lru_cache.

4. backend/app/models.py — Pydantic v2 модели ровно по контрактам из <interfaces>: ChatRequest, ChatSSEEvent (с полями event: str, data: dict), MCPPingResponse, HealthResponse, MCPConnection (id, name, endpoint, channel: str|None, anon_enabled: bool). Никаких лишних полей сверх контракта.

5. backend/app/storage/db.py — функции init_db() (открыть aiosqlite соединение, включить WAL mode pragma, прогнать apply_migrations), close_db(), get_db() (FastAPI dependency, возвращает соединение из app.state).

6. backend/app/storage/migrations.py — функция apply_migrations(db) с DDL ровно по ARCHITECTURE.md "Storage Schema" (4 таблицы: sessions, messages, mcp_connections, llm_settings) + таблица schema_version для идемпотентности. CREATE TABLE IF NOT EXISTS. Все timestamp через DEFAULT CURRENT_TIMESTAMP.

7. backend/app/main.py — FastAPI app, CORS middleware (allow_origins из Settings), lifespan asynccontextmanager (startup: init_db; shutdown: close_db), регистрация только health router в этой задаче (chat и mcp роутеры — в Task 2 и 3).

8. backend/app/routes/health.py — GET /health возвращает HealthResponse (проверяет SELECT 1 из БД), GET / возвращает {"name": "1c-analyst-backend", "version": settings.APP_VERSION}.

9. backend/Dockerfile — FROM python:3.12-slim, WORKDIR /app, COPY pyproject.toml ., RUN pip install --no-cache-dir -e ., COPY app ./app, EXPOSE 8010, CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8010"]. backend/.dockerignore — __pycache__, .pytest_cache, tests/, .env, *.db.

10. docker-compose.yml (в корне проекта, не в backend/) — version-less compose, service backend: build: ./backend, ports: "8010:8010", volumes: ["./data:/data"], env_file: ./backend/.env (если есть), restart: unless-stopped. Создать пустую папку data/ через volume — БД ляжет туда.

11. backend/tests/conftest.py — async fixture httpx.AsyncClient с ASGITransport(app=app), временная in-memory БД (DATABASE_URL override через monkeypatch), фикстура db. backend/tests/test_health.py — два теста: GET /health → 200, поле db == "ok"; GET / → 200, version совпадает. backend/tests/test_db.py — apply_migrations создаёт все 4 таблицы (запрос к sqlite_master), повторный вызов не падает (идемпотентность).

Использовать pydantic v2 синтаксис (model_config = ConfigDict(...), не class Config). httpx AsyncClient везде (не requests). НЕ использовать SQLAlchemy/Alembic — только сырой aiosqlite + DDL строкой (по решению из ARCHITECTURE: «SQLite via aiosqlite», без ORM). НЕ создавать models в стиле dataclass — только Pydantic.

Логирование — стандартный logging, format JSON-style минимально (timestamp level name message). Никаких структурированных логгеров (loguru/structlog).
  </action>
  <verify>
    <automated>cd backend && pip install -e . && pytest -x -v && ruff check . && cd .. && docker compose build backend &amp;&amp; docker compose up -d backend &amp;&amp; sleep 3 &amp;&amp; curl -fsS http://localhost:8010/health | grep -q '"status":"ok"' &amp;&amp; docker compose down</automated>
  </verify>
  <done>
    - `docker compose up backend` поднимает контейнер; `curl http://localhost:8010/health` → 200 + JSON {status, version, db:"ok"}
    - cold start (от docker run до первого 200 на /health) ≤ 2 сек на локальной машине (NFR-4)
    - SQLite файл создаётся в ./data/app.db с 4 таблицами + schema_version
    - pytest backend/tests/ — все тесты зелёные
    - ruff check . — ноль ошибок
  </done>
</task>

<task type="auto">
  <name>Task 2: LLM-клиент (OpenAI-compat streaming) + smoke /chat SSE</name>
  <files>backend/app/clients/__init__.py, backend/app/clients/llm.py, backend/app/routes/chat.py, backend/tests/test_llm_client.py, backend/tests/test_chat_route.py</files>
  <action>
Реализовать OpenAI-совместимый LLM-клиент со streaming и подключить минимальный /chat endpoint, который проксирует LLM поток в SSE (БЕЗ MCP, БЕЗ оркестратора, БЕЗ SQLite persistence — это Phase 2). Smoke-уровень: «POST /chat → SSE chunks из LLM пробрасываются клиенту».

1. backend/app/clients/llm.py — класс LLMClient:
   - __init__(endpoint: str, model: str, timeout: float = 60.0) — хранит httpx.AsyncClient с base_url
   - async def stream_chat_completion(messages: list[dict], api_key: str, tools: list[dict] | None = None, temperature: float = 0.3) → AsyncIterator[dict]
   - Отправляет POST {endpoint}/chat/completions с body {model, messages, stream: true, tools?, temperature}, header Authorization: Bearer {api_key}
   - Парсит SSE response (httpx stream='POST'): для каждой строки `data: ...`, json.loads, yield chunk. Останов на `data: [DONE]`.
   - Каждый chunk — это dict с choices[0].delta. Возможные поля delta: content (str), tool_calls (list with index, function.name, function.arguments — может приходить инкрементально частями).
   - aclose() для закрытия AsyncClient
   - Никакого retry — это Phase 3 (NFR-12). Только пробрасывать httpx.HTTPStatusError наверх.

2. backend/app/routes/chat.py — POST /chat:
   - Принимает ChatRequest body + header X-LLM-API-Key (если нет → 400 "missing api key")
   - Header X-LLM-Endpoint и X-LLM-Model опциональные, иначе settings defaults
   - НЕ читает session_id/channel_id из БД в этой фазе (это Phase 2 orchestrator). Просто строит messages=[{"role":"user","content": request.message}] и стримит LLM.
   - Использует sse_starlette.EventSourceResponse (или вручную StreamingResponse media_type="text/event-stream")
   - Async generator:
     - yield event=status data={"stage":"thinking"} немедленно (для NFR-1 first byte ≤ 500 мс)
     - async for chunk in llm.stream_chat_completion(...):
       - извлечь delta.content → yield event=delta data={"content": ...}
     - В конце yield event=done data={}
     - При исключении: yield event=error data={"message": str(e), "code": "llm_error"}
   - Формат SSE строки: f"event: {name}\ndata: {json.dumps(data)}\n\n"
   - Регистрировать router в backend/app/main.py.

3. backend/tests/test_llm_client.py — два теста:
   - test_stream_chat_completion_parses_content_chunks: мокировать httpx через httpx.MockTransport, вернуть SSE байт-поток с 3 chunks (data: {choices:[{delta:{content:"Hello"}}]} \n\n × 3 + data: [DONE]), проверить что yield дал 3 dict с content="Hello".
   - test_stream_chat_completion_handles_tool_calls: вернуть chunk с delta.tool_calls=[{index:0, function:{name:"foo", arguments:"{\"a\":1}"}}], проверить что yield этого chunk сохраняет tool_calls.
   Тесты — pytest-asyncio, никаких реальных сетевых вызовов.

4. backend/tests/test_chat_route.py — два теста:
   - test_chat_missing_api_key_returns_400: POST /chat без header → 400
   - test_chat_returns_sse_with_status_and_delta: подменить LLMClient (через app.dependency_overrides или monkeypatch) на стаб с фиксированными chunks, POST /chat → response.headers["content-type"].startswith("text/event-stream"), в теле есть `event: status` и `event: delta` и `event: done`.

Не использовать openai SDK (PROJECT.md упоминает его, но раздел «MCP Client: прямой HTTP» — стиль проекта прямой httpx). Если в будущем понадобится — обёртка LLMClient уже изолирует это решение.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; pytest tests/test_llm_client.py tests/test_chat_route.py -x -v &amp;&amp; ruff check app/clients/llm.py app/routes/chat.py</automated>
  </verify>
  <done>
    - LLMClient.stream_chat_completion парсит SSE из OpenAI-compat endpoint и отдаёт chunks
    - POST /chat (с заглушкой LLM) возвращает SSE поток с events status → delta(×N) → done
    - First byte (event=status) ≤ 500 мс после запроса (NFR-1) — измеримо в тесте через `await anext(generator)` сразу после старта
    - Все тесты зелёные, ruff clean
  </done>
</task>

<task type="auto">
  <name>Task 3: MCP клиент (Streamable HTTP) + /mcp/{id}/ping</name>
  <files>backend/app/clients/mcp.py, backend/app/routes/mcp.py, backend/tests/test_mcp_client.py, backend/tests/test_mcp_route.py</files>
  <action>
Реализовать MCP Streamable HTTP клиент по спецификации из .planning/intel/MCP_INTEGRATION.md (если файл противоречит — приоритет ARCHITECTURE.md). Smoke-эндпоинт ping подтверждает что транспорт работает.

1. backend/app/clients/mcp.py:
   - dataclass/Pydantic MCPSession: session_id: str, mcp_version: str, server_name: str, tools: list[dict] (cached schema)
   - class MCPClient:
     - __init__(endpoint: str, headers: dict | None = None, timeout: float = 30.0)
     - _request_id: int счётчик (инкремент для каждого jsonrpc id)
     - async def initialize() → MCPSession:
        POST {endpoint} body={"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","clientInfo":{"name":"1c-analyst","version":"0.1.0"},"capabilities":{}}}
        Headers: Accept: application/json, text/event-stream; Content-Type: application/json
        Из response header взять Mcp-Session-Id, сохранить в self.session_id
        Парсить body (может быть application/json или SSE — поддержать оба: если content-type=text/event-stream — собрать первый JSON-RPC event, иначе response.json())
        Вернуть MCPSession(session_id, result.protocolVersion, result.serverInfo.name, tools=[])
     - async def list_tools() → list[dict]:
        Требует initialize() уже выполнен. POST с header Mcp-Session-Id, method=tools/list. Вернуть result.tools.
        Сохранить в self._tools_cache.
     - async def call_tool(name: str, arguments: dict) → dict:
        POST с Mcp-Session-Id, method=tools/call, params={name, arguments}. Вернуть result (содержит content array).
     - async def close() — httpx aclose
   - Все ошибки JSON-RPC (response.error) → raise MCPError(code, message)

2. backend/app/routes/mcp.py — POST /mcp/{conn_id}/ping:
   - В Phase 1 conn_id игнорируется (нет ещё CRUD connections — это Phase 2.4). Берём endpoint из query/header:
     - Header X-MCP-Endpoint (для тестов) ИЛИ query параметр endpoint=
     - Если не передан → 400
   - Создать MCPClient(endpoint), initialize(), list_tools(), измерить total duration_ms, aclose()
   - Вернуть MCPPingResponse(mcp_version, tool_count=len(tools), session_id, duration_ms)
   - Регистрировать router в backend/app/main.py.

3. backend/tests/test_mcp_client.py:
   - test_initialize_extracts_session_id_from_header: httpx.MockTransport вернёт {result:{protocolVersion:"2025-03-26",serverInfo:{name:"test"}}} + header Mcp-Session-Id=test-sid. Проверить client.session_id=="test-sid".
   - test_list_tools_uses_session_id: проверить что в request headers есть Mcp-Session-Id из сохранённого.
   - test_initialize_handles_sse_response: MockTransport возвращает text/event-stream body с одним event=message и data=<json-rpc result>. Парсер должен извлечь result корректно.
   - test_call_tool_raises_on_jsonrpc_error: response = {"jsonrpc":"2.0","id":3,"error":{"code":-32601,"message":"method not found"}} → raises MCPError.

4. backend/tests/test_mcp_route.py:
   - test_ping_missing_endpoint_returns_400
   - test_ping_returns_tool_count: monkeypatch MCPClient на стаб, POST /mcp/test/ping → 200 + JSON с tool_count и session_id.

Никаких WebSocket. Никакого stdio transport. Только Streamable HTTP (один POST endpoint, ответ либо JSON либо SSE) — IR-2.
  </action>
  <verify>
    <automated>cd backend &amp;&amp; pytest tests/test_mcp_client.py tests/test_mcp_route.py -x -v &amp;&amp; ruff check app/clients/mcp.py app/routes/mcp.py</automated>
  </verify>
  <done>
    - MCPClient.initialize() выполняет JSON-RPC initialize и сохраняет Mcp-Session-Id из header (IR-5)
    - MCPClient.list_tools() возвращает schema discovery (IR-3)
    - MCPClient.call_tool() выполняет JSON-RPC tools/call (IR-4)
    - POST /mcp/{conn_id}/ping → 200 с {mcp_version, tool_count, session_id, duration_ms}
    - Все тесты MCP зелёные, ruff clean
    - Полный pytest всего backend проходит (зелёные test_health + test_db + test_llm_client + test_chat_route + test_mcp_client + test_mcp_route)
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Browser → Backend | Аналитик может слать произвольный JSON в /chat и /mcp/*/ping; backend должен валидировать через Pydantic |
| Backend → LLM Provider | API ключ берётся из header X-LLM-API-Key, форвардится одноразово, НЕ персистится в БД |
| Backend → MCP Server | MCP endpoint указывает аналитик; обычно localhost но может быть удалённым с auth headers |
| Backend → SQLite | Файл лежит в volume ./data; в Phase 1 в БД пишется только schema; никаких user-controlled SQL пока нет |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01 | Information Disclosure | LLM API key в логах/ошибках | mitigate | LLMClient не логирует Authorization header; pytest проверяет что str(LLMClient) не содержит api_key; в SSE event=error не пробрасывать exception args без фильтрации (только code+message) |
| T-01-02 | Tampering | CORS — произвольный origin может пытаться обратиться к localhost:8010 | mitigate | CORS allow_origins=Settings.CORS_ORIGINS (default только http://localhost:3010), allow_credentials=true; не использовать "*" (NFR-8) |
| T-01-03 | Spoofing | Backend проксирует к произвольному endpoint в LLM/MCP клиентах | accept | В MVP это by design (аналитик сам указывает endpoints). В Phase 3 — добавить allowlist; пока accept |
| T-01-04 | Denial of Service | Streaming endpoint /chat может висеть бесконечно если LLM не закроет поток | mitigate | httpx timeout=60.0 на LLMClient; sse_starlette уже корректно закрывает connection при client disconnect |
| T-01-05 | Information Disclosure | SQLite файл доступен любому процессу с правами на ./data | accept | Local-first приложение, БД содержит только sessions/messages пользователя, никаких credentials (API ключи только в localStorage). Mitigation = ОС-level права на volume |
| T-01-06 | Tampering | SQL injection через будущие user inputs | mitigate | В Phase 1 нет user-controlled SQL; миграции — статические DDL; в Phase 2 storage слой обязан использовать параметризованные запросы aiosqlite (?, не f-string) |
| T-01-07 | Repudiation | Нет аудита кто и когда дёргал /chat | accept | Single-user local-first приложение; аудит — это enterprise feature вне MVP |
| T-01-08 | Elevation of Privilege | Pydantic валидация легко обходится если строгий режим не включён | mitigate | Все модели — pydantic v2 с model_config = ConfigDict(extra="forbid") |
</threat_model>

<verification>
1. `cd backend && pip install -e . && pytest -x -v` — все тесты зелёные
2. `cd backend && ruff check .` — ноль нарушений
3. `docker compose build backend && docker compose up -d backend` — контейнер поднимается
4. `curl -fsS http://localhost:8010/health` → `{"status":"ok","version":"0.1.0","db":"ok"}`
5. `curl -fsS http://localhost:8010/` → JSON с name + version
6. Cold start: `time docker compose restart backend && time curl --retry 10 --retry-delay 1 -fsS http://localhost:8010/health` — общее время ≤ 2 сек (NFR-4)
7. SSE smoke (с заглушкой LLM в режиме test): `curl -N -X POST http://localhost:8010/chat -H "Content-Type: application/json" -H "X-LLM-API-Key: test" -d '{"message":"hi"}'` — поток содержит `event: status`, `event: delta`, `event: done`
8. Контракт MCP ping (с заглушкой endpoint): pytest test_mcp_route.py зелёный — POST /mcp/test/ping возвращает tool_count
9. SQLite файл `./data/app.db` создан, 5 таблиц (sessions, messages, mcp_connections, llm_settings, schema_version)
10. `docker compose down` — корректное завершение, БД сохраняется в volume
</verification>

<success_criteria>
- `docker compose up backend` поднимает FastAPI на :8010 за ≤ 2 сек до первого 200 на /health (NFR-4)
- GET /health возвращает 200 с {status, version, db} (IR-7)
- POST /chat принимает X-LLM-API-Key и стримит SSE минимум events status/delta/done; первый byte ≤ 500 мс (NFR-1, FR-7)
- POST /mcp/{conn_id}/ping выполняет MCP initialize + tools/list и возвращает {mcp_version, tool_count, session_id} (IR-2, IR-3, IR-4, IR-5)
- LLMClient и MCPClient покрыты unit-тестами на mock-транспорте; coverage ≥ 70% (двигаемся к NFR-18=80% к концу M3)
- pytest зелёный (все 6 test файлов), ruff clean
- API ключи нигде не персистятся (T-01-01 закрыт): grep по backend/ не находит persist логики для api_key
- CORS настроен на http://localhost:3010 (T-01-02, NFR-8)
- Pydantic модели с extra="forbid" (T-01-08)
</success_criteria>

<output>
После завершения создать `.planning/phases/01-foundation/01-01-SUMMARY.md` со списком созданных файлов, реальными командами для запуска (`docker compose up backend`, `curl /health`, `curl -N /chat ...`, `curl /mcp/.../ping`), измеренным cold-start временем, статусом pytest и ruff.
</output>
