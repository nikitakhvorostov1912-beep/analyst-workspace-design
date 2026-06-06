# Индикатор хода запроса (свёрнутый + анимация) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать состояние запроса всегда понятным — свёрнутый индикатор с анимацией появляется мгновенно по `isStreaming`, разворачивается в существующий StreamingStages, чётко показывает «готово» и громко — «ошибку».

**Architecture:** Новый `StreamProgress` (свёрнутая строка: дышащие точки + лейбл этапа + живой таймер + шеврон; развёрнутый режим рендерит неизменный `StreamingStages`). Индикатор завязан на реальный `isStreaming` из `useChatStream` (фикс мёртвой зоны), таймер — от `streamStartedAt`. Ошибки транспорта (SSL) пишутся в `message.error` → громкий inline-`Alert` с «Повторить». Аватар пульсирует кольцом во время стрима.

**Tech Stack:** Next.js 15, React 19, TypeScript, Vitest + @testing-library/react. Бренд: только `--accent` + существующие keyframes `status-pulse`/`blink`/`fade-up` (без glow/gradient/glass). Бэкенд не трогаем.

**Спека:** `docs/superpowers/specs/2026-06-06-stream-progress-indicator-design.md`

---

### Task 1: Storage-префы свёрнуто/развёрнуто

**Files:**
- Modify: `frontend/lib/storage.ts` (добавить KEY + getter/setter по образцу `getActiveTypicalChannelId`)
- Test: `frontend/lib/__tests__/stream-steps-pref.test.ts`

- [ ] **Step 1: Написать падающий тест**

```ts
// frontend/lib/__tests__/stream-steps-pref.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import {
  getStreamStepsExpanded,
  setStreamStepsExpanded,
} from "@/lib/storage";

beforeEach(() => {
  window.localStorage.clear();
});

describe("stream steps pref", () => {
  it("по умолчанию свёрнуто (false)", () => {
    expect(getStreamStepsExpanded()).toBe(false);
  });

  it("сохраняет true и читает обратно", () => {
    setStreamStepsExpanded(true);
    expect(getStreamStepsExpanded()).toBe(true);
  });

  it("сохраняет false", () => {
    setStreamStepsExpanded(true);
    setStreamStepsExpanded(false);
    expect(getStreamStepsExpanded()).toBe(false);
  });
});
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `cd frontend && ./node_modules/.bin/vitest run lib/__tests__/stream-steps-pref.test.ts`
Expected: FAIL — `getStreamStepsExpanded` не экспортируется.

- [ ] **Step 3: Добавить KEY + функции в storage.ts**

Добавить константу рядом с другими `KEY_*` (после строки `const KEY_ACTIVE_TYPICAL = "analyst.active_typical";`):

```ts
const KEY_STREAM_STEPS_EXPANDED = "analyst.stream_steps_expanded";
```

Добавить в конец файла:

```ts
// --- Индикатор хода запроса: свёрнуто/развёрнуто (StreamProgress) ---

/** Развёрнут ли детальный список шагов в индикаторе стрима. Default — false (свёрнуто). */
export function getStreamStepsExpanded(): boolean {
  const ls = safeLocalStorage();
  if (!ls) return false;
  return ls.getItem(KEY_STREAM_STEPS_EXPANDED) === "true";
}

/** Сохраняет предпочтение развёрнутости шагов. */
export function setStreamStepsExpanded(expanded: boolean): void {
  const ls = safeLocalStorage();
  if (!ls) return;
  ls.setItem(KEY_STREAM_STEPS_EXPANDED, expanded ? "true" : "false");
}
```

- [ ] **Step 4: Запустить — зелено**

Run: `cd frontend && ./node_modules/.bin/vitest run lib/__tests__/stream-steps-pref.test.ts`
Expected: PASS (3 теста).

- [ ] **Step 5: Коммит**

```bash
git add frontend/lib/storage.ts frontend/lib/__tests__/stream-steps-pref.test.ts
git commit -m "feat(frontend): storage-преф свёрнуто/развёрнуто для индикатора стрима"
```

---

### Task 2: buildStreamingStages — seed «Анализирую» при running без стадии

**Files:**
- Modify: `frontend/lib/streaming-stages.ts` (добавить флаг `running` в input + seed-ветку)
- Test: `frontend/lib/__tests__/streaming-stages.test.ts` (добавить кейс; если файла нет — создать)

> Проверь существование `frontend/lib/__tests__/streaming-stages.test.ts`. Если есть — добавь блок `describe` ниже в конец. Если нет — создай файл с импортами и этим блоком.

- [ ] **Step 1: Написать падающий тест**

```ts
// добавить в frontend/lib/__tests__/streaming-stages.test.ts
import { describe, it, expect } from "vitest";
import { buildStreamingStages } from "@/lib/streaming-stages";

describe("buildStreamingStages — running seed", () => {
  it("running && stage=null → seed [analyzing], activeIndex 0", () => {
    const r = buildStreamingStages({
      streamingStage: null,
      currentToolName: null,
      toolCalls: [],
      running: true,
    });
    expect(r).not.toBeNull();
    expect(r!.stages).toEqual([{ kind: "analyzing" }]);
    expect(r!.activeIndex).toBe(0);
  });

  it("не running && stage=null → null (как раньше)", () => {
    const r = buildStreamingStages({
      streamingStage: null,
      currentToolName: null,
      toolCalls: [],
      running: false,
    });
    expect(r).toBeNull();
  });

  it("running не указан && stage=null → null (обратная совместимость)", () => {
    const r = buildStreamingStages({
      streamingStage: null,
      currentToolName: null,
      toolCalls: [],
    });
    expect(r).toBeNull();
  });
});
```

- [ ] **Step 2: Запустить — падает**

Run: `cd frontend && ./node_modules/.bin/vitest run lib/__tests__/streaming-stages.test.ts`
Expected: FAIL — `running` не в типе / seed не возвращается (первый кейс получает `null`).

- [ ] **Step 3: Реализовать**

В `frontend/lib/streaming-stages.ts` изменить интерфейс input и начало функции.

Заменить:

```ts
interface BuildStagesInput {
  streamingStage: StreamingStage | null;
  currentToolName: string | null;
  toolCalls: ToolCallRecord[];
}
```

на:

```ts
interface BuildStagesInput {
  streamingStage: StreamingStage | null;
  currentToolName: string | null;
  toolCalls: ToolCallRecord[];
  /** true пока идёт стрим. При running && streamingStage===null показываем seed «Анализирую». */
  running?: boolean;
}
```

Заменить:

```ts
  const { streamingStage, currentToolName, toolCalls } = input;

  if (streamingStage === null) return null;
```

на:

```ts
  const { streamingStage, currentToolName, toolCalls, running } = input;

  if (streamingStage === null) {
    // Мёртвая зона: стрим идёт, но первый SSE-status ещё не пришёл —
    // показываем seed «Анализирую», чтобы индикатор был непустым сразу.
    if (running) return { stages: [{ kind: "analyzing" }], activeIndex: 0 };
    return null;
  }
```

- [ ] **Step 4: Запустить — зелено**

Run: `cd frontend && ./node_modules/.bin/vitest run lib/__tests__/streaming-stages.test.ts`
Expected: PASS (новые 3 + существующие, если были).

- [ ] **Step 5: Коммит**

```bash
git add frontend/lib/streaming-stages.ts frontend/lib/__tests__/streaming-stages.test.ts
git commit -m "feat(frontend): buildStreamingStages seed «Анализирую» в мёртвой зоне (running)"
```

---

### Task 3: Компонент StreamProgress (свёрнутый индикатор + таймер + тоггл)

**Files:**
- Create: `frontend/components/chat/StreamProgress.tsx`
- Test: `frontend/components/chat/__tests__/StreamProgress.test.tsx`

- [ ] **Step 1: Написать падающий тест**

```tsx
// frontend/components/chat/__tests__/StreamProgress.test.tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

vi.mock("@/lib/storage", () => ({
  getStreamStepsExpanded: vi.fn(() => false),
  setStreamStepsExpanded: vi.fn(),
}));

import { StreamProgress } from "@/components/chat/StreamProgress";
import {
  getStreamStepsExpanded,
  setStreamStepsExpanded,
} from "@/lib/storage";
import type { Stage } from "@/components/chat/StreamingStages";

const mockGet = getStreamStepsExpanded as ReturnType<typeof vi.fn>;
const mockSet = setStreamStepsExpanded as ReturnType<typeof vi.fn>;

const stages: Stage[] = [{ kind: "analyzing" }];

beforeEach(() => {
  vi.clearAllMocks();
  mockGet.mockReturnValue(false);
});

describe("StreamProgress", () => {
  it("свёрнут по умолчанию: видна строка-индикатор, НЕ виден детальный StreamingStages", () => {
    render(<StreamProgress stages={stages} activeIndex={0} startedAt={null} />);
    expect(screen.getByTestId("stream-progress")).toBeInTheDocument();
    expect(screen.queryByTestId("streaming-stages")).not.toBeInTheDocument();
  });

  it("клик по тогглу разворачивает детальные шаги + пишет в storage", () => {
    render(<StreamProgress stages={stages} activeIndex={0} startedAt={null} />);
    fireEvent.click(screen.getByTestId("stream-progress-toggle"));
    expect(screen.getByTestId("streaming-stages")).toBeInTheDocument();
    expect(mockSet).toHaveBeenCalledWith(true);
  });

  it("инициализируется развёрнутым, если в storage true", () => {
    mockGet.mockReturnValue(true);
    render(<StreamProgress stages={stages} activeIndex={0} startedAt={null} />);
    expect(screen.getByTestId("streaming-stages")).toBeInTheDocument();
  });

  it("показывает живой таймер от startedAt", () => {
    vi.useFakeTimers();
    vi.setSystemTime(1_000);
    try {
      render(<StreamProgress stages={stages} activeIndex={0} startedAt={1_000} />);
      act(() => {
        vi.setSystemTime(4_200);
        vi.advanceTimersByTime(600);
      });
      expect(screen.getByTestId("stream-progress-timer").textContent).toContain("3");
    } finally {
      vi.useRealTimers();
    }
  });
});
```

- [ ] **Step 2: Запустить — падает**

Run: `cd frontend && ./node_modules/.bin/vitest run components/chat/__tests__/StreamProgress.test.tsx`
Expected: FAIL — модуль `StreamProgress` не существует.

- [ ] **Step 3: Реализовать компонент**

```tsx
// frontend/components/chat/StreamProgress.tsx
"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { StreamingStages, type Stage, type StageKind } from "./StreamingStages";
import { getStreamStepsExpanded, setStreamStepsExpanded } from "@/lib/storage";
import { cn } from "@/lib/utils";

/**
 * StreamProgress — свёрнутый по умолчанию индикатор хода запроса.
 *
 *  • Свёрнут: дышащие точки (--accent, keyframe blink) + лейбл текущего этапа +
 *    живой таймер. Появляется мгновенно (caller рендерит пока isStreaming).
 *  • Развёрнут (по клику, запоминается в localStorage): детальный StreamingStages.
 *
 * Бренд: только --accent + keyframes blink/fade-up, без glow/gradient/glass.
 */

const COLLAPSED_LABEL: Record<StageKind, string> = {
  analyzing: "Анализирую",
  learn: "Ищу прошлые ответы",
  tool: "Выполняю запрос",
  tool_done: "Обрабатываю",
  finalizing: "Формирую ответ",
};

interface StreamProgressProps {
  stages: Stage[];
  activeIndex: number;
  /** Время старта стрима (Date.now()) для живого таймера; null — таймер скрыт. */
  startedAt: number | null;
}

export function StreamProgress({ stages, activeIndex, startedAt }: StreamProgressProps) {
  const [expanded, setExpanded] = useState<boolean>(() => getStreamStepsExpanded());
  const [elapsedMs, setElapsedMs] = useState<number>(0);

  useEffect(() => {
    if (startedAt === null) return;
    setElapsedMs(Date.now() - startedAt);
    const id = window.setInterval(() => {
      setElapsedMs(Date.now() - startedAt);
    }, 500);
    return () => window.clearInterval(id);
  }, [startedAt]);

  function toggle() {
    setExpanded((v) => {
      const next = !v;
      setStreamStepsExpanded(next);
      return next;
    });
  }

  const active = stages[activeIndex];
  const label = active ? COLLAPSED_LABEL[active.kind] : "Думаю";
  const seconds = startedAt !== null ? (elapsedMs / 1000).toFixed(1) : null;

  return (
    <div data-testid="stream-progress" className="mt-2 animate-fade-up">
      <button
        type="button"
        onClick={toggle}
        data-testid="stream-progress-toggle"
        aria-expanded={expanded}
        className="inline-flex items-center gap-2 h-8 px-2.5 rounded-md bg-[var(--bg-1)] border border-[var(--bd-2)] text-xs text-[var(--fg-2)] hover:border-[var(--bd-3)] transition-colors"
      >
        {/* Дышащие точки — --accent, keyframe blink со стаггером */}
        <span className="inline-flex items-center gap-0.5" aria-hidden="true">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="inline-block h-1.5 w-1.5 rounded-full bg-[var(--accent)] animate-blink"
              style={{ animationDelay: `${i * 160}ms` }}
            />
          ))}
        </span>
        <span className="text-[var(--fg-1)]">{label}…</span>
        {seconds !== null && (
          <span
            data-testid="stream-progress-timer"
            className="tabular-nums text-[var(--fg-3)]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            {seconds}с
          </span>
        )}
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-[var(--fg-3)]" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-[var(--fg-3)]" />
        )}
        <span className="sr-only">шаги</span>
      </button>

      {expanded && (
        <div className="mt-1.5">
          <StreamingStages stages={stages} activeIndex={activeIndex} />
        </div>
      )}
    </div>
  );
}
```

> ВНИМАНИЕ: импорт `type StageKind` из `./StreamingStages` требует, чтобы `StageKind` был экспортирован. Он уже `export type StageKind` (StreamingStages.tsx:25) — это НЕ переписывание компонента, только используем существующий экспорт.

- [ ] **Step 4: Запустить — зелено**

Run: `cd frontend && ./node_modules/.bin/vitest run components/chat/__tests__/StreamProgress.test.tsx`
Expected: PASS (4 теста).

- [ ] **Step 5: Коммит**

```bash
git add frontend/components/chat/StreamProgress.tsx frontend/components/chat/__tests__/StreamProgress.test.tsx
git commit -m "feat(frontend): StreamProgress — свёрнутый индикатор стрима + таймер + тоггл"
```

---

### Task 4: useChatStream — streamStartedAt + ошибка транспорта в пузырь

**Files:**
- Modify: `frontend/components/chat/useChatStream.ts`
- Test: `frontend/components/chat/__tests__/useChatStream.test.tsx` (добавить 1 кейс на catch→message.error)

- [ ] **Step 1: Написать падающий тест (catch пишет inline error)**

> Добавь кейс в существующий describe. Паттерн мока `fetchChat` возьми из соседних кейсов файла (он уже мокает `@/lib/api`). Ключевая проверка: если `fetchChat` бросает (транспорт/SSL), у последнего assistant-сообщения появляется `error`.

```tsx
// добавить в frontend/components/chat/__tests__/useChatStream.test.tsx
it("ошибка транспорта (throw из fetchChat) пишется в message.error", async () => {
  const { fetchChat } = await import("@/lib/api");
  (fetchChat as ReturnType<typeof vi.fn>).mockImplementation(() => {
    throw new Error("[SSL: SSLV3_ALERT_BAD_RECORD_MAC]");
  });

  const { result } = renderHook(() =>
    useChatStream({ sessionId: "s1", channelId: "c1" }),
  );

  await act(async () => {
    await result.current.send("привет");
  });

  const last = result.current.messages[result.current.messages.length - 1];
  expect(last.role).toBe("assistant");
  expect(last.error?.message).toContain("SSL");
  expect(result.current.isStreaming).toBe(false);
});
```

> Если в файле нет `renderHook`/`act` импортов — добавь `import { renderHook, act } from "@testing-library/react";`. Проверь, как другие тесты мокают `configCache.getLLMConfig` (должен вернуть валидный конфиг, иначе send выйдет раньше на «LLM не настроен»). Используй тот же mock-setup, что и существующие кейсы send.

- [ ] **Step 2: Запустить — падает**

Run: `cd frontend && ./node_modules/.bin/vitest run components/chat/__tests__/useChatStream.test.tsx`
Expected: FAIL — `last.error` равен `undefined` (catch сейчас только `setError`, не пишет inline).

- [ ] **Step 3: Реализовать**

В `frontend/components/chat/useChatStream.ts`:

(a) Добавить state рядом с другими (после `const [currentToolName, setCurrentToolName] = useState<string | null>(null);`):

```ts
  const [streamStartedAt, setStreamStartedAt] = useState<number | null>(null);
```

(b) В `send`, сразу после `setIsStreaming(true);` (там же где `setStreamingStage(null)`), добавить:

```ts
      setStreamStartedAt(Date.now());
```

(c) В блоке `done` (после `setIsStreaming(false);`) и в каждой ветке `error` (после соответствующего `setIsStreaming(false);`) — не обязательно, таймер скрывается в finally. Главное — finally. Перейти к (d).

(d) В `catch (err)` заменить:

```ts
        const msg = err instanceof Error ? err.message : "Неизвестная ошибка";
        setError(msg);
```

на:

```ts
        const msg = err instanceof Error ? err.message : "Неизвестная ошибка";
        setError(msg);
        // Громкий сигнал в пузыре: транспорт/SSL-падение пишем в message.error,
        // иначе пустой пузырь + крошечная строка у композера легко пропустить.
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (!last || last.role !== "assistant") return prev;
          return [
            ...prev.slice(0, -1),
            { ...last, error: { message: msg, code: "llm_network_error" } },
          ];
        });
```

(e) В `finally` добавить сброс таймера (после `setStreamingStage(null);` внутри `if (mountedRef.current)`):

```ts
          setStreamStartedAt(null);
```

(f) Добавить `streamStartedAt` в return-объект (рядом с `streamingStage`):

```ts
    streamStartedAt,
```

(g) Добавить `streamStartedAt` в тип `UseChatStreamReturn` (после `streamingStage: StreamingStage | null;`):

```ts
  /** Время старта текущего стрима (Date.now()) для живого таймера; null если не стримим. */
  streamStartedAt: number | null;
```

- [ ] **Step 4: Запустить — зелено**

Run: `cd frontend && ./node_modules/.bin/vitest run components/chat/__tests__/useChatStream.test.tsx`
Expected: PASS (новый кейс + существующие без регресса).

- [ ] **Step 5: Коммит**

```bash
git add frontend/components/chat/useChatStream.ts frontend/components/chat/__tests__/useChatStream.test.tsx
git commit -m "feat(frontend): useChatStream — streamStartedAt + ошибка транспорта в пузырь"
```

---

### Task 5: AssistantMessage + проброс isStreaming/streamStartedAt

**Files:**
- Modify: `frontend/components/chat/AssistantMessage.tsx`
- Modify: `frontend/components/chat/Message.tsx`
- Modify: `frontend/components/chat/Thread.tsx`
- Modify: `frontend/app/sessions/[id]/page.tsx`
- Test: `frontend/components/chat/__tests__/AssistantMessage.test.tsx` (создать; проверяет 3 поведения)

- [ ] **Step 1: Написать падающий тест**

```tsx
// frontend/components/chat/__tests__/AssistantMessage.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/storage", () => ({
  getStreamStepsExpanded: vi.fn(() => false),
  setStreamStepsExpanded: vi.fn(),
  getMCPConnections: vi.fn(() => []),
  getActiveChannelId: vi.fn(() => null),
}));

import { AssistantMessage } from "@/components/chat/AssistantMessage";
import type { ChatMessage } from "@/lib/types";

const baseMsg: ChatMessage = {
  id: "m1",
  role: "assistant",
  content: "",
  created_at: new Date(0).toISOString(),
  cards: [],
  tool_calls: [],
};

beforeEach(() => vi.clearAllMocks());

describe("AssistantMessage — индикатор стрима", () => {
  it("isStreaming=true БЕЗ streamingStage → StreamProgress виден сразу (фикс мёртвой зоны)", () => {
    render(
      <AssistantMessage
        message={baseMsg}
        isStreaming
        streamingStage={null}
        streamStartedAt={1000}
      />,
    );
    expect(screen.getByTestId("stream-progress")).toBeInTheDocument();
  });

  it("isStreaming=false + есть content + duration → маркер «готово за Xс»", () => {
    render(
      <AssistantMessage
        message={{ ...baseMsg, content: "Ответ", duration_ms: 4100 }}
        isStreaming={false}
        streamingStage={null}
      />,
    );
    expect(screen.getByTestId("done-marker").textContent).toMatch(/готово/i);
    expect(screen.queryByTestId("stream-progress")).not.toBeInTheDocument();
  });

  it("message.error → Alert + кнопка «Повторить» (если onRepeat задан)", () => {
    const onRepeat = vi.fn();
    render(
      <AssistantMessage
        message={{ ...baseMsg, error: { message: "[SSL] bad record mac", code: "llm_network_error" } }}
        isStreaming={false}
        streamingStage={null}
        onRepeat={onRepeat}
      />,
    );
    expect(screen.getByText(/SSL/)).toBeInTheDocument();
    const retry = screen.getByTestId("error-retry");
    retry.click();
    expect(onRepeat).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Запустить — падает**

Run: `cd frontend && ./node_modules/.bin/vitest run components/chat/__tests__/AssistantMessage.test.tsx`
Expected: FAIL — нет `stream-progress`/`done-marker`/`error-retry`, проп `isStreaming` не используется.

- [ ] **Step 3a: AssistantMessage.tsx**

Заменить импорт `StreamingStages`:

```ts
import { StreamingStages } from "./StreamingStages";
```

на:

```ts
import { StreamProgress } from "./StreamProgress";
```

В `AssistantMessageProps` добавить (после `currentToolName?`):

```ts
  /** Реальный флаг стрима из useChatStream (не Boolean(streamingStage)). */
  isStreaming?: boolean;
  /** Время старта стрима для таймера. */
  streamStartedAt?: number | null;
```

В сигнатуре деструктуризации добавить `isStreaming = false, streamStartedAt = null`:

```ts
export function AssistantMessage({
  message,
  streamingStage,
  currentToolName,
  isStreaming = false,
  streamStartedAt = null,
  sessionId,
  onRepeat,
}: AssistantMessageProps) {
```

Заменить:

```ts
  const pipeline = buildStreamingStages({
    streamingStage: streamingStage ?? null,
    currentToolName: currentToolName ?? null,
    toolCalls: message.tool_calls ?? [],
  });

  const time = formatTime(message.created_at);
  const isStreaming = Boolean(streamingStage);
```

на:

```ts
  const pipeline = buildStreamingStages({
    streamingStage: streamingStage ?? null,
    currentToolName: currentToolName ?? null,
    toolCalls: message.tool_calls ?? [],
    running: isStreaming,
  });

  const time = formatTime(message.created_at);
```

Заменить аватар (строка `<BrandMark size={28} className="flex-none mt-0.5" />`) на пульсирующую обёртку:

```tsx
      {/* Аватар-глиф (F-06). Во время стрима — мягкое пульсирующее кольцо (--accent). */}
      <span
        className="flex-none mt-0.5 inline-flex rounded-[5px]"
        style={
          isStreaming
            ? {
                color: "var(--accent)",
                animation:
                  "status-pulse 1.8s var(--ease, cubic-bezier(0.4,0,0.2,1)) infinite",
              }
            : undefined
        }
      >
        <BrandMark size={28} />
      </span>
```

Заменить inline-error блок:

```tsx
        {message.error && (
          <div className="mb-2">
            <Alert tone="error" title={message.error.message} />
          </div>
        )}
```

на (добавить `data-testid` + actions «Повторить»):

```tsx
        {message.error && (
          <div className="mb-2">
            <Alert
              tone="error"
              title={message.error.message}
              data-testid="message-error"
              actions={
                onRepeat ? (
                  <button
                    type="button"
                    onClick={onRepeat}
                    data-testid="error-retry"
                    className="inline-flex items-center gap-1 h-7 px-2 rounded-md border border-[var(--error-40)] text-[12px] text-[var(--error)] hover:bg-[var(--error-12)] transition-colors"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    Повторить
                  </button>
                ) : undefined
              }
            />
          </div>
        )}
```

Заменить блок StreamingStages:

```tsx
        {/* Streaming pipeline — pipeline-визуализация с иконками + переходы */}
        {pipeline && (
          <div className="mt-2">
            <StreamingStages
              stages={pipeline.stages}
              activeIndex={pipeline.activeIndex}
            />
          </div>
        )}
```

на StreamProgress (только пока стримим) + done-маркер:

```tsx
        {/* Индикатор хода запроса — свёрнутый по умолчанию (StreamProgress) */}
        {isStreaming && pipeline && (
          <StreamProgress
            stages={pipeline.stages}
            activeIndex={pipeline.activeIndex}
            startedAt={streamStartedAt}
          />
        )}

        {/* Однозначное «готово» по завершении */}
        {!isStreaming && message.content && message.duration_ms != null && message.duration_ms > 0 && (
          <div
            data-testid="done-marker"
            className="mt-2 inline-flex items-center gap-1 text-[11px] text-[var(--success)]"
            style={{ fontFamily: "var(--font-jb-mono), ui-monospace, monospace" }}
          >
            <Check className="h-3 w-3" />
            готово за {formatDuration(message.duration_ms)}
          </div>
        )}
```

Добавить импорт иконки `Check` (в строке `import { RotateCcw } from "lucide-react";`):

```ts
import { Check, RotateCcw } from "lucide-react";
```

- [ ] **Step 3b: Message.tsx — проброс**

В `MessageProps` добавить (после `currentToolName?`):

```ts
  isStreaming?: boolean;
  streamStartedAt?: number | null;
```

В деструктуризации и в JSX `<AssistantMessage>` пробросить их:

```tsx
export function Message({ message, streamingStage, currentToolName, isStreaming, streamStartedAt, sessionId, onRepeat }: MessageProps) {
```

```tsx
      <AssistantMessage
        message={message}
        streamingStage={streamingStage}
        currentToolName={currentToolName}
        isStreaming={isStreaming}
        streamStartedAt={streamStartedAt}
        sessionId={sessionId}
        onRepeat={onRepeat}
      />
```

- [ ] **Step 3c: Thread.tsx — проброс в последний assistant**

В `ThreadProps` добавить (после `currentToolName?`):

```ts
  isStreaming?: boolean;
  streamStartedAt?: number | null;
```

В сигнатуре:

```tsx
export function Thread({ messages, streamingStage, currentToolName, isStreaming, streamStartedAt, sessionId, onRepeat }: ThreadProps) {
```

В `<Message>` (внутри map) добавить пробросы только для последнего assistant:

```tsx
            <Message
              key={msg.id}
              message={msg}
              streamingStage={i === lastAssistantIdx ? streamingStage : null}
              currentToolName={i === lastAssistantIdx ? currentToolName : null}
              isStreaming={i === lastAssistantIdx ? isStreaming : false}
              streamStartedAt={i === lastAssistantIdx ? streamStartedAt : null}
              sessionId={sessionId}
              onRepeat={prevUser ? () => onRepeat?.(prevUser) : undefined}
            />
```

- [ ] **Step 3d: page.tsx — отдать streamStartedAt в Thread**

В деструктуризации хука (строка с `useChatStream`) добавить `streamStartedAt`:

```ts
  const { messages, isStreaming, error, streamingStage, streamStartedAt, currentToolName, pendingConfirm, resolveConfirm, pendingClarify, resolveClarify, send, interrupt } = useChatStream({
```

В JSX `<Thread ... streamingStage={streamingStage}>` добавить рядом:

```tsx
            streamingStage={streamingStage}
            isStreaming={isStreaming}
            streamStartedAt={streamStartedAt}
```

> Найди существующий проп `streamingStage={streamingStage}` в `<Thread>` и добавь две строки рядом. Если у Thread проброс currentToolName тоже есть — оставь как есть.

- [ ] **Step 4: Запустить тесты + типы + сборку**

Run: `cd frontend && ./node_modules/.bin/vitest run components/chat/__tests__/AssistantMessage.test.tsx`
Expected: PASS (3 теста).

Run: `cd frontend && ./node_modules/.bin/tsc --noEmit`
Expected: без НОВЫХ ошибок в наших файлах (pre-existing ошибки в чужих тест-файлах допустимы — см. примечание).

- [ ] **Step 5: Коммит**

```bash
git add frontend/components/chat/AssistantMessage.tsx frontend/components/chat/Message.tsx frontend/components/chat/Thread.tsx "frontend/app/sessions/[id]/page.tsx" frontend/components/chat/__tests__/AssistantMessage.test.tsx
git commit -m "feat(frontend): AssistantMessage — StreamProgress, готово-маркер, retry; проброс isStreaming"
```

---

### Task 6: Финальная верификация

- [ ] **Step 1: Полный фронт-прогон**

Run: `cd frontend && ./node_modules/.bin/vitest run`
Expected: PASS — без регрессий (включая существующие StreamingStages/useChatStream-тесты).

- [ ] **Step 2: Сборка**

Run: `cd frontend && ./node_modules/.bin/next build`
Expected: успешная сборка.

- [ ] **Step 3: Live-проверка в Chrome**

Поднять `pwsh .claude/skills/awd-dev-up/scripts/up.ps1`, открыть http://localhost:3010, подключиться к КА Демо, отправить вопрос. Ожидаемо:
- сразу после отправки в пузыре появляется свёрнутый индикатор «●●● Анализирую… 0.5с» (без мёртвой зоны);
- клик по шеврону разворачивает детальные шаги; перезагрузка страницы сохраняет выбор;
- аватар пульсирует кольцом;
- при SSL-падении MiMo — в пузыре громкий Alert с «Повторить» (а не пустой пузырь);
- при успехе — индикатор исчез, под ответом «✓ готово за Xс».

---

## Self-Review

**1. Покрытие спеки:**
- Поведение (мгновенно по isStreaming, свёрнут default, тоггл, персист) → Task 1 (преф) + Task 2 (seed) + Task 3 (компонент) + Task 5 (isStreaming проброс). ✔
- Анимация (пульс аватара + дышащие точки + таймер) → Task 3 (точки+таймер) + Task 5 (пульс аватара). ✔
- Готово (G3) → Task 5 (done-marker). ✔
- Ошибка в пузыре + Повторить (G2) → Task 4 (catch→message.error) + Task 5 (Alert actions). ✔
- Тесты → Task 1/2/3/4/5 + Task 6 прогон. ✔
- Out of scope (глоб. полоса, новые keyframes, скелетоны) — не реализуются. ✔

**2. Плейсхолдеры:** нет — код приведён целиком/точными блоками. Два места требуют сверки с фактическим файлом (существующий mock-setup в useChatStream.test и точное место `<Thread>`-пропа в page.tsx) — отмечены явными инструкциями, не заглушки.

**3. Согласованность имён:** `getStreamStepsExpanded/setStreamStepsExpanded`, `streamStartedAt`, `StreamProgress` (props `stages`/`activeIndex`/`startedAt`), `buildStreamingStages({running})`, testid `stream-progress`/`stream-progress-toggle`/`stream-progress-timer`/`done-marker`/`error-retry`/`message-error` — единообразны во всех тасках. `StageKind`/`Stage` импортируются из существующего экспорта StreamingStages (компонент не переписывается).
