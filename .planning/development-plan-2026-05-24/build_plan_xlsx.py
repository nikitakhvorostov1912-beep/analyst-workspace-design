# -*- coding: utf-8 -*-
"""Build the development plan Excel for 1С Аналитик (v1.4.5)."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

OUT = r"C:/CLOUDE_PR/projects/analyst-workspace-design/.planning/development-plan-2026-05-24/План_развития_1С_Аналитик_2026-05-24.xlsx"

# ---- Палитра серьёзности -----------------------------------------------------
SEV = {
    "CRITICAL": ("FFB91C1C", "FFFFFFFF"),  # red bg / white text
    "HIGH":     ("FFEA580C", "FFFFFFFF"),  # orange bg / white
    "MEDIUM":   ("FFCA8A04", "FFFFFFFF"),  # amber bg / white
    "LOW":      ("FF374151", "FFFFFFFF"),  # slate bg / white
    "INFO":     ("FF1F2937", "FFFFFFFF"),
}

# ---- Финдинги ----------------------------------------------------------------
# Поля:
# id | category | severity | subject | description | location |
# problem_solved | proposed_fix | effort | days | quarter |
# in_user_backlog | dependencies | impact | source_agent | comment
FINDINGS = [
    # ============================ DOCUMENTATION & STATE ============================
    ("DOC-1", "Документация", "HIGH",
     "ARCHITECTURE.md устарел на 7 версий БД и 2 milestone",
     "Описывает Phase 3 (10 tools, schema v3). Реально проект в M7 с Hermes (Memory + Skills + Curator + 30 фич), schema_version=10 в migrations.py:77. Нет упоминаний: mcp_pool, sql_validator, learning/, memory/, security/, skills/ — 10+ модулей без архитектурного описания.",
     "ARCHITECTURE.md:58 vs migrations.py:77",
     "Любой новый разработчик (или сам через полгода) онбордится по неверной карте. Тимлид/контрактник тратит часы на 'что устарело'.",
     "Полная ревизия ARCHITECTURE.md под M6/M7. Описать orchestrator/learning/memory/security/skills модули. Добавить раздел Schema Evolution v3→v10 с миграциями. Сделать процесс: при бампе CURRENT_VERSION — обязательно patch ARCHITECTURE.md.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Снижает онбординг с 5 дней до 1. Критично перед наймом/передачей.",
     "architect", ""),

    ("DOC-2", "Документация", "MEDIUM",
     "STATE.md заявляет loop.py 689 строк, реально 1506",
     "STATE.md (строка 98) фиксирует 'P1.2 phase 3 step 3 — 870 → 689 строк (-181)'. Реальный `wc -l backend/app/orchestrator/loop.py` = 1506. Сама функция `run_chat_loop` = 688 строк (819-1507). Заявление написано про сокращение функции, но прочитывается как сокращение файла.",
     "STATE.md:98 vs loop.py wc -l",
     "Брутальная честность нарушена в собственном документе проекта. При переговорах с клиентом/партнёром цифры из STATE.md могут быть проверены — попадание = удар по доверию.",
     "Переписать формулировку в STATE.md: 'функция run_chat_loop 870→688 строк, файл 1506 строк'. Завести правило: ревью STATE.md перед каждым релизом.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Доверие пользователя/инвестора, чистота метрик.",
     "architect", ""),

    ("DOC-3", "Документация", "MEDIUM",
     "BACKLOG-POST-MVP.md устарел (Phase 4, до Hermes)",
     "Создан 2026-05-15 до Hermes integration. Многие пункты уже сделаны (rate-limit, drill-down ссылки) или устарели (Vector RAG отложено в пользу Hermes Memory + Skills). Файл больше дезинформирует, чем помогает.",
     ".planning/BACKLOG-POST-MVP.md:1-71",
     "Любая попытка спланировать sprint по этому backlog приведёт к дублированию работы или к фокусу на уже устаревшем.",
     "Архивировать как `BACKLOG-PRE-HERMES-2026-05-15.md` + создать новый BACKLOG-M8.md с актуальными пунктами из этого Excel-плана.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "DOC-1", "Гигиена планирования.",
     "claude", ""),

    # ============================ ARCHITECTURE ============================
    ("ARCH-1", "Архитектура", "HIGH",
     "God-функция run_chat_loop 688 строк, 6 уровней вложенности",
     "loop.py:819-1507. Делает: init 8 зависимостей, system prompt build, main while, обработка tool calls, компрессия, clarify/confirm/interrupt/todo routing, persist card states, auto-title, memory sync, skill review. Каждая новая фича (attachments, vision, sql_validator) добавляется inline. P1.2 'decompose' зафиксирован Done, но цель ≤400 строк не достигнута (TD-1 в POST-RELEASE-DEBT.md).",
     "loop.py:819-1507",
     "Тестировать unit-тестом невозможно — только интеграция. Каждая новая фича увеличивает risk регрессий. Debug сложен — стек глубиной 6 уровней.",
     "Завершить P1.2 phase 2/3 по плану в POST-RELEASE-DEBT.md TD-1: `_handle_internal_tool`, `_handle_mcp_tool`, `LoopContext` dataclass. Атомарные коммиты, полный pytest после каждого.",
     "L", 5, "Q3 2026", "Да (TD-1)", "—",
     "Снижает risk регрессий в основном пайплайне на 80%. Critical для maintenance.",
     "architect, code-reviewer", ""),

    ("ARCH-2", "Архитектура", "HIGH",
     "Module-level global state: _pending, INTERRUPTS, CLARIFY",
     "3 singleton'а живут в памяти процесса: safety.py:153 `_pending: dict`, interrupt.py:89 `INTERRUPTS = InterruptRegistry()`, clarify.py:108 `CLARIFY = ClarifyRegistry()`. Process-level, не request-scoped. При multi-worker uvicorn (или 2+ pod) interrupt/confirm/clarify из request A не найдут ответ из B.",
     "safety.py:153, interrupt.py:89, clarify.py:108",
     "Блокирует горизонтальное масштабирование backend. В Electron single-process — незаметно, в production multi-worker — race condition гарантирован.",
     "Перевести на asyncio-native структуры с TTL очисткой. Либо contextvars.ContextVar для per-request scope. Перед multi-tenant deploy — обязательное условие.",
     "M", 2, "Q3 2026", "Да (W2.2)", "ARCH-1",
     "Открывает дверь к multi-tenant / corporate self-hosted deploy.",
     "architect", ""),

    ("ARCH-3", "Архитектура", "HIGH",
     "Multi-tenant изоляция per-session, не per-channel/user",
     "persistence.py не фильтрует `load_history_for_llm` по channel_id, только по session_id. SkillStore и Memory per-channel — правильно. Но при self-hosted multi-user разные аналитики имеют общий SQLite без user-level разграничения.",
     "persistence.py, loop.py:914",
     "PROJECT.md фиксирует single-user only как Non-Goal MVP. Commerce-readiness требует явного решения: либо disclaimer в docs, либо user_id в schema.",
     "Краткосрочно: явный disclaimer в README + блокирующая проверка в backend если ENVIRONMENT=prod. Долгосрочно: schema migration v11 с user_id (FK), RLS через WHERE user_id = current_user_id.",
     "L", 5, "Q4 2026", "Да (W2.2)", "ARCH-2",
     "Без этого закрыта дверь к 'team-tier' (TEAM 4900 руб./мес. в pricing recommendation).",
     "architect, security-reviewer", ""),

    ("ARCH-4", "Архитектура", "MEDIUM",
     "schedule_review получает закрытый httpx client",
     "loop.py:1492-1500 schedule_review(aux_client=aux_compressor_client) вызывается ПОСЛЕ `finally: aux_compressor_client.aclose()` (строка 1415). Fire-and-forget через asyncio.create_task — background task получает уже-закрытый client.",
     "loop.py:1492-1500, 1415",
     "Тихие ошибки в skill learning pipeline. Skills могут не сохраняться без alert.",
     "Создать отдельный aux client для schedule_review, либо защёлкнуть aux_compressor_client.aclose() как `done_callback` после schedule_review.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Чистота background pipeline + предотвращение скрытых регрессий.",
     "architect", ""),

    ("ARCH-5", "Архитектура", "MEDIUM",
     "TodoRegistry in-memory не выживает restart",
     "routes/skills.py:214,227,252 `TODOS` (in-memory `TodoRegistry`) сбрасывается при каждом рестарте backend. Аналитик теряет все todos при автообновлении Electron.",
     "routes/skills.py:214",
     "UX-deal-breaker для долгоживущих todos. Аналитик заводит TODO в сессии, перезапускает приложение — todo пропали.",
     "Persistence layer: новая таблица `session_todos` (session_id, item_id, content, status, created_at). Уже есть `todo.py` модуль — добавить save/load.",
     "L", 5, "Q4 2026", "Нет (новое)", "—",
     "Сохраняет user trust в фичу todos.",
     "code-reviewer", ""),

    # ============================ SECURITY ============================
    ("SEC-1", "Безопасность", "CRITICAL",
     "SSRF: нет валидации пользовательского MCP endpoint",
     "Пользователь вводит произвольный URL в MCP endpoint. MCPClient нормализует localhost→127.0.0.1 но не блокирует http://169.254.169.254/ (AWS metadata), http://192.168.1.1, http://127.0.0.1:6379/ (Redis). DNS rebinding: evil.com→169.254.169.254 проходит первый check.",
     "routes/connections.py:128-186, clients/mcp.py:65-90",
     "В корп-сети где backend имеет доступ к интранет-сервисам — RCE/exfiltration через SSRF. Для desktop-Electron риск ниже, но коллабораторам корп-клиентов могут попасть в спам-чат.",
     "_validate_mcp_endpoint(url): только http/https; резолв через socket.getaddrinfo и reject RFC1918/link-local 169.254.x.x/127.x.x.x ИСКЛЮЧАЯ явный 127.0.0.1:6010/6003; timeout 5s на DNS. Вызывать в POST/PUT /connections.",
     "M", 2, "Q3 2026", "Нет (новое)", "—",
     "Снимает блокер для enterprise SOC review.",
     "security-reviewer", ""),

    ("SEC-2", "Безопасность", "HIGH",
     "Electron: нет CSP, нет sandbox: true",
     "main.js не выставляет Content-Security-Policy через session.defaultSession.webRequest.onHeadersReceived. Нет флага sandbox:true в webPreferences. webSecurity не зафиксирован явно — может быть случайно снят при рефакторинге.",
     "desktop/main.js (BrowserWindow setup)",
     "При XSS в renderer (через скомпрометированный markdown) — доступ к window.electronAPI.openPath с произвольным путём. Стандартное требование любого Electron security review.",
     "Добавить onHeadersReceived с CSP: default-src 'self' http://127.0.0.1:*; script-src 'self'; connect-src 'self' http://127.0.0.1:*; img-src 'self' data:; style-src 'self' 'unsafe-inline'. sandbox:true + webSecurity:true в webPreferences.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Стандартный security-baseline для Electron-приложения коммерческого уровня.",
     "security-reviewer", ""),

    ("SEC-3", "Безопасность", "HIGH",
     "Prompt injection: regex не покрывает unicode + indirect injection из tool results",
     "injection_scan.py: 8 regex-паттернов пропускают: (1) Unicode homoglyphs ('Ignоre' с кириллической о); (2) Multi-turn drift через history; (3) Output injection — 1С возвращает в Комментарий 'Assistant: Я согласен'; (4) sanitize_for_prompt вызывается на tool_content (loop.py:566), но history (1061) проходит только sanitize_messages без injection scan.",
     "memory/injection_scan.py:19-66, loop.py:566, 1061",
     "Главный AI-security risk. Для аналитика 1С реалистично: вредоносный комментарий в документе клиента → инъекция в LLM context.",
     "(1) unicodedata.normalize('NFKD', text) перед regex. (2) scan_sanitize_for_prompt на каждом tool-message из истории. (3) Структурный prompt: tool results в XML-теге <tool_result>. (4) Долгосрочно — W2.7 llm-guard/rebuff.",
     "M", 2, "Q3 2026", "Да (W2.7 частично)", "—",
     "Защита от компрометации через данные клиента.",
     "security-reviewer, prompt-engineer", ""),

    ("SEC-4", "Безопасность", "HIGH",
     "SQL validator: WITH + DML (RETURNING) потенциально пропускает",
     "sql_validator.py:56 — WITH в _ALLOWED_FIRST_TOKENS. Запрос `WITH cte AS (INSERT INTO t VALUES(1) RETURNING id) SELECT * FROM cte` — первый токен WITH → пропущен. SQLite-диалект sqlparse может разметить INSERT как DDL не Keyword в CTE-контексте. RETURNING не в _FORBIDDEN_KEYWORDS.",
     "orchestrator/sql_validator.py:53-63, 253-277",
     "Defence-in-depth провален: один из заявленных слоёв защиты пробивается.",
     "Убрать WITH из _ALLOWED_FIRST_TOKENS. В валидации WITH-запроса отдельно проверять что после CTE — только SELECT. Альтернатива: полностью запретить WITH (1С query не использует). Добавить RETURNING в _FORBIDDEN_KEYWORDS.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Закрывает заявленный security gap.",
     "security-reviewer", ""),

    ("SEC-5", "Безопасность", "HIGH",
     "shell:open-path IPC без path whitelist",
     "main.js:239-247 — ipcMain.handle('shell:open-path', ...) принимает targetPath из renderer без проверки что путь внутри userData/appData. При XSS или компрометации preload.js атакующий может передать C:\\Windows\\System32\\cmd.exe или \\\\attacker-smb\\share\\malware.exe — shell.openPath откроет в проводнике (UNC-path execution риск).",
     "desktop/main.js:239-247",
     "Path traversal через IPC. Один из стандартных Electron-attack vectors.",
     "Whitelist: разрешать только пути в app.getPath('userData') и app.getPath('logs'). Все остальное — return 'path not allowed'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Полное закрытие IPC-attack surface.",
     "security-reviewer", ""),

    ("SEC-6", "Безопасность", "HIGH",
     "Rate-limit per-IP + allow_headers wildcard с credentials",
     "main.py allow_headers:['*'] с allow_credentials:True — нарушение CORS-spec (некоторые Chromium-версии могут пропускать). slowapi `get_remote_address` спуфится через X-Forwarded-For если когда-либо появится reverse proxy без trusted_hosts.",
     "main.py:103, routes/chat.py:57",
     "CSRF surface расширена; в будущем — bypass rate-limit при reverse proxy.",
     "allow_headers заменить явным списком: ['Content-Type','X-LLM-API-Key','X-LLM-Endpoint','X-LLM-Model','X-Anon-Enabled','X-Confirm-Reset']. Добавить TRUST_PROXY=0 guard в Electron.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Compliance baseline для CORS strict.",
     "security-reviewer", ""),

    ("SEC-7", "Безопасность", "HIGH",
     "admin/reset-local-db без auth + без rate-limit",
     "Единственная защита — header X-Confirm-Reset:true. Любой с доступом к backend-порту (если пользователь сделает ngrok / в корп-сети где Electron открыт через RDP) может стереть все сессии. mcp_connections не в RESET_TABLES — инконсистентность.",
     "routes/admin.py:31-67",
     "Уничтожение данных пользователя через простой POST. Bypass через ошибку конфигурации.",
     "Rate-limit 3/hour. Одноразовый CSRF-токен из UI state. Добавить mcp_connections в RESET_TABLES (или явно объяснить почему нет).",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Hardening критичного destructive endpoint.",
     "security-reviewer", ""),

    ("SEC-8", "Безопасность", "MEDIUM",
     "AES-GCM: .app-secret без ACL на Windows + нет ротации ключа",
     "user_secrets_crypto.py:107 os.chmod(tmp, 0o600) — на Windows silently игнорируется ACL. .app-secret в %APPDATA% читается любым процессом этого пользователя. Нет механизма ротации: при компрометации — пользователь вручную удаляет файл.",
     "security/user_secrets_crypto.py:78-112",
     "Vulnerability windows: малware под текущим пользователем читает .app-secret и получает доступ ко всем LLM ключам клиента.",
     "(1) На Windows: win32security/icacls для ACL только текущему пользователю. (2) Endpoint /admin/rotate-secret. (3) Долгосрочно — рассмотреть DPAPI (Windows Data Protection API) как замену файлу с ключом.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Hardening encrypted storage до enterprise-grade.",
     "security-reviewer", ""),

    ("SEC-9", "Безопасность", "MEDIUM",
     "Trajectory JSONL: PII без redact и без retention",
     "memory_integration.py:38-40, loop.py:1471 — trajectory-лог пишется при learning_enabled=True. Содержит полные user-messages и LLM-ответы с ИНН контрагентов, суммами, ФИО. redact.py применяется к логам ошибок, не к trajectory. Файлы растут бесконечно.",
     "orchestrator/memory_integration.py:38, loop.py:1471",
     "152-ФЗ нарушение: персональные данные хранятся неструктурированно без срока. При прокидывании trajectory наружу (для обучения / отправки разработчику) — leak PII.",
     "(1) redact(json.dumps(turn)) перед записью. (2) Retention: удалять JSONL старше N дней (env). (3) UI toggle с явным предупреждением. (4) Документировать в privacy policy.",
     "M", 2, "Q3 2026", "Нет (новое)", "—",
     "152-ФЗ compliance для аналитика, работающего с РФ-клиентскими базами.",
     "security-reviewer", ""),

    ("SEC-10", "Безопасность", "MEDIUM",
     "Attachment upload: MIME не верифицируется + ZIP-bomb риск в DOCX/XLSX",
     "attachments.py:147-228 — mime берётся из запроса (user-supplied) или из расширения. malicious.pdf с ZIP-содержимым (полиглот) пройдёт в pypdf. openpyxl.load_workbook(read_only=True) не защищён от decompression bomb — 1MB XLSX → 500MB RAM. base64.b64decode без validate=True пропускает невалидные символы.",
     "orchestrator/attachments.py:147-228",
     "DoS через ZIP-bomb. Exploit через полиглот файл.",
     "(1) Magic bytes первые 16 байт перед extractor (PDF: %PDF, DOCX/XLSX: PK\\x03\\x04). (2) base64.b64decode(..., validate=True). (3) zipfile.ZipFile с проверкой суммарного размера unzipped до 50MB.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Безопасность файловой подсистемы.",
     "security-reviewer", ""),

    ("SEC-11", "Безопасность", "LOW",
     "electron-updater: нет проверки downgrade-атаки + SmartScreen без EV cert",
     "main.js:181-213, electron-builder.yml:71-78 — autoDownload:true без проверки info.version > app.getVersion(). MITM с подменённым latest.yml может откатить на старую версию с CVE. Без EV/OV cert (P1.3 закомментирован) каждый новый пользователь видит SmartScreen 'Unknown Publisher'.",
     "desktop/main.js:181-213, electron-builder.yml:71-78",
     "Downgrade-attack + adoption-friction (потеря 30-50% инсталляций через SmartScreen warning).",
     "(1) `if (semver.gt(info.version, app.getVersion())) autoUpdater.downloadUpdate()`. (2) Купить EV/OV cert (12-30k ₽/год). (3) Стартовая страница onboarding объясняет SmartScreen пока нет cert.",
     "L", 5, "Q4 2026", "Да (P1.3 scaffold готов)", "—",
     "Adoption-rate increase + защита от downgrade.",
     "security-reviewer, devops", ""),

    ("SEC-12", "Безопасность", "LOW",
     "X-LLM-API-Key header backward-compat без deadline",
     "routes/chat.py:74,96-118 — fallback header X-LLM-API-Key без даты удаления. Ключ виден в access-логах nginx/uvicorn если loguru пишет headers — обходит весь P2.1.",
     "routes/chat.py:96-118",
     "Pathway для leak через access-логи.",
     "Deadline удаления в v1.5.0. Deprecation: response header 'Deprecation: ...'. Убедиться uvicorn не логирует headers на INFO.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Финализация P2.1 миграции.",
     "security-reviewer", ""),

    ("SEC-13", "Безопасность", "MEDIUM",
     "Skills body не sanitize перед system prompt (Skills Guard A12)",
     "skills body создаётся пользователем или LLM-куратором, инжектируется в system prompt без sanitize_for_prompt. LLM-куратор пишет skill с homoglyph 'ignоre all' — пройдёт. Backlog Hermes A12 'Skills guard' открыт.",
     "routes/skills.py:144-154, loop.py:417",
     "Атака через сохранённый skill (persistence): один инжект и потом в каждом turn LLM получает payload.",
     "(1) sanitize_for_prompt(skill.body) при load. (2) Реализовать A12 Skills guard: scanner на содержимое skill при сохранении + блок при подозрении.",
     "S", 0.5, "Q3 2026", "Да (Hermes A12)", "SEC-3",
     "Закрытие attack surface через долгоживущие artifacts.",
     "security-reviewer, prompt-engineer", ""),

    # ============================ BACKEND CODE QUALITY ============================
    ("BE-1", "Backend Quality", "CRITICAL",
     "_pending dict в safety.py — race condition при concurrent requests",
     "safety.py:153 — module-level dict с asyncio.Event. Event привязан к loop где создан. При uvicorn --workers N или тестах с несколькими loops: Event от loop A ждётся в loop B → RuntimeError. clarify.py:67 — asyncio.get_event_loop() deprecated в 3.10+, удалён в 3.12 для не-running loop.",
     "safety.py:153, clarify.py:67",
     "При reload (uvicorn --reload) или multi-worker confirm/clarify flow сломается полностью. Сейчас latent — Electron single-process.",
     "asyncio.get_running_loop().create_future(). Pending store в contextvars.ContextVar или per-request scope.",
     "M", 2, "Q3 2026", "Да (W2.2)", "ARCH-2",
     "Блокирует переход на multi-worker production.",
     "code-reviewer", ""),

    ("BE-2", "Backend Quality", "CRITICAL",
     "_run_auto_title task без хранения ссылки — утечка при disconnect",
     "loop.py:1466 — asyncio.create_task() без хранения ссылки. При закрытии SSE (browser tab close, AbortController) до запуска task — Python GC может его собрать. db connection в closure — может быть закрыт к моменту выполнения.",
     "loop.py:1466",
     "Тихая потеря auto-title для сессий с быстрым disconnect.",
     "_tasks = set(); t = asyncio.create_task(...); _tasks.add(t); t.add_done_callback(_tasks.discard). Передавать db параметром, не через closure.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Stability в кратких сессиях.",
     "code-reviewer", ""),

    ("BE-3", "Backend Quality", "HIGH",
     "Silent failures в loop.py — message_id='unknown'",
     "loop.py:1447-1449 — except Exception: logger.exception('Ошибка сохранения...') + message_id = 'unknown'. Пользователь получает done event с message_id='unknown', frontend молча работает с битым id. loop.py:1499-1500: except Exception: logger.debug(...) для schedule_review — debug уровень скрывает регрессии learning pipeline.",
     "loop.py:873, 1447-1449, 1499-1500",
     "Тихие потери данных в production. Бага в save_assistant_message не дойдёт до alert.",
     "Типизировать исключения где возможно. message_id='unknown' → явный error SSE event. logger.debug → logger.warning для learning failures. Sentry/Logfire integration для критичных catch.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Observability + защита от data loss.",
     "code-reviewer", ""),

    ("BE-4", "Backend Quality", "HIGH",
     "CLARIFY registry leak при GeneratorExit",
     "loop.py:1338-1349 — при закрытии SSE GeneratorExit → CancelledError. CLARIFY.cancel вызывается только при TimeoutError|CancelledError изнутри asyncio.wait_for. GeneratorExit поднимается ДО wait_for. PendingClarify остаётся в CLARIFY._items навсегда. active_count растёт.",
     "loop.py:1338-1349",
     "Memory leak: каждый прерванный clarify накапливается до restart.",
     "try/finally вокруг asyncio.wait_for с гарантированным CLARIFY.cancel(clarify_id) в finally.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Long-running stability.",
     "code-reviewer", ""),

    ("BE-5", "Backend Quality", "HIGH",
     "_TOOL_FOR_CARD_TYPE — magic mapping, теряет args при 2+ execute_query",
     "loop.py:367-374 — dict {'log':'get_event_log','table':'execute_query',...}. Если один turn содержит 2 execute_query с разными args, берётся первый (break:681). Для второй таблицы card_state сохраняется с args первого → load-more вернёт неверные данные.",
     "loop.py:367-374, 681",
     "Баг load-more: пользователь нажимает 'показать больше' на 2-й таблице, видит данные 1-й.",
     "Хранить tool_call_id в card.payload и матчить по нему, не по имени инструмента.",
     "M", 2, "Q3 2026", "Нет (новое)", "—",
     "Корректность load-more для multi-table ответов.",
     "code-reviewer", ""),

    ("BE-6", "Backend Quality", "HIGH",
     "SQLite write contention — commit() на каждое save_*",
     "persistence.py — save_user_message, save_assistant_message, touch_session, save_card_state, update_session_title — каждая отдельный commit(). save_card_state в цикле (loop.py:664-701) — commit per card. WAL = один writer. При concurrent SSE стриминге очередь write locks.",
     "persistence.py multiple, loop.py:664-701",
     "Latency роста при длинных сессиях. SQLite — bottleneck при 2+ открытых вкладках.",
     "Батчить save_card_state — один commit() после цикла. Контекстный менеджер `async with db.execute_many()`. Долгосрочно — выделенный write connection.",
     "M", 2, "Q3 2026", "Нет (новое)", "PERF-3",
     "Снижение write-latency на 30-60% при цепочках карточек.",
     "code-reviewer, perf", ""),

    ("BE-7", "Backend Quality", "MEDIUM",
     "_parse_updated_at — fallback datetime.now() маскирует битые данные",
     "persistence.py:130-140 — при непарсируемой дате возвращает datetime.now(). Сессии с битой датой всегда в группе 'today' в list_sessions_grouped. Пользователь не видит что данные испорчены.",
     "persistence.py:130-140",
     "Тихая порча данных скрыта от пользователя.",
     "raise или return None. Вызывающий код обрабатывает явно (показывает badge 'дата неизвестна').",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Data integrity visibility.",
     "code-reviewer", ""),

    ("BE-8", "Backend Quality", "MEDIUM",
     "MIGRATIONS_V9 после V10 — порядок файла нарушен",
     "migrations.py: CURRENT_VERSION=10 на строке 77, MIGRATIONS_V9 на строке 214, MIGRATIONS_V10 на строке 202. Не влияет на runtime — но усложняет аудит миграций (можно пропустить V9 при review V10).",
     "storage/migrations.py:77, 202, 214",
     "Risk maintenance: при добавлении V11 разработчик не знает где её писать.",
     "Реорганизовать в хронологическом порядке: V1, V2, ..., V10, V11. CURRENT_VERSION — последним.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Гигиена migration history.",
     "code-reviewer", ""),

    ("BE-9", "Backend Quality", "MEDIUM",
     "InterruptRegistry: threading.Lock в async — GIL contention",
     "interrupt.py:36 — threading.Lock в asyncio loop не блокирует loop (lock без I/O), но смешение примитивов. При высокой частоте should_interrupt (после каждого chunk) — GIL overhead. Правильно — plain set (CPython atomic set.add/discard/in под GIL).",
     "orchestrator/interrupt.py:36",
     "Перформанс при стримминге 50+ chunks/сек.",
     "Убрать threading.Lock, использовать plain set.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "ARCH-2",
     "Снижение overhead на горячем пути.",
     "code-reviewer, perf", ""),

    ("BE-10", "Backend Quality", "MEDIUM",
     "MCPConnectionCreate.validate_endpoint — classmethod без @field_validator",
     "models.py:84-87 — @classmethod не вызывается Pydantic v2 как validator. Реальная валидация в model_post_init. Public classmethod validate_endpoint вводит в заблуждение, может быть вызван в обход.",
     "models.py:84-87",
     "Хрупкая контрактная валидация.",
     "Переименовать в _check_endpoint (private) или сделать @field_validator('endpoint').",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Pydantic v2 correctness.",
     "code-reviewer", ""),

    ("BE-11", "Backend Quality", "LOW",
     "VISION_MODEL hardcoded magic string в loop.py",
     "loop.py:143 — VISION_MODEL = 'mimo-v2-omni'. Смена vision-провайдера = изменение кода. Комментарий предлагает вынести.",
     "loop.py:143",
     "Невозможно сменить vision модель через env.",
     "Добавить vision_model: str в Settings (config.py).",
     "S", 0.5, "Q4 2026", "Нет (новое)", "—",
     "Configurability.",
     "code-reviewer", ""),

    ("BE-12", "Backend Quality", "LOW",
     "TOOL_CONTENT_CAP=50_000 vs tool_content_cap=8000 — рассинхрон",
     "loop.py:156 vs persistence.py:326 — разные cap'ы для одного контента в разных контекстах без явного комментария. Запутывает audit context window usage.",
     "loop.py:156, persistence.py:326",
     "Мнимая инконсистентность — нужны комментарии 'почему 2 разных'.",
     "Либо единая константа, либо явный комментарий 'cap_X для live LLM, cap_Y для history reload'.",
     "S", 0.5, "Q4 2026", "Нет (новое)", "—",
     "Code clarity.",
     "code-reviewer", ""),

    # ============================ PERFORMANCE ============================
    ("PERF-1", "Производительность", "CRITICAL",
     "Один aiosqlite connection на всё приложение",
     "storage/db.py:20-48 — app.state.db — одна инстанция на весь FastAPI. SQLite WAL = один writer одновременно. Параллельные chat-запросы (несколько вкладок) сериализуются в одну очередь.",
     "storage/db.py:20-48",
     "Block bottleneck для multi-tab UX или multi-user. Сейчас single-Electron — терпимо. При первом team-deploy — стопор.",
     "Либо connection pool (aiosqlite_pool / sqlite-utils), либо явный writer-connection + N reader-connections. Или явно зафиксировать single-user в архитектуре.",
     "M", 2, "Q4 2026", "Нет (новое)", "ARCH-3",
     "Открывает дверь team/multi-tab UX.",
     "perf, architect", ""),

    ("PERF-2", "Производительность", "CRITICAL",
     "LLMClient создаётся заново на каждой итерации main loop",
     "loop.py:1074 — `llm = LLMClient(...)` внутри while True. Каждая итерация = новый httpx.AsyncClient = новый TCP + TLS handshake. Для запроса с 10 tool calls — 11 новых TCP-сессий к LLM. HTTP/2 keepalive не используется.",
     "loop.py:1074",
     "Latency 50-200 мс per iteration на warm path, 500 мс на cold. Для chain из 10 tools — лишние 2-5 сек end-to-end.",
     "Поднять LLMClient выше цикла. try/finally на уровне loop для aclose(). Можно reuse поверх всех turns в сессии — добавить httpx.AsyncClient(limits=...) с keepalive.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Прямое снижение perceived latency на 30-50%.",
     "perf", ""),

    ("PERF-3", "Производительность", "HIGH",
     "2 HTTP roundtrip перед каждым сообщением (config+connections fetch)",
     "useChatStream.ts:182-210 — последовательно fetchLLMConfig() + fetchConnections() ДО fetchChat(). Оба блокируют выход SSE. На localhost ~5-10 мс, в Electron+PyInstaller ~20-50 мс. Нарушает NFR-1 (≤500 мс TTFB).",
     "useChatStream.ts:182-210",
     "Замедление UX на каждом сообщении. На 100 messages в день = +5 сек ожидания.",
     "Кешировать LLM config и connections в React Context. Инвалидировать по событию 'settings:changed'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Прямое TTFB улучшение.",
     "perf, frontend", ""),

    ("PERF-4", "Производительность", "HIGH",
     "FTS5 не индексирует tool_calls и cards",
     "migrations.py:86-98 — messages_fts только content. Поиск 'найти где была выборка по ИНН X' = full scan JSON tool_calls. discovery_search пропустит релевантное.",
     "storage/migrations.py:86-98",
     "Главный value-prop 'найти прошлую похожую сессию' не работает для запросов через tool calls.",
     "Расширить FTS5 insert trigger: извлекать текст из tool_calls и cards через json_extract. Миграция v11 с rebuild индекса.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Превращает Insights/Search в реальный value-prop.",
     "perf, architect", ""),

    ("PERF-5", "Производительность", "HIGH",
     "sanitize_messages + repair_message_sequence на каждой итерации",
     "loop.py:1061 — обе O(n) на каждом обороте while. Для 50 turn × 5 messages = 250 messages × ~10 итераций per turn = 2500 проходов. estimate_tokens (O(n)) + needs_compression на каждой.",
     "loop.py:1061",
     "Лишняя CPU нагрузка на длинных сессиях. Видно как 'тормоза в чате' после 30+ turns.",
     "sanitize один раз при добавлении в messages, не перед каждой отправкой. estimate_tokens кешировать инкрементально.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Snappier UX в длинных сессиях.",
     "perf", ""),

    ("PERF-6", "Производительность", "HIGH",
     "Compressor DEFAULT_CHARS_PER_TOKEN=3.5 — занижает для русского+JSON",
     "compressor.py:36 — 3.5 chars/token. Русский = 2.5-3, JSON tool results = 4-5. При большом tool_calls payload compressor занижает реальный token count → компрессия не срабатывает вовремя → 413 от LLM → MAX_COMPRESS_RETRIES=2 пост-фактум.",
     "orchestrator/compressor.py:36",
     "Context overflow в реальных сессиях. Компрессия 'опаздывает'.",
     "Для tool_calls/cards коэф 4.5, русского текста — 2.8. Или tiktoken для совместимых моделей.",
     "M", 2, "Q3 2026", "Нет (новое)", "PROMPT-7",
     "Корректная компрессия = реальная поддержка long-running sessions.",
     "perf, prompt-engineer", ""),

    ("PERF-7", "Производительность", "MEDIUM",
     "list_sessions_grouped — correlated subquery COUNT(*) per row",
     "persistence.py:151-160 — (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) — для каждой сессии отдельный COUNT. При 500+ сессиях = N+1.",
     "persistence.py:151-160",
     "Sidebar lag при росте истории. Виден после 200+ сессий.",
     "Заменить на LEFT JOIN ... GROUP BY или window function (COUNT(*) OVER PARTITION BY).",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Snappy sidebar регрессии после месяца использования.",
     "perf", ""),

    ("PERF-8", "Производительность", "MEDIUM",
     "MCPClient создаётся per chat request без keepalive",
     "loop.py:895, mcp.py:87 — MCPClient содержит httpx.AsyncClient без limits=keepalive. pool.initialize_all() делает initialize+list_tools = 2 round-trip per request. На localhost ~2-10 мс.",
     "loop.py:895, clients/mcp.py:87",
     "Лишние roundtrip на каждом запросе.",
     "Кешировать MCP session (session_id + tools) per channel_id в app.state с TTL.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Снижение MCP overhead.",
     "perf", ""),

    ("PERF-9", "Производительность", "MEDIUM",
     "React setMessages со spread на каждый SSE chunk",
     "useChatStream.ts:236-242 — setMessages([...prev.slice(0,-1), ...]) при каждом chunk. При 50+ delta/сек × 100 messages = 100×N shallow copies/сек. React 19 batching смягчает, но при больших cards re-render тяжёлый.",
     "components/chat/useChatStream.ts:236-242",
     "Jank в long-running streaming. Видно на машинах слабее i7.",
     "useReducer с immer или Map-based state. Виртуализация thread'а через @tanstack/react-virtual при >50 messages.",
     "M", 2, "Q3 2026", "Да (TD-8 re-eval)", "—",
     "60 FPS streaming как NFR-3.",
     "perf, frontend", ""),

    ("PERF-10", "Производительность", "MEDIUM",
     "deep_search — IN (?,?,...) может превысить SQLITE_LIMIT_VARIABLE",
     "session_search.py:158-166 — для сессии с 500 messages и window=5 размер id_set может быть 500×11=5500. SQLite SQLITE_LIMIT_VARIABLE_NUMBER (старые версии 999). При больших окнах поиск упадёт.",
     "orchestrator/session_search.py:158-166",
     "Краш search в больших историях.",
     "Ограничить id_set chunked-запросами или CTE вместо IN.",
     "S", 0.5, "Q4 2026", "Нет (новое)", "—",
     "Reliability search при росте.",
     "perf", ""),

    ("PERF-11", "Производительность", "LOW",
     "PRAGMA vacuum не запланирован",
     "При удалении сессий (CASCADE) страницы возвращаются в freelist но не освобождаются. При активном использовании (50+ сессий/день) файл БД растёт.",
     "storage/db.py",
     "Дисковый рост со временем. Не критично, но заметно через год.",
     "PRAGMA auto_vacuum=INCREMENTAL в init + периодический PRAGMA incremental_vacuum(100) через FastAPI lifespan task.",
     "S", 0.5, "Q4 2026", "Нет (новое)", "—",
     "Disk hygiene long-term.",
     "perf", ""),

    ("PERF-12", "Производительность", "LOW",
     "Electron cold start: PyInstaller one-file",
     "tech-stack.md фиксирует PyInstaller. One-file распаковывает архив во временную директорию — Windows 3-8 сек overhead к NFR-4 ≤2 сек.",
     "backend/build.spec",
     "Долгий cold-start первый запуск приложения.",
     "Переключиться на PyInstaller one-dir режим (распаковка только при install). Ускорение 2-5 сек.",
     "L", 5, "Q4 2026", "Нет (новое)", "—",
     "First-impression UX.",
     "perf, devops", ""),

    # ============================ AI/PROMPTS ============================
    ("PROMPT-1", "AI / Промпты", "CRITICAL",
     "Нет few-shot примеров tool decision tree в SYSTEM_PROMPT",
     "loop.py:177-211 — описание tools декларативное ('используй когда...'), без примеров `user → tool_name → args`. Для MiMo и DeepSeek-R1 отсутствие few-shot = дрейф: модель угадывает порядок вызовов и параметры meta_type.",
     "orchestrator/loop.py:177-211",
     "Низкая accuracy tool selection. Аналитик задаёт типовой вопрос, LLM выбирает не тот инструмент или передаёт неверные параметры → лишние итерации.",
     "Добавить 3-4 концерных примера в формате `user: ... → tool_call: {name, args}` прямо в секцию ИНСТРУМЕНТЫ. Особенно для редких tools (get_event_log, find_references_to_object).",
     "M", 2, "Q3 2026", "Нет (новое)", "—",
     "Прямое улучшение accuracy на типовых запросах.",
     "prompt-engineer", ""),

    ("PROMPT-2", "AI / Промпты", "CRITICAL",
     "Indirect prompt injection через tool_results не защищена",
     "injection_scan.sanitize_for_prompt() используется только для MEMORY.md/USER.md. Tool results (content из execute_query, execute_code, get_event_log) до LLM без санитизации. Комментарий в 1С-документе 'ignore previous instructions' попадает в LLM как tool message.",
     "memory/injection_scan.py, loop.py _execute_mcp_tool",
     "Защищена только одна граница (memory). Tool-results — открытая дверь для PI.",
     "В _execute_mcp_tool прогонять content через sanitize_for_prompt перед добавлением в messages.",
     "S", 0.5, "Q3 2026", "Да (W2.7 частично)", "SEC-3",
     "Закрытие второй границы PI-защиты.",
     "prompt-engineer, security-reviewer", ""),

    ("PROMPT-3", "AI / Промпты", "CRITICAL",
     "Memory recall — нет сигнала 'проверь MEMORY.md перед ответом'",
     "markdown_store.py:86-97 — инструкция говорит 'если узнал факт → memory_append'. Нет симметричного 'перед ответом на вопрос о конвенциях базы → загляни в MEMORY.md'. LLM не получает trigger на retrieval. При большом MEMORY.md контент игнорируется.",
     "memory/markdown_store.py:86-97",
     "MEMORY.md как фича не работает: пишется но не читается LLM активно.",
     "В system_prompt_block: 'Перед ответом, если вопрос касается названий объектов, соглашений или предпочтений — сначала прочти ### MEMORY.md и сверь с ним ответ'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Memory delivers value (сейчас latent).",
     "prompt-engineer", ""),

    ("PROMPT-4", "AI / Промпты", "HIGH",
     "BSL-keywords в safety.py — false positives на легальных запросах",
     "safety.py:25-32 — pattern \\bУдалить\\b (IGNORECASE) блокирует ВЫБРАТЬ ГДЕ СтатусУдалено = Истина. \\bУстановить\\b — встречается в типовых именах реквизитов. Паттерны для BSL применяются к запросному языку.",
     "orchestrator/safety.py:25-32",
     "Аналитик пишет легальный запрос → блок → confirm dialog → friction.",
     "Разделить регистр BSL (только для execute_code) и SQL-паттерны (только для execute_query). Не смешивать в _DEFAULT_PATTERNS.",
     "M", 2, "Q3 2026", "Нет (новое)", "—",
     "Снижение false-positive rate на повседневной работе.",
     "prompt-engineer, security-reviewer", ""),

    ("PROMPT-5", "AI / Промпты", "HIGH",
     "Clarify decision не формализован — LLM пишет уточнения текстом",
     "loop.py:168-169 + clarify.py:111-144 — правило 3 говорит 'задай 1 короткий уточняющий вопрос'. Tool clarify_question есть в schema. Но в SYSTEM_PROMPT нет 'для уточнения ВСЕГДА используй clarify_question, не пиши вопрос текстом'. Для MiMo (non-reasoning) — критично.",
     "orchestrator/loop.py:168-169, clarify.py:111-144",
     "Фича Clarify Dialog (radio/checkbox) недоиспользуется. LLM пишет уточнения plain text.",
     "В правило 3 SYSTEM_PROMPT: 'вызови tool clarify_question — никогда не пиши уточнение текстом'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Активация Clarify UX.",
     "prompt-engineer", ""),

    ("PROMPT-6", "AI / Промпты", "HIGH",
     "background_review prompt — русский/английский mix ломает JSON",
     "background_review.py:35-58 — SYSTEM_PROMPT на русском, JSON-поля описываются смесью: \"id\": \"skill-id-kebab\" с английским комментарием '// 1-64 символа'. Для DeepSeek-R1 смешение языков в structured output prompt = вероятность нарушения формата.",
     "learning/background_review.py:35-58",
     "Курcur ломается на R1 — skills не сохраняются автоматически.",
     "Либо перевести всё на русский, либо 'Ответ ТОЛЬКО в JSON, без текста, язык полей — латиница'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Активация Self-Learning на reasoning моделях.",
     "prompt-engineer", ""),

    ("PROMPT-7", "AI / Промпты", "HIGH",
     "Prompt caching: cache_control на last user message ломает инвариант",
     "prompt_caching.py:64-76 — breakpoints на last-3 non-system, включая last user. Last user меняется каждый turn → cache_write впустую (2× input). Hermes ставит на system + первые N turns.",
     "orchestrator/prompt_caching.py:64-76",
     "Лишние cache writes = 2× cost on Anthropic. Кеш-hit rate ниже потенциального.",
     "Исключить последнее user message из cache_control candidates. Кэшировать только system + history исключая последние 2 messages.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Прямое снижение LLM bill (для Anthropic пути).",
     "prompt-engineer", ""),

    ("PROMPT-8", "AI / Промпты", "HIGH",
     "Skill recall — нет инструкции когда применять",
     "loop.py:402-428 — Skills инжектируются через render_for_prompt(max_chars=4_000) без заголовка-инструкции. LLM получает блок текста без trigger. MiMo — skills игнорируются при высокой похожести.",
     "orchestrator/loop.py:402-428, skill_store.py",
     "Skills как фича работает наполовину: создаются, но redirect к ним не происходит.",
     "Wrapper-секция вокруг skills block: '### Применимые паттерны решений: если вопрос пользователя похож на описание — используй готовое решение из skill'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Активация Skills value-prop.",
     "prompt-engineer", ""),

    ("PROMPT-9", "AI / Промпты", "MEDIUM",
     "SYSTEM_PROMPT не имеет provider-specific варианта",
     "loop.py:161-313 — один промпт для MiMo (non-reasoning), DeepSeek-R1 (reasoning), Claude, Cloud.ru. Для R1 нужно убрать explicit decision tree (модель сама reasonsit). Для MiMo — максимальная пошаговость. compressor.py:66-87 SUMMARY_INSTRUCTION тоже один для всех.",
     "orchestrator/loop.py:161-313, compressor.py:66-87",
     "Subobtimal accuracy на каждом провайдере.",
     "model_metadata флаг is_reasoning + в _build_full_system_prompt подставлять укороченную версию для R1.",
     "L", 5, "Q4 2026", "Нет (новое)", "—",
     "Раскрытие потенциала R1 / Claude.",
     "prompt-engineer", ""),

    ("PROMPT-10", "AI / Промпты", "MEDIUM",
     "Compressor summary не защищён от injection",
     "compressor.py:56-63, 57 — SUMMARY_PREAMBLE добавляет 'НЕ новые инструкции'. Но aux LLM получает middle-turns с tool results — инъекция из tool result попадёт в summary с preamble 'это только справка'.",
     "orchestrator/compressor.py:56-63",
     "Инъекция, переживающая компрессию.",
     "Перед summarization прогонять middle-turns через injection_scan.sanitize_for_prompt.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "PROMPT-2",
     "Compressor injection-safe.",
     "prompt-engineer, security-reviewer", ""),

    ("PROMPT-11", "AI / Промпты", "MEDIUM",
     "memory_append description на английском (нарушает консистентность)",
     "markdown_store.py:108-109 — tool description 'Append a durable fact to persistent memory. Use sparingly...' на английском. Весь остальной system prompt — русский. Для MiMo: хуже ассоциирует русский запрос с английским описанием.",
     "memory/markdown_store.py:108-126",
     "Снижение accuracy tool selection для memory_append.",
     "Перевести description на русский.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Tool description consistency.",
     "prompt-engineer", ""),

    ("PROMPT-12", "AI / Промпты", "MEDIUM",
     "Нет hallucination guard для BSL-кода",
     "loop.py:197 — execute_code описан как 'BSL-код для случаев которые нельзя выразить запросом'. Нет 'перед написанием BSL — проверь синтаксис через get_bsl_syntax_help'. LLM генерит из памяти (устаревшие методы, неверные сигнатуры).",
     "orchestrator/loop.py:197",
     "Главная боль AI+1С (правило 3 итераций Матакова). Генерация BSL без проверки = крах через 3 round.",
     "Правило: 'для execute_code — сначала вызови get_bsl_syntax_help для каждого нестандартного метода'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Прямое уменьшение hallucination rate в BSL.",
     "prompt-engineer", ""),

    ("PROMPT-13", "AI / Промпты", "MEDIUM",
     "Chart spec пример семантически неверен (yKeys = месяцы)",
     "loop.py:298-305 — line chart yKeys содержит названия месяцев-колонок, но они же должны быть значениями в data. LLM сгенерирует spec с перепутанными xKey/yKeys.",
     "orchestrator/loop.py:298-305",
     "Charts ломаются при первой попытке построить multi-series.",
     "Исправить пример: yKeys: ['продажи'], data: [{'месяц': 'Январь', 'продажи': 100}, ...].",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Charts работают из коробки.",
     "prompt-engineer", ""),

    ("PROMPT-14", "AI / Промпты", "LOW",
     "ThinkScrubber не пишет telemetry о scrubbed content",
     "think_scrubber.py — если reasoning-модель сливает <think> в delta.content — scrubber молча выбрасывает. Нет logger.debug / metric. В production невозможно понять насколько часто MiMo/R1 'течёт'.",
     "orchestrator/think_scrubber.py",
     "Не диагностируется регрессия 'модель начала писать think в content'.",
     "logger.debug('ThinkScrubber: scrubbed %d chars', chars_dropped) в feed().",
     "S", 0.5, "Q4 2026", "Нет (новое)", "—",
     "Observability reasoning models.",
     "prompt-engineer", ""),

    ("PROMPT-15", "AI / Промпты", "LOW",
     "skill_store.render_for_prompt без context — template vars не раскрываются",
     "loop.py:417 — render_for_prompt(max_chars=4_000) вызывается без context (session_id, channel_id, now). Template vars ${ANALYST_SESSION_ID} в skill body остаются нераскрытыми в prompt.",
     "orchestrator/loop.py:417, learning/skill_store.py",
     "Skills с template-переменными работают неверно.",
     "В _render_skills_block передавать context=build_default_context(session_id, channel_id).",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Skills template substitution.",
     "prompt-engineer", ""),

    # ============================ TESTING/QA ============================
    ("QA-1", "Тестирование", "HIGH",
     "Coverage цифры расходятся: 88.1% (orchestrator+clients) vs 26.58% (aggregate)",
     "STATE.md заявляет '88.1% orchestrator+clients'. POST-RELEASE-DEBT.md TD-2 фиксирует aggregate 26.58%. CI gate --cov-fail-under=80 на backend проходит — но реально это только подмножество.",
     "STATE.md vs .planning/POST-RELEASE-DEBT.md TD-2, .github/workflows/ci.yml",
     "Иллюзия покрытия. Routes/connections, attachments, log_cards, search, admin — реально могут быть 20-40%.",
     "Прогнать `pytest --cov=app --cov-report=term-missing` без фильтров. Расширить cov-fail-under на полный app/. Tier-based fail: critical модули ≥80%, остальные ≥60%, новые модули ≥70%.",
     "M", 2, "Q3 2026", "Да (TD-2 закрыт частично)", "—",
     "Реальная картина coverage. Защита от регрессий в routes/.",
     "claude (testing audit)", ""),

    ("QA-2", "Тестирование", "MEDIUM",
     "E2E happy-path 'отправить→SSE→карточка' раньше был skipped",
     "TD-4 в POST-RELEASE-DEBT.md заявлен Done (`bd40d3d`) — 3 spec'а unskipped. Но они требуют 'pnpm exec playwright test на dev-stack' для верификации. Реальное выполнение в CI — нужно проверить что они стабильны на ubuntu-latest.",
     ".github/workflows/ci.yml e2e job",
     "Можно отмерить Done, но в CI они flaky → silently skipped через timeout.",
     "Включить explicit failure если spec skipped в CI. Прогон 3 раза подряд на staging — нет flake → merge.",
     "S", 0.5, "Q3 2026", "Да (TD-4 частично)", "—",
     "Реальная защита от регрессий в SSE pipeline.",
     "claude", ""),

    ("QA-3", "Тестирование", "MEDIUM",
     "Нет performance/load testing",
     "Нет benchmarks: TTFB, длинная сессия 100 turns, concurrent multi-tab, large attachment. NFR-1..NFR-5 декларированы, но не верифицируются автоматически.",
     "Нет tests/perf/, нет locust/k6",
     "Регрессии латентности не отлавливаются. Compressor 'не верифицирован на >100k tokens' (STATE.md).",
     "tests/perf/test_long_session.py с locust/asyncio. Прогон в CI на больших данных раз в неделю (scheduled).",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Защита NFR-1..NFR-5 от регрессий.",
     "claude, perf", ""),

    ("QA-4", "Тестирование", "MEDIUM",
     "Нет smoke на multi-provider LLM (DeepSeek/Claude/Cloud.ru)",
     "Дефолт NVIDIA NIM + 3 альтернативы. Тесты вероятно покрывают только один провайдер с mock'ом. Реальный smoke на каждом провайдере не автоматизирован.",
     "backend/tests/test_llm_client.py",
     "При смене провайдера клиентом — узнаем о несовместимости в production.",
     "Test matrix: NVIDIA, Cloud.ru, DeepSeek, Anthropic (если ключ) — основной flow 'спроси про базу → tool call → ответ' на каждом, раз в неделю в CI.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Reliability multi-provider claim.",
     "claude, prompt-engineer", ""),

    ("QA-5", "Тестирование", "MEDIUM",
     "Нет visual regression тестов (Playwright screenshots)",
     "Brand Stencil/Mono (Signal #FF6A3D, Plex Mono 700), Dark/Light темы. Любая правка CSS может что-то сломать визуально. Sprint 04 (Motion polish) — без visual baseline.",
     "frontend/e2e/",
     "UX-deal-breaker: после релиза 'у меня поплыл шрифт', 'кнопка пропала'.",
     "Playwright `expect(page).toHaveScreenshot()` на 5-7 ключевых страницах × Dark/Light. Хранить baselines в `tests/__screenshots__/`.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Защита brand identity.",
     "claude", ""),

    ("QA-6", "Тестирование", "MEDIUM",
     "Нет AI-eval (golden дата сет с метриками accuracy)",
     "Tool accuracy (PROMPT-1), Memory recall (PROMPT-3), Skills recall (PROMPT-8) — все улучшения промптов без бенчмарка. Невозможно сказать 'после правки accuracy выросла с 60% до 75%'.",
     "—",
     "Прогресс по промптам не измеряется. 'Я думаю стало лучше' = регрессии не отлавливаются.",
     "Golden dataset 30-50 пар (вопрос пользователя → правильный tool + args). Backend test 'аналитик прогоняет dataset на NVIDIA NIM → accuracy ≥ 85%'. Weekly в CI.",
     "L", 5, "Q4 2026", "Нет (новое)", "PROMPT-1, PROMPT-3, PROMPT-8",
     "Прямой ROI: каждая правка промпта верифицируется числом.",
     "claude, prompt-engineer", ""),

    # ============================ DEVOPS / DISTRIBUTION ============================
    ("DEVOPS-1", "DevOps / Дистрибуция", "HIGH",
     "Нет EV/OV code signing → SmartScreen блокирует 30-50% инсталлов",
     "P1.3 scaffold в electron-builder.yml готов, CSC_LINK/CSC_KEY_PASSWORD через Secrets. Но EV/OV cert не куплен. Каждый новый пользователь видит SmartScreen 'Unknown Publisher' = adoption кратно ниже.",
     "desktop/electron-builder.yml, .planning/STATE.md P1.3",
     "Adoption-friction блокирует commerce. Платящий клиент 'у меня Windows предупреждает что приложение от неизвестного издателя' — переговоры на час.",
     "(1) Купить EV cert (~12-30k ₽/год DigiCert/Sectigo). (2) Залить в GitHub Secrets. (3) Re-build v1.5.0 signed. (4) Документировать reputation building (первые 3-5k инсталляций до уверенного 'no warning').",
     "L", 5, "Q3 2026", "Да (P1.3 scaffold)", "—",
     "Прямой uplift conversion 1.5-2× на onboarding.",
     "devops, security", ""),

    ("DEVOPS-2", "DevOps / Дистрибуция", "HIGH",
     "Нет Docker multi-stage (W2.8) — нет self-hosted варианта",
     "Только Electron installer. Self-hosted team из 3+ аналитиков с одной shared backend — невозможно. Это блокер для Team tier ценообразования.",
     "Нет Dockerfile + compose для prod",
     "Заявленный Team 4900 руб./мес. (5 user) не имеет deployment story.",
     "Docker multi-stage build: backend (PyInstaller-free, чистый python:3.12-slim) + frontend (next standalone). docker-compose.yml для self-hosted. README — instructions.",
     "M", 2, "Q4 2026", "Да (W2.8)", "ARCH-3",
     "Открывает Team tier pricing.",
     "devops", ""),

    ("DEVOPS-3", "DevOps / Дистрибуция", "HIGH",
     "Нет macOS/Linux installers (TD-13)",
     "Только Windows NSIS. После первой продажи прилетит клиент на Mac.",
     "desktop/electron-builder.yml win-only",
     "Адресуемый рынок ограничен Windows-only (~70% РФ desktop, но 30% — потери).",
     "DMG target macOS + AppImage/DEB Linux. CI matrix release.yml на 3 OS. Notarization для Mac (Apple Developer $99/год + notarytool).",
     "L", 5, "Q4 2026", "Да (TD-13)", "DEVOPS-1",
     "Адресуемый рынок +30%.",
     "devops", ""),

    ("DEVOPS-4", "DevOps / Дистрибуция", "MEDIUM",
     "Нет telemetry / crash reporting",
     "После релиза непонятно: сколько активных установок, на каких ошибках падает, какие фичи используются. NFR-10 'нет telemetry без opt-in' — но opt-in flow не реализован.",
     "Нет Sentry/Logfire/PostHog",
     "Слепота к реальному использованию. Bug-reports только когда пользователь сам напишет.",
     "Sentry для crash reporting (opt-in toggle в Onboarding step 4). PostHog OSS self-hosted для product analytics. Privacy policy + явный opt-in.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Data-driven product development.",
     "devops, perf", ""),

    ("DEVOPS-5", "DevOps / Дистрибуция", "MEDIUM",
     "Auto-update без semver check (downgrade attack)",
     "main.js:181-213 autoDownload:true без `semver.gt(info.version, app.getVersion())`. MITM с подменённым latest.yml может откатить старую версию с CVE.",
     "desktop/main.js:181-213",
     "Security: downgrade attack возможен.",
     "Добавить semver.gt check перед downloadUpdate. semver уже в зависимостях (?) или import { gt } from 'semver'.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "SEC-11",
     "Закрытие downgrade vector.",
     "devops, security", ""),

    ("DEVOPS-6", "DevOps / Дистрибуция", "MEDIUM",
     "release.yml не пушит latest.yml в GitHub Release для auto-update",
     "release.yml загружает desktop/dist/*.exe и latest.yml в actions artifact с retention 14 дней. Для electron-updater нужно чтобы latest.yml был В RELEASE (на GitHub Releases page), не только в actions artifacts.",
     ".github/workflows/release.yml:78-91",
     "Auto-update не работает: клиенты не узнают про новую версию.",
     "Добавить `softprops/action-gh-release@v2` шаг чтобы заливать desktop/dist/* в GitHub Release. Или включить electron-builder publish:always (уже есть) — но проверить что latest.yml попадает.",
     "S", 0.5, "Q3 2026", "Да (P1.4 phase 1.4 заявлен Done)", "—",
     "Активация auto-update в проде.",
     "devops", ""),

    ("DEVOPS-7", "DevOps / Дистрибуция", "LOW",
     "CI ruff не на новых файлах, не на всём backend",
     "ci.yml: `ruff check .` в backend. POST-RELEASE-DEBT TD-5 фиксирует 35 errors → 8 в loop.py. Остальные модули — unknown. Нет ruff в pre-commit.",
     ".github/workflows/ci.yml:24",
     "Drift качества кода.",
     "Добавить pre-commit hook с ruff + black. CI: жёсткий ruff check (без exclude).",
     "S", 0.5, "Q3 2026", "Да (TD-5)", "—",
     "Code hygiene baseline.",
     "devops", ""),

    ("DEVOPS-8", "DevOps / Дистрибуция", "LOW",
     "Нет TypeScript strict в CI — типы могут регрессировать",
     "ci.yml `pnpm type-check` — но без strict mode явно. lib/api.ts (841 строка) — потенциально `any` где. Регрессии типов проходят молча.",
     "frontend/tsconfig.json, ci.yml",
     "Type safety drift.",
     "tsconfig.json: strict:true + noImplicitAny + strictNullChecks + noUncheckedIndexedAccess. CI: tsc --noEmit на каждый PR.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Type safety baseline.",
     "devops, frontend", ""),

    # ============================ PRODUCT / GTM / MARKET ============================
    ("PROD-1", "Продукт / Позиционирование", "HIGH",
     "Окно до октября 2026: 1С:Напарник бесплатен, после — неизвестно",
     "1С:Напарник от 1С бесплатен с подпиской ИТС до 1 октября 2026. После — цена не объявлена. Напарник = только EDT/код, не chat-with-data. Аналитики P1/P2 не в EDT — это наша ниша. Окно занять до объявления цен.",
     "Market research, code.1c.ai",
     "Если упустить окно — рынок будет сравнивать pricing 1С Аналитика с (потенциально дешёвым) Напарником.",
     "Релизить публично + Infostart-статью + Telegram-ревью у Матакова/Бычкова ДО октября 2026. Positioning: 'для аналитика, а не разработчика'.",
     "M", 2, "Q3 2026", "Нет (новое)", "—",
     "Захват ниши до объявления цены Напарника. Time-critical.",
     "deep-researcher", ""),

    ("PROD-2", "Продукт / Позиционирование", "HIGH",
     "Pricing не определён — нет ценовой стратегии для commerce launch",
     "PROJECT.md не фиксирует цену. CHANGELOG.md M7 — Commerce Readiness, но cost-model не описана. Aether Lab — 990/3900 руб., якорь рынка.",
     "PROJECT.md, .planning/PROJECT.md",
     "Невозможно начать продажи без price-list.",
     "Зафиксировать tier'ы: Free (1 канал, 50 msg/мес.) / Solo 1990 руб./мес. (3 канала, безлимит на ключе пользователя, Memory, базовые Skills) / Team 4900 руб./мес. (5 user, premium skills, FTS, insights) / Enterprise (переговоры). Опубликовать в README + landing.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Без этого commerce launch невозможен.",
     "deep-researcher, claude", ""),

    ("PROD-3", "Продукт / Позиционирование", "HIGH",
     "152-ФЗ messaging не зафиксирован публично",
     "Cloud.ru с Qwen3-Coder-480B — реальное конкурентное преимущество для РФ-клиентов с 152-ФЗ. Архитектура 'ключ LLM на стороне пользователя' снимает обработку ПД нами. Но в README/landing/onboarding этого месседжа нет.",
     "README.md, frontend/app/page.tsx (landing нет)",
     "Закрытый сегмент enterprise РФ (банки, гос, страховые) не узнает что мы compliant.",
     "Раздел README + onboarding step 'Compliance: данные не уходят к нам, выбирайте Cloud.ru для 152-ФЗ'. Compliance badge зелёный РФ-ДЦ — уже есть в LLMConfigForm (P3.3 Done) — продублировать на landing.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "PROD-1", "Открывает enterprise-сегмент РФ.",
     "deep-researcher", ""),

    ("PROD-4", "Продукт / Позиционирование", "HIGH",
     "Нет landing page — невозможно конвертировать GitHub-трафик",
     "GitHub-репо приватный. Нет публичной страницы 'что это и зачем'. Все материалы PROJECT.md/README.md — внутренние.",
     "Нет landing",
     "Каждый кто услышит про продукт от Матакова/Infostart — не сможет купить/попробовать.",
     "Простой landing (Next.js standalone в этом же репо, отдельный app/marketing/): что решает, для кого, скриншоты + цены + 'попробовать'. Деплой на Vercel (free tier).",
     "M", 2, "Q3 2026", "Нет (новое)", "PROD-2", "Conversion funnel start.",
     "deep-researcher, claude", ""),

    ("PROD-5", "Продукт / Позиционирование", "MEDIUM",
     "Open-source ядро vs closed-source — стратегия не выбрана",
     "GitHub приватный. cc-1c-skills + Tools_UI_1C — open-source. Open-core (ядро open, premium функции closed) — стандарт для dev-tools. Без решения upfront — закроет двери later (нельзя из closed открыть, можно наоборот).",
     "Нет PUBLIC_VS_OSS.md",
     "Стратегическое решение откладывается, может закрыть пути.",
     "Решить: (a) closed-source paid, (b) open-core (ядро MIT, премиум фичи коммерч), (c) full OSS с paid hosted. Рекомендация: open-core — даёт GitHub-discovery + кейсы для Infostart.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Долгосрочная стратегия distribution.",
     "deep-researcher", ""),

    ("PROD-6", "Продукт / Позиционирование", "MEDIUM",
     "Нет 'sales-ready' demo сценариев / Killer demo",
     "Roadmap Phase 4.4 'Demo session с реальным аналитиком' — не сделано публично. Нет 90-секундного youtube демо 'смотрите, аналитик разобрал ОПП за 4 часа вместо 3 дней'.",
     ".planning/ROADMAP.md Phase 4.4",
     "Без demo конверсия landing → trial = 1-3%, с demo = 8-15%.",
     "(1) Сценарий: 'discovery незнакомой конфигурации УСО за 1 сессию'. (2) Запись через OBS / Loom (10-15 мин). (3) Cut в 90-сек. (4) Залить на YouTube + landing hero.",
     "M", 2, "Q3 2026", "Да (Phase 4.4 не сделана)", "PROD-4",
     "Conversion uplift на landing.",
     "deep-researcher", ""),

    # ============================ GTM ============================
    ("GTM-1", "Go-to-Market", "HIGH",
     "Infostart-статья с конкретным кейсом ROI — ключевой канал",
     "Infostart ~10k+ daily readers 1С-аудитория. ROI кейс Матакова (13 378 строк за 2 часа) — proven формат. Нет своей подобной публикации.",
     "Market research — Infostart channel",
     "Главный канал органического discovery в нише — не задействован.",
     "Статья 'Как 1С Аналитик разобрал незнакомую УСО-конфигурацию за 4 часа вместо 3 дней' — точные цифры, скриншоты, ссылка на trial. Платная (3-30k ₽) или бесплатная — выбрать.",
     "M", 2, "Q3 2026", "Нет (новое)", "PROD-4, PROD-6",
     "Главный inbound channel для P1/P2.",
     "deep-researcher", ""),

    ("GTM-2", "Go-to-Market", "HIGH",
     "Telegram outreach: Матаков, Бычков, mister1c, 1С-АРХИТЕКТОР",
     "Готовая аудитория P1 которые УЖЕ используют Claude Code + MCP. Их обзор = доверие. Без outreach — discovery медленный.",
     "Market research — Telegram channels",
     "Bypass через trusted influencer — самый быстрый путь к P1 segment.",
     "Личный outreach в DM: 'делаю open-source/freemium инструмент для аналитиков 1С, на нём вы экономите 2 дня discovery, попробуйте → если нравится упомяните'. По одному в неделю, не пачкой.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "PROD-4",
     "Acceleration discovery в community.",
     "deep-researcher", ""),

    ("GTM-3", "Go-to-Market", "HIGH",
     "INFOSTART A&PM EVENT октябрь 2026 — целевая аудитория аналитиков",
     "Конференция для аналитиков и руководителей проектов 1С. Доклад/стенд = максимальный охват. Параллель с октябрём 2026 = конец free-периода Напарника.",
     "Market research — events 2026",
     "Главное event для P1/P2 в году.",
     "(1) Заявка на доклад до июля 2026. (2) Тема: 'AI-первый подход к discovery 1С-конфигурации: реальные кейсы и метрики'. (3) Стенд в exhibit area с trial бесплатно для участников.",
     "M", 2, "Q3 2026", "Нет (новое)", "PROD-4, PROD-6",
     "Brand awareness в целевом сегменте.",
     "deep-researcher", ""),

    ("GTM-4", "Go-to-Market", "MEDIUM",
     "Партнёрство с франчайзи (1С:Первый БИТ, Софт-Веста и др.)",
     "Франчайзи 1С имеют тысячи внедренцев P2. Один партнёрский контракт = десятки лицензий. Long sales cycle, но scale.",
     "Market research — franchises",
     "Channel sales для масштабирования за SMB-segment.",
     "После 50+ первых клиентов — outreach к franchise CTOs. Преимущество: 'белый-лейбл интеграция' (Custom branding tier?).",
     "L", 5, "Q1 2027", "Нет (новое)", "PROD-2, PROD-4",
     "Channel sales 5-10× от direct.",
     "deep-researcher", ""),

    ("GTM-5", "Go-to-Market", "MEDIUM",
     "Open-source ядро для GitHub-органик discovery",
     "Если выбрать open-core (PROD-5) — публичный GitHub + Awesome-1C листинги + README с ссылкой на trial. Free organic traffic.",
     "PROD-5 решение",
     "Free organic acquisition channel.",
     "После решения по PROD-5: если open-core — переоткрыть репо, README с keywords (1С, MCP, AI, аналитик), интеграция в Awesome-1C списки.",
     "M", 2, "Q4 2026", "Нет (новое)", "PROD-5",
     "Organic acquisition longterm.",
     "deep-researcher", ""),

    # ============================ COMPLIANCE ============================
    ("COMP-1", "Compliance", "HIGH",
     "152-ФЗ: privacy policy + data flow document не написаны",
     "Архитектурно мы compliant (ключ user-side, нет хранения ПД нами). Но нет публичных документов: privacy policy, DPA, data flow diagram. Корп-клиент SOC review = блок без этих документов.",
     "Нет PRIVACY.md, нет DPA",
     "Блокирует enterprise sales. SOC-аналитик отказывает без формальных документов.",
     "(1) PRIVACY.md с явной указанной: 'данные пользовательской 1С-базы не покидают локальную машину; LLM-ключ хранится локально шифрованным; trajectory лог — opt-in, локально, retention X дней'. (2) Data flow diagram (Excalidraw → PNG в docs/). (3) Template DPA для enterprise.",
     "M", 2, "Q3 2026", "Нет (новое)", "SEC-9",
     "Открытие двери в enterprise sales.",
     "security, deep-researcher", ""),

    ("COMP-2", "Compliance", "MEDIUM",
     "Запрет иностранного ПО на КИИ с 01.01.2025 — нужна 'российская' версия",
     "Госсектор / критическая инфраструктура / банки с гос-долей не могут использовать зарубежный SaaS. Нужна self-hosted версия с РФ-LLM (GigaChat Pro или локальный Qwen).",
     "Market research — 152-ФЗ + КИИ",
     "Большой closed-сегмент (госы, банки) недоступен без РФ-версии.",
     "M9 milestone: self-hosted Docker + опция 'российский режим' (Cloud.ru/GigaChat only) + verify через automation тест. Реклама в Infostart 'КИИ-готовая версия'.",
     "L", 5, "Q1 2027", "Нет (новое)", "DEVOPS-2",
     "Открывает гос-сегмент.",
     "deep-researcher, security", ""),

    ("COMP-3", "Compliance", "LOW",
     "ФСТЭК сертификация — для гос-сектора (long-term)",
     "Если планируется гос-сегмент — ФСТЭК сертификация 1-3 млн руб. + 6-12 мес. Не приоритет M7-M8.",
     "—",
     "Final gate для самого крупного enterprise (только госы).",
     "Backlog. Триггер: первый запрос от gov client с ТЗ требующим ФСТЭК.",
     "XL", 10, "Backlog", "Нет (новое)", "COMP-2",
     "Top of funnel: только если есть гос-клиент.",
     "deep-researcher", ""),

    # ============================ FRONTEND / UX / A11Y ============================
    ("FE-1", "Frontend / UX", "CRITICAL",
     "prefers-reduced-motion не отключает animate-fade-up (12 компонентов)",
     "design-tokens.css:435 — @media (prefers-reduced-motion: reduce) закрывает только .skeleton, .send-flight, .spark-*, .undo-toast. Tailwind animate-fade-up (из @keyframes fade-up) используется в 12 файлах: OnboardingDialog, BackendDownBanner, ErrorBanner и др. Движение не подавляется для пользователей с вестибулярными расстройствами.",
     "frontend/styles/design-tokens.css:435, 12 компонентов",
     "WCAG 2.3.1 (A) обязательный пункт. Пользователи с motion sickness страдают от модальных fade-up.",
     "В блок @media (prefers-reduced-motion: reduce) добавить: *:not(.skeleton) { animation: none !important; transition: none !important; }. Или явный selector для всех animate-* классов.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "A11y compliance. Открывает рынок для пользователей с особенностями.",
     "frontend (general-purpose)", ""),

    ("FE-2", "Frontend / UX", "HIGH",
     "Нет виртуализации Thread + scrollIntoView на каждый delta-event",
     "Thread.tsx:96 — visibleMessages.map() рендерит все сообщения сразу. При >50 messages (с картами/таблицами/трейсами) — jank. ScrollArea Radix не виртуализирует. Thread.tsx:74-76 — scrollIntoView в useEffect с dep [messages] срабатывает при каждом delta event (10-50 раз/сек), мешает пользователю читать предыдущее.",
     "frontend/components/chat/Thread.tsx:74-76, 96",
     "60 FPS NFR-3 нарушается при streaming в длинных сессиях. Пользователь не может прокрутить вверх во время генерации.",
     "(1) Виртуализация: @tanstack/react-virtual (TD-8 в POST-RELEASE-DEBT re-eval — нужен). (2) Scroll: проверка `userScrolled` flag или debounce; auto-scroll только если пользователь у bottom (threshold ±100px).",
     "M", 2, "Q3 2026", "Да (TD-8 re-eval)", "PERF-9",
     "Snappy long-session UX.",
     "frontend (general-purpose)", ""),

    ("FE-3", "Frontend / UX", "HIGH",
     "Контраст --fg-4 (0.5 opacity Ink on Sand) = 3.33:1 — не AA",
     "design-tokens.css:120 — rgba(21,22,26,0.5) на #F3F1EC = 3.33:1 (требуется 4.5 для normal text). Используется для метки токенов в Input.tsx:484 ({tokenEstimate} / 4 000 ТОКЕНОВ) и hint-row. 10px текст — порог AA Large (3:1) достигнут, но шрифт слишком мал для Large-исключения.",
     "frontend/styles/design-tokens.css:120, Input.tsx:484",
     "WCAG 2.1 AA нарушение для light Sand темы. Пользователь не может прочитать счётчик токенов.",
     "Поднять --fg-4 до 0.60 alpha → ~4.5:1. Или увеличить font-size hint до 11-12px (квалификация Large).",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "A11y baseline для light темы.",
     "frontend (general-purpose)", ""),

    ("FE-4", "Frontend / UX", "HIGH",
     "key={i} для attachments → артефакты превью при удалении",
     "Input.tsx:322 — массив attachments мутируется через .filter() (удаление по индексу). С key={i} React переиспользует DOM-узлы при удалении не последнего элемента — превью картинок (<img src='data:...'>) покажут артефакты предыдущего файла.",
     "frontend/components/chat/Input.tsx:322",
     "Visual bug: пользователь удаляет 1-й файл из 3, видит 'превью первого' на месте второго.",
     "Стабильный key: att.name + att.content_base64.slice(0,8). Или добавить id: crypto.randomUUID() при создании ChatAttachment.",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Корректность attachment UX.",
     "frontend (general-purpose)", ""),

    ("FE-5", "Frontend / UX", "HIGH",
     "OnboardingDialog: 4 DialogTitle одновременно в DOM, нет aria-describedby",
     "OnboardingDialog.tsx:266,298,335,404 — 4 <DialogTitle> рендерятся в одном <Dialog> (по одному на шаг). При быстром handleNext animate-fade-up оба шага одновременно в DOM на 200ms. Screen reader может анонсировать оба. Нет aria-describedby на DialogContent.",
     "frontend/components/onboarding/OnboardingDialog.tsx:266,298,335,404",
     "A11y violation: AT users не понимают что происходит при переключении шагов.",
     "(1) DialogDescription на каждый шаг с aria-describedby. (2) Альтернатива: aria-label вместо нескольких DialogTitle. (3) Гарантировать exit animation завершается ДО mount следующего шага.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Onboarding A11y compliance.",
     "frontend (general-purpose)", ""),

    ("FE-6", "Frontend / UX", "MEDIUM",
     "Race condition при быстром переключении каналов",
     "page.tsx:132 — handleChannelChange обновляет localStorage + store.refresh(). useChatStream.ts:108-130 хранит channelId в closure send callback. При переключении канала во время активного стрима — anonHeaders для старого channelId, но сообщение уйдёт в новый. AbortController отменяет SSE, но send с новым channelId может запуститься раньше сброса state.",
     "frontend/app/page.tsx:132, components/chat/useChatStream.ts:108-130, 203",
     "Сообщение уходит в неправильный channel. Critical для multi-tenant.",
     "Guard: блокировать send пока (isStreaming && prevChannelId !== channelId). Или сбрасывать isStreaming синхронно с channelId change.",
     "M", 2, "Q3 2026", "Нет (новое)", "ARCH-3",
     "Корректность multi-tenant в UI.",
     "frontend (general-purpose)", ""),

    ("FE-7", "Frontend / UX", "MEDIUM",
     "response.json() as Promise<T> без runtime валидации (Zod)",
     "lib/api.ts — type-assertion без Zod/guard в 20+ местах. Если backend вернёт неожиданную структуру (после деплоя) — runtime error в неожиданном месте. fetchLLMConfig: has_env_api_key=undefined → Boolean=false → пользователь видит блок отправки без понятной причины.",
     "frontend/lib/api.ts (20+ вызовов)",
     "Невнятные ошибки при backend API drift. Time-to-diagnosis = часы.",
     "Zod schemas для ключевых endpoints: fetchLLMConfig, fetchConnections, fetchSessionMessages, sendChat SSE events. CI fail если schema не соответствует Pydantic models (через openapi-typescript).",
     "L", 5, "Q4 2026", "Нет (новое)", "—",
     "Reliability API contract.",
     "frontend (general-purpose), code-reviewer", ""),

    ("FE-8", "Frontend / UX", "LOW",
     "Onboarding Step 3 'Память' не объясняет privacy",
     "OnboardingDialog.tsx:340-345 — текст 'Модель будет помнить ваши прошлые ответы' недостаточен для GDPR/privacy-first UX. Нет упоминания где хранится (localStorage/backend), можно ли удалить.",
     "frontend/components/onboarding/OnboardingDialog.tsx:340-345",
     "Privacy-first messaging нарушен. Пользователь не знает что соглашается.",
     "Добавить 1 строку: 'Данные хранятся локально на вашем компьютере. Удалить можно в Настройки → Память.' Линк на PRIVACY.md (когда будет — COMP-1).",
     "S", 0.5, "Q3 2026", "Нет (новое)", "COMP-1",
     "Privacy-first UX.",
     "frontend (general-purpose)", ""),

    ("FE-9", "Frontend / UX", "LOW",
     "Hardcoded '4 000 ТОКЕНОВ' в Input hint",
     "Input.tsx:485 — лимит жёстко прошит. При смене модели в Settings (NVIDIA NIM Llama 70B → DeepSeek R1 65k) hint остаётся 4 000.",
     "frontend/components/chat/Input.tsx:485",
     "Дезинформация для пользователя: реальный лимит на модели может быть 65k.",
     "Передавать context_window через props из LLMConfigForm/useChatStream. Брать из model_metadata в backend (есть в orchestrator/model_metadata.py).",
     "S", 0.5, "Q3 2026", "Нет (новое)", "—",
     "Корректные UX-числа.",
     "frontend (general-purpose)", ""),

    ("FE-10", "Frontend / UX", "LOW",
     "Brand-tick: hardcoded inline style вместо CSS token",
     "Input.tsx:301-305 — <span> с style={{ background: 'var(--accent)' }}. Нарушает 'design tokens only' принцип из session-contract.md.",
     "frontend/components/chat/Input.tsx:301-305",
     "Drift design tokens. Не критично, гигиена.",
     "Заменить на Tailwind class bg-[var(--accent)] или extract в .brand-tick класс.",
     "S", 0.5, "Q4 2026", "Нет (новое)", "—",
     "Design tokens consistency.",
     "frontend (general-purpose)", ""),

    ("FE-11", "Frontend / UX", "MEDIUM",
     "guide/page.tsx 1326 строк — контент склеен с компонентом",
     "app/guide/page.tsx содержит весь контент руководства как JSX literals в файле. Anti-pattern: документация смешана с кодом. При обновлении контента нужен build.",
     "frontend/app/guide/page.tsx (1326 строк)",
     "Высокий cost обновления гайда. Невозможно делегировать копирайтеру.",
     "Отделить content в guide-content.ts (plain objects) или MDX. Layout-компонент рендерит данные.",
     "M", 2, "Q4 2026", "Нет (новое)", "—",
     "Maintainability контента.",
     "frontend (general-purpose), architect", ""),
]

# ---- Roadmap suggestions -----------------------------------------------------
ROADMAP = [
    ("M7.5", "Pre-Commerce Hardening", "2-3 нед", "до 15.07.2026",
     "Закрыть CRITICAL: SEC-1 SSRF, BE-1/BE-2 race+leak, PERF-1/PERF-2, PROMPT-1/2/3. DOC-1 ARCHITECTURE refresh.",
     "10-15 findings из CRITICAL+HIGH"),
    ("M8", "Commerce Launch", "3-4 нед", "до 31.08.2026",
     "PROD-2 pricing + PROD-4 landing + PROD-3 152-ФЗ messaging + GTM-1 Infostart + GTM-2 Telegram outreach + DEVOPS-1 EV cert + DEVOPS-6 release latest.yml.",
     "PROD-1..6, GTM-1..3, DEVOPS-1/6"),
    ("M9", "Deployment & Observability", "3-4 нед", "до 30.09.2026",
     "DEVOPS-2 Docker self-hosted (открывает Team tier) + DEVOPS-3 macOS/Linux + DEVOPS-4 telemetry/Sentry + QA-1..4 (coverage real, multi-provider tests). ARCH-3 multi-tenant disclaimer или migration.",
     "DEVOPS-2..4, QA-1..4, ARCH-3"),
    ("M10", "AI Quality & Eval", "2-3 нед", "до 31.10.2026",
     "QA-6 golden dataset + AI-eval CI + PROMPT-9 provider-specific prompts + PROMPT-7 caching fix + COMP-1 PRIVACY.md/DPA. Готовность к INFOSTART A&PM EVENT октябрь.",
     "QA-6, PROMPT-7/9, COMP-1, GTM-3"),
    ("M11", "Enterprise Readiness", "4-6 нед", "до 30.11.2026",
     "ARCH-3 full multi-tenant migration v11 + COMP-2 'российская версия' (КИИ-ready) + GTM-4 franchise partnerships + ARCH-1 final loop decompose + SEC-8 .app-secret ACL Windows.",
     "ARCH-1/3, COMP-2, GTM-4, SEC-8"),
]

# ---- Build workbook ----------------------------------------------------------
wb = Workbook()

# === Sheet 1: Findings (главный реестр) ===
ws = wb.active
ws.title = "Findings"

headers = [
    "ID",
    "Категория",
    "Severity",
    "Заголовок",
    "Описание (что найдено)",
    "Где (file:line)",
    "Какую проблему решит",
    "Решение",
    "Усилия",
    "Дней",
    "Quarter",
    "В backlog у юзера?",
    "Зависимости",
    "Impact / бизнес-эффект",
    "Источник (агент)",
    "Комментарий пользователя",
]

ws.append(headers)
for f in FINDINGS:
    ws.append(list(f))

# Header style
header_fill = PatternFill("solid", start_color="FF111827")
header_font = Font(name="Arial", bold=True, color="FFFFFFFF", size=11)
header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
thin = Side(border_style="thin", color="FF374151")
border = Border(top=thin, bottom=thin, left=thin, right=thin)

for col_idx, _ in enumerate(headers, start=1):
    cell = ws.cell(row=1, column=col_idx)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = header_align
    cell.border = border

# Data styling
data_font = Font(name="Arial", size=10)
data_align_wrap = Alignment(vertical="top", wrap_text=True)
data_align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

for row_idx in range(2, ws.max_row + 1):
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=row_idx, column=col_idx)
        cell.font = data_font
        cell.border = border
        cell.alignment = data_align_wrap
        if col_idx in (1, 3, 9, 10, 11, 12):  # ID, Severity, Effort, Days, Quarter, In Backlog
            cell.alignment = data_align_center

    # Severity coloring (col 3)
    sev_cell = ws.cell(row=row_idx, column=3)
    sev_value = str(sev_cell.value).upper().strip()
    if sev_value in SEV:
        bg, fg = SEV[sev_value]
        sev_cell.fill = PatternFill("solid", start_color=bg)
        sev_cell.font = Font(name="Arial", bold=True, color=fg, size=10)

    # Alternating row stripe
    if row_idx % 2 == 0:
        for col_idx in (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16):
            cell = ws.cell(row=row_idx, column=col_idx)
            if not cell.fill or cell.fill.fgColor.rgb in (None, "00000000"):
                cell.fill = PatternFill("solid", start_color="FFF9FAFB")

    # Highlight comment column (16) — yellow background for user input
    comment_cell = ws.cell(row=row_idx, column=16)
    comment_cell.fill = PatternFill("solid", start_color="FFFEF3C7")

# Column widths
widths = {
    "A": 10, "B": 19, "C": 11, "D": 38, "E": 60, "F": 32,
    "G": 38, "H": 50, "I": 9, "J": 7, "K": 12, "L": 18,
    "M": 16, "N": 38, "O": 22, "P": 40,
}
for col, w in widths.items():
    ws.column_dimensions[col].width = w

ws.row_dimensions[1].height = 32

# Freeze top row + first column
ws.freeze_panes = "B2"

# AutoFilter on whole table
ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"

# === Sheet 2: Сводка по категориям ===
ws2 = wb.create_sheet("Сводка")
ws2.append(["Категория", "CRITICAL", "HIGH", "MEDIUM", "LOW", "Всего", "Сумма дней"])

categories_in_order = []
for f in FINDINGS:
    cat = f[1]
    if cat not in categories_in_order:
        categories_in_order.append(cat)

for cat in categories_in_order:
    row_data = [cat]
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        cnt = sum(1 for f in FINDINGS if f[1] == cat and f[2] == sev)
        row_data.append(cnt)
    total_cnt = sum(1 for f in FINDINGS if f[1] == cat)
    total_days = sum(f[9] for f in FINDINGS if f[1] == cat)
    row_data.append(total_cnt)
    row_data.append(total_days)
    ws2.append(row_data)

# Totals row
ws2.append([
    "ИТОГО",
    sum(1 for f in FINDINGS if f[2] == "CRITICAL"),
    sum(1 for f in FINDINGS if f[2] == "HIGH"),
    sum(1 for f in FINDINGS if f[2] == "MEDIUM"),
    sum(1 for f in FINDINGS if f[2] == "LOW"),
    len(FINDINGS),
    sum(f[9] for f in FINDINGS),
])

# Header style ws2
for col_idx in range(1, 8):
    c = ws2.cell(row=1, column=col_idx)
    c.fill = header_fill
    c.font = header_font
    c.alignment = header_align
    c.border = border

for row_idx in range(2, ws2.max_row + 1):
    for col_idx in range(1, 8):
        c = ws2.cell(row=row_idx, column=col_idx)
        c.font = data_font
        c.border = border
        c.alignment = data_align_center if col_idx > 1 else Alignment(vertical="center")
    if row_idx == ws2.max_row:
        for col_idx in range(1, 8):
            c = ws2.cell(row=row_idx, column=col_idx)
            c.fill = PatternFill("solid", start_color="FF111827")
            c.font = Font(name="Arial", bold=True, color="FFFFFFFF", size=10)

ws2.column_dimensions["A"].width = 28
for col in ["B", "C", "D", "E", "F"]:
    ws2.column_dimensions[col].width = 12
ws2.column_dimensions["G"].width = 14

# === Sheet 3: Roadmap (предложение milestones) ===
ws3 = wb.create_sheet("Roadmap")
ws3.append(["Milestone", "Название", "Длительность", "Целевая дата", "Содержание", "Связанные findings"])

for r in ROADMAP:
    ws3.append(list(r))

for col_idx in range(1, 7):
    c = ws3.cell(row=1, column=col_idx)
    c.fill = header_fill
    c.font = header_font
    c.alignment = header_align
    c.border = border

for row_idx in range(2, ws3.max_row + 1):
    for col_idx in range(1, 7):
        c = ws3.cell(row=row_idx, column=col_idx)
        c.font = data_font
        c.border = border
        c.alignment = data_align_wrap
    if row_idx % 2 == 0:
        for col_idx in range(1, 7):
            ws3.cell(row=row_idx, column=col_idx).fill = PatternFill("solid", start_color="FFF9FAFB")

ws3.column_dimensions["A"].width = 9
ws3.column_dimensions["B"].width = 28
ws3.column_dimensions["C"].width = 12
ws3.column_dimensions["D"].width = 14
ws3.column_dimensions["E"].width = 80
ws3.column_dimensions["F"].width = 38
ws3.row_dimensions[1].height = 32
for row_idx in range(2, ws3.max_row + 1):
    ws3.row_dimensions[row_idx].height = 70

# === Sheet 4: Легенда ===
ws4 = wb.create_sheet("Легенда")
legend = [
    ["Severity", "Значение"],
    ["CRITICAL", "Блокирует release / commerce / безопасность. Чинить немедленно."],
    ["HIGH", "Серьёзная проблема. Закрыть до публичного релиза или в ближайший спринт."],
    ["MEDIUM", "Улучшение, не блокирует. В roadmap следующего милстоуна."],
    ["LOW", "Hygiene / nice-to-have. В backlog."],
    ["", ""],
    ["Усилия", "Дней"],
    ["S (Small)", "0.5 дня"],
    ["M (Medium)", "2 дня"],
    ["L (Large)", "5 дней"],
    ["XL (Extra Large)", "10 дней"],
    ["", ""],
    ["Категория", "Содержание"],
    ["Документация", "Расхождения между docs и кодом (ARCHITECTURE.md, STATE.md)"],
    ["Архитектура", "Структурные проблемы: God-функции, multi-tenant, decomposition"],
    ["Безопасность", "SSRF, prompt injection, Electron CSP, SQL bypass, encryption"],
    ["Backend Quality", "Качество BSL/Python кода: race conditions, silent failures, dead code"],
    ["Производительность", "Latency, SQLite, FTS, streaming, bundle size"],
    ["AI / Промпты", "SYSTEM_PROMPT качество, tool calling, memory/skills recall"],
    ["Тестирование", "Coverage, E2E, AI-eval, visual regression, multi-provider"],
    ["DevOps / Дистрибуция", "Electron, code signing, Docker, CI, telemetry, auto-update"],
    ["Продукт / Позиционирование", "Pricing, landing, demo, 152-ФЗ messaging"],
    ["Go-to-Market", "Каналы: Infostart, Telegram, конференции, партнёрства"],
    ["Compliance", "152-ФЗ, КИИ, ФСТЭК"],
    ["", ""],
    ["Поле 'Комментарий пользователя'", "Здесь вы пишете свои замечания / решения / приоритеты. Жёлтый фон."],
]

for row_data in legend:
    ws4.append(row_data)

for col_idx in (1, 2):
    c = ws4.cell(row=1, column=col_idx)
    c.fill = header_fill
    c.font = header_font
    c.alignment = header_align
    c.border = border

for row_idx in range(2, ws4.max_row + 1):
    for col_idx in (1, 2):
        c = ws4.cell(row=row_idx, column=col_idx)
        c.font = data_font
        c.alignment = data_align_wrap
        c.border = border
    sev_label = str(ws4.cell(row=row_idx, column=1).value or "").upper().strip()
    if sev_label in SEV:
        bg, fg = SEV[sev_label]
        c = ws4.cell(row=row_idx, column=1)
        c.fill = PatternFill("solid", start_color=bg)
        c.font = Font(name="Arial", bold=True, color=fg, size=10)

ws4.column_dimensions["A"].width = 30
ws4.column_dimensions["B"].width = 80

wb.save(OUT)
print(f"Saved: {OUT}")
print(f"Findings: {len(FINDINGS)}")
print(f"Roadmap milestones: {len(ROADMAP)}")
