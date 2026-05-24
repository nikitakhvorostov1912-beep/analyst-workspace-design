# Release v1.4.5 — checklist на 2 дня

> Создан 2026-05-24 после фиксации 5 решений пользователя.
> Цель: выпустить v1.4.5 (unsigned) с GitHub Release + tag, закрыть M7 partial.
> Бюджет: ~6 часов работы день 1, отдельная фокус-сессия TD-1 день 3-5.

---

## ДЕНЬ 1 — Закрыть 3 finding + smoke + release (~6 часов)

### Block A — Closing OPEN findings (~2 часа)

#### A1. FINDING-00 / FINDING-06 — backend version desync (1 час) · P1

**Проблема:** `GET /health` → `{"version":"1.3.0"}`, в `desktop/package.json` → `1.4.5`. Карточка `/status` показывает «Серверная часть v1.3.0».

**Корень:** backend читает версию из своего `pyproject.toml` / `version.py`, не синкается с desktop при bundling.

**Fix (выбрать один из двух подходов):**

Вариант A (минимальный — в build-bundle.js):
```javascript
// desktop/scripts/build-bundle.js — после копирования backend
const desktopPkg = require('../package.json');
const pyprojectPath = path.join(BACKEND_DEST, 'pyproject.toml');
let pyproject = fs.readFileSync(pyprojectPath, 'utf-8');
pyproject = pyproject.replace(
  /^version = "[^"]+"/m,
  `version = "${desktopPkg.version}"`
);
fs.writeFileSync(pyprojectPath, pyproject);
```

Вариант B (более robust — backend читает sibling package.json):
```python
# backend/app/version.py
from pathlib import Path
import json

def get_version() -> str:
    desktop_pkg = Path(__file__).resolve().parent.parent.parent / "desktop" / "package.json"
    if desktop_pkg.exists():
        return json.loads(desktop_pkg.read_text())["version"]
    return "0.0.0-dev"
```

**Тест:** `curl http://localhost:8010/health` → `{"version":"1.4.5"}`

**Acceptance:** карточка `/status` показывает «Серверная часть v1.4.5».

---

#### A2. FINDING-05 — Status card model id вместо label (30 мин) · P2

**Проблема:** Status card отображает `deepseek-ai/deepsee…` (обрезанный raw id), нужно «DeepSeek V4 Flash».

**Корень:** `frontend/app/status/page.tsx` функция `aggregateLlm` использует `llm.summary` regex вместо `resolveProviderAndModel`.

**Fix:**
```typescript
// frontend/app/status/page.tsx
function aggregateLlm(llm: LlmStatus) {
  const resolved = resolveProviderAndModel(llm.model_id);
  const label = resolved?.model.label ?? llm.model_id;
  // ... остальное
}
```

**Тест:** Status → карточка «Модель ИИ» → видно «DeepSeek V4 Flash · 0.3».

---

#### A3. FINDING-14 NVIDIA NIM — закрыть как resolved (5 мин)

**Действие:** пометить в `qa-prod-release-2026-05-24/FINDINGS.md`:
```
**Статус:** ✅ RESOLVED (2026-05-24, подтверждено пользователем — embedded key работает).
```

Не требует кода. Просто документация.

---

### Block B — Quality gate (~30 мин)

```bash
cd backend
ruff check app/orchestrator/loop.py        # должно остаться 8 E501 (TD-5)
python -m pytest -q                         # 847+/847+ зелёных

cd ../frontend
npx tsc --noEmit                            # 0 errors
pnpm test                                   # 323+/323+ зелёных
pnpm build                                  # clean
```

**Acceptance:** все 4 проверки PASS, никаких регрессий от A1/A2 fixes.

---

### Block C — Manual smoke v1.4.5 (~2 часа)

Использовать `.planning/SMOKE-v1.3.0.md` как baseline (9 секций), переименовать checklist под v1.4.5:

```bash
cp .planning/SMOKE-v1.3.0.md .planning/SMOKE-v1.4.5.md
# отредактировать заголовок и обновить evidence-секции с актуальной версией
```

**Минимальный набор smoke-проверок:**

1. ✅ Установка `analyst-setup-v1.4.5.exe` на чистый Win10/Win11 (без подписи — должна сработать с SmartScreen warning «Подробнее → Выполнить»)
2. ✅ Backend стартует, `/health` → `1.4.5`
3. ✅ Frontend открывается на `localhost:3010`, нет console.error
4. ✅ Onboarding 4-step проходит до конца
5. ✅ NVIDIA NIM key из installer работает (FINDING-14 verify)
6. ✅ Главная — Composer отправляет «Расскажи про базу» → SSE → TableCard
7. ✅ ModelBadge popover — переключение модели работает (FINDING-10/11 verify)
8. ✅ Status card — версия `1.4.5`, модель `DeepSeek V4 Flash` (A1/A2 verify)
9. ✅ Memory editor `/settings/memory` — открывается, сохраняет MEMORY.md
10. ✅ Skills `/settings/skills` — отображает список, archive/unarchive работает
11. ✅ `/insights` — показывает 6 KPI cards
12. ✅ Stop button в Composer — прерывает SSE stream
13. ✅ java.exe не открывает консольное окно при чате (FINDING-17 verify)
14. ✅ Анонимизация toggle — amber pill горит, реальные данные не утекают

**Acceptance:** Все 14 пунктов PASS. Любой FAIL → исправить и пересобрать installer до перехода к Block D.

---

### Block D — Tag + GitHub Release (~30 мин)

```bash
# 1. Commit любые незакоммиченные фиксы из Block A
git add backend/app/version.py frontend/app/status/page.tsx desktop/scripts/build-bundle.js
git commit -m "fix(v1.4.5): backend version desync + status model label (FINDING-00/05/06)"

# 2. Tag (один прыжок с v1.2.2 на v1.4.5)
git tag -a v1.4.5 -m "v1.4.5 — first commerce-ready release (M7 partial close)"
git push origin v1.4.5

# 3. Опубликовать GitHub Release (на основе RELEASE-NOTES-v1.4.5.md ниже)
gh release create v1.4.5 \
  --title "v1.4.5 — Commerce-Ready Release" \
  --notes-file .planning/RELEASE-NOTES-v1.4.5.md \
  ./1C-Analyst-v1.4.5/analyst-setup-v1.4.5.exe
```

**Если нужен новый installer с фиксами из Block A** — пересобрать:
```bash
cd desktop
pnpm run build         # frontend
node scripts/build-bundle.js    # backend bundle
pnpm run dist          # electron-builder
# результат: 1C-Analyst-v1.4.5/analyst-setup-v1.4.5.exe
```

---

### Block E — STATE.md M7 partial close (~30 мин)

Обновить `.planning/STATE.md`:

```yaml
---
gsd_state_version: 1.0
milestone: M7
milestone_name: "Commerce Readiness — Security + Stability + Distribution"
status: partial_done  # ← было in_progress
last_updated: "2026-05-24T22:00:00Z"
progress:
  wave_1_critical: 9
  wave_1_done: 9         # ✅ полностью
  wave_2_total: 14
  wave_2_done: 1         # продолжается
  # ...
  commerce_plan:
    phase_4_done: 5      # ✅ release выпущен
note: "v1.4.5 released 2026-05-24. M7 partial close: Wave 1 + Commerce Plan Phase 1-4 done. Wave 2/3 + TD-1 переносятся в M8."
---
```

Открыть M8 секцию:
```markdown
## Milestone M8 — Pilot Stabilization (2026-05-25 → ?)

**Goal:** первый платный пилот + closing of TD-1 / Wave 2-3.

### Wave A — Pre-pilot polish (this week)
- [ ] TD-1 decompose loop.py phase 2/3 (6-10h, отдельная сессия без UI)
- [ ] Wave 3 medium polish — A11y audit, lazy load
- [ ] Релиз v1.4.6 если найдутся critical в пилоте

### Wave B — First pilot (June)
- [ ] Контракт с первым кандидатом (15-30K ₽/мес символический)
- [ ] Установка на их машины + onboarding session
- [ ] Weekly feedback collection
- [ ] Bug fixing на основе real usage
```

---

## ДЕНЬ 2 (опционально) — TD-1 decompose loop.py phase 2/3

**Только если день 1 закрыт полностью и есть энергия.** Иначе перенести на следующий понедельник.

См. `.planning/POST-RELEASE-DEBT.md` секция TD-1. Главное:

1. Снять snapshot SSE-выходов на текущем main (baseline)
2. Extract `_handle_internal_tool()` из `loop.py:953-1073` → `loop_tool_handler.py`
3. Полный pytest → 0 регрессий
4. Extract `_handle_mcp_tool()` из `loop.py:1075-1136`
5. Создать `LoopContext` dataclass, обернуть `INTERRUPTS`/`_pending`/`CLARIFY` глобалы
6. Snapshot SSE — байт-в-байт совпадение
7. `wc -l loop.py` → <400 (с 689)

---

## КРИТЕРИИ УСПЕХА ДНЯ 1

- [ ] 3 finding закрыты (A1/A2/A3)
- [ ] Quality gate зелёный (ruff/tsc/pytest/vitest/build)
- [ ] Manual smoke v1.4.5 — все 14 пунктов PASS
- [ ] git tag v1.4.5 в репо
- [ ] GitHub Release опубликован с installer attached
- [ ] STATE.md обновлён (M7 partial done + M8 opened)
- [ ] Можно дать ссылку на release первому пилотному кандидату

---

## NEXT STEP ПОСЛЕ DAY 1

1. **Контакт с пилотным кандидатом** — отправить ссылку на GitHub Release + USER.md + предложить 30-минутный onboarding call
2. **TD-1 в фокус-сессии** на этой или следующей неделе
3. **Wave 2 HIGH commerce-blockers** — постепенно по 1-2 тикета в неделю параллельно с пилотом
4. **Feedback log** в `.planning/handoff-2026-06-XX/` после первой недели пилота
