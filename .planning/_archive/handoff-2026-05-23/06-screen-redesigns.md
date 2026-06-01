# 06 · Screen Redesigns

Четыре экрана с детальными layout-спеками. Открой `reference/visual-audit-report.html` (раздел «05 · Редизайн экранов») для визуальной сверки.

---

## Welcome — Composer Hub

**Файл:** `frontend/app/page.tsx:226-292` (welcome screen, рендерится когда `hasConfig && !activeSession`).
**Новый компонент:** `frontend/components/chat/ComposerHub.tsx`.

### Цель

Сейчас welcome — пустой текст + кнопка «+ Новый чат» + две сине-подчёркнутые ссылки. Это «web-троп». У аналитика нет ни триггера, ни справочной информации, ни истории.

### Целевой layout

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                       │
├──────────┬──────────────────────────────────────────────────┤
│ SIDEBAR  │                                                   │
│          │   eyebrow: БАЗА 1С · ● A4F2-PROD · УТ 11.5        │
│ Новый    │   h2: О чём спросим базу?                         │
│ чат      │   sub: Свободная формулировка — оформление        │
│          │       и запросы возьмёт на себя.                  │
│ ─────    │                                                   │
│          │   ┌────────────────────────────────────────┐     │
│ Today    │   │ ▎ Напишите вопрос или начните...      │     │
│ [3 sess] │   │ ──────────────────────────────────── │     │
│          │   │ /slash @объект 📎 файл    0/4000  ↵   │     │
│          │   └────────────────────────────────────────┘     │
│ Yesterday│                                                   │
│          │   [↺ повторить «продажи апрель»]                  │
│          │   [найти контрагента по ИНН] [⚙ движения...]      │
│          │   [+ ещё 4 шаблона]                               │
│          │                                                   │
│          │   ─────────── Последние чаты · 12 ── смотреть → ──│
│          │                                                   │
└──────────┴──────────────────────────────────────────────────┘
```

### Подробная разметка

#### Контейнер
- `max-width: 720px`, `margin: 0 auto`, padding `64px 24px`
- `display: flex; flex-direction: column; gap: 32px`

#### Eyebrow + Title block
- Eyebrow: `БАЗА 1С · ● {activeConn.name} · {kind/configType}` — JetBrains Mono 10px tracking 0.16em uppercase, color `--fg-3`, точка status pulse
- H2: «О чём спросим базу?» — `font-family: var(--font-plex-mono); font-weight: 600; font-size: 28px; letter-spacing: 0;`
- Subtitle: `font-family: var(--font-plex-sans); font-size: 14px; color: var(--fg-3); max-width: 480px;`

```tsx
<div className="text-center">
  <div
    className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)] mb-3 flex items-center justify-center gap-2"
    style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
  >
    База 1С
    <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)] status-online" />
    {activeConn?.name}
    {configType && (
      <>
        <span>·</span>
        <span>{configType}</span>
      </>
    )}
  </div>
  <h2
    className="font-semibold text-[28px] tracking-[0] mb-2"
    style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
  >
    О чём спросим базу?
  </h2>
  <p className="text-sm text-[var(--fg-3)] max-w-md mx-auto leading-relaxed">
    Свободная формулировка — оформление и запросы возьмёт на себя.
  </p>
</div>
```

#### Composer (большой)

Использует **тот же `<Input>` компонент** из `chat/Input.tsx`, но без `disabled`, с дефолтным placeholder для welcome:

```tsx
<div className="border border-[var(--bd-3)] bg-[var(--bg-1)] rounded-lg p-1 relative">
  {/* Brand-tick */}
  <span
    aria-hidden="true"
    className="pointer-events-none absolute top-0 left-6 h-[2px] w-[22px] bg-[var(--accent)]"
  />
  <Input
    channelId={activeChannelId}
    onSubmit={handleFirstQuestion}    // создаёт session, добавляет первое user-сообщение, переходит в /sessions/{id}
    placeholder="Напишите вопрос или начните с шаблона"
    autoFocus
  />
</div>
```

`handleFirstQuestion` должен:
1. Вызвать `store.createNew(channelId)` — создаёт session
2. Сразу отправить первое сообщение
3. `router.push(/sessions/{newId})`
4. Не показывать welcome обратно

#### Templates chips strip

```tsx
<div className="flex flex-wrap gap-2">
  {WELCOME_TEMPLATES.map((tpl) => (
    <button
      key={tpl.id}
      onClick={() => prefillComposer(tpl.text)}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full
                 border border-[var(--bd-2)] bg-[var(--bg-1)] text-[12.5px] text-[var(--fg-2)]
                 hover:border-[var(--bd-3)] hover:bg-[var(--bg-2)] transition-colors
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]
                 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-0)]"
      style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
    >
      {tpl.icon && <tpl.icon className="h-3 w-3 text-[var(--fg-3)]" />}
      {tpl.title}
    </button>
  ))}
</div>
```

Templates — `frontend/lib/welcome-templates.ts`:

```ts
import { RotateCcw, Search, BarChart3, FileText, Users, Box, ScrollText } from "lucide-react";

export interface Template {
  id: string;
  title: string;       // отображается на чипе
  text: string;        // вставляется в composer
  icon?: ComponentType<{ className?: string }>;
}

export const WELCOME_TEMPLATES: Template[] = [
  { id: "repeat-last", title: "↺ Повторить последний", text: "", icon: RotateCcw },     // text заполняется dynamic
  { id: "find-counterparty", title: "Найти контрагента по ИНН", text: "Найди контрагента с ИНН ", icon: Search },
  { id: "sales-period", title: "Продажи за период", text: "Покажи продажи за апрель 2026 с разбивкой по складам", icon: BarChart3 },
  { id: "doc-by-number", title: "Документ по номеру", text: "Покажи документ № ", icon: FileText },
  { id: "user-actions", title: "Действия пользователя", text: "Что делал пользователь ", icon: Users },
  { id: "stock-balance", title: "Остатки на складе", text: "Остатки на складе ", icon: Box },
  { id: "event-log-errors", title: "Ошибки в журнале", text: "Покажи ошибки в журнале регистраций за сегодня", icon: ScrollText },
];
```

«↺ Повторить последний» — динамический: если есть session с user-сообщением — title = «↺ Повторить «{first 30 chars of last user msg}…»», text = это сообщение.

#### Recent chats strip

```tsx
<div className="border-t border-[var(--bd-1)] pt-4 flex items-center justify-between">
  <span
    className="text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)]"
    style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
  >
    Последние чаты · {totalCount}
  </span>
  <Link
    href="#"
    onClick={(e) => { e.preventDefault(); focusSidebar(); }}
    className="text-[10px] tracking-[0.14em] uppercase text-[var(--accent)] hover:underline"
    style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
  >
    Смотреть все →
  </Link>
</div>
```

`focusSidebar()` — прокрутить список сессий и поставить фокус на первый item.

### Что удалить

Из `frontend/app/page.tsx:282-291` — **полностью убрать** блок с двумя ссылками «Подробнее о приложении · Проверить диагностику». Эти действия уже доступны в шапке.

---

## Channel Selector — enrichment

**Файл:** `frontend/components/shell/ChannelSelector.tsx`
**Дополнительно:** расширение модели `MCPConnection`.

### Цель

Dropdown должен отвечать на главный вопрос аналитика: «**что это за база и насколько она актуальна?**».

### Текущее состояние

```
[ ● ] {name} {kind-badge}
       {host:port}
       Канал: {channel}              ← убрать
       {tool_count} инструментов
       [✓]
```

### Целевое состояние

```
┌────────────────────────────────────────────────────────────┐
│ eyebrow: БАЗЫ 1С · 3                          + добавить   │
│ ────────────────────────────────────────────────────────── │
│ ● {name}            [УТ 11.5]                         [✓]  │ ← active, signal-08 bg
│   2 134 ОБЪЕКТА · 24 ИНСТРУМЕНТА · ОБНОВЛЕНО 5 МИН НАЗАД   │
│ ────────────────────────────────────────────────────────── │
│ ● {name}            [ERP 2.5]                              │
│   4 820 ОБЪЕКТОВ · 31 ИНСТРУМЕНТ · ЧАС НАЗАД               │
│ ────────────────────────────────────────────────────────── │
│ ● {name} (offline)  [УСО]                                  │
│   ОФЛАЙН · ПОСЛЕДНЯЯ СВЯЗЬ 2 ДНЯ НАЗАД · ↻ ПЕРЕПРОВЕРИТЬ   │
└────────────────────────────────────────────────────────────┘
```

### Расширение модели

`frontend/lib/types.ts` — расширь `MCPConnection`:

```ts
export interface MCPConnection {
  id: string;
  name: string;
  endpoint: string;
  kind: MCPKind;
  channel: string | null;
  anon_enabled: boolean;
  // ===== НОВОЕ =====
  /** Тип конфигурации 1С, если удалось определить — UT/ERP/USO/Custom/Unknown */
  config_type?: string | null;       // "УТ 11.5" | "ERP 2.5" | "УСО" | "Самописная" | null
  /** Кол-во объектов в метаданных */
  metadata_object_count?: number | null;
  /** ISO timestamp последней синхронизации метаданных */
  metadata_last_sync?: string | null;
  /** Кол-во tools, отданных MCP */
  tool_count?: number | null;
}
```

Backend (FastAPI) при `GET /connections/{id}/info` должен возвращать эти поля. Detection логика — отдельная задача backend. Frontend готов работать с `null` (показывает «—»).

### Helper — last-sync формат

`frontend/lib/format-relative-time.ts`:

```ts
const RTF = new Intl.RelativeTimeFormat('ru', { numeric: 'auto' });

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diff = (then - now) / 1000;  // в секундах
  if (Math.abs(diff) < 60) return RTF.format(Math.round(diff), 'second');
  if (Math.abs(diff) < 3600) return RTF.format(Math.round(diff / 60), 'minute');
  if (Math.abs(diff) < 86400) return RTF.format(Math.round(diff / 3600), 'hour');
  return RTF.format(Math.round(diff / 86400), 'day');
}
```

### JSX dropdown-item

Заменить L283-303 в `ChannelSelector.tsx`:

```tsx
{connections.map((conn) => {
  const isActive = conn.id === activeId;
  const isOffline = conn.ping === 'error';
  return (
    <div
      key={conn.id}
      className={cn(
        "flex items-start gap-3 pr-1 my-1 mx-1 rounded-md transition-colors",
        isActive && "bg-[var(--accent-08)]",
      )}
    >
      <DropdownMenuItem
        className="flex-1 gap-3 cursor-pointer items-start py-2.5 px-3"
        onSelect={() => handleSelect(conn.id)}
      >
        <PingDot status={conn.ping} />
        <div className="flex-1 min-w-0">
          {/* Row 1: name + config type chip */}
          <div className="flex items-center gap-2 mb-1">
            <span
              className="font-semibold text-[13px] truncate"
              style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
            >
              {conn.name}
            </span>
            {conn.config_type && (
              <span
                className={cn(
                  "px-1.5 py-[1px] rounded text-[9px] tracking-[0.14em] uppercase font-medium border",
                  isActive
                    ? "bg-[var(--accent-12)] text-[var(--accent)] border-[var(--accent-32)]"
                    : "bg-[var(--bg-2)] text-[var(--fg-2)] border-[var(--bd-2)]",
                )}
                style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
              >
                {conn.config_type}
              </span>
            )}
          </div>
          {/* Row 2: meta */}
          {!isOffline && (
            <div
              className="text-[10px] tracking-[0.12em] uppercase text-[var(--fg-3)] flex items-center gap-1.5 flex-wrap"
              style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
            >
              {conn.metadata_object_count != null && (
                <>
                  <span>{conn.metadata_object_count.toLocaleString('ru')} {pluralObject(conn.metadata_object_count)}</span>
                  <span className="text-[var(--fg-4)]">·</span>
                </>
              )}
              {conn.tool_count != null && (
                <>
                  <span>{conn.tool_count} {pluralTool(conn.tool_count)}</span>
                  <span className="text-[var(--fg-4)]">·</span>
                </>
              )}
              <span>обновлено {formatRelativeTime(conn.metadata_last_sync)}</span>
            </div>
          )}
          {/* Offline row */}
          {isOffline && (
            <div
              className="text-[10px] tracking-[0.12em] uppercase text-[var(--error)] flex items-center gap-1.5 flex-wrap"
              style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
            >
              <span>Офлайн</span>
              {conn.metadata_last_sync && (
                <>
                  <span className="text-[var(--fg-4)]">·</span>
                  <span>последняя связь {formatRelativeTime(conn.metadata_last_sync)}</span>
                </>
              )}
              <span className="text-[var(--fg-4)]">·</span>
              <button
                onClick={(e) => { e.stopPropagation(); void pingOne(conn); }}
                className="text-[var(--accent)] hover:underline"
              >
                ↻ Перепроверить
              </button>
            </div>
          )}
        </div>
        {isActive && (
          <span className="text-[var(--accent)] text-sm flex-none mt-1" aria-label="Активный">
            ✓
          </span>
        )}
      </DropdownMenuItem>
    </div>
  );
})}
```

`pluralObject` / `pluralTool` — helpers по аналогии с `plural()` в `tool-summary.ts`.

### Также убрать строку 296

```diff
-  {conn.channel && (
-    <div className="text-xs text-[var(--fg-muted)] truncate">
-      Канал: {conn.channel}
-    </div>
-  )}
```

Аналогично убрать `Канал` label на L273.

---

## Status — split на high-level + expert

**Файл:** `frontend/app/status/page.tsx`

### Цель

Сейчас status page показывает аналитику технический ряд: «канал», «версия MCP», «обработка MCP_Toolkit», endpoint URL'ы. Это вводит в заблуждение.

### Целевая структура

```
┌──────────────────────────────────────────────────────────┐
│ ●  Всё в порядке                          [↻ Перепровер.]│
│    3 проверки пройдено · последняя 18 сек назад           │
│                                                            │
│ ┌─────────────────┬─────────────────┬─────────────────┐  │
│ │ ● БАЗЫ 1С       │ ● МОДЕЛЬ ИИ     │ ● СЕРВЕРНАЯ Ч.  │  │
│ │ 2 из 3          │ MiMo v2.5 Pro   │ v1.2.4 · здорова│  │
│ │ A4F2·B91X·C71*  │ отклик 312 мс   │ SQLite · 142 ч. │  │
│ └─────────────────┴─────────────────┴─────────────────┘  │
│                                                            │
│ ▸ Технические подробности (для разработчика)              │
└──────────────────────────────────────────────────────────┘
```

При раскрытии details — показывается то, что раньше было в основном теле (endpoint URLs, версия MCP, channel id, mcp protocol version, etc.).

### High-level cards

```tsx
<div className="grid grid-cols-3 gap-3">
  <StatusCard
    label="Базы 1С"
    state={baseState}              // 'ok' | 'warn' | 'error'
    headline={`${onlineCount} из ${totalCount}`}
    subtitle={baseSubtitle}
  />
  <StatusCard
    label="Модель ИИ"
    state={llmState}
    headline={llmModel}
    subtitle={`отклик ${llmMs} мс`}
  />
  <StatusCard
    label="Серверная часть"
    state={backendState}
    headline={`v${appVersion} · здорова`}
    subtitle={`SQLite · ${sessionCount} ${pluralSession(sessionCount)}`}
  />
</div>
```

`StatusCard` — простой компонент:

```tsx
function StatusCard({ label, state, headline, subtitle }: ...) {
  const stateClasses = {
    ok:    'text-[var(--success)]',
    warn:  'text-[var(--warning)]',
    error: 'text-[var(--error)]',
  }[state];
  return (
    <div className="rounded-lg bg-[var(--bg-2)] border border-[var(--bd-2)] p-4">
      <div
        className={cn("text-[10px] tracking-[0.16em] uppercase mb-2 flex items-center gap-1.5", stateClasses)}
        style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-current" />
        {label}
      </div>
      <div
        className="font-semibold text-lg leading-tight"
        style={{ fontFamily: "var(--font-plex-mono), ui-monospace, monospace" }}
      >
        {headline}
      </div>
      <div className="text-xs text-[var(--fg-3)] mt-1">{subtitle}</div>
    </div>
  );
}
```

### Expert block

```tsx
<details className="mt-6 border-t border-[var(--bd-1)] pt-4">
  <summary
    className="cursor-pointer text-[10px] tracking-[0.18em] uppercase text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors flex items-center gap-2"
    style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
  >
    <ChevronRight className="h-3 w-3" />
    Технические подробности (для разработчика)
  </summary>
  <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 p-4 bg-[var(--code-bg)] rounded border border-[var(--bd-2)]
                  font-mono text-[12px] text-[var(--code-fg)]">
    <span className="text-[var(--fg-4)]">MCP endpoint</span>
    <span className="text-[var(--accent)] truncate">{conn.endpoint}</span>
    <span className="text-[var(--fg-4)]">Channel</span>
    <span>{conn.channel ?? '—'}</span>
    <span className="text-[var(--fg-4)]">MCP version</span>
    <span className="text-[var(--success)]">{mcpVersion}</span>
    <span className="text-[var(--fg-4)]">Tools loaded</span>
    <span><span className="text-[var(--success)]">{toolCount}</span> in {loadMs} ms</span>
    <span className="text-[var(--fg-4)]">LLM endpoint</span>
    <span className="text-[var(--accent)] truncate">{llmEndpoint}</span>
  </div>
</details>
```

### Чего не должно быть в основном теле

- Слов «Канал», «MCP», «endpoint», «обработка MCP_Toolkit».
- Полных URL.
- Версий MCP-протокола.

Всё это уезжает в `<details>` блок.

---

## Chat — TraceSummary integration

См. `05-component-additions.md` § E (TraceSummary). Здесь только добавлю визуальный layout:

### Куда вставляется

Между user-сообщением и assistant-сообщением, **если** у assistant есть `tool_calls.length > 0`:

```
┌─ user-msg ──────────────────────────────────────┐
│ Покажи продажи за апрель                        │
└──────────────────────────────────────────────────┘
                       ↓
┌─ trace ─────────────────────────────────────────┐
│ ● Анализ запроса · Выполнено · 872 мс · 3 шага  │
│ 01  Поиск контрагента · ✓ найдено 1 · 124 мс    │
│ 02  Регистр продаж    · ✓ 24 записи · 380 мс    │
│ 03  Расчёт дельты     · ✓ 2 склада · 12 мс      │
└──────────────────────────────────────────────────┘
                       ↓
┌─ assistant data card ───────────────────────────┐
│ Из шести складов Альфа-снаба провалились два... │
│ [таблица]                                       │
└──────────────────────────────────────────────────┘
```

Trace по-дефолту **раскрыт** в человеческом виде (TraceSummary). JSON-вид доступен по клику на каждый шаг.

### Acceptance

- В `AssistantMessage.tsx`: при наличии `tool_calls` рендерится `<TraceContainer>` с `<TraceSummary>` items, не сразу `<JsonTree>`.
- Клик «JSON» на конкретном шаге раскрывает raw — там цвета по `--syntax-*` токенам.
- Если шагов > 5 — первые 5 показаны, остальные под «+ {N} шагов» chevron.
