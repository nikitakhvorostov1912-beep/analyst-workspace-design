# Индикатор хода запроса: свёрнутый + красивая анимация — Design

**Status:** approved
**Date:** 2026-06-06
**Branch:** feature/m-k3-relational-cfe

## Problem

Во время запроса в чате пользователь не понимает, идёт ли процесс и закончился ли. Инфраструктура стриминга в проекте богатая (`StreamingStages`: «Анализирую → Вызываю → Формирую»), но три дыры:

- **G1 — мёртвая зона.** `buildStreamingStages` возвращает `null` при `streamingStage === null` (streaming-stages.ts:49), а `streamingStage` = `null` от `send()` до первого SSE-`status`. Между «отправил» и первым статусом — пустой пузырь «Аналитик · 18:50», ничего не анимируется. Единственный признак — Send→⏹ внизу (легко не заметить).
- **G2 — слабый сигнал ошибки.** Падение на транспорте (на этой машине — MiMo SSL / Kaspersky) уходит в `catch` хука → крошечная строка `text-xs` у композера (page.tsx:438), **не в пузыре**. Легко пропустить → «завис или нет».
- **G3 — нечёткое «готово».** Завершение = шаги исчезли + появился текст + длительность в шапке (если >0). Явного маркера «готово»/«ошибка» в пузыре нет.

Среда (MiMo SSL) роняет запрос ровно в незаметный путь, поэтому G1+G2 максимально видны. SSL вне объёма — но состояние «в работе» делаем очевидным, а падение — громким.

## Goal

Спокойный по умолчанию, но **всегда понятный** индикатор состояния запроса: видно, что идёт; видно прогресс по желанию; однозначно видно «готово» и «ошибка». Появляется мгновенно по нажатию, не зависит от тайминга бэкенда.

## Design (утверждён пользователем)

### Поведение
- Индикатор завязан на **`isStreaming`** (true сразу по `send()`), а не на первый SSE-`status` → нет мёртвой зоны (G1).
- По умолчанию **свёрнут**: одна строка — анимация + текущий этап + таймер.
- Шеврон **«⌄ шаги»** разворачивает подробный конвейер — переиспользуется существующий `StreamingStages` (не переписываем).
- Свёрнуто/развёрнуто **запоминается** в localStorage (default — свёрнуто).

### Анимация «пока идёт» (в рамках брендовых запретов)
- **Аватар-глиф «А»** (`BrandMark`) — мягкое пульсирующее кольцо во время стрима (keyframe `status-pulse`, уже есть).
- Свёрнутая строка: **три дышащие точки** в `--accent` (keyframe `blink`, со стаггером) + морфящийся текст этапа («Анализирую…») + **живой таймер** «3.2с» (тик ~0.5с).
- Запреты бренда соблюдаются: **без** glow / gradient-text / glass / shadow; только `--accent` + существующие keyframes (`status-pulse`, `blink`, `fade-up`). Новые keyframes не вводим.

### Терминальные состояния
- **Готово (G3):** индикатор исчезает; под ответом тонкое «готово за 4.1с» (из `message.duration_ms`). Однозначное завершение.
- **Ошибка (G2):** ошибка транспорта из `catch` пишется **в пузырь** (`message.error`) как заметный inline-`Alert` с кнопкой **«Повторить»** (повтор последнего вопроса), а не строкой у композера.

## Architecture / Components

| Юнит | Ответственность | Зависимости |
|------|-----------------|-------------|
| `components/chat/StreamProgress.tsx` *(new)* | Свёрнутая строка-индикатор (точки + лейбл + таймер + шеврон). Развёрнутый режим рендерит `StreamingStages`. Владеет интервалом таймера от `startedAt`. | `StreamingStages`, storage-pref |
| `components/chat/StreamingStages.tsx` | Без изменений — детальный конвейер для развёрнутого режима. | — |
| `lib/streaming-stages.ts` | `buildStreamingStages` получает флаг `running`: при `running && streamingStage===null` возвращает seed `[{analyzing}]` (а не `null`) — чтобы развёрнутый режим показывал «Анализирую…» сразу. | — |
| `components/chat/useChatStream.ts` | Экспортировать `streamStartedAt: number \| null`; в `catch`-ветке писать ошибку в `message.error` (в дополнение к `error`). | — |
| `components/chat/AssistantMessage.tsx` | Принять реальный `isStreaming` (проп, не `Boolean(streamingStage)`) + `streamStartedAt`. Рендерить `StreamProgress` пока `isStreaming`. «готово за Xс». `Alert` ошибки + «Повторить». | `StreamProgress` |
| `components/chat/Thread.tsx`, `Message.tsx` | Пробросить `isStreaming`/`streamStartedAt` в последний assistant. | — |
| `lib/storage.ts` | `getStreamStepsExpanded()/setStreamStepsExpanded(bool)`, ключ `analyst.stream_steps_expanded`, default `false`. | — |

### Data flow
```
send() → isStreaming=true, streamStartedAt=now (мгновенно)
   → AssistantMessage(последний).isStreaming=true → StreamProgress (свёрнут, точки+таймер) появляется СРАЗУ
SSE status/tool_call/tool_result → streamingStage/tool_calls → StreamProgress (развёрнут) показывает шаги
done → isStreaming=false, duration_ms → «готово за Xс», индикатор скрыт
error (SSE structured) → message.error → inline Alert
error (catch транспорт/SSL) → message.error (НОВОЕ) → inline Alert + «Повторить»
```

### Error handling
- Структурные SSE-ошибки — как сейчас (MCP→banner, LLM→toast+inline).
- Транспорт/SSL (`catch`) — **новое**: пишем `message.error` на последний assistant → громкий inline-`Alert` в пузыре. Маленькая `error`-строка у композера остаётся как было (дубликат-страховка, не убираем).

## Testing (Vitest)
- `StreamProgress`: свёрнут по умолчанию; тоггл свёрнуто↔развёрнуто; персист в storage (mock); таймер тикает (fake timers); развёрнутый рендерит `StreamingStages`.
- `buildStreamingStages`: `running && stage===null` → seed `[{analyzing}]`, activeIndex 0 (новый кейс); существующие кейсы не ломаются.
- `useChatStream`: `streamStartedAt` ставится на send, сбрасывается на done; `catch` пишет `message.error`.
- `AssistantMessage`: `isStreaming=true` → `StreamProgress` виден сразу (без `streamingStage`); `duration_ms>0 && !isStreaming` → «готово за Xс»; `message.error` → `Alert` + «Повторить».

## Out of scope (YAGNI)
- Глобальная полоса прогресса вверху экрана (пользователь выбрал индикатор в пузыре).
- Новые CSS keyframes сверх существующих.
- Скелетоны текста ответа.
- Починка MiMo SSL (среда, не код).

## Risks
- Таймер на `setInterval` в каждом стриме — чистить на unmount/done (иначе утечка). Покрыто тестом fake timers.
- Не сломать существующие тесты `StreamingStages`/`AssistantMessage` (компонент Stages не трогаем; AssistantMessage меняет источник `isStreaming`).
