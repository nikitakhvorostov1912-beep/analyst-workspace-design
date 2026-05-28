# Parallel Plan 2026-05-28 — работы пока NIM rebuild крутится

**Контекст:** NVIDIA NIM rebuild 60k карточек (`qwen/qwen3.5-122b-a10b`) запущен в фоне, ETA ~10-43 часов. Параллельно закрываем незавершённое из M-K0 / Phase 11 / технический долг.

**Ограничения:** не трогать схему `typical_object_cards` в `data/pilot.db` (NIM пишет каждые 50 carts). Read-only мониторинг ОК.

**Корректировка на старте:** Wave 6 Docs+DevOps по факту уже ЗАКРЫТ коммитом `f956a21` (M-K0.7). STATE.md показывает `🟡 в работе` из устаревшего snapshot. Это honesty fix, не работа.

---

## Сводная таблица

| ID | Описание | ETA | Приор | Зависит от | Output |
|----|----------|-----|-------|-----------|--------|
| F0 | NIM watchdog + базовый мониторинг | 15 мин | P0 | — | команда в терминал |
| F1 | Post-NIM smoke checklist + rollback plan | 30 мин | P0 | F0 | `.planning/SMOKE-NIM-REBUILD.md` |
| A1 | Верифицировать M-K0 DONE → STATE.md | 20 мин | P0 | — | `STATE.md` honesty fix |
| B1 | MetricCard → CardHeader (6/6 cards refactor) | 30 мин | P1 | — | `frontend/components/cards/MetricCard.tsx` |
| B2 | Vitest для обновлённого MetricCard | 20 мин | P1 | B1 | `MetricCard.test.tsx` |
| C1 | TD-5: ruff E501 fix в loop.py (8 ошибок) | 30 мин | P1 | — | `backend/app/orchestrator/loop.py` |
| C2 | TD-3: flaky tests encoding fix (7 тестов) | 2 ч | P1 | — | 7 test files |
| E1 | `.claude/CLAUDE.md` snapshot update | 20 мин | P1 | A1 | `.claude/CLAUDE.md` |
| E2 | `ARCHITECTURE.md` заголовок — убрать Phase 3 | 20 мин | P2 | — | `ARCHITECTURE.md` |
| E3 | `BACKLOG-POST-MVP.md` triage M6/M7 items | 30 мин | P2 | — | `BACKLOG-POST-MVP.md` |
| E4 | `ROADMAP.md` Phase 10 — Replaced by Hermes | 15 мин | P2 | — | `.planning/ROADMAP.md` |
| E5 | Verify `docs/CERT-PROCESS.md` (DEVOPS-1) | 10 мин | P2 | — | верификация |
| F2 | NIM post-rebuild commit message шаблон | 15 мин | P2 | — | в этом плане |

**Итого: ~5.5 часов активной работы.**

---

## Watchdog команда (F0)

```powershell
sqlite3 C:\CLOUDE_PR\projects\analyst-workspace-design\data\pilot.db "SELECT channel_id, COUNT(*) t, SUM(is_mock=0) real, PRINTF('%.1f%%', 100.0*SUM(is_mock=0)/COUNT(*)) pct FROM typical_object_cards GROUP BY channel_id;"
```

Признак живого rebuild: `real` растёт пачками по 50 каждые 2-5 минут.
Признак зависшего: `real` не меняется >30 мин — проверить процесс Python.

---

## Suggested order

### Час 1 (0:00 - 1:00)
1. **F0** (15 мин) — watchdog запущен, baseline зафиксирован
2. **A1** (20 мин) — STATE.md Wave 6 → DONE
3. **E1** (20 мин) — `.claude/CLAUDE.md` snapshot 2026-05-28

### Часы 1-2
4. **C1** (30 мин) — ruff E501 fix в loop.py
5. **B1** (30 мин) — MetricCard → CardHeader

### Часы 2-3
6. **B2** (20 мин) — Vitest для MetricCard
7. **E2** (15 мин) — ARCHITECTURE.md заголовок
8. **E4** (15 мин) — ROADMAP.md Phase 10

### Часы 3-5
9. **C2** (2 часа) — flaky tests encoding fix

### Часы 5-6
10. **E3** (30 мин) — BACKLOG triage
11. **E5** (10 мин) — verify CERT-PROCESS.md
12. **F1** (30 мин) — SMOKE-NIM-REBUILD.md

### Часы 6-10
13. Watchdog мониторинг каждые 20-30 мин
14. Если NIM завершил — F1 smoke + F2 коммиты M-K2.5 closure

---

## Acceptance criteria (Success)

- [ ] NIM rebuild живой
- [ ] STATE.md Wave 6 = DONE
- [ ] MetricCard использует CardHeader (6/6 cards refactor complete)
- [ ] `ruff check loop.py` → 0 errors
- [ ] Flaky tests ≤ 3
- [ ] `.claude/CLAUDE.md` актуален
- [ ] SMOKE-NIM-REBUILD.md готов
- [ ] NIM rebuild завершён → commit M-K2.5 closure

---

## Risks

- TD-3 `test_orchestrator_loop_confirm` (SSRF DNS) может не поддаться encoding fix — pre-existing
- MetricCard CardHeader может конфликтовать с outer border — проверить визуально
- NIM rate-limit → watchdog должен ловить

---

## Post-NIM commit template (F2)

```
feat(M-K2.5.10.7): bulk real LLM rebuild 63k карточек NVIDIA NIM

4 типовые: БП 3.0 / КА 2.5 / УТ 11.5 / ERP 2.5.
- Карточек rebuilt: <N> / 60192
- is_mock=0: <N>
- Validation pass rate: <X>%
- Модель: qwen/qwen3.5-122b-a10b

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

Полный детальный план с командами для каждой задачи — см. ответ агента-планировщика в conversation log.
