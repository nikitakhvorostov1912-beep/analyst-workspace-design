# Phase 4: Demo & Refine — Context

**Gathered:** 2026-05-14
**Status:** Ready for planning
**Source:** Direct extraction (yolo) — ROADMAP.md + REQUIREMENTS.md + Phase 3 outcomes

<domain>
## Phase Boundary

Что эта фаза доставляет:
- **Anonymization** — toggle в Header, backend пробрасывает anon mode в MCP `submit_for_deanonymization`, UI подсвечивает токены `[ORG-001]`, кнопка «Раскрыть»
- **3 расширенных карточки** — MetricCard, ReferencesCard, CodeCard (BSL syntax highlight)
- **Productivity quick wins** — Quick prompts (chips над input), Slash commands (`/sql /journal /find /audit /clear`), @-mentions, Cmd-K
- **Live Demo Session** — артефакты для прогона с реальным аналитиком (demo-script, observer-checklist, feedback-template); сам прогон — human activity вне sandbox

Что эта фаза НЕ доставляет:
- Vector search / RAG over metadata — за пределами MVP/v2
- Mobile UI, multi-user, real-time collaboration, voice, light theme — Out of Scope (REQUIREMENTS)
- Direct 1С editing через UI (полноценная запись объектов помимо confirmed execute_code) — Out of Scope

Вход в Phase 4 (что есть после Phase 3):
- End-to-end chat работает (Phase 2: orchestrator + 3 cards + sessions + channel + trace)
- Error states + security + tests + docs (Phase 3)
- Backend coverage 92.74%, 215 pytest + 97 vitest + 9 Playwright green
- CI pipeline (GitHub Actions), docker-compose backend+frontend

</domain>

<decisions>
## Implementation Decisions

### Plan 4.1 — Anonymization (ANON-01..03)

**ANON-01 (toggle в Header)**:
- Header получает кнопку-переключатель «Анонимизация» рядом с ChannelSelector (компактная, иконка + текст). Состояние persist в localStorage `analyst.anon_enabled`
- При toggle ON: новые сообщения в `/chat` отправляются с заголовком `X-Anon-Enabled: true`
- При toggle OFF: header не отправляется, backend работает в обычном режиме
- Существующие сессии — anon флаг хранится per-session (как session-level setting? Или global?). **Решение:** global toggle, не per-session. Per-session добавление было бы overkill для MVP. При toggle во время активного чата — новые сообщения уже идут с новым режимом

**ANON-02 (визуальное выделение токенов)**:
- Регулярка для подсветки токенов в TL;DR markdown и в cards: `\[(ORG|INN|PER|PHONE|EMAIL|ACCT|AGREE)-\d+\]`
- Подсветка: фон `bg-amber-500/10`, рамка `border-amber-500/30`, шрифт mono, padding `px-1`
- Применяется в `Markdown.tsx` через `react-markdown` `remark` plugin или post-process через regex над renderable text-узлами
- В Cards (Table cells, Object attribute values) — отдельная утилита `highlightAnonTokens(text)` возвращающая React fragment

**ANON-03 (раскрытие через submit_for_deanonymization)**:
- Кнопка «Раскрыть реальные значения» появляется в footer cards (TableCard, ObjectCard, LogCard) **только если** в payload найден хотя бы один anon token
- При клике: backend `POST /sessions/{sid}/messages/{mid}/cards/{cid}/deanonymize` (новый endpoint) → вызывает MCP `submit_for_deanonymization(tokens=[...])` → возвращает map `{token: real_value}` → frontend заменяет токены на реальные значения inline
- После раскрытия кнопка пропадает, добавляется бейдж «Реальные значения» (warning visual cue)
- В DB карточка не модифицируется — раскрытие client-side runtime (security: real values не персистятся)

### Plan 4.2 — Advanced Cards (CARD-04..06)

**MetricCard (CARD-04)** — один большой число + sparkline + подпись:
- Source: tool_result от `execute_query` где результат это single row + numeric columns. Backend `cards.py` `build_card_from_tool_result` распознаёт metric shape: row count = 1 AND все ключевые колонки numeric → MetricCard
- Альтернативный путь: aggregated multi-row queries (sums, counts). Backend применяет heuristic — если строк ≤ 5 и есть column "Период"/"Дата"/"Месяц" + numeric column → MetricCard со sparkline
- Sparkline: SVG inline ~80×24px, native React, без зависимостей (~50 строк)
- Payload: `{ value: number, label: string, sparkline?: number[], delta?: { value: number, direction: "up"|"down" } }`

**ReferencesCard (CARD-05)** — где используется:
- Source: tool_result от `find_references_to_object`. Backend строит ReferencesCard если результат — array объектов с полями `{type, name, link, usage_kind}` (или похожей структуры из 1C MCP Toolkit response)
- UI: список grouped by `usage_kind` (Реквизит / Подчинённый / Шаблон / Подписка / Право / Прочее). Каждая ссылка — clickable (открывает дополнительный запрос через `/chat` → новое сообщение `Покажи {name}`)
- Payload: `{ groups: [{ kind: string, items: [{ type, name, navigation_link, full_path }] }], total: number }`

**CodeCard (CARD-06)** — BSL/SQL syntax highlight:
- Source: tool_result от `execute_code` (возвращает результат + текст кода) ИЛИ от `get_bsl_syntax_help` (синтаксис снippet)
- Альтернативно: внутри markdown TL;DR находятся fenced code blocks с `bsl` / `sql` — рендерятся через CodeCard inline
- Syntax highlight: используем `prismjs` (стандарт, ~10kb gzip) с компонентами для bsl (custom) + sql. Или `shiki` (better quality, slower). **Решение:** `prismjs` + custom BSL grammar (наследует sql + ключевые слова 1С), потому что shiki требует WASM bundle
- Payload: `{ language: "bsl"|"sql"|"json", code: string, executable?: boolean, result?: any }`

### Plan 4.3 — Productivity (PROD-01..05)

**Quick prompts (PROD-01)** — chips над input:
- Компонент `QuickPrompts.tsx`: горизонтальная row из 3-5 chip-кнопок над `Input.tsx`. Click — заполняет textarea текстом prompt + auto-focus
- Default prompts (configurable later): «Обзор базы», «Ошибки за сутки», «Сводка по типам документов», «Журнал за последний час», «Структура справочника Номенклатура»
- Скрываются если есть текст в input (фокус на user typing)
- Хранение default-set в `lib/quick-prompts.ts` (константа), без backend storage — простота

**Slash commands (PROD-02)** — `/sql /journal /find /audit /clear`:
- Detection: если пользователь начинает сообщение с `/<command>` → специальная обработка:
  - `/sql <query>` → отправляет prompt «Выполни запрос: ```sql <query>```» (forces execute_query tool)
  - `/journal [filters]` → «Покажи журнал регистрации с фильтрами: <filters>»
  - `/find <name>` → «Найди где используется <name>»
  - `/audit <object>` → «Проведи аудит объекта <object>: реквизиты, ТЧ, формы, права»
  - `/clear` → client-side очистка textarea (не отправляется на backend)
- UI: попап при typing `/` с подсказкой 5 команд (shadcn Command primitive)

**@-mentions (PROD-03)** — объекты 1С:
- Detection: при typing `@` в textarea — открывается popover с metadata cache (типы: Документ, Справочник, Регистр и т.д.)
- Cache: backend endpoint `GET /channels/{id}/metadata-suggest?q=<prefix>` — возвращает список матчинговых объектов из cached `get_metadata` (cache в SQLite таблица `metadata_cache` с TTL 1 час)
- Mention в тексте: при выборе вставляется `@Документ.ОПП` — backend при отправке /chat распознаёт `@<type>.<name>` и добавляет в system prompt контекст об объекте

**Cmd-K search (PROD-04)** — поиск по сессиям и messages:
- Modal Dialog с input + результаты. Hotkey: Cmd+K / Ctrl+K (cross-platform)
- Backend endpoint `GET /search?q=<text>&channel=<id>` — полнотекстовый поиск по messages.content (FTS5 SQLite virtual table)
- Migration v4: создаёт FTS5 виртуальную таблицу `messages_fts` + триггеры INSERT/UPDATE/DELETE
- Результаты: список «session title — snippet с подсветкой» → click ведёт на `/sessions/{id}#message-{mid}` (scroll to anchor)

**Экспорт (PROD-05 deferred):** PROD-05 в ROADMAP не упомянут в Phase 4 четвёртом плане ("Productivity" includes только PROD-01..04). PROD-05 (Copy markdown / CSV / PDF) → **частично уже закрыт** (CSV export в TableCard есть), остальное deferred к post-MVP. Документировать в SUMMARY как «частично через CSV export».

### Plan 4.4 — Live Demo Session (артефакты + ритуал)

**Что делает план:**
- НЕ код. Это процессные артефакты для проведения live demo:
  - `docs/DEMO-SCRIPT.md` — пошаговый сценарий 15-минутного демо (5 разделов: подключение → первый prompt → cards → channel switch → trace). Конкретные prompts на реальной 1С (РТ или УСО)
  - `docs/DEMO-OBSERVER-CHECKLIST.md` — чек-лист для наблюдателя (что отметить: время ответа, UX-затыки, неожиданные паттерны вопросов)
  - `docs/DEMO-FEEDBACK-TEMPLATE.md` — шаблон фидбека для аналитика (5 разделов: что понравилось / что мешало / чего не хватает / частота использования / 3 priority items)
- Скрипт автоматизации: `scripts/seed-demo-data.py` — заполняет SQLite демо-сессиями + примерами cards для preview (без реальной 1С)
- Backlog инициализация: `.planning/BACKLOG-POST-MVP.md` — точечки для добавления feedback items

**Что НЕ делает план:**
- Сам прогон demo с реальным аналитиком — это human activity, она будет после merge Phase 4
- Запись pain points в реальном времени — это уже шаг после демо

### Stack additions (over Phase 3)

- Frontend: `prismjs` (~10kb gzip) + custom BSL grammar; никаких других новых зависимостей
- Backend: FTS5 SQLite native (без extension); migration v4 для `messages_fts` + `metadata_cache`
- Никаких новых state libraries

### Out of scope для Phase 4 (явно)

- Vector search / RAG over metadata — v2 (REQUIREMENTS)
- PROD-05 Export PDF — частично через CSV, PDF deferred (нужен дополнительный либ как `pdfkit` или server-side rendering)
- Mobile UI — Out of Scope
- Voice / TTS — Out of Scope
- Light theme — Out of Scope
- OAuth / SSO — Out of Scope

### Claude's Discretion

- Anon токены regex pattern — точно: `\[(ORG|INN|PER|PHONE|EMAIL|ACCT|AGREE|FIO|DOC|ADDR)-\d+\]`. Список префиксов из REQUIREMENTS + здравый смысл; planner может расширить если найдёт документацию MCP submit_for_deanonymization
- prismjs vs shiki — рекомендация prismjs (10kb vs WASM bundle)
- @-mentions cache TTL — 1 час по умолчанию, можно расширить через env
- Cmd-K hotkey: cross-platform Cmd+K (Mac) / Ctrl+K (Windows/Linux) — детект через `navigator.platform`
- Sparkline rendering — inline SVG ~50 строк; никакого chart.js / recharts

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project documentation
- `PROJECT.md`, `ARCHITECTURE.md`, `CLAUDE.md`
- `REQUIREMENTS.md` — REQ Phase 4: ANON-01..03, CARD-04..06, PROD-01..04 (PROD-05 — partial)
- `ROADMAP.md` — Phase 4 секция

### Phase 1-3 артефакты (контракты)
- `.planning/phases/01-foundation/01-01-SUMMARY.md`, `01-02-SUMMARY.md`
- `.planning/phases/02-mvp-chat/*-SUMMARY.md` + `VERIFICATION.md`
- `.planning/phases/03-production-ready/*-SUMMARY.md` + `VERIFICATION.md`

### Existing code (точки интеграции)
- Backend: `app/orchestrator/{loop,cards,events,persistence}.py`, `app/clients/mcp.py` (`submit_for_deanonymization` уже описан в MCP capability map)
- Routes: `app/routes/{chat,sessions,connections,log_cards}.py`
- Migrations: `app/storage/migrations.py` (текущая v3)
- Frontend: `components/cards/{TableCard,ObjectCard,LogCard,CardRenderer}.tsx`, `components/chat/{AssistantMessage,Thread,Message,Input,ToolTrace}.tsx`, `lib/{api,types,sse,storage,useChatStream}.ts`
- shadcn primitives: `Dialog`, `DropdownMenu`, `Command` (нужно скопировать из shadcn для Cmd-K), `Popover`

### MCP capability map
- `docs/00b-mcp-capability-map.md` — особенно `submit_for_deanonymization`, `find_references_to_object`, `get_bsl_syntax_help` (Phase 4 новые tools)

</canonical_refs>

<specifics>
## Specific Ideas

### Anon tokens regex и highlight
```ts
const ANON_TOKEN_RE = /\[(ORG|INN|PER|PHONE|EMAIL|ACCT|AGREE|FIO|DOC|ADDR)-\d+\]/g;

function highlightAnonTokens(text: string): React.ReactNode {
  // split → возвращает массив с alternating string и span с highlight class
}
```

CSS class: `bg-amber-500/10 border border-amber-500/30 rounded px-1 font-mono text-xs`

### Card type matrix (расширение)
| Source tool | Result shape | Card type |
|-------------|--------------|-----------|
| execute_query | rows[] (>1) | TableCard (Phase 2) |
| execute_query | 1 row + numeric cols | **MetricCard** (Phase 4) |
| execute_query | timeline rows (date col + value col) | **MetricCard** + sparkline (Phase 4) |
| get_metadata(detail) | object meta | ObjectCard (Phase 2) |
| get_object_by_link | object | ObjectCard (Phase 2) |
| find_references_to_object | array of usages | **ReferencesCard** (Phase 4) |
| get_event_log | log entries | LogCard (Phase 2) |
| execute_code | result + code | **CodeCard** (Phase 4) |
| get_bsl_syntax_help | snippet | **CodeCard** (Phase 4) |

### Slash commands matrix
| Command | Expanded prompt |
|---------|-----------------|
| `/sql <query>` | "Выполни запрос: ```sql\n<query>\n```" — forces execute_query tool |
| `/journal [Период=Час]` | "Покажи журнал регистрации с фильтрами: <filters>" |
| `/find <name>` | "Найди где используется <name>" |
| `/audit <object>` | "Проведи полный аудит <object>: реквизиты, ТЧ, формы, права, использование" |
| `/clear` | client-side: очистить textarea + reset draft (без отправки) |

### Cmd-K search migration v4
```sql
-- FTS5 virtual table
CREATE VIRTUAL TABLE messages_fts USING fts5(
  content,
  session_id UNINDEXED,
  message_id UNINDEXED,
  tokenize = 'porter unicode61'
);

-- INSERT trigger
CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, content, session_id, message_id)
  VALUES (new.rowid, new.content, new.session_id, new.id);
END;
-- + UPDATE, DELETE triggers
```

### Demo script structure (Plan 4.4)
1. **Подключение (2 мин)** — Connections → добавить MCP endpoint реальной 1С
2. **Первый prompt (3 мин)** — «Расскажи про базу» → ObjectCard
3. **Сложный prompt (4 мин)** — «Покажи документы реализации за вчера, group by контрагент» → TableCard + sort/CSV export
4. **Channel switching (2 мин)** — переключить на вторую базу → новые tools работают
5. **Trace + curl (2 мин)** — раскрыть trace → click Copy as curl → показать что запрос воспроизводится
6. **Wrap-up (2 мин)** — feedback короткий

</specifics>

<deferred>
## Deferred Ideas (НЕ в Phase 4)

- **PROD-05 PDF export** — нужен server-side rendering или client-side jspdf. Partial: CSV из TableCard уже есть. PDF → post-MVP
- **Vector search / RAG** — отдельная итерация после MVP
- **Mobile UI / Light theme / Voice / TTS / OAuth** — Out of Scope

</deferred>

---

*Phase: 04-demo-refine*
*Context gathered: 2026-05-14 — yolo mode, direct extraction*
