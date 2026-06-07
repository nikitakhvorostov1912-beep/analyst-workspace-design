# Выжать максимум из Напарника (ИТС) — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перестать выбрасывать ссылки и полный текст статей, которые возвращает Напарник: карточка «Источники ИТС» со ссылками + кнопка «Разобрать статью» (`fetch_its`) + авто-дочитывание топ-1 статьи + консервативный трим системного промпта.

**Architecture:** Backend строит новую карточку `its_sources` из markdown-результата `buddy.search_its` (парсит ссылки, конструирует `doc_id` из URL). Frontend рендерит карточку со ссылками на its.1c.ru + кнопкой, которая отправляет follow-up сообщение через существующий `send` (модель вызывает `buddy.fetch_its`). Промпт правится точечно: директива search→fetch-топ-1, запрет дублировать ссылки, консервативный трим.

**Tech Stack:** Python 3.12 / FastAPI / pydantic v2 (backend), Next.js 15 / React 19 / TypeScript / Vitest (frontend).

**Спека:** `docs/superpowers/specs/2026-06-07-naparnik-its-value-design.md`

**Команды тестов:**
- Backend: `./.venv/Scripts/python.exe -m pytest <files> --no-cov -p no:cacheprovider -q` (из `backend/`)
- Frontend: `./node_modules/.bin/vitest run <files>` и `./node_modules/.bin/next build` (из `frontend/`)

**git add — только перечисленные файлы** (рабочее дерево содержит NIM-файлы + probe-скрипты — НЕ коммитить через `-A`).

---

## File Structure

| Файл | Ответственность | Действие |
|---|---|---|
| `backend/app/orchestrator/cards.py` | парсер + payload + регистрация карточки ИТС | Modify |
| `backend/tests/test_its_sources_card.py` | юнит парсера карточки | Create |
| `backend/app/orchestrator/loop.py` | промпт: fetch-директива + анти-дубль + трим | Modify (SYSTEM_PROMPT) |
| `backend/tests/test_loop_system_prompt.py` | проверки нового промпта | Modify |
| `frontend/lib/types.ts` | типы `ITSSource`, `ITSSourcesCardPayload`, union | Modify |
| `frontend/components/cards/CardHeader.tsx` | `CardType` + `TYPE_META` для `its_sources` | Modify |
| `frontend/components/cards/ITSSourcesCard.tsx` | компонент карточки | Create |
| `frontend/components/cards/__tests__/ITSSourcesCard.test.tsx` | тест компонента | Create |
| `frontend/components/cards/CardRenderer.tsx` | `case "its_sources"` | Modify |
| `frontend/components/chat/AssistantMessage.tsx` | проп `onAsk` → `sendMessage` | Modify |
| `frontend/components/chat/Message.tsx` | проброс `onAsk` | Modify |
| `frontend/components/chat/Thread.tsx` | проброс `onAsk` | Modify |
| `frontend/app/sessions/[id]/page.tsx` | разводка `onAsk` → `send` | Modify |

---

## Task 1: Backend — карточка «Источники ИТС»

**Files:**
- Modify: `backend/app/orchestrator/cards.py`
- Test: `backend/tests/test_its_sources_card.py`

- [ ] **Step 1: Написать падающий тест**

Create `backend/tests/test_its_sources_card.py`:

```python
"""Карточка «Источники ИТС» из результата buddy.search_its (markdown с ссылками)."""
from __future__ import annotations

from app.orchestrator.cards import (
    _its_doc_id_from_url,
    build_card_from_tool_result,
)

# Усечённый, но реальный по форме результат buddy.search_its (см. probe).
_SEARCH_ITS_TEXT = (
    "По запросу '*RLS*' в **Базе знаний ИТС** найдено **3** документов.\n"
    "[Молокозавод > Глава 2. ПРАВА ДОСТУПА]"
    "(https://its.1c.ru/db/molmoderpka25#content:711:hdoc)\n"
    "[Практическое пособие разработчика > Ограничение доступа]"
    "(https://its.1c.ru/db/pubdevguide83#content:461:hdoc)\n"
    "[Каталог без якоря](https://its.1c.ru/db/bsp321doc)\n"
    "# Ограничение доступа на уровне записей (RLS)\n\nТекст синтез-ответа...\n"
)


def _mcp_result(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}]}


def test_doc_id_from_url_with_anchor():
    assert (
        _its_doc_id_from_url("https://its.1c.ru/db/pubdevguide83#content:461:hdoc")
        == "its-pubdevguide83-461-hdoc"
    )


def test_doc_id_from_url_without_anchor_is_none():
    assert _its_doc_id_from_url("https://its.1c.ru/db/bsp321doc") is None


def test_card_built_from_search_its():
    card = build_card_from_tool_result(
        "buddy.search_its", {"query": "RLS"}, _mcp_result(_SEARCH_ITS_TEXT)
    )
    assert card is not None
    assert card["type"] == "its_sources"
    sources = card["payload"]["sources"]
    assert len(sources) == 3
    # порядок сохранён, doc_id сконструирован из URL (или None без якоря)
    assert sources[0]["url"] == "https://its.1c.ru/db/molmoderpka25#content:711:hdoc"
    assert sources[0]["doc_id"] == "its-molmoderpka25-711-hdoc"
    assert sources[1]["doc_id"] == "its-pubdevguide83-461-hdoc"
    assert sources[2]["doc_id"] is None  # без якоря — кнопки не будет
    assert card["payload"]["total"] == 3
    assert card["payload"]["card_id"]  # uuid проставлен


def test_no_its_links_returns_none():
    # search_1c_documentation иногда без ссылок its.1c.ru — карточки нет.
    card = build_card_from_tool_result(
        "buddy.search_1c_documentation",
        {"query": "x"},
        _mcp_result("найдено 2 документов\nУправлениеБлокировкой/Элемент\n"),
    )
    assert card is None


def test_dedup_same_url():
    text = (
        "[A](https://its.1c.ru/db/x#content:1:hdoc)\n"
        "[A повтор](https://its.1c.ru/db/x#content:1:hdoc)\n"
    )
    card = build_card_from_tool_result("buddy.search_its", {}, _mcp_result(text))
    assert card is not None
    assert len(card["payload"]["sources"]) == 1
```

- [ ] **Step 2: Запустить — убедиться что падает**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_its_sources_card.py --no-cov -p no:cacheprovider -q`
Expected: FAIL — `ImportError: cannot import name '_its_doc_id_from_url'`.

- [ ] **Step 3: Реализовать в `cards.py`**

В `backend/app/orchestrator/cards.py` после `_extract_mcp_content` (около строки 189) добавить хелперы и payload. Сначала payload-классы рядом с другими (после `CodeCardPayload`, ~строка 126):

```python
class ITSSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    doc_id: str | None = None  # для fetch_its; None если URL без якоря content:N:kind


class ITSSourcesCardPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[ITSSource]
    total: int
    card_id: str | None = None
```

Хелперы (после `_extract_mcp_content`):

```python
# Ссылка на статью ИТС в markdown результата buddy.search_its.
_ITS_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://its\.1c\.ru/[^\s)]+)\)")
# Якорь content:N:kind → конструируем стабильный doc_id для fetch_its.
_ITS_ANCHOR_RE = re.compile(
    r"its\.1c\.ru/db/([^#/?\s]+)#content:(\d+):(hdoc|hdir)"
)


def _its_doc_id_from_url(url: str) -> str | None:
    """its.1c.ru/db/pubdevguide83#content:461:hdoc → its-pubdevguide83-461-hdoc.

    URL без якоря content:N:kind → None (fetch_its по нему не вызвать,
    кнопка «Разобрать» скрывается, ссылка остаётся).
    """
    m = _ITS_ANCHOR_RE.search(url or "")
    if not m:
        return None
    return f"its-{m.group(1)}-{m.group(2)}-{m.group(3)}"


def _extract_mcp_text(result: dict) -> str:
    """Сырой текст из MCP content[] (без попытки json-парсинга)."""
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list):
        return ""
    parts = [
        item.get("text", "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    return "\n".join(p for p in parts if p)


def _build_its_sources_card(args: dict, result: dict) -> dict | None:
    """Карточка «Источники ИТС» из markdown-результата buddy.search_its."""
    text = _extract_mcp_text(result)
    if not text:
        return None
    seen: set[str] = set()
    sources: list[ITSSource] = []
    for m in _ITS_LINK_RE.finditer(text):
        title = m.group(1).strip()
        url = m.group(2).strip()
        if url in seen:
            continue
        seen.add(url)
        sources.append(ITSSource(title=title, url=url, doc_id=_its_doc_id_from_url(url)))
    if not sources:
        return None
    payload = ITSSourcesCardPayload(
        sources=sources, total=len(sources), card_id=str(uuid4())
    )
    return {"type": "its_sources", "payload": payload.model_dump()}
```

Зарегистрировать в `_CARD_BUILDERS` (строка ~550):

```python
_CARD_BUILDERS = {
    "execute_query": _dispatch_query_card,
    "get_object_by_link": _build_object_card,
    "get_event_log": _build_log_card,
    "find_references_to_object": _build_references_card,
    "execute_code": _build_code_card,
    "get_bsl_syntax_help": _build_code_card,
    "buddy.search_its": _build_its_sources_card,
    "buddy.search_1c_documentation": _build_its_sources_card,
}
```

- [ ] **Step 4: Запустить — убедиться что зелёный**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_its_sources_card.py --no-cov -p no:cacheprovider -q`
Expected: PASS (5 тестов).

- [ ] **Step 5: Регресс существующих карточек**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cards_advanced.py tests/test_orchestrator_cards.py --no-cov -p no:cacheprovider -q`
Expected: PASS (без регресса).

- [ ] **Step 6: Commit**

```bash
git add backend/app/orchestrator/cards.py backend/tests/test_its_sources_card.py
git commit -m "feat(its): карточка «Источники ИТС» из результата buddy.search_its"
```

---

## Task 2: Frontend — типы карточки ИТС

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/components/cards/CardHeader.tsx`

- [ ] **Step 1: Добавить типы в `lib/types.ts`**

После `CodeCardPayload` (около строки 289) добавить:

```typescript
export type ITSSource = {
  title: string;
  url: string;
  doc_id?: string | null;
};

export type ITSSourcesCardPayload = {
  sources: ITSSource[];
  total: number;
  card_id?: string | null;
};
```

Расширить union `CardEnvelope` (строка ~318) новым вариантом:

```typescript
export type CardEnvelope =
  | { type: "table"; payload: TableCardPayload }
  | { type: "object"; payload: ObjectCardPayload }
  | { type: "log"; payload: LogCardPayload }
  | { type: "metric"; payload: MetricCardPayload }
  | { type: "references"; payload: ReferencesCardPayload }
  | { type: "code"; payload: CodeCardPayload }
  | { type: "graph"; payload: GraphCardPayload }
  | { type: "its_sources"; payload: ITSSourcesCardPayload };
```

- [ ] **Step 2: Расширить `CardType` + `TYPE_META` в `CardHeader.tsx`**

Строка 18 — добавить `"its_sources"` в union:

```typescript
export type CardType = "table" | "object" | "log" | "metric" | "references" | "code" | "graph" | "its_sources";
```

Импорт иконки `BookMarked` (в строке импорта lucide-react вверху файла добавить `BookMarked`). Затем в `TYPE_META` (строка ~26) добавить запись:

```typescript
  its_sources: {
    icon: BookMarked,
    label: "Источники ИТС",
    accentClass: "text-[var(--accent)]",
  },
```

- [ ] **Step 3: Проверить компиляцию типов**

Run: `./node_modules/.bin/tsc --noEmit`
Expected: без ошибок (union исчерпан, `CardRenderer` ещё имеет `default` ветку — не падает).

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/components/cards/CardHeader.tsx
git commit -m "feat(its): типы its_sources карточки + CardHeader meta"
```

---

## Task 3: Frontend — компонент ITSSourcesCard

**Files:**
- Create: `frontend/components/cards/ITSSourcesCard.tsx`
- Test: `frontend/components/cards/__tests__/ITSSourcesCard.test.tsx`

- [ ] **Step 1: Написать падающий тест**

Create `frontend/components/cards/__tests__/ITSSourcesCard.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ITSSourcesCard } from "../ITSSourcesCard";
import type { ITSSourcesCardPayload } from "@/lib/types";

const payload: ITSSourcesCardPayload = {
  total: 2,
  sources: [
    {
      title: "Практическое пособие разработчика",
      url: "https://its.1c.ru/db/pubdevguide83#content:461:hdoc",
      doc_id: "its-pubdevguide83-461-hdoc",
    },
    { title: "Каталог без якоря", url: "https://its.1c.ru/db/bsp321doc", doc_id: null },
  ],
};

describe("ITSSourcesCard", () => {
  it("рендерит ссылки на its.1c.ru (открываются в новой вкладке)", () => {
    render(<ITSSourcesCard payload={payload} />);
    const link = screen.getByRole("link", { name: /Практическое пособие/ });
    expect(link).toHaveAttribute("href", payload.sources[0].url);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("кнопка «Разобрать» только у источника с doc_id, вызывает onAnalyze", () => {
    const onAnalyze = vi.fn();
    render(<ITSSourcesCard payload={payload} onAnalyze={onAnalyze} />);
    const buttons = screen.getAllByRole("button", { name: /Разобрать/ });
    expect(buttons).toHaveLength(1); // только у первого источника (doc_id есть)
    fireEvent.click(buttons[0]);
    expect(onAnalyze).toHaveBeenCalledWith(payload.sources[0]);
  });

  it("без onAnalyze кнопок нет (read-only история)", () => {
    render(<ITSSourcesCard payload={payload} />);
    expect(screen.queryByRole("button", { name: /Разобрать/ })).toBeNull();
  });
});
```

- [ ] **Step 2: Запустить — убедиться что падает**

Run: `./node_modules/.bin/vitest run components/cards/__tests__/ITSSourcesCard.test.tsx`
Expected: FAIL — модуль `../ITSSourcesCard` не найден.

- [ ] **Step 3: Реализовать компонент**

Create `frontend/components/cards/ITSSourcesCard.tsx`:

```tsx
"use client";

import { ExternalLink, Sparkles } from "lucide-react";
import type { ITSSource, ITSSourcesCardPayload } from "@/lib/types";
import { CardHeader } from "./CardHeader";

interface ITSSourcesCardProps {
  payload: ITSSourcesCardPayload;
  /** Клик «Разобрать статью» → follow-up к модели (fetch_its). Нет → кнопки скрыты. */
  onAnalyze?: (source: ITSSource) => void;
}

export function ITSSourcesCard({ payload, onAnalyze }: ITSSourcesCardProps) {
  const { sources, total } = payload;
  const meta = `${total} ${total === 1 ? "статья" : total < 5 ? "статьи" : "статей"}`;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden">
      <CardHeader type="its_sources" title="Источники ИТС" meta={meta} />
      <ul className="py-0.5">
        {sources.map((s, idx) => (
          <li
            key={idx}
            className="px-3 py-1.5 flex items-start gap-2 border-b border-[var(--border)] last:border-b-0"
          >
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-1.5 text-xs text-[var(--fg)] hover:text-[var(--accent)] flex-1 min-w-0"
            >
              <ExternalLink className="h-3.5 w-3.5 shrink-0 mt-0.5 text-[var(--fg-muted)]" />
              <span className="break-words">{s.title}</span>
            </a>
            {onAnalyze && s.doc_id && (
              <button
                type="button"
                onClick={() => onAnalyze(s)}
                title="Дочитать статью целиком и разобрать"
                className="shrink-0 inline-flex items-center gap-1 h-6 px-2 rounded-md border border-[var(--bd-1)] text-[11px] text-[var(--fg-3)] hover:text-[var(--fg-1)] hover:border-[var(--bd-2)] transition-colors"
              >
                <Sparkles className="h-3 w-3" />
                Разобрать
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Запустить — убедиться что зелёный**

Run: `./node_modules/.bin/vitest run components/cards/__tests__/ITSSourcesCard.test.tsx`
Expected: PASS (3 теста).

- [ ] **Step 5: Commit**

```bash
git add frontend/components/cards/ITSSourcesCard.tsx frontend/components/cards/__tests__/ITSSourcesCard.test.tsx
git commit -m "feat(its): компонент ITSSourcesCard (ссылки + кнопка «Разобрать»)"
```

---

## Task 4: Frontend — рендер карточки + проброс onAsk до send

**Files:**
- Modify: `frontend/components/cards/CardRenderer.tsx`
- Modify: `frontend/components/chat/AssistantMessage.tsx`
- Modify: `frontend/components/chat/Message.tsx`
- Modify: `frontend/components/chat/Thread.tsx`
- Modify: `frontend/app/sessions/[id]/page.tsx`

- [ ] **Step 1: `CardRenderer` — ветка its_sources**

В `frontend/components/cards/CardRenderer.tsx`:
- Импортировать компонент и тип:
```typescript
import { ITSSourcesCard } from "./ITSSourcesCard";
```
- Добавить `ITSSource` к импорту типов из `@/lib/types` (в существующей строке `import type { CardEnvelope, CardContext, ReferenceItem } from "@/lib/types";` → добавить `ITSSource`).
- Перед `case "code":` добавить:
```typescript
    case "its_sources": {
      const onAnalyze = sendMessage
        ? (s: ITSSource) =>
            sendMessage(
              `Разбери статью ИТС «${s.title}»: вызови fetch_its(id="${s.doc_id}") и дай разбор.`,
            )
        : undefined;
      return (
        <CardMountWrapper>
          <ITSSourcesCard payload={card.payload} onAnalyze={onAnalyze} />
        </CardMountWrapper>
      );
    }
```

- [ ] **Step 2: `AssistantMessage` — проп onAsk → CardRenderer.sendMessage**

В `frontend/components/chat/AssistantMessage.tsx`:
- В `AssistantMessageProps` добавить (после `onRepeat`):
```typescript
  /** Карточка ИТС → «Разобрать статью»: отправка follow-up к модели (fetch_its). */
  onAsk?: (text: string) => void;
```
- В деструктуризацию параметров добавить `onAsk`.
- Строку 177 заменить на:
```tsx
              <CardRenderer key={i} card={card} context={cardContext} sendMessage={onAsk} />
```

- [ ] **Step 3: `Message` — проброс onAsk**

В `frontend/components/chat/Message.tsx`:
- В `MessageProps` добавить:
```typescript
  /** Проброс «Разобрать статью» из карточки ИТС в send. */
  onAsk?: (text: string) => void;
```
- В сигнатуру `MessageBase` добавить `onAsk`.
- В JSX `<AssistantMessage ... onRepeat={onRepeat} />` добавить `onAsk={onAsk}`.
- В `areMessagePropsEqual` НЕ добавлять `onAsk` (как и `onRepeat` — новое замыкание каждый рендер, поведение идентично; ре-рендер истории не нужен).

- [ ] **Step 4: `Thread` — проброс onAsk**

В `frontend/components/chat/Thread.tsx`:
- В `ThreadProps` добавить:
```typescript
  /** Карточка ИТС → «Разобрать статью»: отправка нового сообщения. */
  onAsk?: (text: string) => void;
```
- В деструктуризацию `Thread({...})` добавить `onAsk`.
- В `<Message ... onRepeat={...} />` добавить `onAsk={onAsk}`.

- [ ] **Step 5: `sessions/[id]/page.tsx` — разводка onAsk → send**

В `frontend/app/sessions/[id]/page.tsx` в `<Thread>` (строка ~426) после `onRepeat={...}` добавить:
```tsx
              onAsk={(text) => {
                if (!isStreaming) void send(text);
              }}
```

- [ ] **Step 6: Тест рендера через CardRenderer**

Добавить в `frontend/components/cards/__tests__/ITSSourcesCard.test.tsx` блок:

```tsx
import { CardRenderer } from "../CardRenderer";

describe("CardRenderer · its_sources", () => {
  it("прокидывает sendMessage → onAnalyze с шаблоном fetch_its", () => {
    const sendMessage = vi.fn();
    render(
      <CardRenderer
        card={{ type: "its_sources", payload }}
        sendMessage={sendMessage}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: /Разобрать/ })[0]);
    expect(sendMessage).toHaveBeenCalledWith(
      expect.stringContaining('fetch_its(id="its-pubdevguide83-461-hdoc")'),
    );
  });
});
```

- [ ] **Step 7: Тесты + сборка**

Run: `./node_modules/.bin/vitest run components/cards/__tests__/ITSSourcesCard.test.tsx components/chat/__tests__/Message.memo.test.tsx`
Expected: PASS.
Run: `./node_modules/.bin/next build`
Expected: build OK (типы сходятся, union исчерпан).

- [ ] **Step 8: Commit**

```bash
git add frontend/components/cards/CardRenderer.tsx frontend/components/chat/AssistantMessage.tsx frontend/components/chat/Message.tsx frontend/components/chat/Thread.tsx frontend/app/sessions/[id]/page.tsx frontend/components/cards/__tests__/ITSSourcesCard.test.tsx
git commit -m "feat(its): рендер ITSSourcesCard + проброс onAsk до send (кнопка «Разобрать»→fetch_its)"
```

---

## Task 5: Backend — промпт: fetch-директива + анти-дубль

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (SYSTEM_PROMPT, buddy-строка ~294)
- Modify: `backend/tests/test_loop_system_prompt.py`

- [ ] **Step 1: Падающий тест на новый промпт**

В `backend/tests/test_loop_system_prompt.py` добавить:

```python
def test_prompt_its_fetch_top1_directive():
    from app.orchestrator.loop import SYSTEM_PROMPT
    # авто-дочитывание топ-1 статьи на knowledge-вопросах
    assert "fetch_its" in SYSTEM_PROMPT
    assert "карточк" in SYSTEM_PROMPT.lower()  # ссылки показаны карточкой
    # запрет дублировать ссылки текстом
    assert "не дублируй" in SYSTEM_PROMPT.lower() or "не повторяй ссылк" in SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Запустить — убедиться что падает**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_system_prompt.py::test_prompt_its_fetch_top1_directive --no-cov -p no:cacheprovider -q`
Expected: FAIL (нет «карточк»/«не дублируй» в промпте).

- [ ] **Step 3: Правка buddy-строки в SYSTEM_PROMPT**

В `backend/app/orchestrator/loop.py` найти строку про `buddy.search_its / buddy.fetch_its` (~294) и заменить её содержимое на:

```
• buddy.search_its / buddy.fetch_its (1С:Напарник, ЕСЛИ доступен) — ЖИВОЙ источник ИТС/методик/инструкций 1С. Для knowledge-вопросов: СНАЧАЛА buddy.search_its (один точный запрос), ЗАТЕМ buddy.fetch_its САМОЙ релевантной (первой) найденной статьи — и ответь, опираясь на оба. Ссылки на статьи ИТС НЕ дублируй текстом в ответе — они автоматически показаны пользователю карточкой «Источники ИТС»; остальные статьи он откроет/разберёт сам кнопкой. Напарник медленный (~15с/вызов): максимум 1 search_its + 1 fetch_its за ответ, не переформулируй поиск.
```

- [ ] **Step 4: Запустить — убедиться что зелёный**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_system_prompt.py --no-cov -p no:cacheprovider -q`
Expected: PASS (новый тест + существующие).

- [ ] **Step 5: Регресс loop-тестов**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_its_unavailable_block.py tests/test_loop_buddy_config.py --no-cov -p no:cacheprovider -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/orchestrator/loop.py backend/tests/test_loop_system_prompt.py
git commit -m "feat(its): промпт — fetch топ-1 статьи + не дублировать ссылки (есть карточка)"
```

---

## Task 6: Backend — консервативный трим системного промпта

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (SYSTEM_PROMPT)
- Modify: `backend/tests/test_loop_system_prompt.py`

> Трим — judgment-задача с измеримым гейтом. Цель: ≥20% сокращение БЕЗ потери поведенческих правил. Режем ТОЛЬКО объём примеров, не правила.

- [ ] **Step 1: Зафиксировать базовый размер + тест-гейт**

Замер до: `./.venv/Scripts/python.exe -c "from app.orchestrator.loop import SYSTEM_PROMPT; print(len(SYSTEM_PROMPT))"` → записать число (ожидаемо ~22600 после Task 5).

Добавить в `backend/tests/test_loop_system_prompt.py` тест-гейт (число BASELINE подставить из замера):

```python
def test_prompt_trimmed_under_budget():
    from app.orchestrator.loop import SYSTEM_PROMPT
    # Консервативный трим: ≤ 18000 символов (было ~22600). Режем примеры, не правила.
    assert len(SYSTEM_PROMPT) <= 18000
    # Ключевые ПРАВИЛА на месте (не вырезать):
    assert "НИКОГДА не отвечай по «общим знаниям»" in SYSTEM_PROMPT
    assert "СТРАТЕГИЯ ВЫБОРА ИСТОЧНИКОВ" in SYSTEM_PROMPT
    assert "meta_type" in SYSTEM_PROMPT
    assert "ТекущаяДатаСеанса" in SYSTEM_PROMPT
    assert "memory_append" in SYSTEM_PROMPT
    assert "```chart" in SYSTEM_PROMPT  # формат графика сохранён (хотя бы 1 пример)
```

- [ ] **Step 2: Запустить — убедиться что падает по размеру**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_system_prompt.py::test_prompt_trimmed_under_budget --no-cov -p no:cacheprovider -q`
Expected: FAIL — `len > 18000`.

- [ ] **Step 3: Консервативный трим — конкретные цели**

В `SYSTEM_PROMPT` сократить ТОЛЬКО объём примеров (правила/директивы не трогать):

1. **Секция «ПРИМЕРЫ ВЫБОРА TOOL (few-shot)»** (между «ПРИМЕРЫ ВЫБОРА TOOL» и «ПАМЯТЬ»): оставить по ОДНОМУ примеру Q/A на каждую рубрику (СТРУКТУРА/ВЫБОРКА/ДИАГНОСТИКА/ЗАВИСИМОСТИ/ПРАВА/ПЕРЕХОДЫ/СПРАВКА/BSL/КОГДА НЕ НУЖЕН/АНТИ-ПАТТЕРНЫ), убрать 2-й и 3-й примеры в рубриках где их несколько.
2. **Секция «ГРАФИКИ»**: оставить ОДИН пример spec (bar), убрать примеры pie и line (правила использования графиков оставить текстом).
3. **Секция «ПАМЯТЬ»**: оставить все нумерованные правила (1-6) и namespace-различие, но сократить развёрнутые Q/A-примеры до 1 короткого на правило; убрать дублирующие анти-паттерны если повторяют правило.

После каждой правки — замер: `./.venv/Scripts/python.exe -c "from app.orchestrator.loop import SYSTEM_PROMPT; print(len(SYSTEM_PROMPT))"` → добиться ≤ 18000.

- [ ] **Step 4: Запустить — гейт зелёный**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_system_prompt.py --no-cov -p no:cacheprovider -q`
Expected: PASS (размер ≤18000 И все ключевые правила на месте).

- [ ] **Step 5: Поведенческий smoke (анти-регресс) — 3 контрольных вопроса**

Поднять стек (если не поднят): `pwsh .claude/skills/awd-dev-up/scripts/up.ps1`.
Через UI/чат на живой базе задать и глазами проверить:
1. data: «сколько контрагентов в базе?» → вызов `execute_query`, без ИТС.
2. knowledge: «как правильно настроить RLS по ИТС?» → `buddy.search_its` + `buddy.fetch_its` + карточка «Источники ИТС».
3. structure: «какие документы есть в базе?» → `get_metadata(meta_type="Документ")`.
Если поведение совпадает с ожидаемым по каждому — гейт пройден. Если регресс — вернуть вырезанный фрагмент правила.

- [ ] **Step 6: Commit**

```bash
git add backend/app/orchestrator/loop.py backend/tests/test_loop_system_prompt.py
git commit -m "perf(its): консервативный трим системного промпта (~-20%+), правила сохранены"
```

---

## Task 7: Финальный smoke + замер токенов + очистка

**Files:**
- Delete: probe-скрипты (диагностика)

- [ ] **Step 1: Полный smoke ИТС-сценария на живой базе**

Стек поднят. В чате: «как правильно настроить ограничение доступа RLS?»
Проверить глазами по критериям приёмки спеки:
1. Под ответом — карточка «Источники ИТС» с кликабельными ссылками на its.1c.ru.
2. В трейсе виден вызов `buddy.fetch_its` (авто топ-1).
3. Клик «Разобрать статью» у источника с doc_id → бот делает разбор именно этой статьи (новый вызов `fetch_its`).

- [ ] **Step 2: Замер токенов (до/после трима)**

Зафиксировать в сообщении пользователю: размер SYSTEM_PROMPT до (~22600) и после (≤18000), % сокращения. Карточка ссылок = +0 LLM-токенов (парсинг уже полученного).

- [ ] **Step 3: Очистка probe-скриптов**

```bash
git rm --cached --ignore-unmatch backend/scripts/_buddy_capability_probe.py backend/scripts/_buddy_probe_out.txt backend/scripts/_its_read_probe.py backend/scripts/_its_read_out.txt 2>/dev/null
rm -f backend/scripts/_buddy_probe_out.txt backend/scripts/_its_read_out.txt
```
(probe-скрипты `.py` оставить как reusable-диагностику ИЛИ удалить по решению пользователя — out-файлы удалить в любом случае.)

- [ ] **Step 4: Полный прогон тестов**

Run (backend): `./.venv/Scripts/python.exe -m pytest tests/test_its_sources_card.py tests/test_loop_system_prompt.py tests/test_cards_advanced.py --no-cov -p no:cacheprovider -q`
Run (frontend): `./node_modules/.bin/vitest run components/cards/ components/chat/` и `./node_modules/.bin/next build`
Expected: всё зелёное.

- [ ] **Step 5: Финальный отчёт пользователю**

Что сделано (W1-W4), что проверено live, замер токенов, что НЕ верифицировано (если что-то).

---

## Self-Review (выполнено при написании)

**Покрытие спеки:** W1 (карточка) → Task 1-4; W2 (кнопка fetch) → Task 3-4; W3 (промпт fetch+анти-дубль) → Task 5; W3 (трим) → Task 6; W4 (тесты+smoke) → встроено в каждый Task + Task 7. Критерии приёмки 1-5 → Task 7 Step 1 + Task 6 Step 5. ✓

**Плейсхолдеры:** нет — весь код приведён; BASELINE для трима получается замером в Task 6 Step 1 (не плейсхолдер, а измеримая величина). ✓

**Консистентность типов:** `ITSSource{title,url,doc_id}` / `ITSSourcesCardPayload{sources,total,card_id}` одинаковы в backend (pydantic) и frontend (ts); тип карточки `"its_sources"` единый в cards.py, types.ts, CardHeader, CardRenderer; `onAsk`/`sendMessage`/`onAnalyze` — согласованная цепочка (Thread.onAsk → Message.onAsk → AssistantMessage.onAsk → CardRenderer.sendMessage → ITSSourcesCard.onAnalyze). ✓
