# 05 · Component Additions

Новые компоненты + ревизии существующих. Полные спеки: props, поведение, файлы, реализация. Все компоненты — `"use client"`.

---

## A · UndoToast (НОВЫЙ)

**Файл:** `frontend/components/ui/UndoToast.tsx`
**Заменяет:** `window.confirm()` в `frontend/components/shell/SessionList.tsx:84`

### Назначение

Optimistic-удаление с возможностью отмены. Аналитик кликает «удалить» → запись пропадает мгновенно → toast в правом-нижнем углу с прогресс-баром (5 сек) и кнопкой «↺ Отменить». Если за 5 сек не отменил — `DELETE` уходит на бэк.

### API

```ts
interface UndoToastProps {
  /** Уникальный id операции — для идемпотентности */
  id: string;
  /** Заголовок: что произошло */
  title: string;             // "Чат удалён"
  /** Уточнение (mono, eyebrow-style) */
  subtitle?: string;         // «A4F2 · продажи апрель»
  /** Сколько секунд держать. Дефолт: 5 */
  durationMs?: number;       // default 5000
  /** Вызывается если пользователь нажал Undo */
  onUndo: () => void;
  /** Вызывается после истечения durationMs (commit) */
  onCommit: () => void | Promise<void>;
}

interface UndoToastHandle {
  dismiss(): void;
}
```

### Поведение

1. На mount — `animation: toast-in 280ms ease-spring both;` (см. `04-motion-system.md` M09).
2. Progress-bar внизу toast'а — `width: 100% → 0` за `durationMs` (linear).
3. Click на «↺ Отменить» — `onUndo()` + dismiss.
4. После `durationMs` — `onCommit()` + dismiss с `toast-out` animation (240ms).
5. Закрытие через `dismiss()` снаружи — тот же exit animation, **без** `onCommit()`.
6. **Pause on hover:** при hover на toast — заморозить progress-bar (`animation-play-state: paused`).

### JSX

```tsx
"use client";
import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from "react";
import { cn } from "@/lib/utils";

interface UndoToastProps {
  id: string;
  title: string;
  subtitle?: string;
  durationMs?: number;
  onUndo: () => void;
  onCommit: () => void | Promise<void>;
}

export const UndoToast = forwardRef<UndoToastHandle, UndoToastProps>(function UndoToast(
  { id, title, subtitle, durationMs = 5000, onUndo, onCommit },
  ref,
) {
  const [closing, setClosing] = useState(false);
  const committedRef = useRef(false);
  const timerRef = useRef<number>();

  useImperativeHandle(ref, () => ({
    dismiss() {
      window.clearTimeout(timerRef.current);
      setClosing(true);
    },
  }));

  useEffect(() => {
    timerRef.current = window.setTimeout(() => {
      if (!committedRef.current) {
        committedRef.current = true;
        void onCommit();
        setClosing(true);
      }
    }, durationMs);
    return () => window.clearTimeout(timerRef.current);
  }, [durationMs, onCommit]);

  function handleUndo() {
    if (committedRef.current) return;
    committedRef.current = true;
    window.clearTimeout(timerRef.current);
    onUndo();
    setClosing(true);
  }

  return (
    <div
      data-id={id}
      data-state={closing ? "closing" : "open"}
      role="status"
      aria-live="polite"
      className={cn(
        "toast-undo fixed left-1/2 bottom-4 z-50 min-w-[320px] max-w-md",
        "bg-[var(--bg-2)] border border-[var(--bd-3)] rounded-lg shadow-xl px-4 py-3",
        "flex items-center gap-3",
      )}
      style={{ ['--toast-duration' as string]: `${durationMs}ms` }}
    >
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <div className="text-sm font-medium text-[var(--fg-1)]">{title}</div>
        {subtitle && (
          <div
            className="text-[10px] tracking-[0.14em] uppercase text-[var(--fg-4)] truncate"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            {subtitle}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={handleUndo}
        className={cn(
          "px-3 py-1 text-[10px] tracking-[0.14em] uppercase rounded border",
          "border-[var(--bd-3)] text-[var(--accent)] hover:bg-[var(--accent-08)] transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-2)]",
        )}
        style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
      >
        ↺ Отменить
      </button>
      <div
        className="toast-progress absolute left-0 bottom-0 h-[2px] bg-[var(--accent)] rounded-b-lg"
        aria-hidden="true"
      />
    </div>
  );
});
```

### Integration (SessionList delete)

`frontend/components/shell/SessionList.tsx` — заменить L84 `window.confirm`:

```diff
-  function handleDelete(sessionId: string) {
-    if (!window.confirm(`Удалить чат?`)) return;
-    void store.remove(sessionId);
-  }
+  function handleDelete(sessionId: string) {
+    const session = findSessionById(sessionId);
+    if (!session) return;
+    // Оптимистично убираем из UI:
+    store.removeOptimistic(sessionId);
+    publishUndoToast({
+      id: `delete-${sessionId}`,
+      title: "Чат удалён",
+      subtitle: session.title ?? session.id,
+      durationMs: 5000,
+      onUndo: () => store.restoreOptimistic(sessionId),
+      onCommit: () => store.commitRemove(sessionId),  // → actual DELETE
+    });
+  }
```

В `useSessionsStore` (zustand) добавь:
- `removeOptimistic(id)` — снять из локального state, но не дёргать backend
- `restoreOptimistic(id)` — вернуть обратно
- `commitRemove(id)` — реальный `DELETE /sessions/{id}`

### Toast host

Создай `frontend/components/ui/UndoToastHost.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";
import { UndoToast, type UndoToastProps } from "./UndoToast";
import { listenUndoToast } from "@/lib/undo-toast";

export function UndoToastHost() {
  const [active, setActive] = useState<UndoToastProps | null>(null);

  useEffect(() => listenUndoToast(setActive), []);

  if (!active) return null;
  return <UndoToast key={active.id} {...active} />;
}
```

И `frontend/lib/undo-toast.ts` с тонкой `EventEmitter`-обёрткой (по аналогии с `frontend/lib/toast.ts`):

```ts
type Listener = (toast: UndoToastProps | null) => void;
const listeners = new Set<Listener>();
let current: UndoToastProps | null = null;

export function publishUndoToast(toast: UndoToastProps) {
  current = toast;
  listeners.forEach((l) => l(toast));
}

export function listenUndoToast(l: Listener): () => void {
  listeners.add(l);
  l(current);
  return () => listeners.delete(l);
}
```

Подключить `<UndoToastHost />` в `app/layout.tsx` рядом с существующим `<ToastHost />`.

---

## B · LiveTestResult (НОВЫЙ — inline test feedback)

**Файл:** `frontend/components/ui/LiveTestResult.tsx`
**Используется в:** `MCPConnectionForm.tsx`, `LLMConfigForm.tsx` — рядом с кнопкой «Тест».

### Назначение

Inline-чип результата теста подключения. Не исчезает (как toast), показывает время отклика и success/error.

### API

```ts
interface LiveTestResultProps {
  /** Состояние — null = ничего не показывать (до первого теста) */
  state: 'idle' | 'testing' | 'success' | 'error';
  /** Время отклика в мс (показывается при success) */
  ms?: number;
  /** Доп. инфо (например, кол-во tools) */
  detail?: string;        // "24 операций"
  /** Сообщение ошибки */
  errorMessage?: string;
}
```

### JSX

```tsx
"use client";
import { Check, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function LiveTestResult({ state, ms, detail, errorMessage }: LiveTestResultProps) {
  if (state === 'idle') return null;

  const cfg = {
    testing: {
      label: 'Проверяю...',
      classes: 'bg-[var(--info-12)] text-[var(--info)] border-[var(--info-40)]',
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
    },
    success: {
      label: ms ? `Готово · ${ms} мс${detail ? ` · ${detail}` : ''}` : 'Готово',
      classes: 'bg-[var(--success-12)] text-[var(--success)] border-[var(--success-40)]',
      icon: <Check className="h-3 w-3" />,
    },
    error: {
      label: errorMessage ?? 'Не удалось',
      classes: 'bg-[var(--error-12)] text-[var(--error)] border-[var(--error-40)]',
      icon: <X className="h-3 w-3" />,
    },
  }[state];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-1 rounded border text-[10px] tracking-[0.14em] uppercase font-medium",
        "animate-fade-up",
        cfg.classes,
      )}
      style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
      role="status"
      aria-live="polite"
    >
      {cfg.icon}
      <span>{cfg.label}</span>
    </span>
  );
}
```

### Integration (MCPConnectionForm)

Где сейчас на тест отправляется toast — параллельно:

```tsx
const [testState, setTestState] = useState<'idle' | 'testing' | 'success' | 'error'>('idle');
const [testMs, setTestMs] = useState<number>();
const [testDetail, setTestDetail] = useState<string>();
const [testError, setTestError] = useState<string>();

async function handleTest() {
  setTestState('testing');
  const t0 = performance.now();
  try {
    const r = await pingConnection(initial!.id);
    setTestMs(Math.round(performance.now() - t0));
    setTestDetail(`${r.tool_count} операций`);
    setTestState('success');
    // Опционально оставить toast как дополнительный сигнал.
  } catch (e: any) {
    setTestError(e?.message ?? 'Не удалось подключиться');
    setTestState('error');
  }
}

// В JSX рядом с кнопкой:
<div className="flex items-center gap-3">
  <Button type="button" onClick={handleTest} disabled={testState === 'testing' || !initial?.id}>
    Тест
  </Button>
  <LiveTestResult
    state={testState}
    ms={testMs}
    detail={testDetail}
    errorMessage={testError}
  />
</div>
```

Аналогично для `LLMConfigForm`.

---

## C · FieldError (НОВЫЙ — единая валидация форм)

**Файл:** `frontend/components/ui/FieldError.tsx`
**Заменяет:** 17+ inline `<p className="text-xs text-red-400 mt-1">{errors.X}</p>` в формах.

### API

```ts
interface FieldErrorProps {
  message?: string | null;
  /** Связать с input id для aria-describedby */
  id?: string;
}
```

### JSX

```tsx
"use client";
import { AlertCircle } from "lucide-react";

export function FieldError({ message, id }: FieldErrorProps) {
  if (!message) return null;
  return (
    <p
      id={id}
      role="alert"
      className="flex items-start gap-1.5 text-xs text-[var(--error)] mt-1 leading-tight"
    >
      <AlertCircle className="h-3 w-3 flex-none mt-[2px]" aria-hidden="true" />
      <span>{message}</span>
    </p>
  );
}
```

### Integration

```diff
-  {errors.endpoint && (
-    <p className="text-xs text-red-400 mt-1">{errors.endpoint}</p>
-  )}
+  <FieldError id="endpoint-error" message={errors.endpoint} />
```

И на input — `aria-describedby="endpoint-error"`, `aria-invalid={!!errors.endpoint}`.

---

## D · Skeleton (НОВЫЙ)

**Файл:** `frontend/components/ui/Skeleton.tsx`
См. `04-motion-system.md` M01 для CSS и кода.

---

## E · TraceSummary (НОВЫЙ — заменяет raw JsonTree в Trace)

**Файл:** `frontend/components/chat/TraceSummary.tsx`
**Интегрируется в:** `frontend/components/chat/ToolTrace.tsx`

### Назначение

Раскрывая trace, пользователь видит **человеческий summary**: «Спросил у 1С: документы за май → получил 24 записи (380 мс)». Только при клике «Показать JSON» — раскрывается raw `<JsonTree>` (теперь с правильными цветами после REM-1).

### API

```ts
interface TraceSummaryProps {
  toolCall: ToolCallRecord;       // тип уже есть в lib/types.ts
  index: number;
}

interface ToolCallRecord {
  name: string;                   // "execute_query", "get_metadata", ...
  args?: Record<string, unknown>;
  result?: unknown;
  ok: boolean;
  duration_ms?: number;
  error?: string;
}
```

### Human-readable summary

Для каждого `tool_name` — функция в `frontend/lib/tool-summary.ts`:

```ts
import type { ToolCallRecord } from "./types";

export function summarizeToolCall(call: ToolCallRecord): {
  title: string;       // что сделал
  result: string;      // что получил
} {
  const { name, args, result, ok } = call;

  switch (name) {
    case 'execute_query': {
      const q = String(args?.query ?? '').slice(0, 60);
      const rowCount = Array.isArray(result) ? result.length :
                       (result as any)?.rows?.length ?? 0;
      return {
        title: `Запрос к 1С${q ? ` — «${q}${q.length >= 60 ? '…' : ''}»` : ''}`,
        result: ok ? `${rowCount} ${plural(rowCount, 'запись', 'записи', 'записей')}` : 'ошибка',
      };
    }
    case 'get_metadata': {
      const path = String(args?.path ?? args?.object ?? '');
      return {
        title: `Чтение структуры${path ? ` — ${path}` : ''}`,
        result: ok ? 'получено' : 'не найдено',
      };
    }
    case 'get_event_log': {
      const fromTs = args?.from ? String(args.from) : '';
      const count = Array.isArray(result) ? result.length : 0;
      return {
        title: `Журнал регистраций${fromTs ? ` с ${fromTs}` : ''}`,
        result: `${count} ${plural(count, 'запись', 'записи', 'записей')}`,
      };
    }
    case 'find_references_to_object': {
      const refCount = Array.isArray(result) ? result.length : 0;
      return {
        title: `Поиск ссылок на объект`,
        result: `${refCount} ${plural(refCount, 'ссылка', 'ссылки', 'ссылок')}`,
      };
    }
    // ... добавь все из mcp-tool-descriptions.ts
    default:
      return {
        title: name,
        result: ok ? 'выполнено' : 'ошибка',
      };
  }
}

function plural(n: number, one: string, few: string, many: string) {
  const mod10 = n % 10, mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 14) return many;
  if (mod10 === 1) return one;
  if (mod10 >= 2 && mod10 <= 4) return few;
  return many;
}
```

### JSX

```tsx
"use client";
import { useState } from "react";
import { ChevronRight, ChevronDown, Check, AlertTriangle } from "lucide-react";
import { JsonTree } from "@/lib/json-tree";
import { summarizeToolCall } from "@/lib/tool-summary";
import { cn } from "@/lib/utils";
import type { ToolCallRecord } from "@/lib/types";

interface TraceSummaryProps {
  toolCall: ToolCallRecord;
  index: number;
}

export function TraceSummary({ toolCall, index }: TraceSummaryProps) {
  const [showRaw, setShowRaw] = useState(false);
  const summary = summarizeToolCall(toolCall);
  const { ok, duration_ms } = toolCall;

  return (
    <div
      className="border-b border-[var(--bd-1)] last:border-b-0 px-4 py-2.5"
      data-testid={`trace-step-${index}`}
    >
      <div className="flex items-start gap-3">
        <span
          className="text-[10px] tracking-[0.14em] text-[var(--fg-4)] tabular-nums pt-0.5 select-none"
          style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
        >
          {String(index + 1).padStart(2, '0')}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
            <span className="font-medium text-[var(--accent)]">{summary.title}</span>
            <span className="text-[var(--fg-3)]">·</span>
            <span className={cn(ok ? "text-[var(--success)]" : "text-[var(--error)]")}>
              {ok ? <Check className="inline h-3 w-3 mr-1" /> : <AlertTriangle className="inline h-3 w-3 mr-1" />}
              {summary.result}
            </span>
            {duration_ms !== undefined && (
              <span
                className="text-[var(--fg-4)] tabular-nums text-[10px] tracking-[0.06em]"
                style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
              >
                {duration_ms} мс
              </span>
            )}
            <button
              type="button"
              onClick={() => setShowRaw((s) => !s)}
              className="ml-auto text-[9px] tracking-[0.18em] uppercase text-[var(--fg-3)] hover:text-[var(--fg-1)] transition-colors flex items-center gap-1"
              style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
            >
              {showRaw ? <ChevronDown className="h-2.5 w-2.5" /> : <ChevronRight className="h-2.5 w-2.5" />}
              JSON
            </button>
          </div>
          {showRaw && (
            <div className="mt-2 p-3 bg-[var(--code-bg)] rounded border border-[var(--bd-2)] text-[var(--code-fg)] animate-fade-up">
              <div className="text-[9px] tracking-[0.16em] uppercase text-[var(--fg-4)] mb-2"
                   style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}>
                Параметры
              </div>
              <JsonTree value={toolCall.args ?? null} defaultExpanded={2} />
              <div className="text-[9px] tracking-[0.16em] uppercase text-[var(--fg-4)] mb-2 mt-3"
                   style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}>
                Результат
              </div>
              <JsonTree value={toolCall.result ?? null} defaultExpanded={1} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

### ToolTrace integration

`frontend/components/chat/ToolTrace.tsx` — заменить рендер раскрытого state (где сейчас крутится JsonTree напрямую):

```diff
   {expanded && (
     <div className="border-t border-[var(--bd-2)]">
-      {toolCalls.map((call, i) => (
-        <div key={i} className="...">
-          <JsonTree value={call} defaultExpanded={1} />
-        </div>
-      ))}
+      {toolCalls.map((call, i) => (
+        <TraceSummary key={i} toolCall={call} index={i} />
+      ))}
     </div>
   )}
```

---

## F · BackendDownBanner (НОВЫЙ)

**Файл:** `frontend/components/shell/BackendDownBanner.tsx`
**Заменяет:** `BackendIndicator` в `app/page.tsx:18-53` (когда status = unavailable).

### Назначение

Когда `fetchHealth()` падает — вместо мелкого красного chip'а в углу показывается верхний баннер с понятным сообщением и действием.

### JSX

```tsx
"use client";
import { useState } from "react";
import { RefreshCw, AlertOctagon } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  visible: boolean;
  onRetry: () => Promise<void>;
}

export function BackendDownBanner({ visible, onRetry }: Props) {
  const [retrying, setRetrying] = useState(false);

  if (!visible) return null;

  async function handleRetry() {
    setRetrying(true);
    try {
      await onRetry();
    } finally {
      setRetrying(false);
    }
  }

  return (
    <div
      role="alert"
      className="fixed top-0 inset-x-0 z-50 flex items-center justify-between gap-3 px-4 py-2.5 bg-[var(--error-12)] border-b border-[var(--error-40)] text-[var(--error)] text-sm animate-fade-up"
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <AlertOctagon className="h-4 w-4 flex-none" />
        <span className="text-[var(--fg-1)]">
          Серверная часть не отвечает.
        </span>
        <span className="text-[var(--fg-3)] truncate hidden md:inline">
          Откройте «Диагностика» — там кнопка перезапуска и подробности.
        </span>
      </div>
      <div className="flex items-center gap-2 flex-none">
        <Button
          size="sm"
          variant="secondary"
          onClick={handleRetry}
          disabled={retrying}
          className="text-[var(--error)] border-[var(--error-40)] hover:bg-[var(--error-20)]"
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${retrying ? 'animate-spin' : ''}`} />
          {retrying ? 'Проверяю…' : 'Повторить'}
        </Button>
        <a
          href="/status"
          className="text-xs uppercase tracking-wider text-[var(--accent)] hover:underline"
        >
          Диагностика →
        </a>
      </div>
    </div>
  );
}
```

### Integration

`app/page.tsx` — `BackendIndicator` оставь как маленький success-indicator (только когда ok), либо удали целиком если хочется чистого. Дополнительно — добавь в AppShell `<BackendDownBanner>` с глобальным state из `useHealthStore` (создать).

---

## G · EnhancedChannelDropdownItem (РЕВИЗИЯ)

См. `06-screen-redesigns.md` § Channel — там вся структура item'а раскрашена.

Для самого минимума — в `ChannelSelector.tsx:283-303` (внутри dropdown item):
- Добавь chip с типом конфигурации (УТ / ERP / УСО / Auto)
- Замени «24 инструментов» на «N объектов · N инструментов» с last-sync
- Убери строку «Канал: tranzit-prod» (это техническая инфа)

Это требует расширения `MCPConnection` модели — см. `06-screen-redesigns.md`.

---

## H · Composer Hub (РЕВИЗИЯ Welcome screen)

См. `06-screen-redesigns.md` § Welcome — там полный JSX.

---

## Резюме новых файлов

```
frontend/components/ui/
  UndoToast.tsx              ← новый
  UndoToastHost.tsx          ← новый
  LiveTestResult.tsx         ← новый
  FieldError.tsx             ← новый
  Skeleton.tsx               ← новый

frontend/components/chat/
  TraceSummary.tsx           ← новый
  ComposerHub.tsx            ← новый (см. 06)

frontend/components/shell/
  BackendDownBanner.tsx      ← новый

frontend/lib/
  undo-toast.ts              ← новый (event bus)
  tool-summary.ts            ← новый (human-readable mapper)
  app-version.ts             ← новый (REM-3)
```

Реструктуризованные:
```
frontend/components/chat/StreamingIndicator.tsx  ← УДАЛИТЬ (REM-5)
```
