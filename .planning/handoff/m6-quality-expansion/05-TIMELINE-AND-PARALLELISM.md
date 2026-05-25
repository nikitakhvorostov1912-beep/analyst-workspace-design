# 05 — Timeline + Parallelism + Critical Path

## Расклад по неделям (с параллелизацией)

```
Week 1-2   [Phase 12] Multi-MCP + Capabilities ████████████
                                                 ↓
Week 3-4   [Phase 13a] EPF Lite ████████
                                  ↓
Week 5-7   [Phase 13b] CFE Full ████████████████████   ┐
                                                       │
Week 5-7   [Phase 14] Triple RAG ███████████████████   │ parallel
                                                       │
Week 8-9   [Phase 15] BSL LS ████████
                              ↓
Week 10-13 [Phase 16] MetaVision ████████████████████  ┐
                                                       │
Week 10-12 [Phase 17] Cards + Gates ███████████████   │ parallel
                                                       │
Week 12-13 [Phase 17b] Activity Stream ████████        │
                                                       │
Week 14-15 [Phase 18] Distribution ██████████
                                    ↓
Week 16    Smoke + bug fixes + release v2.0
```

**Итого: 16 недель ≈ 4 месяца**

## Без параллелизации

Если работаем sequentially:
- Phase 12: 2 нед
- Phase 13a: 2 нед
- Phase 13b: 3 нед
- Phase 14: 3 нед
- Phase 15: 2 нед
- Phase 16: 4 нед
- Phase 17: 2 нед
- Phase 17b: 1 нед
- Phase 18: 1.5 нед

**Итого: 20.5 недель ≈ 5 месяцев** (12% больше)

## Критический путь

```
12 → 13a → 13b → 17b → 18
 2     2     3     1     1.5  = 9.5 недель минимум
```

Это **абсолютный минимум** даже если параллелизуем всё что можем.

## Phase dependencies (граф)

```
Phase 12 ─┬─→ Phase 13a ─→ Phase 13b ─┬─→ Phase 17b ─┐
          │                            │              │
          └─→ Phase 14 ─────────────────┼─→ Phase 17 ──┤
          │                            │              │
          └─→ Phase 15 ─────────────────┘              │
          │                                            ├─→ Phase 18
          └─→ Phase 16 ────────────────────────────────┘
```

### Объяснение
- **Phase 12** — фундамент, всё после него
- **Phase 13a** — нужен Phase 12 (Capability discovery)
- **Phase 13b** — нужен Phase 13a (общие модули)
- **Phase 14** — нужен Phase 12 (Capability protocol для service.rag_*)
- **Phase 15** — нужен Phase 12 (Capability service.bsl_ls)
- **Phase 16** — нужен Phase 12 (Capability service.metavision)
- **Phase 17** — нужен 13a + 14 + 15 + 16 (отрисовка cards для всех)
- **Phase 17b** — нужен 13b (CFE-only фичи)
- **Phase 18** — нужен все остальные

## Возможные ускорения

### Если есть бюджет на параллельную команду

Можно нанять помощника на:
- **Phase 16 (MetaVision Java)** — Java/D3 разработчик может работать независимо после Phase 12 готов
- **Phase 14 (RAG)** — Python ML инженер на парсеры

С 1 помощником можно сэкономить ~4 недели → **12 недель вместо 16**.

### Если резать scope

**Минимальный M6** (без MetaVision, без HBK файла):
- Phase 12 + 13a + 13b + 14 (только v8std + ssl_api) + 15 + 17 + 18
- ~12 недель

**Аггрессивно минимальный** (только базовое):
- Phase 12 + 13a + 14 (только v8std) + 17 + 18
- ~9 недель
- Но это не "Quality Expansion" — это просто "Multi-MCP + RAG"

### Если резать качество

**Quick & Dirty:**
- Использовать MetaVision GUI отдельно (без CLI fork) — экономия 2 недели на Phase 16
- Skip .hbk RAG — экономия 1 неделя на Phase 14
- Skip Posting Trace — экономия 0.5 недели на Phase 13b

Экономия 3.5 недели → **12.5 недель**.

## Risk-aware планирование

### Если Phase 16 (MetaVision CLI) не получится за 1 неделю → fallback на GUI integration
- Экономим время на форке
- Frontend всё равно делает MetaVisionGraphCard
- Но граф рендерим из MetaVision GUI экспорта (manual JSON import)

### Если Phase 14 .hbk парсер не получится → skip
- Только v8std + ssl_api достаточно
- Экономия 5 дней

### Если Phase 13b HMAC SSO сложен → manual token mode
- Аналог EPF flow для CFE
- Экономия 1 день

## Контрольные точки (checkpoints)

| Week | Контрольная точка | Что проверяем |
|------|-------------------|---------------|
| 2 | Phase 12 done | Multi-MCP работает с 3 источниками |
| 4 | Phase 13a done | EPF собран, smoke OK |
| 7 | Phase 13b done | CFE на 3 типовых, SSO OK |
| 7 | Phase 14 done | Тройной RAG работает |
| 9 | Phase 15 done | BSL LS diagnostics live |
| 13 | Phase 16 done | MetaVision граф рендерится |
| 13 | Phase 17 done | Все cards интегрированы |
| 13 | Phase 17b done | Activity Stream + Posting Trace |
| 15 | Phase 18 done | Installer v2.0 готов |
| 16 | Release | v2.0.0 в production |

## Definition of Done для M6

Milestone M6 считается завершённым когда:

- [ ] Все 8 фаз завершены (PHASE-summary.md в `.planning/phases/`)
- [ ] v2.0.0 installer работает на чистой Windows 10/11 VM
- [ ] Smoke on УТ 11.5 + ERP 2.5 + КА 2.5 (все 3 типовых)
- [ ] 23 capabilities активны в CFE режиме
- [ ] 8 capabilities активны в EPF режиме
- [ ] Migration EPF ↔ CFE без потери истории
- [ ] Auto-update работает
- [ ] Backend tests coverage ≥ 80% на новом коде
- [ ] Frontend vitest coverage ≥ 80% на новом коде
- [ ] Playwright e2e тесты зелёные
- [ ] Документация для пользователя написана (4 docs/INSTALL-* + 1 README-V2)
- [ ] CHANGELOG.md обновлён
- [ ] RELEASE-NOTES.md для v2.0.0
