# Hermes Agent Research · 2026-05-20

Эта папка содержит **полный анализ NousResearch/hermes-agent** и
**implementation plan для интеграции 75 фич в наш проект**.

## Файлы

- **`HERMES-IMPLEMENTATION-PLAN.md`** — главный документ (~30 000 слов).
  Полный каталог фич, матрица приоритизации, 5-спринтовый план реализации
  с конкретным кодом для каждого спринта.

## Как пользоваться

### Если ты Claude, попавший в новую сессию

1. **Прочитай `HERMES-IMPLEMENTATION-PLAN.md` целиком** (~10 минут чтения).
2. Посмотри **таблицу статусов в самом конце документа** — где остановились.
3. Возьми следующий незавершённый спринт.
4. **НЕ ЗАБЕГАЙ ВПЕРЁД** — спринты идут последовательно.
5. После завершения спринта — обнови таблицу статусов + добавь запись в раздел 9.

### Если ты пользователь

Скажи Claude: «Начинай Sprint N из плана `.planning/research/hermes-2026-05-20/HERMES-IMPLEMENTATION-PLAN.md`».
Или: «Продолжай Hermes-план с того места где остановились».

## Спринты (выжимка)

| # | Тема | Длительность | Главное |
|---|---|---|---|
| 1 | Memory Foundation | 1.5 нед | MEMORY.md + USER.md, MemoryManager, aux client, trajectory log |
| 2 | Context & Resilience | 1.5 нед | ContextCompressor, ErrorClassifier, sanitization, interrupt |
| 3 | Self-Learning Loop | 2 нед | Background review, Curator, todo list, skill provenance |
| 4 | UX & Interactivity | 1 нед | Clarify dialog, injection scan, /insights, FTS5 search |
| 5 | Polish & Observability | 1 нед | Prompt caching, tool storage, usage pricing |

**Итого: ~7 недель работы → новое качественное состояние приложения.**

## Что НЕ берём (зафиксировано)

- 16 LLM adapters
- 5 messenger gateways
- 7 terminal backends
- Browser / computer use / image generation
- Voice tools
- Cron jobs

См. раздел 3 главного документа.
