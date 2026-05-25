# CHECKLIST — Pre-flight для каждой фазы

**Назначение:** перед стартом ЛЮБОГО milestone — пройти соответствующий
checklist. Pre-flight catches mistakes before they happen.

## Universal checklist (любая фаза)

- [ ] `.planning/STATE.md` обновлён под текущий milestone
- [ ] `<phase>/PHASE-PLAN.md` создан и committed
- [ ] `RISKS.md` — пересмотрен на новые риски для этой фазы
- [ ] Branch `feature/<milestone-slug>` создан от свежего `master`
- [ ] `pytest` + `vitest` + `pnpm build` зелёные на baseline
- [ ] Predecessor SUMMARY.md прочитан (если есть)
- [ ] Открытые ADR/Q-NEW вопросы для этой фазы решены пользователем

## Pre-flight для M-K1 Foundation

### Документы
- [x] ADR-001 vector-db
- [x] ADR-002 graph-db
- [x] ADR-003 embeddings-runtime
- [x] ADR-004 capability-discovery
- [x] ADR-005 migrations-strategy
- [x] RISKS.md initial population
- [x] CHECKLIST.md (этот файл)
- [x] M-K1-PLAN.md обновлён под Q1+Q2+Q4+Q-NEW (см. G3 в AUDIT-GAPS.md)

### Архитектурные решения
- [x] Q1 CFE именование — подсистема `АналитикПлюс` + префикс `АП_` для критичных
- [x] Q2 типовые — УТ + ERP + КА + БГУ + ЗУП (5 на БСП 3.1+)
- [x] Q3 EPF first
- [x] Q4 MetaVision Spike 3 days в M-K4
- [x] Q6 Dual license (Apache 2.0 core + Proprietary EPF/CFE)
- [x] Q-NEW Напарник primary + наш RAG fallback

### Технические требования
- [ ] `~/.analyst-1c/knowledge/` path conventions согласованы (per-config layout)
- [ ] sqlite-vec extension скачана локально для smoke
- [ ] BGE-M3 модель скачана локально для smoke (570 MB)
- [ ] 1c-buddy MCP запущен на :6002 (Docker или native)
- [ ] tools/v8std/ доступен (sfaqer 317 ИТС)
- [ ] tools/ssl_3_2/src/ доступен (БСП API)
- [ ] LICENSE-CORE (Apache 2.0) создан
- [ ] LICENSE-EPF, LICENSE-CFE (proprietary) — placeholder created
- [ ] NOTICE с атрибуциями (БСП CC-BY-4.0, sfaqer, OnesTemplates)

### Готовность инфраструктуры
- [ ] Backend pytest baseline: 972 passed (M-K0 last)
- [ ] Frontend vitest baseline: 322 passed
- [ ] Coverage backend baseline: 87.3%
- [ ] M-K0 branch `feature/m-k0-stabilization` merged в master
- [ ] `feature/m-k1-foundation` создан

## Pre-flight для M-K2 Knowledge Foundation

- [ ] M-K1 SUMMARY.md прочитан
- [ ] `backend/app/knowledge/` модуль существует с базовыми types
- [ ] Configuration Fingerprint работает на 2+ конфигурациях
- [ ] sqlite-vec extension успешно loaded в production environment
- [ ] BGE-M3 cold-start ≤ 5 sec на reference machine
- [ ] M-K2-PLAN.md создан с G4 .hbk Spike acceptance criterion

## Pre-flight для M-K3 EPF/CFE Delivery

- [ ] M-K2 SUMMARY.md прочитан
- [ ] Capability matrix реально работает на 1+ типовой
- [ ] EPF skeleton создан (см. M-K3-PLAN.md Phase 13a.0)
- [ ] G5 BSL LS scope решён (detector vs streaming)
- [ ] G7 M-K3-PLAN.md с atomic tasks
- [ ] G11 Cards registry создан в frontend

## Pre-flight для M-K4 Visual + Activity Stream

- [ ] M-K3 SUMMARY.md прочитан
- [ ] CFE delivery работает на 1+ smoke base
- [ ] G6 MetaVision Spike в Phase 16.0 — go/no-go gate
- [ ] G8 M-K4-PLAN.md с Activity Stream связкой к L4

## Pre-flight для M-K5 Predictive + Distribution v2.0

- [ ] M-K4 SUMMARY.md прочитан
- [ ] 5 typical configurations прошли smoke tests
- [ ] G9 M-K5-PLAN.md с Distribution v2.0 phase
- [ ] Code-signing cert (Q5) решено — Sectigo OV или self-signed
- [ ] Bundle size ≤ 250 MB target после оптимизаций R-05

## Post-flight для каждой фазы

- [ ] `phases/<milestone>/SUMMARY.md` написан
- [ ] `.planning/STATE.md` обновлён (status=done)
- [ ] `RISKS.md` — обновить закрытые риски в нижнюю секцию
- [ ] Tests baseline зафиксирован в SUMMARY (passed, failed, coverage)
- [ ] Atomic commits сформированы с правильными conventional types
- [ ] Open follow-ups перенесены в следующий milestone

## Quality gates

Запускать перед каждым коммитом значимых изменений:

```bash
# Backend
cd backend && python -m pytest --no-cov -q
cd backend && python -m pytest --cov=app --cov-report=term-missing  # для coverage

# Frontend
cd frontend && pnpm vitest run
cd frontend && pnpm build

# Полный pre-merge
cd .. && /awd-quality-gate  # custom skill (см. .claude/skills/)
```

## Когда checklist игнорировать

Только при hotfix критичного production бага. В этом случае:
1. Минимальный фикс
2. Регрессионный тест на воспроизведение
3. Документ в `RISKS.md` (закрытые) с reference на commit
4. Полный pre-flight для следующего planned milestone — не пропускать
