# Handoff Prompt — следующая сессия после NIM rebuild

> Скопируй текст из блока ниже целиком и вставь в начало новой сессии Claude Code в проекте `analyst-workspace-design`. Это самодостаточный брифинг — не нужно вспоминать предыдущую сессию.

---

## ПРОМПТ (скопировать)

```
Привет. Я работаю в проекте C:\CLOUDE_PR\projects\analyst-workspace-design (Next.js 15 + FastAPI + SQLite чат для бизнес-аналитиков 1С). В предыдущей сессии запустил NVIDIA NIM rebuild эталонных knowledge-карточек (60 192 объекта через qwen/qwen3.5-122b-a10b, скрипт backend/scripts/nvidia_nim_rebuild.py).

ТВОЯ ЗАДАЧА в этой сессии: доделать параллельный план задач M-K0/Phase 11/tech debt по файлу `.planning/PARALLEL-PLAN-2026-05-28.md`.

### Шаг 0 — Проверить статус NIM rebuild (5 минут)

Запусти watchdog:
```powershell
python -c "
import sqlite3
c = sqlite3.connect('C:/CLOUDE_PR/projects/analyst-workspace-design/data/pilot.db').cursor()
for ch in ['_bp30_138_24','_ut115_17_226','_ka2_25_92','_erp25_21_118']:
    t = c.execute('SELECT COUNT(*) FROM typical_object_cards WHERE channel_id=?', (ch,)).fetchone()[0]
    r = c.execute('SELECT COUNT(*) FROM typical_object_cards WHERE channel_id=? AND is_mock=0', (ch,)).fetchone()[0]
    print(f'{ch:25s} {r}/{t} ({100*r/t:.1f}%)')
"
```

Проверь жив ли python процесс rebuild:
```bash
tasklist | grep python.exe
```

3 варианта что увидишь:

**Вариант 1 — NIM закончил (90%+ во всех каналах)**: переходи сразу к Шагу 1 — Post-NIM commit и smoke.

**Вариант 2 — NIM ещё крутится (прогресс < 90%, процесс python работает)**: НЕ останавливай. Сразу переходи к Шагу 2 — параллельные задачи. Проверяй watchdog каждые 30 минут.

**Вариант 3 — NIM упал (процесс не работает, прогресс < 100%)**: проверь последние строки лога `C:\Users\KHVORO~1\AppData\Local\Temp\claude\...\tasks\b1b0x1jdx.output` (или поиск последнего файла с output). Если ошибка восстановимая (rate-limit, 500) — рестартуй командой:

```bash
cd C:/CLOUDE_PR/projects/analyst-workspace-design/backend
python -m scripts.nvidia_nim_rebuild --all --model qwen/qwen3.5-122b-a10b --concurrency 20 --chunk-size 50 --apply-immediately --api-key $env:NVIDIA_NIM_KEY  # ключ удалён из файла — задать через env/user_secrets
```

(скрипт идемпотентен — пропускает уже обработанные is_mock=0)

### Шаг 1 — Если NIM закончил: Post-NIM closure (1-2 часа)

1. **Smoke check** (читай `.planning/PARALLEL-PLAN-2026-05-28.md` раздел F1, если есть; иначе следуй пунктам ниже):
   - Итоговый счёт `is_mock=0` по каналам
   - Validation pass rate >95% по каждому каналу
   - 5 случайных карточек на eyeball проверку
   - Длина summary >50, purpose >80

2. **Commit M-K2.5 closure**:
```bash
cd C:/CLOUDE_PR/projects/analyst-workspace-design
git add data/pilot.db .planning/knowledge-layer-2026-05-24/phases/M-K2.5/claude-responses/response-nim-*.json
git commit -m "feat(M-K2.5.10.7): bulk real LLM rebuild ~60k carts NVIDIA NIM

4 типовые: БП 3.0 / КА 2.5 / УТ 11.5 / ERP 2.5
- is_mock=0: <число>
- Validation pass rate: <%>
- Модель: qwen/qwen3.5-122b-a10b
- Skрипт: backend/scripts/nvidia_nim_rebuild.py

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

3. **Rollback план** если карточки плохие — см. `.planning/PARALLEL-PLAN-2026-05-28.md`.

### Шаг 2 — Параллельные задачи (5-6 часов)

Все задачи описаны в `.planning/PARALLEL-PLAN-2026-05-28.md`. Иди по suggested order:

**Час 1**: A1, E1
- **A1 (20 мин)** — `.planning/STATE.md`: Wave 6 `🟡 в работе` → `✅ DONE` + примечание о коммите `f956a21` M-K0.7 (фактически M-K0 100%/28-28)
- **E1 (20 мин)** — `.claude/CLAUDE.md` секция "Текущее состояние": обновить дату snapshot на 2026-05-28, milestone статусы (M-K0 closed, M-K2.5 closed после NIM, v1.3.0 готов)

**Часы 1-2**: C1, B1
- **C1 (30 мин)** — `backend/app/orchestrator/loop.py`: `ruff check loop.py --select E501` → найти 8 длинных строк SYSTEM_PROMPT → разбить через конкатенацию `"..." "..."`. Verify: `ruff check loop.py` → 0 errors + `pytest -x` зелёный
- **B1 (30 мин)** — `frontend/components/cards/MetricCard.tsx`: добавить import CardHeader, заменить самодельный header на `<CardHeader type="metric" title={label} meta={unit ?? ""} toolName="execute_query" />`. Verify: `pnpm vitest run` зелёный + визуально через `pnpm dev` (port 3010)

**Часы 2-3**: B2, E2, E4
- **B2 (20 мин)** — Vitest тест для MetricCard CardHeader
- **E2 (15 мин)** — `ARCHITECTURE.md` строка 3 заменить устаревший "Phase 3" на "M7 Commerce Readiness + M-K2.5 Knowledge Layer"
- **E4 (15 мин)** — `.planning/ROADMAP.md` Phase 10 пометить как DEFERRED/REPLACED by Hermes Memory+Skills (M6)

**Часы 3-5**: C2 (самая долгая)
- **C2 (2 часа)** — 7 flaky tests на Windows cp1251. Найти `open(...)` без `encoding='utf-8'` в:
  - `backend/tests/test_memory.py` (3 теста markdown_store)
  - `backend/tests/test_migrations_v5.py` (FTS5 кириллица)
  - `backend/tests/test_orchestrator_loop_confirm.py` (2 теста — может быть pre-existing SSRF DNS, помечай skip с комментом если не лечится энкодингом)
  - `backend/tests/test_trajectory.py` (multimodal content)
  
  Запуск: `set PYTHONIOENCODING=utf-8 && python -X utf8 -m pytest tests/test_memory.py tests/test_trajectory.py tests/test_migrations_v5.py tests/test_orchestrator_loop_confirm.py -v`

**Часы 5-6**: E3, E5, F1 (если NIM ещё идёт)
- **E3 (30 мин)** — `.planning/BACKLOG-POST-MVP.md` добавить knowledge layer (M-K2.5+) и Hermes (M6) пункты — список в `.planning/PARALLEL-PLAN-2026-05-28.md`
- **E5 (10 мин)** — проверить существование `docs/CERT-PROCESS.md`, создать минимальный если нет
- **F1 (30 мин)** — создать `.planning/SMOKE-NIM-REBUILD.md` с smoke-проверками и rollback SQL

### Правила

- Атомарные коммиты после каждой задачи
- Не пушить в main без явного запроса
- Тесты + lint после invasive change
- `data/pilot.db` — read-only пока NIM работает (apply_immediately блокирует кратко)
- Брутальная честность: если задача провалилась — говори, не молча пивотить
- Правило 3 итераций: за 3 раунда без прогресса — стоп

### Контекст из CLAUDE.md проекта

- Стек: Next.js 15 + React 19 + shadcn/ui + Tailwind 4 (frontend, port 3010), FastAPI + Pydantic v2 + aiosqlite (backend, port 8010)
- Темная тема default, русский UI, Plex Sans + Plex Mono шрифты, accent #FF6A3D (Signal orange brand Stencil)
- Workflow: NL → LLM → tool_calls → результат → inline cards. MCP — это всё.
- Текущая ветка: `feature/m-k2.5-pilot-ka2`
- Git: HTTPS+PAT, repo `analyst-workspace-design` (не часть Cloude_PR)

Поехали с Шага 0.
```

---

## Где этот файл

`C:\CLOUDE_PR\projects\analyst-workspace-design\.planning\HANDOFF-PROMPT-NEXT-SESSION.md`

## Использование

1. Эта сессия завершается (NIM крутится в фоне)
2. Новая сессия начинается — скопируй блок промпта выше как первое сообщение
3. Claude сам проверит NIM watchdog и пойдёт по плану

## Что важно

- Промпт самодостаточный — не зависит от памяти этой сессии
- Учитывает 3 сценария NIM (закончил / идёт / упал) с конкретной командой restart
- Содержит api-key NIM (если пользователь захочет вынести — заменить на $env:NVIDIA_NIM_KEY)
- Все ссылки на детальный план — `.planning/PARALLEL-PLAN-2026-05-28.md`
