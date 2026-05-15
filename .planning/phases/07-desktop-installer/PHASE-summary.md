# Phase 7: Desktop Installer (Electron) — Planning Summary

**Phase:** 07-desktop-installer
**Created:** 2026-05-15
**Mode:** mvp (vertical slices) · coarse · 5 plans
**User Story:** Аналитик скачивает один `analyst-setup-v1.0.0.exe` (~180 MB), кликает → ставится без админских прав → двойной клик ярлыка → окно «1С Аналитик» открывается за ≤ 10 сек. БЕЗ Python, Node.js, pnpm, Docker, cmd окон.

---

## Wave Schedule

| Wave | Plans | Параллельность | Depends |
|------|-------|----------------|---------|
| 1 | **07-02** (PyInstaller backend.exe), **07-03** (Next standalone + build-bundle.js) | parallel — изолированы | — |
| 2 | **07-01** (Electron main.js + preload.js) | single | wave 1 артефакты (resources/backend.exe + resources/frontend/) |
| 3 | **07-04** (electron-builder.yml + NSIS installer) | single | wave 2 (main.js + node_modules/electron*) |
| 4 | **07-05** (Verification + release) | single, checkpoint:human-verify | wave 3 (analyst-setup-v1.0.0.exe) |

**Total:** 4 waves, 5 plans, autonomous: 4 / checkpoint: 1.

---

## Requirements Coverage (DIST-01..05)

| Req | Plan | Phase wave | Status after Phase 7 |
|-----|------|------------|----------------------|
| DIST-01 — Electron spawn backend + frontend + waitForUrl + BrowserWindow | 07-01 | wave 2 | ✓ closed by Plan 7.1 |
| DIST-02 — PyInstaller backend.exe (~50 MB) без Python | 07-02 | wave 1 | ✓ closed by Plan 7.2 |
| DIST-03 — Next standalone build (`output:"standalone"`) | 07-03 | wave 1 | ✓ closed by Plan 7.3 |
| DIST-04 — electron-builder NSIS installer (per-user, ярлыки) | 07-04 | wave 3 | ✓ closed by Plan 7.4 |
| DIST-05 — Auto-cleanup child процессов (SIGTERM + SIGKILL fallback) | 07-01 | wave 2 | ✓ closed by Plan 7.1 |

**Coverage:** 5 / 5 requirements addressed. All DIST-* IDs map to at least one plan.

---

## Plans Catalog

| Plan | File | Tasks | Files modified | Karpathy budget |
|------|------|-------|----------------|-----------------|
| 7.1 Electron main process | `07-01-PLAN.md` | 3 | desktop/main.js, desktop/preload.js, desktop/package.json | main.js ≤ 200 строк |
| 7.2 PyInstaller backend bundle | `07-02-PLAN.md` | 3 | backend/app/main_cli.py, backend/build.spec, backend/pyproject.toml | main_cli.py ≤ 30 строк, build.spec ≤ 50 |
| 7.3 Next standalone + bundle script | `07-03-PLAN.md` | 3 | desktop/scripts/build-bundle.js, desktop/package.json, desktop/.gitignore | build-bundle.js ≤ 100 строк |
| 7.4 electron-builder NSIS installer | `07-04-PLAN.md` | 3 | desktop/electron-builder.yml, desktop/icon.ico, desktop/build/installer.nsh, desktop/package.json | electron-builder.yml ≤ 60 строк |
| 7.5 Verification + release | `07-05-PLAN.md` | 4 (1 checkpoint:human-verify + 1 checkpoint:decision + 2 auto) | README.md, ROADMAP.md, REQUIREMENTS.md, SMOKE-RESULTS.md | — |

**Total tasks:** 16 (14 auto + 2 checkpoint).

---

## File ownership (no overlap between same-wave plans)

**Wave 1 parallel:**
- 07-02 touches: `backend/app/main_cli.py`, `backend/build.spec`, `backend/pyproject.toml`
- 07-03 touches: `desktop/scripts/build-bundle.js`, `desktop/package.json`, `desktop/.gitignore`
- ✓ NO overlap (backend vs desktop directories)

**Wave 2 (07-01):**
- Touches `desktop/main.js`, `desktop/preload.js`, `desktop/package.json` (engines field append)
- Note: `desktop/package.json` shared with 07-03 (wave 1) — but waves serialised, no conflict.

**Wave 3 (07-04):**
- Touches `desktop/electron-builder.yml`, `desktop/icon.ico`, `desktop/build/installer.nsh`, `desktop/package.json` (scripts + version + productName)
- After Wave 2 — sequential, no conflict.

**Wave 4 (07-05):**
- Touches `README.md`, `ROADMAP.md`, `REQUIREMENTS.md`, `.planning/phases/07-desktop-installer/SMOKE-RESULTS.md`
- All outside desktop/ except SMOKE-RESULTS in phase dir.

---

## Verification Gate (Phase-level)

Phase 7 считается завершённой когда **все** условия истинны:

1. **Build pipeline идемпотентный:** `pnpm run build` в desktop/ собирает installer без ручных вмешательств (после wave 1–3 артефакты воспроизводимы).
2. **Installer работает:** `desktop/dist/analyst-setup-v1.0.0.exe` существует, размер 120–200 MB, валидные VersionInfo metadata.
3. **Smoke A–F прошёл** (Plan 7.5 Task 1):
   - A. Установка per-user, без UAC, ярлыки появились
   - B. Запуск ≤ 10 сек, нет cmd окон, окно UI отрисовалось
   - C. Функциональность: Settings, Chat работают (если backend + LLM настроены)
   - D. Close → backend.exe + electron.exe убиты, Task Manager пуст
   - E. Перезапуск работает (random freeport)
   - F. Uninstall убирает Programs/* (user data в %APPDATA% остаётся — норма)
4. **Документация:** README с Desktop Distribution секцией.
5. **Tracking:** ROADMAP Phase 7 ✓ Done, REQUIREMENTS DIST-01..05 ✓ Done.

---

## Known Risks (для Phase 7 в целом)

| ID | Sev | Risk | Mitigation Plan |
|----|-----|------|-----------------|
| R-7-01 | HIGH | PyInstaller hidden imports неполные — backend.exe падает на aiosqlite/sse_starlette на чистой машине | 07-02 hiddenimports список + `--collect-all aiosqlite` если нужно; verify Task 3 запускает exe без Python в PATH |
| R-7-02 | HIGH | Windows symlinks в pnpm node_modules ломают standalone copy без admin | 07-03 fs.cpSync с `{recursive:true, dereference:true}`; verify через Get-ChildItem -Attributes ReparsePoint |
| R-7-03 | HIGH | ELECTRON_RUN_AS_NODE='1' забыто в spawn frontend — открывается второе окно Electron вместо запуска server.js | 07-01 ENV var обязательный, lint в verify Task 2 (grep token) |
| R-7-04 | MED | Child процессы не убиваются при main crash | 07-01 четыре lifecycle hooks (window-all-closed, before-quit, SIGINT, SIGTERM) + Plan 7.5 smoke Task Manager check |
| R-7-05 | MED | Windows SmartScreen warning при первом запуске (нет code signing) | Документировать в README (Plan 7.5); пользователь жмёт «More info» → «Run anyway»; code signing — v2 |
| R-7-06 | MED | electron-builder NSIS toolchain (~50 MB) скачивается через сеть на первом build | Документировать в SUMMARY; CI/dev машина требует интернет |
| R-7-07 | LOW | Размер installer >200 MB | excludes в build.spec (tkinter, matplotlib, numpy, pandas); электрон bundle уже минимальный |
| R-7-08 | LOW | Кириллица в productName → не-ASCII путь в %APPDATA% | aiosqlite поддерживает unicode пути; verify в Plan 7.5 smoke |
| R-7-09 | LOW | Antivirus false-positive на PyInstaller `--onefile` exe | Документировать в README; enterprise client — whitelisting или `--onedir` (v2) |

---

## Out of Scope (Phase 7 GLOBAL)

Подтверждено пользователем (yolo + CONTEXT.md `<deferred>`):

- macOS / Linux installers — v2 (electron-builder поддерживает, но требует Mac для подписи)
- Auto-update через electron-updater — v2 (нужен publish endpoint + certificate)
- Code signing certificate (~$200/год EV cert для Win) — v2
- Tray icon + minimize-to-tray — v2
- Auto-launch on Windows boot — v2
- Системные глобальные hotkeys (Cmd+Shift+A) — v2
- Multi-window support — v2
- Telemetry / crash reporting (Sentry-electron) — v2
- Portable single-exe (без installer) — v2

---

## Stack additions (relative to Phase 1-6)

- **electron** ^33.0.0 (~120 MB на dev машине) — desktop wrapper
- **electron-builder** ^25.0.0 (~50 MB + NSIS toolchain download) — installer builder
- **pyinstaller** ≥6.10 (~15 MB) — backend → .exe
- **node** ≥20 (engines.node в desktop/package.json) — для встроенного fetch + ESM support

В runtime/installer всё embedded — у аналитика никаких внешних зависимостей.

---

## Karpathy Compliance

| Skill | Adherence |
|-------|-----------|
| Think Before Coding | Reference main.js в 07-CONTEXT.md ~100 строк; ясные контракты child процессов; ELECTRON_RUN_AS_NODE caveat явно задокументирован |
| Simplicity First | main.js ≤ 200 строк; build-bundle.js ≤ 100; electron-builder.yml ≤ 60; никаких абстракций (BackendManager класса, EventEmitter, config files) |
| Surgical Changes | Только desktop/ + backend/main_cli.py + backend/build.spec + 1 поле в backend/pyproject.toml. Frontend код не трогаем (Next.js standalone уже подготовлен через env). |
| Goal-Driven Execution | Каждый план имеет measurable verify + done. Phase 7 success criteria из ROADMAP → smoke checklist A–F в Plan 7.5. |

---

## Next Steps

После approval этого плана:
1. Запустить `/gsd-execute-phase 07-desktop-installer` или эквивалент
2. Wave 1 параллельный execution (Plan 7.2 + Plan 7.3)
3. Wave 2 (Plan 7.1) после успешного wave 1
4. Wave 3 (Plan 7.4) после успешного wave 2
5. Wave 4 (Plan 7.5) после успешного wave 3, с manual smoke checkpoint
6. Merge feature/desktop-installer → master + tag v1.1.0

Recommended: `/clear` перед execute — фаза большая, фрагментарность контекста полезна.
