# PLAN-CHECK - Phase 04-demo-refine

**Дата проверки:** 2026-05-15
**Планы:** 04-01, 04-02, 04-03, 04-04 (8 задач, 3 волны)

## ВЕРДИКТ: VERIFICATION PASSED

Блокирующих проблем не обнаружено. Найдены 3 предупреждения.

---

## D1: Requirement Coverage

| Требование | Планы | Статус |
|------------|-------|--------|
| ANON-01 (toggle) | 04-01 T-2 | PASS |
| ANON-02 (highlight) | 04-01 T-2 | PASS |
| ANON-03 (reveal) | 04-01 T-1+T-2 | PASS |
| CARD-04 (MetricCard) | 04-02 T-1+T-2 | PASS |
| CARD-05 (ReferencesCard) | 04-02 T-1+T-2 | PASS |
| CARD-06 (CodeCard) | 04-02 T-1+T-2 | PASS |
| PROD-01 (chips) | 04-03 T-2 | PASS |
| PROD-02 (slash) | 04-03 T-2 | PASS |
| PROD-03 (@-mention) | 04-03 T-1+T-2 | PASS |
| PROD-04 (Cmd-K) | 04-03 T-1+T-2 | PASS |
| PROD-05 (export) | PARTIAL | Задокументировано (CSV есть, PDF deferred) |

ROADMAP строка 190 явно фиксирует PROD-05 partial. FR-18 (KB похожее) не входит в Phase 4. **PASS**

---

## D2: Task Completeness

Все 8 задач содержат files / action (пронумерованные шаги) / verify (automated команды) / done (измеримые критерии). **PASS**

---

## D3: Dependency Correctness

04-01 (wave=1) -> 04-02, 04-03 (wave=2) -> 04-04 (wave=3). Циклов нет. Все referenced планы существуют. Номера волн соответствуют зависимостям. **PASS**

---

## D4: Key Links Planned

Все критические связи задокументированы в key_links frontmatter и в action-шагах:
- Header -> AnonymizationToggle -> localStorage -> useChatStream header
- chat.py -> run_chat_loop(x_anon_enabled) -> MCPClient header
- CardRenderer -> onDeanonymize -> api.ts -> /deanonymize
- cards.py _CARD_BUILDERS (6 ключей) -> CardRenderer switch (6 case)
- CodeCard -> lib/highlight.ts -> prismjs (импорт только в lib/)
- /search -> messages_fts FTS5 -> CommandPalette navigate + scroll
- /metadata-suggest -> metadata_cache -> MentionPopover
- Input.tsx -> QuickPrompts / SlashPopover / MentionPopover (conditional render)
- seed-demo-data.py -> app.storage.db -> apply_migrations

**PASS**

---

## D5: Scope Sanity

| План | Задач | Файлов | Context |
|------|-------|--------|---------|
| 04-01 | 2 | 27 | ~40% |
| 04-02 | 2 | 18 | ~45% |
| 04-03 | 2 | 29 | ~50% |
| 04-04 | 2 | 7 | ~25% |

Задач в плане: 2 (норма 2-3). Файлов в задачах T-04-01-2 (18) и T-04-03-2 (20) выше нормы 5-8, но файлы реально нужны (одна feature end-to-end). Context budget не превышен. **PASS с 2 WARNING**

---

## D6: Verification Derivation

Truths user-observable ("аналитик видит", "кнопка появляется", "токены заменяются"). Artifacts с path/provides/min_lines/contains. Key_links с from/to/via/pattern. **PASS**

---

## D7: Context Compliance

Все locked decisions из 04-CONTEXT.md покрыты задачами. Deferred items (PDF, vector search) не включены в планы. Scope reduction не обнаружен - PROD-05 partial соответствует locked decision из CONTEXT.md и ROADMAP. **PASS**

---

## D7c / D8 / D11 / D12

D7c: SKIPPED (RESEARCH.md отсутствует)
D8: SKIPPED (nyquist_validation: false в config.json)
D11: SKIPPED (research: false, RESEARCH.md не создавался)
D12: SKIPPED (PATTERNS.md не существует для Phase 4)

---

## D9: Cross-Plan Data Contracts

migrations.py: 04-01 пишет MIGRATIONS_V4 (anon_tokens), 04-03 пишет MIGRATIONS_V5 (FTS5). Append-only, разные версии. cards.py: 04-01 добавляет card_id к трём существующим payload-схемам, 04-02 добавляет три новых - без конфликта. models.py, lib/types.ts, lib/api.ts: все изменения append-only. PHASE-summary строка 39-64 явно документирует все пересечения. **PASS**

---

## D10: CLAUDE.md Compliance

Нарушений нет. prismjs (не shiki), Sparkline SVG (не recharts), dark theme, нет work-modes, нет TODO/placeholder в acceptance criteria. dangerouslySetInnerHTML для snippet покрыт тестом XSS escape. **PASS с 1 WARNING**

---

## Structured Issues

issues:
  - plan: "04-01"
    dimension: scope_sanity
    severity: warning
    description: "T-04-01-2 модифицирует 18 frontend файлов (target 5-8 на задачу). Все файлы принадлежат одной anon-feature."
    task: "T-04-01-2"
    fix_hint: "Правка PLAN.md не требуется. Executor проходит шаги линейно 1-16 - логически единая feature. Context ~40%."

  - plan: "04-03"
    dimension: scope_sanity
    severity: warning
    description: "T-04-03-2 модифицирует 20 frontend файлов - 4 независимых UX-компонента в одной задаче."
    task: "T-04-03-2"
    fix_hint: "Компоненты (QuickPrompts / Slash / Mention / CmdK) независимы - executor может останавливаться после каждого. Context ~50% при sequential. Блокером не является."

  - plan: "04-03"
    dimension: claude_md_compliance
    severity: warning
    description: "CommandPalette dangerouslySetInnerHTML для snippet. Тест XSS присутствует в done-критерии, но verify-блок не включает pnpm build с CSP-проверкой."
    task: "T-04-03-2"
    fix_hint: "Тест 'snippet HTML escaped except mark tags' покрывает XSS. При verify: убедиться что production build (pnpm build) не выдаёт CSP warnings (риск задокументирован в 04-02 risks)."

---

## Рекомендации по исполнению

1. Wave 2: sequential, не параллельный (04-02 -> 04-03). cards.py и migrations.py при параллельном исполнении дадут merge-конфликты.
2. AssistantMessage id="message-{mid}" должен существовать для CommandPalette scroll-to-anchor (known risk #9 в PHASE-summary). Проверить при исполнении 04-03.
3. После первого E2E теста с живой 1С зафиксировать реальную форму response submit_for_deanonymization (fallback parsers в T-04-01-1 шаг 4 предусмотрены).

---

## Итоговая таблица

| Измерение | Статус |
|-----------|--------|
| D1: Requirement Coverage | PASS |
| D2: Task Completeness | PASS |
| D3: Dependency Correctness | PASS |
| D4: Key Links Planned | PASS |
| D5: Scope Sanity | PASS + 2 WARNING |
| D6: Verification Derivation | PASS |
| D7: Context Compliance | PASS |
| D7b: Scope Reduction | PASS |
| D7c / D8 / D11 / D12 | SKIPPED |
| D9: Cross-Plan Data Contracts | PASS |
| D10: CLAUDE.md Compliance | PASS + 1 WARNING |

**VERIFICATION PASSED. Готово к: `/gsd-execute-phase 04-demo-refine`**

*Revision Gate: iteration 1 из 3 - PASS, revision loop не активируется*
*Plan check: 2026-05-15*
