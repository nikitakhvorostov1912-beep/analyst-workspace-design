# PROJECT-INDEX — карта проекта (НАЧНИ ОТСЮДА)

> Единая навигация по документам и структуре «1С Аналитик». Создан 2026-05-30,
> чтобы не было путаницы: где что лежит, что **актуально**, что **историческое**.
> При сомнении «по какому плану двигаемся» — только раздел 0.

---

## 0. С чего начать (канонная цепочка — ТОЛЬКО ЭТО актуально для планирования)

| Нужно | Файл |
|---|---|
| **Резюм сессии / «продолжай»** | `.claude/CLAUDE.md` → секция **★ КАНОНИЧЕСКИЙ ПЛАН** (грузится авто) |
| **Куда движемся (роадмап)** | `.planning/ROADMAP-2026-05-29.md` ← **единственный актуальный роадмап** |
| **Что сейчас активно (граф/grounding)** | `.planning/knowledge-layer-2026-05-24/phases/M-K3/17-graph-accuracy/SUMMARY.md` → **§0.5** |
| **Критерии приёмки «Объяснителя»** | `.planning/knowledge-layer-2026-05-24/ACCEPTANCE-explainer.md` |
| **Концепция продукта (что строим)** | корневой `CLAUDE.md` + `README.md` |
| **Правила работы (для Claude)** | `.claude/rules/` (session-contract, design-bans, tech-stack) |

---

## 1. Структура каталогов

| Каталог / файл | Что это | Статус |
|---|---|---|
| `backend/` | FastAPI + SQLite — API, оркестратор чата, Knowledge Layer (`app/knowledge/`) | ✅ актив |
| `frontend/` | Next.js 15 + React 19 — чат-UI | ✅ актив |
| `desktop/` | Electron-обёртка (инсталлятор) | ✅ актив |
| `1c/epf/` | Исходник EPF `АналитикLite` (M-K3 13a) | ✅ актив |
| `.claude/` | Конфиг Claude: `CLAUDE.md` (якорь), `rules/`, `skills/`, `memory/` | ✅ актив |
| `.planning/` | Планирование (GSD): роадмап, фазы, состояние — см. раздел 2–3 | смешанное |
| `docs/` | Справочное: `00b-mcp-capability-map.md`, `API.md`, `USER.md`, `DEMO-*` | ✅ актив |
| `.brand/` | Бренд Stencil (`BRAND.md`) | ✅ актив |
| `data/` | БД: `pilot.db` (прод-граф+карточки), `graph-index/*.db` (рабочие) | 🔒 gitignored |
| `distribution-for-analyst/`, `1C-Analyst-v1.4.5/`, `*.zip` | Сборки/дистрибутивы | 📦 артефакты |
| `mockups/`, `temp/`, `logs/`, `*.log`, `.coverage` | Историческое / временное / локальное | 🗑 gitignored |

---

## 2. Канонические документы (читать ЭТИ)

| Файл | О чём |
|---|---|
| `.claude/CLAUDE.md` | **Операционный якорь** — канонный план, текущее состояние, резюме |
| `CLAUDE.md` (корень) | Концепция продукта, стек, что НЕ делаем |
| `.planning/ROADMAP-2026-05-29.md` | **Единый роадмап** M1–M7 + M-K0..M-K6 |
| `.../17-graph-accuracy/SUMMARY.md` §0.5 | **Живое состояние** активной работы (граф/grounding) |
| `.../ACCEPTANCE-explainer.md` | Критерии приёмки «Объяснителя» (G0–G3) |
| `ARCHITECTURE.md`, `REQUIREMENTS.md` (корень) | Топология + требования (базовые) |
| `CHANGELOG.md` | История изменений по версиям |
| `docs/00b-mcp-capability-map.md` | Реальные возможности MCP Toolkit (10 операций) |
| `.claude/rules/*.md` | session-contract, design-bans, tech-stack |

---

## 3. Историческое / справочное (НЕ источник истины)

> Оставлено для контекста по уже сделанному. **Не использовать для планирования.**

- **Устаревшие роадмапы:** `ROADMAP.md` (корень) и `.planning/ROADMAP.md` → заменены `ROADMAP-2026-05-29.md` (помечены баннерами).
- **Дубли (РАСХОЖДЕНИЕ — к консолидации):** `.planning/PROJECT.md` / `.planning/REQUIREMENTS.md` разошлись с корневыми. Актуальная концепция — корневой `CLAUDE.md` + `ROADMAP-2026-05-29.md`.
- **Релизные/QA артефакты:** `.planning/` — `BASELINE-*`, `COMMERCE-*`, `RELEASE-NOTES-*`, `SMOKE-*`, `VERIFICATION-*`, `SPRINT-SUMMARY.md`, `*-CHECKLIST*.md`, `RESEARCH_*`, `UI-REVIEW-*`.
- **Хэндоффы/фазы:** `.planning/handoff/`, `handoff-2026-05-23/`, `milestones/`, `development-plan-2026-05-24/`, `qa-prod-release-2026-05-24/`, `phases/`, `intel/`, `research/`, `ui-reviews/`.
- **Архив:** `.planning/_archive/` (старые планы/промпты).
- **Мёртвый код:** `docs/_archive-v0-object-ide/`, `mockups/_legacy/` — провальные итерации v0, НЕ трогать.

---

## 4. Известный беспорядок (к чистке — не блокер, см. задачи)

1. **Локальный мусор в корне** (gitignored, в репо НЕТ): `backend-*.log` ×11, `frontend-sprint1.log`, `next-dev.log`, `full-pytest*.log`, `*.zip`, `.coverage`, `.last-bundle-path.txt`. → можно удалить локально, репо чист.
2. **Дубли** `PROJECT.md`/`REQUIREMENTS.md` (корень vs `.planning/`) — консолидировать в один.
3. **Две handoff-папки** — слить в `_archive/` при случае.
4. **NIM-трек** (`samples.json`, `wave*-erp*`, `response-*`, `batch-*`, `apply_loop_erp8.py`, `build_chunks_from_mock.py`) — рабочие файлы фоновой пересборки карточек, **не трогать/не коммитить**.

---

## 5. Правило против путаницы

**Источник истины по «куда движемся» — только канонная цепочка (раздел 0).**
Всё в разделе 3 — историческое. При любом сомнении → `.claude/CLAUDE.md`
секция **★ КАНОНИЧЕСКИЙ ПЛАН**. Новые планы НЕ плодить — обновлять
`ROADMAP-2026-05-29.md` + соответствующий `SUMMARY.md`.
