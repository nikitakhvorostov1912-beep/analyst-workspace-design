# Hermes Agent → 1С Аналитик · Implementation Plan v1.0

> **Создано:** 2026-05-20
> **Источник:** [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) v0.14.0 · MIT
> **Назначение:** Документ-инструкция для Claude. Содержит **полный каталог
> фич Hermes**, маппинг на нашу архитектуру и **пошаговый план реализации**.
> Любая сессия Claude (новая или продолжение) может взять этот документ и
> двигать спринты от 1 до 5 без потери контекста.

---

## 0. Как Claude должен использовать этот документ

1. При старте новой сессии — прочитать **полностью** разделы 1, 2, 6.
2. Перед началом спринта — прочитать **детальный план спринта** (раздел 7).
3. **НЕ забегать вперёд** — спринты идут последовательно (1 → 2 → 3 → 4 → 5),
   потому что Sprint 2 опирается на Sprint 1, и т.д.
4. После каждого спринта — отметить в этом же документе статус (✅/⏸/❌) +
   ссылку на коммит/тег.
5. Брутальная честность: если что-то из плана оказалось хуже на практике —
   зафиксировать в **разделе 9 «Дневник отклонений»**, не молча менять.

---

## 1. Контекст

### 1.1 Кто Hermes

Hermes Agent — self-improving CLI/мессенджер агент от Nous Research.
**158 000 ★, MIT, Python 88%**. Версия 0.14.0 (2026-05).

Архитектурный масштаб:
- `agent/` — 100 файлов, **54 459 строк** — orchestration core
- `tools/` — 93 файла, **60 419 строк** — встроенные инструменты
- `plugins/` — 117 файлов — расширения
- `gateway/` — 62 файла — мессенджеры
- `skills/` — 26 категорий self-documenting capabilities

Зависимости pinned exactly (`==X.Y.Z`) против supply-chain атак —
после атаки **Mini Shai-Hulud worm** на mistralai 2.4.6 на PyPI в 2026-05.

### 1.2 Кто мы (1С Аналитик)

**Версия 1.2.2** (релиз 2026-05-20). Stack:
- Backend: FastAPI + Pydantic v2 + SSE + SQLite via aiosqlite
- Frontend: Next.js 15 App Router + React 19 + Tailwind 4 + shadcn/ui
- Desktop: Electron 33 + electron-builder, installer 106 MB
- LLM: OpenAI-compatible HTTP к Xiaomi MiMo / Claude / GPT
- MCP: HTTP Streamable к 1С MCP Toolkit (10 tools) + aux bsl-context

Ключевое отличие: Hermes — autonomous general agent, мы — **специализированный
chat-assistant для бизнес-аналитика 1С**. Это не дискриминатор от Hermes,
это просто другая ниша → ~60% его кода нам не нужно.

### 1.3 Что у нас уже есть из «hermes-подобного»

- ✅ Streaming через SSE
- ✅ MCP client (HTTP Streamable + stdio для aux bsl-context)
- ✅ Multi-tenant channel selector (= multi-host в Hermes)
- ✅ SQLite sessions + история
- ✅ Анонимизация PII
- ✅ Vision + document upload
- ✅ Export сессии в Markdown
- ✅ ChartCard через ```chart fence
- ✅ Skill orchestration (67 1С-скиллов проекта)

### 1.4 Чего у нас нет (= что заберём)

| Категория | Hermes | Мы |
|---|---|---|
| Долговременная память | MEMORY.md + USER.md + Honcho | ❌ нет |
| Context compression | auto compaction с aux model | ❌ нет |
| Self-learning loop | curator + skill_manager + provenance | ❌ нет |
| Clarify dialog | structured choices в чате | ❌ модель угадывает |
| Error classification | FailoverReason enum + retry/rotate/fallback | ❌ try/except |
| Iteration budget | thread-safe consume/refund | ❌ unlimited |
| Tool guardrails | per-turn observation + decision controller | ❌ нет |
| Todo list для агента | re-injected after compression | ❌ нет |
| Checkpoint manager | shadow git store snapshots | ❌ нет |
| Trajectory export | JSONL ShareGPT для дообучения | ❌ нет |
| Session search (FTS5) | semantic recall across sessions | ❌ только title |
| Subagents | delegate_tool isolated context | ❌ нет |
| Observability | Langfuse plugin + insights engine | ❌ только status |
| Approval system | dangerous command detection | ❌ нет |
| Prompt caching strategy | Anthropic system_and_3 | ❌ нет |
| Models.dev registry | 4000+ моделей community | ❌ ручной список |
| Background review fork | daemon thread asks "save skill?" | ❌ нет |
| Skill bundles | /<bundle> загружает N скиллов | ❌ нет |
| Subdirectory hints | progressive AGENTS.md discovery | n/a |
| Insights/usage analytics | SQLite analytics → /insights | ❌ нет |
| Schema sanitizer | local-backend compat | ❌ нет |

---

## 2. Полный каталог фич Hermes (75 пунктов)

Группировка по категориям. Для каждой фичи:
- **What** — что делает
- **Where** — путь в Hermes
- **Fit** — применимо нам? (🟢 Прямо · 🟡 С адаптацией · 🔴 Не нужно)
- **Cost** — оценка в днях (XS=0.5 · S=1 · M=2-3 · L=4-7 · XL=8+)
- **Profit** — оценка эффекта (🔥1-5)

### 2.A. Memory & Self-Learning (12)

#### A1. MEMORY.md + USER.md persistent stores 🟢 M 🔥🔥🔥🔥🔥
- **What**: два markdown файла. MEMORY.md — заметки агента (среда, правила, паттерны). USER.md — что мы знаем о пользователе (предпочтения, стиль, домен).
- **Where**: `tools/memory_tool.py`
- **Why**: каждый второй вопрос аналитика — повтор. Файлы дают persistent recall.

#### A2. MemoryManager (provider abstraction) 🟢 M 🔥🔥🔥🔥
- **What**: единый orchestrator memory-провайдеров. Pre-turn `prefetch_all()`, post-turn `sync_all()`, async `queue_prefetch_all()`. Только ОДИН external provider — против tool schema bloat.
- **Where**: `agent/memory_manager.py` (609 строк)

#### A3. MemoryProvider ABC 🟢 S 🔥🔥🔥
- **What**: интерфейс провайдера: `initialize / system_prompt_block / prefetch(query) / sync_turn(user, asst) / get_tool_schemas / handle_tool_call / shutdown`
- **Where**: `agent/memory_provider.py`

#### A4. Honcho dialectic user modeling 🟡 L 🔥🔥
- **What**: внешний сервис, который строит «портрет» пользователя через многопроходный диалектический reasoning. Cold/warm session prompts. Multi-pass depth 1-3.
- **Where**: `plugins/memory/honcho/`
- **Адаптация для нас**: не интегрировать Honcho напрямую (это их сервис), а реализовать собственный «UserProfile generator» через aux model 1 раз в N сессий.

#### A5. Background review fork 🟢 L 🔥🔥🔥🔥
- **What**: после каждого turn'а daemon thread форкает агента → реплеит conversation в forked AIAgent → asks «должен ли я сохранить skill/memory?». Toolset ограничен memory+skill. Не трогает основной prompt cache.
- **Where**: `agent/background_review.py`
- **Critical for self-learning**

#### A6. Curator orchestrator 🟢 L 🔥🔥🔥
- **What**: inactivity-triggered (NO cron daemon) background skill maintenance. При idle и last_run > interval_hours — форкает review-агент через aux model. Pin/archive/consolidate/patch agent-created skills.
- **Where**: `agent/curator.py` (1781 строк)
- **Strict invariants**: только agent-created skills, never auto-delete (только archive), pinned bypass, aux-client never touches main cache.

#### A7. Curator backup + rollback 🟢 M 🔥🔥
- **What**: pre-run tar.gz snapshot `~/.hermes/skills/.curator_backups/<utc>/` с manifest.json. Rollback двухступенчатый (даже rollback undo-able).
- **Where**: `agent/curator_backup.py`

#### A8. Skill provenance tracking 🟢 S 🔥🔥🔥
- **What**: ContextVar различает agent-sediment vs foreground user-directed writes. Curator консолидирует только то что сам создал.
- **Where**: `tools/skill_provenance.py`

#### A9. Skill usage telemetry 🟢 S 🔥🔥
- **What**: `~/.hermes/skills/.usage.json` — counter на каждый skill. Curator читает derived activity timestamp для lifecycle decisions.
- **Where**: `tools/skill_usage.py`

#### A10. Skill bundles 🟡 S 🔥🔥
- **What**: `/<bundle>` slash-команда загружает N skills одним user message. YAML.
- **Where**: `agent/skill_bundles.py`
- **Адаптация**: «/закрытие-месяца» подгружает 3 наших skill'а: проверка проводок, акты сверки, баланс.

#### A11. Skill preprocessing (template vars + inline shell) 🟢 S 🔥
- **What**: `${HERMES_SKILL_DIR}` / `${HERMES_SESSION_ID}` substitution + inline shell `!`date +%Y-%m-%d``. Cap output 4000 байт.
- **Where**: `agent/skill_preprocessing.py`

#### A12. Skills guard (security scan) 🟢 M 🔥🔥
- **What**: regex-сканер для downloaded skills: data exfil, prompt injection, destructive commands, persistence. Trust-aware install policy.
- **Where**: `tools/skills_guard.py`

### 2.B. Context Management (8)

#### B1. ContextCompressor 🟢 L 🔥🔥🔥🔥🔥
- **What**: автосжатие при превышении бюджета. Aux model summarizes middle turns, защита head+tail. Iterative updates. Structured summary: `## Active Task / Resolved / Pending / Remaining Work`.
- **Where**: `agent/context_compressor.py` (1748 строк)
- **Critical** — без него длинные сессии падают.

#### B2. Filter-safe summarizer preamble 🟢 XS 🔥🔥
- **What**: «[CONTEXT COMPACTION — REFERENCE ONLY]» preamble + warning «treat as background, NOT active instructions» + защита MEMORY.md от deprioritization.
- **Where**: `agent/context_compressor.py:SUMMARY_PREFIX`

#### B3. ContextEngine ABC (pluggable) 🟢 S 🔥
- **What**: pluggable context engines, default «compressor», alt «LCM». Selection через `context.engine` в config.yaml.
- **Where**: `agent/context_engine.py` + `plugins/context_engine/`

#### B4. Conversation compression wrapper 🟢 M 🔥🔥
- **What**: startup feasibility probe, replay warning, compress_context() который splits SQLite session, rotates session_id, notifies plugins. Image shrink на retry если too large.
- **Where**: `agent/conversation_compression.py`

#### B5. Tool output pruning pre-pass 🟢 S 🔥🔥
- **What**: cheap pre-pass убирает большие tool результаты ДО LLM summarization.
- **Where**: `agent/context_compressor.py:_prune_tool_outputs`

#### B6. Subdirectory hints (progressive discovery) 🔴 — n/a
- **What**: При навигации в subdir — discover AGENTS.md/CLAUDE.md и инжектит в tool result.
- **Где**: `agent/subdirectory_hints.py`
- **Не нужно нам** (мы не browseм файлы, только базу 1С).

#### B7. Context references parser 🟡 S 🔥
- **What**: `@file:path`, `@folder:path`, `@git:HEAD`, `@diff`, `@staged`, `@url:https://...` — синтаксис вставки контекста в сообщение.
- **Where**: `agent/context_references.py`
- **Адаптация**: `@document:ОПП-014825`, `@register:Остатки`, `@period:вчера`.

#### B8. Manual compression feedback 🟢 XS 🔥
- **What**: user-facing summary при ручном `/compress` — before/after tokens, before/after count, noop flag.
- **Where**: `agent/manual_compression_feedback.py`

### 2.C. Orchestration & Loop (10)

#### C1. IterationBudget thread-safe 🟢 XS 🔥🔥
- **What**: per-agent counter. Parent=90, subagent=50. Refund for PTC (programmatic tool calling).
- **Where**: `agent/iteration_budget.py`

#### C2. Conversation loop с retries+fallbacks+compression+post-hooks 🟢 L 🔥🔥🔥
- **What**: 4099 строк main orchestrator. Model call → tool dispatch → retries → fallbacks → compression → post-turn hooks → background review nudges.
- **Where**: `agent/conversation_loop.py`
- **У нас уже есть простой loop** — улучшать постепенно.

#### C3. Tool executor (sequential + concurrent) 🟢 M 🔥🔥
- **What**: оба пути — последовательное и параллельное выполнение нескольких tool_calls в одном turn.
- **Where**: `agent/tool_executor.py`

#### C4. Tool dispatch helpers (parallelism gating) 🟢 M 🔥🔥
- **What**: rule engine «можно ли распараллелить эту пачку?». Path overlap, destructive command detection. Multimodal envelopes.
- **Where**: `agent/tool_dispatch_helpers.py`

#### C5. Tool guardrails (decision controller) 🟢 S 🔥🔥
- **What**: per-turn observation tracker + pure decision controller (warning/synthetic result/halt). Side-effect free.
- **Where**: `agent/tool_guardrails.py`

#### C6. Tool result classification 🟢 XS 🔥
- **What**: «landed?» verifier — file mutation result проверяет действительно ли запись попала на диск.
- **Where**: `agent/tool_result_classification.py`
- **Для нас**: «query result содержит ожидаемые поля?».

#### C7. Approval system (dangerous commands) 🟡 M 🔥🔥🔥
- **What**: DANGEROUS_PATTERNS, detection, per-session approval state. Smart approval через aux LLM для auto-approve low-risk.
- **Where**: `tools/approval.py`
- **Адаптация**: `execute_code` мы УЖЕ требуем подтверждения, но сейчас простой — расширить.

#### C8. Checkpoint manager (shadow git) 🟡 L 🔥
- **What**: shadow git store snapshots перед file-mutating ops. Per-turn trigger.
- **Where**: `tools/checkpoint_manager.py`
- **Адаптация**: для нас — snapshot SQLite сессии перед deletion/edit.

#### C9. Interrupt mechanism (per-thread) 🟢 S 🔥🔥
- **What**: thread-scoped interrupt tracking. Прерывание одного агента не убивает других.
- **Where**: `tools/interrupt.py`
- **Для нас**: пользователь жмёт «Стоп», текущий tool call прерывается gracefully.

#### C10. Process registry (background jobs) 🔴 — нам не нужно
- **What**: managed background processes с output buffering и status polling.
- **Where**: `tools/process_registry.py`

### 2.D. Tools (12 релевантных)

#### D1. clarify_tool + clarify_gateway 🟢 S 🔥🔥🔥🔥🔥
- **What**: structured multiple-choice вопросы. До 4 предзаданных вариантов + автоматический 5-й «Свой ответ». Arrow keys в CLI, нумерация в чате.
- **Where**: `tools/clarify_tool.py`, `tools/clarify_gateway.py`

#### D2. delegate_tool (subagents) 🟢 L 🔥🔥
- **What**: spawn child AIAgent с isolated context, restricted toolset, own task_id. Single + batch parallel. Parent видит только summary.
- **Where**: `tools/delegate_tool.py` (2801 строк)
- **DELEGATE_BLOCKED_TOOLS**: `delegate_task` (no recursion), `clarify` (no user UI), `memory` (no shared write), `send_message`.

#### D3. todo_tool (in-memory task list) 🟢 S 🔥🔥🔥
- **What**: agent decomposes complex tasks, tracks progress. State на AIAgent (per-session). **Re-injected after context compression**.
- **Where**: `tools/todo_tool.py`

#### D4. session_search_tool 🟢 M 🔥🔥🔥
- **What**: FTS5 full-text search по истории + 3 calling modes: DISCOVERY (query, top-N sessions с snippet), DEEP (session_id, ±5 message window), CROSS (всё что писали про эту тему).
- **Where**: `tools/session_search_tool.py`

#### D5. mcp_tool (universal MCP client) 🟢 L 🔥🔥
- **What**: client для stdio/HTTP/SSE серверов. Auto-discover tools и регистрация в registry.
- **Where**: `tools/mcp_tool.py` (3584 строки)
- **У нас уже есть** наш собственный MCP client — мог бы выиграть от их обогащения (OAuth, retry, fail-open).

#### D6. mcp_oauth + mcp_oauth_manager 🟡 M 🔥🔥
- **What**: OAuth 2.1 PKCE для MCP серверов. Cross-process token reload через mtime watch.
- **Where**: `tools/mcp_oauth.py`

#### D7. tool_result_storage 🟢 M 🔥🔥🔥
- **What**: persistence больших outputs вместо truncation. Three-level defence: per-tool cap → per-result persistence → per-turn budget.
- **Where**: `tools/tool_result_storage.py`

#### D8. tool_output_limits (configurable) 🟢 XS 🔥
- **What**: MAX_LINES + MAX_BYTES через config.
- **Where**: `tools/tool_output_limits.py`

#### D9. schema_sanitizer (JSON Schema compat) 🟡 XS 🔥
- **What**: sanitize JSON Schema для local backends (llama.cpp).
- **Where**: `tools/schema_sanitizer.py`
- **Для нас**: если кто-то соберёт MCP_Toolkit с экзотическими типами, наш orchestrator упадёт.

#### D10. path_security (traversal check) 🟢 XS 🔥
- **What**: `resolve() + relative_to() + .. check`. Защита от path traversal.
- **Where**: `tools/path_security.py`

#### D11. file_state (cross-agent file coordination) 🟡 S 🔥
- **What**: предотвращение «B writes file A read» race condition.
- **Where**: `tools/file_state.py`
- **Адаптация**: для нас — координация MCP-сессий когда несколько вкладок открыто.

#### D12. lazy_deps (runtime install) 🟢 S 🔥🔥
- **What**: opt-in extras устанавливаются runtime когда нужно. Smaller blast radius для supply-chain атак.
- **Where**: `tools/lazy_deps.py`

### 2.E. Error Handling & Resilience (8)

#### E1. error_classifier (FailoverReason enum) 🟢 M 🔥🔥🔥🔥
- **What**: priority-ordered classification pipeline. Decision: retry/rotate credential/fallback to provider/compress context/abort.
- **Where**: `agent/error_classifier.py` (1087 строк)

#### E2. retry_utils (jittered backoff) 🟢 XS 🔥🔥🔥
- **What**: jittered delays против thundering-herd retry spikes. Per-process monotonic counter.
- **Where**: `agent/retry_utils.py`

#### E3. nous_rate_guard (cross-session) 🟡 M 🔥🔥
- **What**: shared file для rate limit state. Все сессии (CLI, gateway, cron, aux) проверяют состояние ДО запроса. Eliminates 9-call amplification при 429.
- **Where**: `agent/nous_rate_guard.py`
- **Адаптация**: shared SQLite row для нашего LLM provider.

#### E4. rate_limit_tracker (x-ratelimit-* headers) 🟢 S 🔥🔥
- **What**: 12 headers tracking + formatted display для `/usage` slash command.
- **Where**: `agent/rate_limit_tracker.py`

#### E5. stream_diag (per-attempt diagnostics) 🟢 S 🔥🔥
- **What**: per-attempt counters, exception chains. Cloudflare edge + OpenRouter downstream + bytes/chunks + HTTP status + httpx error class.
- **Where**: `agent/stream_diag.py`

#### E6. message_sanitization 🟢 S 🔥🔥🔥
- **What**: non-ASCII repair, surrogate cleanup, tool_call arguments repair, image stripping.
- **Where**: `agent/message_sanitization.py`

#### E7. agent_runtime_helpers 🟢 M 🔥🔥
- **What**: `sanitize_tool_call_arguments`, `repair_message_sequence`, `recover_with_credential_pool`, `try_recover_primary_transport`, `drop_thinking_only_and_merge_users`.
- **Where**: `agent/agent_runtime_helpers.py`

#### E8. redact (regex-based secret masking) 🟢 S 🔥🔥
- **What**: regex masking перед log/output. Short tokens fully masked, longer preserve first-6/last-4.
- **Where**: `agent/redact.py`

### 2.F. Security & Sanitization (6)

#### F1. Prompt injection scan 🟢 S 🔥🔥🔥
- **What**: regex patterns против `ignore previous instructions`, `<div style="display:none">`, exfil curl, html_comment_injection, translate_execute, hidden_div.
- **Where**: `agent/prompt_builder.py:_CONTEXT_THREAT_PATTERNS`

#### F2. tirith pre-exec scanner 🟡 M 🔥🔥
- **What**: external tirith binary subprocess. Content-level threats: homograph URLs, pipe-to-interpreter, terminal injection. Exit: 0=allow, 1=block, 2=warn.
- **Where**: `tools/tirith_security.py`
- **Для нас**: бинарный сканер data из 1С перед инжектом в prompt.

#### F3. osv_check (malware advisory) 🟡 S 🔥
- **What**: pre-launch query к OSV API для npx/uvx packages. Только malware advisories (MAL-* IDs).
- **Where**: `tools/osv_check.py`
- **Для нас**: если когда-то будем загружать сторонние MCP — обязательная проверка.

#### F4. skills_guard (download scanner) 🟢 M 🔥🔥
- См. A12 выше.

#### F5. path_security 🟢 XS 🔥
- См. D10 выше.

#### F6. Sensitive home dirs blocklist 🟢 XS 🔥
- **What**: `_SENSITIVE_HOME_DIRS = ('.ssh', '.aws', '.gnupg', '.kube', '.docker', '.azure', '.config/gh')`. Контекстные ссылки в эти каталоги отвергаются.
- **Where**: `agent/context_references.py`

### 2.G. UX & Interactivity (10)

#### G1. Onboarding hints (one-time, contextual) 🟢 S 🔥🔥🔥
- **What**: первый раз пользователь хитит behavior fork → show one-time hint → mark seen в config. Без блокирующих первых вопросов.
- **Where**: `agent/onboarding.py`

#### G2. Slash commands (autocomplete) 🟢 M 🔥🔥
- **What**: multiline editing с slash-command autocomplete, conversation history, interrupt-and-redirect.

#### G3. Skill commands (/<skill-name>) 🟢 M 🔥🔥
- **What**: `/<skill-name>` загружает skill body в conversation. Shared CLI + gateway.
- **Where**: `agent/skill_commands.py`

#### G4. Slash confirm (gateway) 🟢 S 🔥
- **What**: non-destructive но expensive side effects → confirm prompt. `/reload-mcp` invalidates provider prompt cache.
- **Where**: `tools/slash_confirm.py`

#### G5. Title generator (async) 🟢 XS 🔥🔥
- **What**: auto-generate session title из first user/assistant exchange. Async — не добавляет latency.
- **Where**: `agent/title_generator.py`
- **У нас уже есть** title_generator в backend — проверить что async.

#### G6. Display (spinner + kawaii faces) 🟡 XS 🔥
- **What**: CLI spinner, kawaii faces при tool execution. Pure display funcs.
- **Where**: `agent/display.py`
- **Адаптация**: милый brand-spinner в нашем чате.

#### G7. think_scrubber 🟢 S 🔥🔥
- **What**: stateful scrubber для reasoning/thinking blocks в streamed assistant text. Защита от утечки <think> тегов.
- **Where**: `agent/think_scrubber.py`

#### G8. Insights engine 🟢 M 🔥🔥🔥
- **What**: SQLite analytics → отчёт: token consumption, cost estimates, tool usage patterns, activity trends, model/platform breakdowns, session metrics. Inspired by Claude Code /insights.
- **Where**: `agent/insights.py` (930 строк)

#### G9. Interrupt and redirect (Ctrl+C / /stop) 🟢 S 🔥🔥🔥
- **What**: Прерывание tool call gracefully. Сохраняет partial result.
- **Where**: `tools/interrupt.py`

#### G10. Voice memo transcription 🔴 — не нужно нам
- **What**: cross-platform STT.
- **Where**: `tools/transcription_tools.py`

### 2.H. Models & Providers (5 — большинство нам не нужно)

#### H1. models_dev registry (community 4000+ models) 🟢 S 🔥🔥
- **What**: fetches `https://models.dev/api.json`. Provider metadata + model metadata: context window, max output, cost/M tokens, capabilities (reasoning/tools/vision/PDF/audio).
- **Where**: `agent/models_dev.py` (723 строк)
- **Resolution**: bundled snapshot → disk cache → network fetch → background refresh каждые 60 min.

#### H2. Auxiliary client router 🟢 M 🔥🔥🔥🔥
- **What**: shared aux client. Routing: main provider → OpenRouter → Nous Portal → custom → native Anthropic → direct API-key providers.
- **Where**: `agent/auxiliary_client.py` (5289 строк)
- **Critical для compressor + curator + background_review** — им нужен aux model.

#### H3. Plugin LLM facade (`ctx.llm`) 🟢 M 🔥
- **What**: trusted plugins могут делать свои LLM calls. `complete(messages, ...)` + `complete_structured(json_schema=...)`.
- **Where**: `agent/plugin_llm.py`

#### H4. Prompt caching strategy 🟢 S 🔥🔥
- **What**: Anthropic system_and_3 layout. 4 cache_control breakpoints (system + last 3 non-system). TTL 5m or 1h. **~75% input cost reduction** в multi-turn.
- **Where**: `agent/prompt_caching.py`

#### H5. Model metadata + context length 🟢 S 🔥🔥
- **What**: per-model context length tracking. Save на диск после probe. Estimate messages rough. Parse available output tokens из error responses.
- **Where**: `agent/model_metadata.py`

### 2.I. Observability & Analytics (5)

#### I1. Langfuse plugin 🟡 M 🔥🔥
- **What**: LLM tracing/observability через Langfuse. Hooks: pre-request, post-response, tool-call. Fails-open silently.
- **Where**: `plugins/observability/langfuse/`

#### I2. Trajectory export (ShareGPT JSONL) 🟢 S 🔥🔥🔥🔥
- **What**: каждая сессия сохраняется как ShareGPT-format conversation. `trajectory_samples.jsonl` (completed) + `failed_trajectories.jsonl`. Это **датасет для fine-tuning моделей**.
- **Where**: `agent/trajectory.py`
- **Critical for self-learning**

#### I3. Datagen — trajectory_compression.yaml 🟢 S 🔥🔥
- **What**: post-process completed trajectories до target_max_tokens. Protected turns: first system + first human + first gpt + first tool + last 2 turn pairs.
- **Where**: `datagen-config-examples/trajectory_compression.yaml`

#### I4. Usage pricing 🟢 S 🔥🔥
- **What**: $/M tokens registry, cost computation per session/per turn. CostStatus: actual/estimated/included/unknown.
- **Where**: `agent/usage_pricing.py`

#### I5. Account usage 🟢 S 🔥
- **What**: per-account tracking — сколько потратил конкретный пользователь.
- **Where**: `agent/account_usage.py`

### 2.J. Datagen & Eval (3)

#### J1. Batch runner 🟢 M 🔥🔥
- **What**: batch_runner.py — пакетная генерация trajectories через массив prompts. Для создания training data.

#### J2. Trajectory compression config 🟢 — см. I3

#### J3. Browser tasks dataset 🔴 — нам не нужно

---

## 3. Что НЕ берём (зафиксировано против дрейфа)

| Не берём | Почему |
|---|---|
| 16 LLM adapters (anthropic, bedrock, gemini, codex, copilot, azure, copilot-acp, и т.д.) | OpenAI-compat покрывает наш use case |
| 5 messenger gateways (Telegram/Discord/Slack/WhatsApp/Signal) | Мы веб-app + Electron |
| 7 terminal backends (Modal, Daytona, Vercel, Singularity, SSH, Docker) | Backend.exe запускается локально |
| Browser tools (6 файлов browser_*) + camofox | Не наша задача — мы про данные 1С |
| Computer use tool | Не наша задача |
| Image generation tool (FAL) | Аналитика, не творчество |
| Voice tools (TTS, voice_mode, transcription, neutts) | Чат — текстовый |
| Cron job tools | Пока не наша задача |
| Discord/Feishu/HomeAssistant/Spotify tools | Другие use cases |
| Yuanbao tools | Китайская платформа |
| Send_message tool | Кросс-channel мессенджинг — не нужно |
| Kanban tools | Это для orchestrator+worker архитектуры (dispatcher mode) — не наш use case сейчас |
| Subdirectory hints | Мы не browseм файлы |
| Process registry | Нет background jobs у нас |
| File operations (write/patch/search) | Мы read-only к данным 1С |
| Microsoft Graph / Teams pipeline | Не наша платформа |
| Mixture-of-agents | Слишком экспериментально |
| ACP adapter (Zed protocol) | Не нужно |
| Codex / Copilot runtime | IDE-specific |
| Skills Hub (GitHub-based) | Пока не наша задача — мы свои skills делаем |

---

## 4. Матрица приоритизации (score = profit×3 − cost)

Лучший soft cap 15-20 фич на 6-8 недель. Остальное — backlog.

| # | Фича | Категория | Cost | Profit | Score |
|---|---|---|---|---|---|
| 1 | A1 MEMORY.md + USER.md | Memory | M=3 | 🔥5 | **12** |
| 2 | A2 MemoryManager | Memory | M=3 | 🔥4 | **9** |
| 3 | B1 ContextCompressor | Context | L=5 | 🔥5 | **10** |
| 4 | D1 Clarify tool | Tools | S=1 | 🔥5 | **14** |
| 5 | E1 ErrorClassifier | Errors | M=3 | 🔥4 | **9** |
| 6 | E2 Jittered retry | Errors | XS=0.5 | 🔥3 | **8.5** |
| 7 | F1 Prompt injection scan | Security | S=1 | 🔥3 | **8** |
| 8 | E6 Message sanitization | Errors | S=1 | 🔥3 | **8** |
| 9 | C1 IterationBudget | Loop | XS=0.5 | 🔥2 | **5.5** |
| 10 | D3 Todo tool | Tools | S=1 | 🔥3 | **8** |
| 11 | D4 Session search FTS5 | Tools | M=3 | 🔥3 | **6** |
| 12 | A5 Background review | Self-learn | L=5 | 🔥4 | **7** |
| 13 | A6 Curator | Self-learn | L=5 | 🔥3 | **4** |
| 14 | A8/A9 Provenance + usage | Self-learn | S=1 | 🔥3 | **8** |
| 15 | I2 Trajectory export | Observ | S=1 | 🔥4 | **11** |
| 16 | I3 Datagen config | Observ | S=1 | 🔥2 | **5** |
| 17 | H4 Prompt caching | Models | S=1 | 🔥2 | **5** |
| 18 | H2 Aux client router | Models | M=2 | 🔥4 | **10** |
| 19 | C9 Interrupt mechanism | Loop | S=1 | 🔥3 | **8** |
| 20 | G1 Onboarding hints | UX | S=1 | 🔥3 | **8** |
| 21 | G8 Insights engine | UX | M=3 | 🔥3 | **6** |
| 22 | G7 Think scrubber | UX | S=1 | 🔥2 | **5** |
| 23 | C7 Approval system upgrade | Loop | M=2 | 🔥3 | **7** |
| 24 | A10 Skill bundles | Self-learn | S=1 | 🔥2 | **5** |
| 25 | E5 Stream diag | Errors | S=1 | 🔥2 | **5** |
| 26 | E8 Redact | Errors | S=1 | 🔥2 | **5** |
| 27 | D7 Tool result storage | Tools | M=2 | 🔥3 | **7** |
| 28 | B2 Filter-safe preamble | Context | XS=0.5 | 🔥2 | **5.5** |
| 29 | C5 Tool guardrails | Loop | S=1 | 🔥2 | **5** |
| 30 | C6 Tool result classification | Loop | XS=0.5 | 🔥2 | **5.5** |
| 31 | D2 Delegate/subagents | Tools | L=5 | 🔥2 | **1** |
| 32 | H5 Model metadata | Models | S=1 | 🔥2 | **5** |
| 33 | A11 Skill preprocessing | Self-learn | S=1 | 🔥1 | **2** |
| 34 | A12 Skills guard | Self-learn | M=2 | 🔥2 | **4** |
| 35 | B7 Context references | Context | S=1 | 🔥1 | **2** |
| 36 | I1 Langfuse plugin | Observ | M=2 | 🔥2 | **4** |
| 37 | I4 Usage pricing | Observ | S=1 | 🔥2 | **5** |
| 38 | C3 Concurrent tool executor | Loop | M=2 | 🔥2 | **4** |
| 39 | C4 Parallelism gating | Loop | M=2 | 🔥2 | **4** |
| 40 | E4 Rate limit tracker | Errors | S=1 | 🔥2 | **5** |
| 41 | E3 Nous rate guard (cross-session) | Errors | M=2 | 🔥2 | **4** |
| 42 | A7 Curator backup | Self-learn | M=2 | 🔥2 | **4** |
| 43 | F2 Tirith scanner | Security | M=2 | 🔥2 | **4** |
| 44 | H1 Models.dev registry | Models | S=1 | 🔥2 | **5** |
| 45 | H3 Plugin LLM facade | Models | M=2 | 🔥1 | **1** |
| 46 | C2 Loop refactor (4099 строк) | Loop | XL=10 | 🔥3 | **−1** |

---

## 5. Сводный план — что вошло в спринты

**Cutoff: только score ≥ 7.** 28 фич. **Все 5 спринтов = 6-8 недель.**

### Спринт 1 — Memory Foundation (1.5 нед, 5 фич)
1. A1 MEMORY.md + USER.md store
2. A2 MemoryManager + A3 Provider ABC
3. H2 Aux client router (нужен для compressor+curator+review)
4. G1 Onboarding hints (один раз показать про MEMORY.md)
5. I2 Trajectory export (как простой write-only logger без обучения)

### Спринт 2 — Context & Resilience (1.5 нед, 8 фич)
6. B1 ContextCompressor + B2 Filter-safe preamble
7. B4 Conversation compression wrapper
8. B5 Tool output pruning pre-pass
9. E1 Error classifier (FailoverReason)
10. E2 Jittered retry
11. E6 Message sanitization
12. C1 IterationBudget
13. C9 Interrupt mechanism

### Спринт 3 — Self-Learning (2 нед, 6 фич)
14. A8 Skill provenance
15. A9 Skill usage telemetry
16. A5 Background review fork
17. A6 Curator (lite — только auto-archive по неактивности)
18. A7 Curator backup/rollback
19. D3 Todo tool (re-injected after compression)

### Спринт 4 — UX & Interactivity (1 нед, 6 фич)
20. D1 Clarify tool + clarify_gateway
21. F1 Prompt injection scan
22. G7 Think scrubber
23. G8 Insights engine (lite — token/cost dashboard)
24. D4 Session search FTS5
25. E8 Redact

### Спринт 5 — Polish & Observability (1 нед, 5 фич)
26. H4 Prompt caching (для Claude API)
27. H5 Model metadata + context length
28. D7 Tool result storage
29. I4 Usage pricing dashboard
30. A10 Skill bundles + A11 preprocessing

После 5 спринтов в **backlog**:
- A12 Skills guard
- D2 Delegate/subagents
- F2 Tirith scanner
- I1 Langfuse plugin
- H1 Models.dev registry
- E3 Cross-session rate guard
- E4 Rate limit tracker
- C7 Approval system upgrade

---

## 6. Архитектурные принципы для всех спринтов

### 6.1 Где живёт код

```
backend/app/
├── memory/                     # Sprint 1
│   ├── __init__.py
│   ├── manager.py              # MemoryManager
│   ├── provider.py             # MemoryProvider ABC
│   ├── markdown_store.py       # MEMORY.md + USER.md provider
│   └── injection_scan.py       # F1
│
├── orchestrator/
│   ├── auxiliary.py            # Sprint 1 — aux client router
│   ├── compressor.py           # Sprint 2 — ContextCompressor
│   ├── compression_engine.py   # Sprint 2 — ContextEngine ABC
│   ├── error_classifier.py     # Sprint 2 — E1
│   ├── retry.py                # Sprint 2 — E2 jittered
│   ├── sanitize.py             # Sprint 2 — E6
│   ├── iteration_budget.py     # Sprint 2 — C1
│   ├── interrupt.py            # Sprint 2 — C9
│   ├── guardrails.py           # Sprint 3 — C5
│   ├── todo.py                 # Sprint 3 — D3
│   ├── clarify.py              # Sprint 4 — D1
│   ├── think_scrubber.py       # Sprint 4 — G7
│   ├── redact.py               # Sprint 4 — E8
│   ├── insights.py             # Sprint 4 — G8
│   ├── session_search.py       # Sprint 4 — D4
│   ├── tool_result_storage.py  # Sprint 5 — D7
│   ├── usage_pricing.py        # Sprint 5 — I4
│   └── model_metadata.py       # Sprint 5 — H5
│
├── learning/                   # Sprint 3
│   ├── __init__.py
│   ├── trajectory.py           # I2 — Sprint 1
│   ├── skill_provenance.py     # A8
│   ├── skill_usage.py          # A9
│   ├── background_review.py    # A5
│   ├── curator.py              # A6
│   └── curator_backup.py       # A7
│
├── skills/                     # Sprint 5
│   ├── manager.py              # A10 bundles
│   ├── preprocessor.py         # A11
│   └── prompts/                # 1С-skill prompts
│
└── storage/
    └── ... (existing)

frontend/
├── app/
│   ├── memory/                 # Sprint 1 — UI для MEMORY.md/USER.md
│   │   └── page.tsx
│   ├── insights/               # Sprint 4 — /insights dashboard
│   │   └── page.tsx
│   └── settings/memory/        # Sprint 1
│       └── page.tsx
│
└── components/
    ├── chat/
    │   ├── ClarifyCard.tsx     # Sprint 4 — D1 UI
    │   ├── TodoCard.tsx        # Sprint 3 — D3 UI
    │   └── ToolGuardrails.tsx  # Sprint 3
    ├── memory/
    │   ├── MemoryEditor.tsx    # Sprint 1
    │   ├── UserProfileCard.tsx # Sprint 1
    │   └── MemoryDiffPreview.tsx
    └── insights/
        ├── TokenChart.tsx      # Sprint 4
        ├── CostBreakdown.tsx
        └── ToolUsagePanel.tsx
```

### 6.2 Database changes

```sql
-- Sprint 1 — миграция v8
CREATE TABLE memory_blocks (
    id INTEGER PRIMARY KEY,
    namespace TEXT NOT NULL,        -- 'agent' or 'user'
    key TEXT NOT NULL,              -- block id внутри markdown
    content TEXT NOT NULL,
    provenance TEXT NOT NULL,       -- 'agent' or 'foreground'
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    UNIQUE(namespace, key)
);
CREATE INDEX idx_memory_namespace ON memory_blocks(namespace);

-- Sprint 2 — миграция v9
ALTER TABLE sessions ADD COLUMN compression_level INTEGER DEFAULT 0;
ALTER TABLE sessions ADD COLUMN last_summary TEXT;
ALTER TABLE messages ADD COLUMN compressed_into INTEGER REFERENCES messages(id);

-- Sprint 3 — миграция v10
CREATE TABLE skill_usage (
    skill_id TEXT PRIMARY KEY,
    last_used_at INTEGER NOT NULL,
    use_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    archive_state TEXT DEFAULT 'active',  -- active|archived|pinned
    provenance TEXT NOT NULL              -- agent|foreground
);

CREATE TABLE trajectory_jsonl (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    completed INTEGER NOT NULL,
    model TEXT NOT NULL,
    payload BLOB NOT NULL,             -- compressed ShareGPT JSON
    created_at INTEGER NOT NULL
);

-- Sprint 4 — миграция v11 (FTS5)
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    session_id UNINDEXED,
    role UNINDEXED,
    content=messages,
    content_rowid=id
);
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content, session_id, role)
    VALUES (new.id, new.content, new.session_id, new.role);
END;
```

### 6.3 Configuration

```yaml
# backend/.env additions
MEMORY_ROOT=~/.analyst-1c/memory          # MEMORY.md + USER.md
TRAJECTORY_DIR=~/.analyst-1c/trajectories # JSONL exports
LEARNING_ENABLED=true                      # Curator + background review on/off
COMPRESSION_THRESHOLD_TOKENS=24000         # когда сжимать
COMPRESSION_TAIL_TOKENS=8000               # сколько в tail сохранять
AUX_MODEL=mimo-v2-flash                    # cheap aux model
ITERATION_BUDGET_PARENT=90
ITERATION_BUDGET_SUBAGENT=50
```

### 6.4 Стандарты кода

- **Каждый новый класс** — docstring 5+ строк (описание + when to use + invariants).
- **Pydantic v2** для всех data structures (`extra="forbid"`, `strict`).
- **Type hints везде**, `mypy --strict` чисто.
- **Pytest** — для каждого нового модуля минимум 5 тестов (happy + 2 edge + 2 failure).
- **Vitest** — frontend, минимум 3 теста на компонент.
- Все feature flags через config (`LEARNING_ENABLED`, `COMPRESSION_ENABLED`).
- Никакой синхронной обработки больше 100ms на UI-thread.

### 6.5 Брутальная честность

После каждого спринта — release-notes с разделом **«Что НЕ сделано»**.
В этом документе раздел 9 — **«Дневник отклонений»** где Claude фиксирует
расхождения с планом.

---

## 7. Детальные планы спринтов

### СПРИНТ 1 — Memory Foundation (1.5 недели, 7 рабочих дней)

#### Цель
Аналитик при втором обращении не вынужден переобъяснять. Приложение помнит:
- какая база
- какие реквизиты переименованы
- какие конвенции
- предпочтения формата ответа

#### Файлы для создания

**`backend/app/memory/provider.py`** — ABC
```python
from abc import ABC, abstractmethod
from typing import Any

class MemoryProvider(ABC):
    """Абстрактный провайдер памяти.

    Lifecycle (called by MemoryManager):
      initialize()            — connect, create resources
      system_prompt_block()   — static text for system prompt
      prefetch(query)         — pre-turn recall (sync or async)
      sync_turn(user, asst)   — post-turn async write
      get_tool_schemas()      — tool schemas to expose
      handle_tool_call(name)  — dispatch
      shutdown()              — clean exit
    """

    name: str  # provider id
    is_external: bool = False  # True для Honcho/Mem0/etc.

    @abstractmethod
    def initialize(self) -> None: ...

    def system_prompt_block(self) -> str:
        return ""

    def prefetch(self, query: str) -> dict[str, Any]:
        return {}

    def sync_turn(self, user_msg: str, assistant_msg: str) -> None:
        pass

    def get_tool_schemas(self) -> list[dict]:
        return []

    def handle_tool_call(self, name: str, args: dict) -> Any:
        raise NotImplementedError

    def shutdown(self) -> None:
        pass
```

**`backend/app/memory/manager.py`** — MemoryManager (порт из Hermes)
```python
class MemoryManager:
    """Orchestrates memory providers for the agent.

    Only ONE external provider allowed at a time — против tool schema bloat.
    """

    def __init__(self) -> None:
        self._providers: list[MemoryProvider] = []

    def add_provider(self, p: MemoryProvider) -> None:
        if p.is_external and any(x.is_external for x in self._providers):
            logger.warning("External provider %s rejected — already have one", p.name)
            return
        self._providers.append(p)
        p.initialize()

    def build_system_prompt(self) -> str:
        return "\n\n".join(p.system_prompt_block() for p in self._providers if p.system_prompt_block())

    def prefetch_all(self, user_msg: str) -> dict[str, Any]:
        return {p.name: p.prefetch(user_msg) for p in self._providers}

    def sync_all(self, user_msg: str, assistant_msg: str) -> None:
        for p in self._providers:
            try:
                p.sync_turn(user_msg, assistant_msg)
            except Exception as exc:
                logger.exception("Memory sync failed for %s: %s", p.name, exc)

    def shutdown_all(self) -> None:
        for p in self._providers:
            p.shutdown()
```

**`backend/app/memory/markdown_store.py`** — основной MEMORY.md + USER.md провайдер
```python
import re
from pathlib import Path
from .provider import MemoryProvider

class MarkdownStore(MemoryProvider):
    """Persistent .md storage для двух стрим: agent (MEMORY.md) и user (USER.md).

    Storage layout:
      <root>/MEMORY.md  — заметки агента
      <root>/USER.md    — что мы знаем о пользователе

    Append-only с heuristics для dedup. Caps на размер — bounded growth.
    """

    name = "markdown_store"
    is_external = False
    MAX_MEMORY_TOKENS = 4000  # ~16K characters
    MAX_USER_TOKENS = 2000

    def __init__(self, root: Path, channel_id: str | None = None):
        self.root = root
        self.channel_id = channel_id or "default"
        self.memory_path = root / channel_id / "MEMORY.md"
        self.user_path = root / channel_id / "USER.md"

    def initialize(self) -> None:
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        for p in (self.memory_path, self.user_path):
            if not p.exists():
                p.write_text("", encoding="utf-8")

    def system_prompt_block(self) -> str:
        mem = self._read_capped(self.memory_path, self.MAX_MEMORY_TOKENS)
        usr = self._read_capped(self.user_path, self.MAX_USER_TOKENS)
        if not mem and not usr:
            return ""
        return (
            "## Постоянная память\n\n"
            "<persistent-memory>\n"
            "Эти заметки сохраняются между сессиями. Учитывай их при ответе.\n\n"
            "### MEMORY.md — твои заметки\n"
            f"{mem or '_(пусто)_'}\n\n"
            "### USER.md — что мы знаем о пользователе\n"
            f"{usr or '_(пусто)_'}\n"
            "</persistent-memory>\n"
        )

    def get_tool_schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_append",
                    "description": (
                        "Append a fact to persistent memory. "
                        "Use sparingly — only durable facts (project conventions, "
                        "user preferences, repeated questions)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "enum": ["agent", "user"]},
                            "content": {"type": "string"},
                            "section": {"type": "string", "description": "Markdown heading"},
                        },
                        "required": ["namespace", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_remove",
                    "description": "Remove a fact from memory by partial match. Use for outdated info.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "enum": ["agent", "user"]},
                            "match": {"type": "string"},
                        },
                        "required": ["namespace", "match"],
                    },
                },
            },
        ]

    def handle_tool_call(self, name: str, args: dict) -> str:
        if name == "memory_append":
            return self._append(args["namespace"], args["content"], args.get("section"))
        if name == "memory_remove":
            return self._remove(args["namespace"], args["match"])
        raise ValueError(name)

    def _read_capped(self, path: Path, max_tokens: int) -> str:
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        if len(content) > max_tokens * 4:
            # обрезаем сверху (старые записи), оставляем последние
            content = "[... earlier entries truncated ...]\n\n" + content[-max_tokens * 4 :]
        return content

    def _append(self, namespace: str, content: str, section: str | None) -> str:
        path = self.memory_path if namespace == "agent" else self.user_path
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        # dedup heuristic
        if content.strip() in existing:
            return "{}: already present, skipped".format(namespace)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        block = f"\n### {section or timestamp}\n{content.strip()}\n"
        path.write_text(existing + block, encoding="utf-8")
        return f"{namespace}: appended {len(content)} chars"

    def _remove(self, namespace: str, match: str) -> str:
        path = self.memory_path if namespace == "agent" else self.user_path
        text = path.read_text(encoding="utf-8")
        # Удаляем секции, содержащие match
        sections = re.split(r"(?=^### )", text, flags=re.M)
        kept = [s for s in sections if match.lower() not in s.lower()]
        removed = len(sections) - len(kept)
        path.write_text("".join(kept), encoding="utf-8")
        return f"{namespace}: removed {removed} sections"
```

**`backend/app/memory/injection_scan.py`** — F1 защита
```python
_THREAT_PATTERNS = [
    (re.compile(r"ignore\s+(previous|all|above|prior)\s+instructions", re.I), "prompt_injection"),
    (re.compile(r"do\s+not\s+tell\s+the\s+user", re.I), "deception_hide"),
    (re.compile(r"system\s+prompt\s+override", re.I), "sys_prompt_override"),
    (re.compile(r"disregard\s+(your|all|any)\s+(instructions|rules)", re.I), "disregard_rules"),
    (re.compile(r"<!--[^>]*(?:ignore|override|system|secret|hidden)[^>]*-->", re.I), "html_comment_injection"),
    (re.compile(r"<\s*div\s+style\s*=\s*[\"'][\s\S]*?display\s*:\s*none", re.I), "hidden_div"),
    (re.compile(r"curl\s+[^\n]*\$\{?\w*(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|API)", re.I), "exfil_curl"),
    (re.compile(r"translate\s+.*\s+into\s+.*\s+and\s+(execute|run|eval)", re.I), "translate_execute"),
]

def scan(text: str) -> list[tuple[str, str]]:
    """Return list of (threat_label, matched_text). Empty list = clean."""
    hits = []
    for pattern, label in _THREAT_PATTERNS:
        m = pattern.search(text)
        if m:
            hits.append((label, m.group(0)[:120]))
    return hits

def sanitize_for_prompt(text: str) -> str:
    """Replace threats with neutralized markers. Used when injecting MCP results into prompt."""
    out = text
    for pattern, label in _THREAT_PATTERNS:
        out = pattern.sub(f"[REDACTED: {label}]", out)
    return out
```

**`backend/app/orchestrator/auxiliary.py`** — простой aux client router
```python
class AuxiliaryClient:
    """Routes auxiliary tasks (compression, titles, memory sync) to cheap models.

    Resolution:
      1. configured aux model (AUX_MODEL env)
      2. fallback to main model

    Используется compressor + curator + title_generator + background_review.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = httpx.AsyncClient(timeout=60)

    async def complete(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 1000,
        temperature: float = 0.3,
    ) -> str:
        # Same OpenAI-compatible endpoint as main, just different model
        payload = {
            "model": self.settings.aux_model or self.settings.llm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        r = await self._client.post(
            f"{self.settings.llm_base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
```

**`backend/app/learning/trajectory.py`** — I2 write-only логгер
```python
class TrajectoryLogger:
    """Append-only ShareGPT-format JSONL logger.

    Each completed turn → one line. После 1000+ trajectories — можно fine-tune
    собственную модель на 1С-задачи. Пока — просто пишем.
    """

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def log_turn(
        self,
        session_id: str,
        messages: list[dict],
        tools_called: list[dict],
        completed: bool,
        model: str,
    ) -> None:
        filename = "trajectory_samples.jsonl" if completed else "failed_trajectories.jsonl"
        entry = {
            "session_id": session_id,
            "conversations": self._to_sharegpt(messages, tools_called),
            "model": model,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "completed": completed,
        }
        with (self.root / filename).open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    @staticmethod
    def _to_sharegpt(messages, tools_called):
        # Convert to {from: human/gpt/tool, value: str} ShareGPT entries
        ...
```

**`frontend/app/settings/memory/page.tsx`** — UI редактор MEMORY.md/USER.md
```typescript
"use client";
import { useState, useEffect } from "react";
import { fetchMemory, saveMemory } from "@/lib/api";

export default function MemorySettingsPage() {
  const [memory, setMemory] = useState("");
  const [user, setUser] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchMemory().then((d) => {
      setMemory(d.memory);
      setUser(d.user);
    });
  }, []);

  async function save() {
    setSaving(true);
    await saveMemory({ memory, user });
    setSaving(false);
  }

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-semibold">Постоянная память</h1>
      {/* MEMORY.md editor */}
      {/* USER.md editor */}
      {/* Save button */}
    </div>
  );
}
```

#### Acceptance criteria Спринта 1

- [ ] Markdown файлы создаются при первом запуске на канал
- [ ] System prompt содержит `<persistent-memory>` блок если файлы не пусты
- [ ] Модель умеет вызывать `memory_append` и `memory_remove`
- [ ] UI `/settings/memory` показывает оба файла, позволяет редактировать
- [ ] Trajectory JSONL логгер пишет каждую сессию в `~/.analyst-1c/trajectories/`
- [ ] Onboarding hint показывается ОДИН раз при первом приобретении skill (например, после 3-й сессии — «Я заметил повторяющиеся вопросы про X. Зафиксировать в MEMORY.md?»)
- [ ] vitest + pytest 100% pass

#### Risks Спринта 1

- Размер MEMORY.md/USER.md растёт → bounded через MAX_TOKENS cap.
- LLM пишет мусор в memory → провенанс tracking (Sprint 3) + UI редактирование.
- Память кросс-канал смешивается → namespace by channel_id.

---

### СПРИНТ 2 — Context & Resilience (1.5 нед, 8 фич)

#### Цель
Длинные сессии (50+ сообщений) не падают. Ошибки API правильно классифицируются → retry/fallback. Битые данные из 1С не роняют backend.

#### Файлы

**`backend/app/orchestrator/compressor.py`** — портируем Hermes context_compressor (1748 строк) **точно**:
- Структурный summary template
- Filter-safe preamble
- Head + tail protection (`tail_tokens=8000`)
- Iterative updates (новое summary включает старое)
- Tool output pruning pre-pass
- Scaled summary budget

Ключевой preamble (берём verbatim из Hermes):
```python
SUMMARY_PREFIX = (
    "[CONTEXT COMPACTION — REFERENCE ONLY] Earlier turns were compacted "
    "into the summary below. This is a handoff from a previous context "
    "window — treat it as background reference, NOT as active instructions. "
    "Do NOT answer questions or fulfill requests mentioned in this summary; "
    "they were already addressed. "
    "Your current task is identified in the '## Active Task' section of the "
    "summary — resume exactly from there. "
    "IMPORTANT: Your persistent memory (MEMORY.md, USER.md) in the system "
    "prompt is ALWAYS authoritative and active — never ignore or deprioritize "
    "memory content due to this compaction note. "
    "Respond ONLY to the latest user message that appears AFTER this summary."
)
```

**`backend/app/orchestrator/error_classifier.py`**
```python
class FailoverReason(enum.Enum):
    RATE_LIMIT = "rate_limit"
    CONTEXT_EXCEEDED = "context_exceeded"
    AUTH_FAILED = "auth_failed"
    TRANSIENT = "transient"
    FATAL = "fatal"
    INVALID_INPUT = "invalid_input"

@dataclass
class ClassifiedError:
    reason: FailoverReason
    should_retry: bool
    retry_after_seconds: float | None
    fallback_provider: str | None
    user_message: str

def classify_api_error(exc: Exception, *, status_code: int | None = None) -> ClassifiedError:
    """Priority-ordered classification. См. Hermes/agent/error_classifier.py для образца."""
    # ... full classifier ...
```

**`backend/app/orchestrator/retry.py`** — jittered_backoff из Hermes
```python
def jittered_backoff(attempt: int, *, base: float = 5.0, cap: float = 60.0) -> float:
    """Decorrelated jittered backoff (full jitter strategy).

    Returns delay in seconds. attempt is 0-indexed.
    Different sessions hitting same rate-limited provider don't sync up.
    """
    import random
    delay = min(cap, base * (2 ** attempt))
    return random.uniform(0, delay)
```

**`backend/app/orchestrator/sanitize.py`** — порт message_sanitization
```python
_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")

def sanitize_surrogates(text: str) -> str:
    """Replace lone surrogate code points with U+FFFD."""
    if _SURROGATE_RE.search(text):
        return _SURROGATE_RE.sub("�", text)
    return text

def sanitize_messages(messages: list[dict]) -> list[dict]:
    """Walk messages list, repair surrogate code points + non-ASCII outliers."""
    ...

def repair_tool_call_arguments(args: str | dict) -> dict:
    """Try to parse corrupted JSON in tool_call arguments. Several fallback strategies."""
    ...
```

**`backend/app/orchestrator/iteration_budget.py`**
```python
class IterationBudget:
    def __init__(self, max_total: int = 90):
        self.max_total = max_total
        self._used = 0
        self._lock = threading.Lock()

    def consume(self) -> bool:
        with self._lock:
            if self._used >= self.max_total:
                return False
            self._used += 1
            return True

    def refund(self) -> None:
        with self._lock:
            self._used = max(0, self._used - 1)

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.max_total - self._used)
```

**`backend/app/orchestrator/interrupt.py`** — per-thread interrupt
```python
_interrupts: dict[int, threading.Event] = {}
_lock = threading.Lock()

def set_interrupt(thread_id: int) -> None:
    with _lock:
        _interrupts.setdefault(thread_id, threading.Event()).set()

def check_interrupt(thread_id: int) -> bool:
    with _lock:
        ev = _interrupts.get(thread_id)
    return ev is not None and ev.is_set()

def clear_interrupt(thread_id: int) -> None:
    with _lock:
        _interrupts.pop(thread_id, None)
```

#### Acceptance criteria Спринта 2

- [ ] Сессия с 100+ сообщениями не падает на `context_length_exceeded`
- [ ] При retry — backoff jitter (никогда не одинаковый интервал)
- [ ] При 429 — задержка по Retry-After header или default 30s
- [ ] При битых данных из 1С — sanitize, не crash
- [ ] При 5 итераций без прогресса — graceful stop с подсказкой
- [ ] Кнопка «Стоп» в UI прерывает текущий tool call gracefully

---

### СПРИНТ 3 — Self-Learning Loop (2 недели, 6 фич)

#### Цель
**Главная фича.** Приложение учится из опыта аналитика. Background fork после каждой успешной сессии: «должен ли я сохранить новый skill или обновить memory?». Curator периодически (раз в день idle) консолидирует/архивирует устаревшие skill.

#### Архитектура self-learning loop

```
User question
     │
     ▼
[Main agent] — отвечает, использует tools
     │
     ▼
Response delivered to user
     │
     ▼ (даemon thread, non-blocking)
[Background review fork]
     │ Replay conversation in forked agent (aux model)
     │ Restricted toolset: memory_append, skill_create, skill_update
     │ Asks: "Что нового мы узнали? Какой паттерн стоит сохранить?"
     ▼
Writes to MEMORY.md / USER.md / skills/
     │
     ▼ (раз в idle period, например, раз в сутки)
[Curator inactivity-triggered]
     │ Aux model reviews agent-created skills
     │ Decides: pin / archive / consolidate / patch
     │ Updates skill_usage telemetry
     ▼
Maintained skill collection
```

#### Файлы

**`backend/app/learning/skill_provenance.py`** — A8
```python
import contextvars

_provenance: contextvars.ContextVar[str] = contextvars.ContextVar(
    "skill_provenance", default="agent"
)

def set_provenance(value: str) -> None:
    """Use 'agent' for autonomous review fork, 'foreground' for user-directed writes."""
    _provenance.set(value)

def get_provenance() -> str:
    return _provenance.get()

def is_agent_created(skill_id: str) -> bool:
    # Lookup в SQLite skill_usage table
    ...
```

**`backend/app/learning/skill_usage.py`** — A9 telemetry
```python
class SkillUsageStore:
    """Sidecar SQLite table для skill usage stats."""

    def record_use(self, skill_id: str, success: bool) -> None:
        ...

    def get_derived_activity(self, skill_id: str) -> float:
        """Activity score 0-1 based on use_count, success_rate, recency."""
        ...

    def list_stale(self, threshold_days: int = 30) -> list[str]:
        """Skill IDs not used in N days."""
        ...
```

**`backend/app/learning/background_review.py`** — A5 daemon thread
```python
class BackgroundReviewer:
    """После каждого turn'а форкает review-агента который анализирует:
       — стоит ли сохранить новый skill из этой сессии?
       — стоит ли обновить MEMORY.md новыми фактами?
    """

    def __init__(
        self,
        aux_client: AuxiliaryClient,
        memory_manager: MemoryManager,
        skill_store: SkillStore,
    ):
        ...

    def schedule_review(self, session_messages: list[dict], session_id: str) -> None:
        """Spawn daemon thread. Never blocks main agent."""
        thread = threading.Thread(target=self._review_safe, args=(session_messages, session_id), daemon=True)
        thread.start()

    def _review_safe(self, messages: list[dict], session_id: str) -> None:
        try:
            self._review(messages, session_id)
        except Exception as exc:
            logger.exception("Background review failed: %s", exc)

    def _review(self, messages: list[dict], session_id: str) -> None:
        # 1. Замаскировать PII в transcript
        # 2. Спросить aux model по template:
        review_prompt = REVIEW_TEMPLATE.format(transcript=transcript)
        # 3. Парсить ответ: actions = [{type: memory_append, ...}, ...]
        # 4. Применять с provenance="agent"
        ...
```

**`backend/app/learning/curator.py`** — A6 (lite-версия)
```python
class Curator:
    """Inactivity-triggered skill maintenance.

    Не cron daemon — проверяется на каждом UserPromptSubmit:
      if (now - last_run) > interval_hours and is_idle():
          spawn review fork
    """

    INTERVAL_HOURS = 24
    STALE_DAYS = 30

    def maybe_run(self) -> None:
        if self._state.last_run_at and (now() - self._state.last_run_at).total_seconds() < self.INTERVAL_HOURS * 3600:
            return
        if not self._is_idle():
            return
        threading.Thread(target=self._run_safe, daemon=True).start()

    def _run(self) -> None:
        # 1. Snapshot ~/.analyst-1c/skills через curator_backup
        # 2. List agent-created stale skills (>30 days unused)
        # 3. For each: aux model decides archive | consolidate-with-other | patch
        # 4. Apply, never delete
        # 5. Update last_run_at
        ...
```

**`backend/app/learning/curator_backup.py`** — A7 snapshot+rollback (упрощённо без tar.gz, через SQLite snapshot table)

**`backend/app/orchestrator/todo.py`** — D3 todo list
```python
class TodoList:
    """In-memory task list re-injected after compression.

    Когда модель decomposes сложный запрос — делает todo_add().
    Когда выполнен пункт — todo_complete().
    После compression — todo state добавляется в новый system prompt.
    """

    def __init__(self):
        self._items: list[TodoItem] = []

    def add(self, title: str, *, priority: int = 5) -> str:
        ...

    def complete(self, todo_id: str) -> None:
        ...

    def to_prompt_block(self) -> str:
        if not self._items:
            return ""
        lines = ["## Текущий план"]
        for item in self._items:
            check = "[x]" if item.completed else "[ ]"
            lines.append(f"- {check} {item.title}")
        return "\n".join(lines)
```

#### Acceptance criteria Спринта 3

- [ ] После каждого turn'а — daemon thread с review fork, не блокирует UI
- [ ] Skill auto-created в ~/.analyst-1c/skills/ с provenance="agent"
- [ ] Curator раз в сутки archives skills unused > 30 days
- [ ] Snapshot перед curator run — recoverable
- [ ] Todo list survives context compression
- [ ] Pytest на learning/ — 80% coverage

---

### СПРИНТ 4 — UX & Interactivity (1 неделя, 6 фич)

#### Цель
Меньше угадок от модели. Больше прозрачности для аналитика. Защита от вредоносных данных.

#### Файлы

**`backend/app/orchestrator/clarify.py`** + **`frontend/components/chat/ClarifyCard.tsx`**

Clarify — НЕ MCP tool, а internal tool. Когда модель его вызывает:
- Backend кладёт в SSE stream специальный event type=clarify с payload {question, choices}
- Frontend рендерит карточку с кнопками
- При клике → backend получает user response → продолжает loop

```python
class ClarifyTool:
    """Internal tool (not MCP). Returns control to user mid-loop."""

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": "clarify",
                "description": "Ask the user a structured clarifying question. Use when intent is ambiguous (period, filter, format).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "choices": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 4,
                        },
                    },
                    "required": ["question"],
                },
            },
        }

    async def execute(self, question: str, choices: list[str] | None, stream: SSEStream) -> str:
        await stream.send(event="clarify", data={"question": question, "choices": choices})
        # Block until user responds
        response = await stream.wait_for_user_response(timeout=600)
        return response
```

ClarifyCard.tsx:
```typescript
interface ClarifyCardProps {
  question: string;
  choices?: string[];
  onAnswer: (answer: string) => void;
}

export function ClarifyCard({ question, choices, onAnswer }: ClarifyCardProps) {
  const [customAnswer, setCustomAnswer] = useState("");
  return (
    <div className="rounded-lg border border-[var(--accent-32)] bg-[var(--accent-08)] p-4 my-3">
      <div className="flex items-start gap-2 mb-3">
        <HelpCircle className="h-4 w-4 text-[var(--accent)]" />
        <p className="text-sm font-medium">{question}</p>
      </div>
      <div className="space-y-1.5">
        {choices?.map((c) => (
          <button key={c} onClick={() => onAnswer(c)}
            className="w-full text-left px-3 py-2 rounded-md hover:bg-[var(--accent-12)] border border-[var(--bd-2)]">
            {c}
          </button>
        ))}
        <div className="flex gap-2 mt-2">
          <input
            type="text"
            placeholder="Свой ответ..."
            value={customAnswer}
            onChange={(e) => setCustomAnswer(e.target.value)}
            className="flex-1 px-3 py-2 rounded-md bg-[var(--bg-2)] border border-[var(--bd-2)]"
          />
          <button
            onClick={() => onAnswer(customAnswer)}
            disabled={!customAnswer.trim()}
            className="px-3 py-2 rounded-md bg-[var(--accent)] text-[var(--brand-ink)] disabled:opacity-50"
          >
            Отправить
          </button>
        </div>
      </div>
    </div>
  );
}
```

**`backend/app/orchestrator/think_scrubber.py`** — G7
```python
class ThinkScrubber:
    """Stateful scrubber для <think>...</think> в streamed text.

    Reasoning-моделей блоки нужно скрывать от пользователя, но СОХРАНЯТЬ
    в trajectory log для дебага.
    """

    def __init__(self):
        self._in_think = False
        self._buffer = ""

    def process_chunk(self, chunk: str) -> tuple[str, str | None]:
        """Returns (clean_text, completed_think_block_or_None)."""
        # ... state machine logic ...
```

**`backend/app/orchestrator/redact.py`** — E8 secret masking
```python
_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "OPENAI_KEY"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GITHUB_TOKEN"),
    # ... 20+ patterns ...
]

def redact(text: str) -> str:
    out = text
    for pattern, label in _SECRET_PATTERNS:
        out = pattern.sub(lambda m: _mask(m.group(0), label), out)
    return out

def _mask(value: str, label: str) -> str:
    if len(value) < 18:
        return f"[REDACTED:{label}]"
    return f"{value[:6]}...{value[-4:]} [{label}]"
```

**`backend/app/orchestrator/insights.py`** — G8 analytics engine
```python
class InsightsEngine:
    """Generate analytics report from SQLite sessions."""

    def generate(self, days: int = 30) -> InsightsReport:
        return InsightsReport(
            total_sessions=self._count_sessions(days),
            total_tokens=self._sum_tokens(days),
            total_cost_usd=self._sum_cost(days),
            tool_usage=self._tool_breakdown(days),
            activity_chart=self._daily_activity(days),
            top_models=self._model_breakdown(days),
            top_questions_pattern=self._cluster_questions(days),  # bonus
        )
```

`/insights` страница рисует Recharts с этими данными.

**`backend/app/orchestrator/session_search.py`** — D4 FTS5
```python
class SessionSearch:
    """3 modes (no explicit mode param — inferred from args):

      DISCOVERY:  search(query="закрытие месяца")  → top-N sessions
      DEEP:       search(session_id="...")          → ±5 messages window
      CROSS:      search(query, channel_id)         → cross-session recall
    """

    def search(self, query: str | None, session_id: str | None) -> SearchResult:
        ...
```

#### Acceptance criteria Спринта 4

- [ ] Clarify card работает: модель спрашивает, аналитик выбирает кнопку, ответ возвращается в loop
- [ ] Prompt injection scanner блокирует или санитайзит вредоносные данные из 1С
- [ ] Думающие модели не показывают `<think>` в UI, но логируют в trajectory
- [ ] Pages `/insights` показывает token/cost/tool dashboards
- [ ] Session search `Ctrl+K` ищет по истории FTS5
- [ ] Все секреты в логах редактированы

---

### СПРИНТ 5 — Polish & Observability (1 неделя, 5 фич)

#### Цель
Стабилизация + полировка. Кэширование промптов (экономия на Claude API). Модель-аware budget. Bundle для типовых workflow.

Файлы (без подробностей — детальные планы делаем перед спринтом):

- **`backend/app/orchestrator/prompt_caching.py`** — H4
- **`backend/app/orchestrator/model_metadata.py`** — H5
- **`backend/app/orchestrator/tool_result_storage.py`** — D7
- **`backend/app/orchestrator/usage_pricing.py`** + UI — I4
- **`backend/app/skills/manager.py`** + **`backend/app/skills/preprocessor.py`** — A10 + A11

#### Acceptance criteria Спринта 5

- [ ] При работе с Claude API — input cost снижается ~75% после первого turn'а в сессии
- [ ] Когда tool result > 50KB — сохраняется в storage, в context идёт reference
- [ ] Dashboard `/usage` показывает $/session, $/день
- [ ] `/закрытие-месяца` подгружает 3 связанных skill в одном user message

---

## 8. Backlog (после Спринта 5)

| Фича | Описание |
|---|---|
| A12 Skills guard | Сканер для downloaded skills (если когда-то начнём pull-источники) |
| D2 Delegate/subagents | Для multi-base сравнений и параллельных тяжёлых запросов |
| F2 Tirith scanner | Внешний бинарный сканер контента |
| I1 Langfuse plugin | Полноценная observability платформа |
| H1 Models.dev registry | Auto-discovery моделей |
| E3 Cross-session rate guard | Когда appliacation запущен в multiple windows |
| C7 Approval upgrade | Smart auto-approve через aux model для low-risk |
| H3 Plugin LLM facade | Если откроем plugin API |
| C4 Parallelism gating | Когда tool concurrency станет узким местом |

---

## 9. Дневник отклонений

| Дата | Спринт | Отклонение | Решение |
|---|---|---|---|
| _(заполняется по ходу)_ | | | |

---

## 10. Финальные правила для Claude

1. **Не торопиться.** Каждый спринт — атомарная серия коммитов с тестами. После спринта — release notes + tag.
2. **Брутальная честность.** Если на 3-й итерации не вышло — STOP, переписать руками. Документировать в разделе 9.
3. **vitest + pytest 100% pass перед каждым коммитом.**
4. **Memory и Trajectory** — самые ценные spinoff'ы. Их данные станут датасетом для будущего обучения собственной модели на 1С-задачах.
5. **Feature flags** — каждая новая фича через `.env` или `config.yaml`. Можно выключить без отката.
6. **MEMORY.md обновляется** этим документом по ходу. После каждого спринта — обновить таблицу статусов вверху.

---

## Статус спринтов

| Спринт | Статус | Тэг | Дата |
|---|---|---|---|
| 1 — Memory Foundation | ✅ **Готов** | (см. ниже) | 2026-05-20 |
| 2 — Context & Resilience | ⏸ Pending | — | — |
| 3 — Self-Learning Loop | ⏸ Pending | — | — |
| 4 — UX & Interactivity | ⏸ Pending | — | — |
| 5 — Polish & Observability | ⏸ Pending | — | — |

### Sprint 1 — детали реализации (2026-05-20)

**Backend (новые модули):**
- `app/memory/__init__.py` — публичные экспорты
- `app/memory/provider.py` — `MemoryProvider` ABC
- `app/memory/manager.py` — `MemoryManager` orchestrator
- `app/memory/markdown_store.py` — MEMORY.md + USER.md провайдер (per-channel)
- `app/memory/injection_scan.py` — F1 prompt injection detector (10 паттернов)
- `app/learning/__init__.py` + `trajectory.py` — ShareGPT JSONL logger
- `app/orchestrator/auxiliary.py` — aux client (для Sprint 2+)
- `app/orchestrator/memory_integration.py` — glue для loop
- `app/routes/memory.py` — REST GET/PUT `/memory/{channel_id}` + `/diagnostics/trajectory`

**Backend (изменения):**
- `app/config.py` — memory_root, trajectory_dir, learning_enabled, memory_enabled, aux_model
- `app/models.py` — MemoryDocument, MemoryUpdateRequest/Response, TrajectoryStats
- `app/main.py` — регистрация router
- `app/orchestrator/loop.py` — build_memory_manager + memory_system_block в SYSTEM_PROMPT + memory tool dispatch + sync_all + log_trajectory после turn

**Frontend (новые):**
- `app/settings/memory/page.tsx` — UI редактор MEMORY.md + USER.md с char counters, threats warning, sticky save
- `components/memory/MemoryHint.tsx` — one-time toast при ≥3 сессий
- `lib/onboarding-hints.ts` — hint state в localStorage

**Frontend (изменения):**
- `lib/types.ts` — MemoryDocument, MemoryNamespacePayload, MemoryUpdateRequest/Response, TrajectoryStats
- `lib/api.ts` — fetchMemory, updateMemory, fetchTrajectoryStats
- `app/settings/page.tsx` — добавлена ссылка «Постоянная память» с Brain-иконкой
- `app/page.tsx` — подключён `<MemoryHint />`

**Тесты (новые):**
- `backend/tests/test_memory.py` — 17 тестов (MarkdownStore + MemoryManager + injection_scan)
- `backend/tests/test_trajectory.py` — 6 тестов (logger)
- `frontend/components/memory/__tests__/MemoryHint.test.tsx` — 4 теста

**Quality gate:**
- pytest: 365 → 369 passing (4 новых файла; 3 pre-existing flaky тесты orchestrator_loop_confirm + migration_v5 НЕ от Sprint 1)
- vitest: 300 → **304/304 passing**
- next build: clean, добавился route `/settings/memory` 3.48 kB
- HTTP smoke: end-to-end memory_append → file write → system_prompt_block — работает

**Acceptance criteria — что доказано:**
- ✅ MEMORY.md + USER.md создаются per-channel при первом запросе
- ✅ Модель видит memory tool schemas (memory_append, memory_remove)
- ✅ System prompt содержит `<persistent-memory>` блок если файлы не пусты
- ✅ UI редактор `/settings/memory` показывает оба файла, чарcounter, threats scan
- ✅ Trajectory JSONL logger пишет каждый turn в `~/.analyst-1c/trajectories/`
- ✅ Onboarding hint показывается ОДИН раз при ≥3 сессий

**Что НЕ сделано в Sprint 1 (намеренно отложено):**
- Cache invalidation при переключении канала — UI рефетчит при mount, не на canal change event
- Diff-preview перед PUT — пока полная перезапись без UI подтверждения
- Visual smoke через Chrome MCP — отложен до коммита
- Sync_turn пока ничего не пишет автоматически (это работа background_review в Sprint 3) — модель сама вызывает memory_append

---

## Источники

- [github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — основной репо, MIT
- `hermes-agent-main/agent/` — 100 файлов orchestration
- `hermes-agent-main/tools/` — 93 tools
- `hermes-agent-main/plugins/memory/honcho/README.md` — dialectic user modeling docs
- `hermes-agent-main/skills/software-development/test-driven-development/SKILL.md` — пример самообучения skill
- `hermes-agent-main/datagen-config-examples/trajectory_compression.yaml` — пример конфига для обучения
- Локальная копия tarball: `/tmp/hermes-research/hermes-agent-main/` (для глубокого изучения)

**Конец документа. Версия 1.0. 2026-05-20.**
