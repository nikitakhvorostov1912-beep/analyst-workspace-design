# ИТС: ask_1c_ai основной + компактная карточка — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Для knowledge-вопросов отвечать через `ask_1c_ai(configuration)` (чистый конфа-ответ), источники подтягивать `search_its` и показывать компактно (топ-3 + свёртка), `fetch_its` — только on-demand.

**Architecture:** Промпт делает `ask_1c_ai` основным для методики; `_inject_buddy_configuration` гарантирует передачу конфы и в `ask_1c_ai`; `cards.py` сортирует источники (платформа/методология вперёд); `ITSSourcesCard` показывает 3 + «показать ещё N».

**Tech Stack:** Python 3.12 / FastAPI / pydantic (backend), Next.js 15 / React 19 / Vitest (frontend).

**Спека:** `docs/superpowers/specs/2026-06-07-its-ask-primary-design.md`

**Команды:** backend `./.venv/Scripts/python.exe -m pytest <files> --no-cov -p no:cacheprovider -q` (из `backend/`); frontend `./node_modules/.bin/vitest run <files>` (из `frontend/`).

**git add — только перечисленные файлы.** Каждый git-вызов делать из корня проекта (`cd /c/CLOUDE_PR/projects/analyst-workspace-design`) — cwd нестабилен.

---

## File Structure

| Файл | Действие |
|---|---|
| `backend/app/orchestrator/loop.py` | `_inject_buddy_configuration` + ask_1c_ai (Task 1); SYSTEM_PROMPT buddy-блок (Task 3) |
| `backend/tests/test_loop_buddy_config.py` | тест инъекции конфы в ask_1c_ai (Task 1) |
| `backend/app/orchestrator/cards.py` | сортировка источников платформа-вперёд (Task 2) |
| `backend/tests/test_its_sources_card.py` | тест сортировки (Task 2) |
| `backend/tests/test_loop_system_prompt.py` | тест ask_1c_ai-директивы (Task 3) |
| `frontend/components/cards/ITSSourcesCard.tsx` | свёртка 3 + «показать ещё» (Task 4) |
| `frontend/components/cards/__tests__/ITSSourcesCard.test.tsx` | тест свёртки (Task 4) |

---

## Task 1: Гарантия конфы в ask_1c_ai

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (`_inject_buddy_configuration`)
- Test: `backend/tests/test_loop_buddy_config.py`

- [ ] **Step 1: Падающий тест**

Добавить в `backend/tests/test_loop_buddy_config.py`:

```python
def test_inject_config_into_ask_1c_ai():
    from app.orchestrator.channel_config import ChannelTypicalContext
    from app.orchestrator.loop import _inject_buddy_configuration
    ctx = ChannelTypicalContext(
        display_name="КА 2.5", typical_channel_id="_ka2_25_92",
        typical_display_name="Комплексная автоматизация 2.5",
        buddy_config_name="Комплексная автоматизация", source="auto",
    )
    args = _inject_buddy_configuration("buddy.ask_1c_ai", {"question": "Как настроить RLS?"}, ctx)
    assert args["configuration"] == "Комплексная автоматизация"
    # явно переданное не перетираем
    args2 = _inject_buddy_configuration(
        "buddy.ask_1c_ai", {"question": "x", "configuration": "ERP"}, ctx
    )
    assert args2["configuration"] == "ERP"
```

- [ ] **Step 2: Запустить — упадёт**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_buddy_config.py::test_inject_config_into_ask_1c_ai --no-cov -p no:cacheprovider -q`
Expected: FAIL (configuration не подставился — ask_1c_ai не в списке).

- [ ] **Step 3: Реализация**

В `backend/app/orchestrator/loop.py` в `_inject_buddy_configuration` заменить строку проверки имени:

```python
    if tool_name not in ("buddy.search_its", "buddy.fetch_its"):
        return tool_args
```
на:
```python
    if tool_name not in ("buddy.search_its", "buddy.fetch_its", "buddy.ask_1c_ai"):
        return tool_args
```

- [ ] **Step 4: Запустить — зелёный**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_buddy_config.py --no-cov -p no:cacheprovider -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /c/CLOUDE_PR/projects/analyst-workspace-design
git add backend/app/orchestrator/loop.py backend/tests/test_loop_buddy_config.py
git commit -m "feat(its): подставлять configuration и в buddy.ask_1c_ai"
```

---

## Task 2: Сортировка источников — платформа/методология вперёд

**Files:**
- Modify: `backend/app/orchestrator/cards.py` (`_build_its_sources_card` + helper)
- Test: `backend/tests/test_its_sources_card.py`

- [ ] **Step 1: Падающий тест**

Добавить в `backend/tests/test_its_sources_card.py`:

```python
def test_platform_sources_sorted_first():
    # Шум-конфа идёт ПЕРВОЙ в выдаче, но платформа/методология должна всплыть выше.
    text = (
        "[Фотоуслуги](https://its.1c.ru/db/fotosuv#content:410:hdoc)\n"
        "[Практическое пособие разработчика](https://its.1c.ru/db/pubdevguide83#content:461:hdoc)\n"
        "[ЖКХ](https://its.1c.ru/db/uukgkx303#content:1:hdoc)\n"
        "[БСП 3.2.1](https://its.1c.ru/db/bsp321doc#content:4:hdoc)\n"
    )
    card = build_card_from_tool_result("buddy.search_its", {}, _mcp_result(text))
    assert card is not None
    dbs = [s["url"].split("/db/")[1].split("#")[0] for s in card["payload"]["sources"]]
    # платформа/методология (pubdevguide83, bsp321doc) — выше шума (fotosuv, uukgkx303)
    assert dbs.index("pubdevguide83") < dbs.index("fotosuv")
    assert dbs.index("bsp321doc") < dbs.index("uukgkx303")
```

- [ ] **Step 2: Запустить — упадёт**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_its_sources_card.py::test_platform_sources_sorted_first --no-cov -p no:cacheprovider -q`
Expected: FAIL (порядок не меняется — fotosuv остаётся первым).

- [ ] **Step 3: Реализация**

В `backend/app/orchestrator/cards.py` после `_ITS_ANCHOR_RE` (рядом с `_its_doc_id_from_url`) добавить:

```python
# Платформа/методология ИТС — универсально-авторитетные источники, всплывают выше.
_ITS_PLATFORM_STEMS = ("pubdevguide", "pubprof", "bsp", "v8std", "dev")
_ITS_PLATFORM_EXACT = frozenset({"answers1c"})


def _its_relevance(url: str) -> int:
    """0 — платформа/методология (выше), 1 — прочее (ниже). Меньше = выше."""
    m = re.search(r"its\.1c\.ru/db/([^#/?\s]+)", url or "")
    db = (m.group(1) if m else "").lower()
    if db in _ITS_PLATFORM_EXACT or db.startswith(_ITS_PLATFORM_STEMS):
        return 0
    return 1
```

В `_build_its_sources_card` ПЕРЕД построением payload (после цикла парсинга, перед `payload = ITSSourcesCardPayload(...)`) добавить стабильную сортировку:

```python
    # Стабильная сортировка: платформа/методология вперёд, прочие — в порядке выдачи.
    sources.sort(key=lambda s: _its_relevance(s.url))
```

Сортировка делает `test_card_built_from_search_its` (прошлый цикл) order-зависимым — заменить в нём жёсткие `sources[0/1/2]` на проверку по url:

old:
```python
    assert sources[0]["url"] == "https://its.1c.ru/db/molmoderpka25#content:711:hdoc"
    assert sources[0]["doc_id"] == "its-molmoderpka25-711-hdoc"
    assert sources[1]["doc_id"] == "its-pubdevguide83-461-hdoc"
    assert sources[2]["doc_id"] is None  # без якоря — кнопки не будет
```
new:
```python
    by_url = {s["url"]: s["doc_id"] for s in sources}
    assert by_url["https://its.1c.ru/db/molmoderpka25#content:711:hdoc"] == "its-molmoderpka25-711-hdoc"
    assert by_url["https://its.1c.ru/db/pubdevguide83#content:461:hdoc"] == "its-pubdevguide83-461-hdoc"
    assert by_url["https://its.1c.ru/db/bsp321doc"] is None  # без якоря — кнопки не будет
```

- [ ] **Step 4: Запустить — зелёный**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_its_sources_card.py --no-cov -p no:cacheprovider -q`
Expected: PASS (новый тест + прежние 6).

- [ ] **Step 5: Commit**

```bash
cd /c/CLOUDE_PR/projects/analyst-workspace-design
git add backend/app/orchestrator/cards.py backend/tests/test_its_sources_card.py
git commit -m "feat(its): источники — платформа/методология вперёд (config-agnostic ранжир)"
```

---

## Task 3: Промпт — ask_1c_ai основной для knowledge

**Files:**
- Modify: `backend/app/orchestrator/loop.py` (SYSTEM_PROMPT, buddy-строка)
- Test: `backend/tests/test_loop_system_prompt.py`

- [ ] **Step 1: Падающий тест**

Добавить в `backend/tests/test_loop_system_prompt.py`:

```python
def test_prompt_ask_1c_ai_primary_for_knowledge():
    from app.orchestrator.loop import SYSTEM_PROMPT
    assert "ask_1c_ai" in SYSTEM_PROMPT
    # ask_1c_ai заявлен основным/приоритетным для методики
    assert "ОСНОВНОЙ" in SYSTEM_PROMPT or "основной инструмент" in SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Запустить — упадёт**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_system_prompt.py::test_prompt_ask_1c_ai_primary_for_knowledge --no-cov -p no:cacheprovider -q`
Expected: FAIL (нет ask_1c_ai в промпте).

- [ ] **Step 3: Реализация**

В `backend/app/orchestrator/loop.py` заменить строку 294 (buddy-блок) целиком:

old:
```
• buddy.search_its / buddy.fetch_its (1С:Напарник, ЕСЛИ доступен) — ЖИВОЙ источник ИТС/методик/инструкций 1С. Для knowledge-вопросов: СНАЧАЛА buddy.search_its (один точный запрос), ЗАТЕМ buddy.fetch_its САМОЙ релевантной (первой) найденной статьи — и ответь, опираясь на оба. Ссылки на статьи ИТС НЕ дублируй текстом в ответе — они автоматически показаны пользователю карточкой «Источники ИТС»; остальные статьи он откроет/разберёт сам кнопкой. Напарник медленный (~15с/вызов): максимум 1 search_its + 1 fetch_its за ответ, не переформулируй поиск.
```
new:
```
• buddy.ask_1c_ai / buddy.search_its / buddy.fetch_its (1С:Напарник, ЕСЛИ доступен) — ЖИВОЙ источник ИТС/методик 1С. Для knowledge-вопросов («как настроить», «как правильно», «что такое», методика) ОСНОВНОЙ инструмент — buddy.ask_1c_ai(configuration=<конфа базы>, question=…): он даёт чистый ответ ПОД КОНКРЕТНУЮ конфигурацию (без чужих конфигураций в тексте). ДОПОЛНИТЕЛЬНО вызови один раз buddy.search_its(configuration=…) — проверяемые источники покажет карточка «Источники ИТС». НЕ вызывай buddy.fetch_its по умолчанию — только когда пользователь просит разбор конкретной статьи. Ссылки ИТС в тексте не дублируй — они в карточке. Напарник медленный (~15с/вызов): ask_1c_ai + один search_its за ответ, не переформулируй.
```

- [ ] **Step 4: Запустить — зелёный (+ гейт трима не сломан)**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_loop_system_prompt.py --no-cov -p no:cacheprovider -q`
Expected: PASS (новый тест + прежние, включая `test_prompt_trimmed_under_budget` ≤18000 и `test_prompt_its_fetch_top1_directive` — «fetch_its»/«карточк»/«не дублируй» всё ещё в тексте).

- [ ] **Step 5: Commit**

```bash
cd /c/CLOUDE_PR/projects/analyst-workspace-design
git add backend/app/orchestrator/loop.py backend/tests/test_loop_system_prompt.py
git commit -m "feat(its): промпт — ask_1c_ai основной для knowledge, search_its для источников, fetch on-demand"
```

---

## Task 4: Компактная карточка — 3 + «показать ещё N»

**Files:**
- Modify: `frontend/components/cards/ITSSourcesCard.tsx`
- Test: `frontend/components/cards/__tests__/ITSSourcesCard.test.tsx`

- [ ] **Step 1: Падающий тест**

Добавить в `frontend/components/cards/__tests__/ITSSourcesCard.test.tsx` (в describe «ITSSourcesCard»):

```tsx
const fivePayload: ITSSourcesCardPayload = {
  total: 5,
  sources: [1, 2, 3, 4, 5].map((n) => ({
    title: `Статья ${n}`,
    url: `https://its.1c.ru/db/x${n}#content:${n}:hdoc`,
    doc_id: `its-x${n}-${n}-hdoc`,
  })),
};

it("показывает 3 источника + кнопку «показать ещё N»", () => {
  render(<ITSSourcesCard payload={fivePayload} />);
  expect(screen.getAllByRole("link")).toHaveLength(3);
  fireEvent.click(screen.getByRole("button", { name: /показать ещё 2/ }));
  expect(screen.getAllByRole("link")).toHaveLength(5);
});

it("при ≤3 источниках кнопки свёртки нет", () => {
  render(<ITSSourcesCard payload={payload} />); // payload = 2 источника
  expect(screen.queryByRole("button", { name: /показать ещё/ })).toBeNull();
});
```

- [ ] **Step 2: Запустить — упадёт**

Run: `./node_modules/.bin/vitest run components/cards/__tests__/ITSSourcesCard.test.tsx`
Expected: FAIL (рендерятся все 5 ссылок, кнопки «показать ещё» нет).

- [ ] **Step 3: Реализация**

Заменить `frontend/components/cards/ITSSourcesCard.tsx` целиком:

```tsx
"use client";

import { useState } from "react";
import { ChevronDown, ExternalLink, Sparkles } from "lucide-react";
import type { ITSSource, ITSSourcesCardPayload } from "@/lib/types";
import { CardHeader } from "./CardHeader";

const COLLAPSED_COUNT = 3;

interface ITSSourcesCardProps {
  payload: ITSSourcesCardPayload;
  /** Клик «Разобрать статью» → follow-up к модели (fetch_its). Нет → кнопки скрыты. */
  onAnalyze?: (source: ITSSource) => void;
}

export function ITSSourcesCard({ payload, onAnalyze }: ITSSourcesCardProps) {
  const { sources, total } = payload;
  const [expanded, setExpanded] = useState(false);
  const meta = `${total} ${total === 1 ? "статья" : total < 5 ? "статьи" : "статей"}`;
  const visible = expanded ? sources : sources.slice(0, COLLAPSED_COUNT);
  const hidden = sources.length - visible.length;

  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)] overflow-hidden">
      <CardHeader type="its_sources" title="Источники ИТС" meta={meta} />
      <ul className="py-0.5">
        {visible.map((s, idx) => (
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
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="w-full flex items-center justify-center gap-1 px-3 py-1.5 text-[11px] text-[var(--accent)] hover:bg-[var(--bg-surface)] border-t border-[var(--border)]"
        >
          <ChevronDown className="h-3 w-3" />
          показать ещё {hidden}
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Запустить — зелёный**

Run: `./node_modules/.bin/vitest run components/cards/__tests__/ITSSourcesCard.test.tsx`
Expected: PASS (новые 2 теста + прежние 4 — рендер ссылок / кнопка «Разобрать» / без onAnalyze / CardRenderer).

- [ ] **Step 5: Commit**

```bash
cd /c/CLOUDE_PR/projects/analyst-workspace-design
git add frontend/components/cards/ITSSourcesCard.tsx frontend/components/cards/__tests__/ITSSourcesCard.test.tsx
git commit -m "feat(its): компактная карточка — 3 источника + «показать ещё N»"
```

---

## Task 5: Smoke + финальная верификация

- [ ] **Step 1: Перезапуск стека**

Run: `pwsh -NoProfile -ExecutionPolicy Bypass -File C:\CLOUDE_PR\projects\analyst-workspace-design\.claude\skills\awd-dev-up\scripts\up.ps1`
Expected: оба PASS (backend подхватит loop.py/cards.py).

- [ ] **Step 2: Live knowledge-вопрос**

В чате (КА 2.5): «как правильно настроить ограничение доступа RLS?». Проверить глазами:
1. В трейсе — `buddy.ask_1c_ai` (а не только search_its); конфа передана.
2. Ответ — КА-специфичный, без Фотоуслуг/ЖКХ в тексте.
3. Карточка «Источники ИТС»: 3 развёрнуты (платформа/методология сверху), «показать ещё N» раскрывает остальные.

- [ ] **Step 3: Live data-вопрос (анти-регресс)**

«сколько контрагентов в базе?» → `execute_query`, без ИТС.

- [ ] **Step 4: Полный прогон тестов**

Run (backend): `./.venv/Scripts/python.exe -m pytest tests/test_its_sources_card.py tests/test_loop_system_prompt.py tests/test_loop_buddy_config.py --no-cov -p no:cacheprovider -q`
Run (frontend): `./node_modules/.bin/vitest run components/cards/`
Expected: всё зелёное.

- [ ] **Step 5: Отчёт пользователю** — что сделано, live-проверка, замеры.

---

## Self-Review

**Покрытие спеки:** W1 промпт → Task 3; W2 инъекция конфы → Task 1; W3 сортировка → Task 2; W4 свёртка → Task 4; W5 тесты+smoke → встроено + Task 5. Критерии 1-6 → Task 5 + per-task тесты. ✓

**Плейсхолдеры:** нет — весь код приведён. ✓

**Консистентность:** `_its_relevance`/`_ITS_PLATFORM_STEMS` (Task 2) согласованы; `COLLAPSED_COUNT=3` (Task 4); имена инструментов `buddy.ask_1c_ai`/`buddy.search_its`/`buddy.fetch_its` едины в Task 1/3; тип `its_sources` уже существует (прошлый цикл). Сортировка (Task 2) не ломает прошлые тесты карточки (порядок в `_SEARCH_ITS_TEXT`: molmoderpka25, pubdevguide83, bsp321doc — после сортировки pubdevguide83+bsp321doc всплывут выше molmoderpka25; тест `test_card_built_from_search_its` проверяет `sources[0].url`==molmoderpka25 — ВНИМАНИЕ: сломается!). → В Task 2 Step 3 также обновить `test_card_built_from_search_its`: проверять наличие источников и doc_id без жёсткой привязки к порядку (заменить `sources[0]`/`sources[1]` на поиск по url в списке).
