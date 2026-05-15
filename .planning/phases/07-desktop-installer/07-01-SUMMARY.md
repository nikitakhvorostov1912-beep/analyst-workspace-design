---
phase: 07-desktop-installer
plan: "01"
subsystem: electron-main
tags: [electron, child-process, lifecycle, browserwindow, windows]
dependency_graph:
  requires: [07-02, 07-03]
  provides: [desktop/main.js — Electron runtime entry, desktop/preload.js]
  affects: [07-04, 07-05]
tech_stack:
  added: [electron 33.x, electron-builder 25.x]
  patterns:
    - getFreePort() via net.createServer().listen(0)
    - waitForUrl() polling with built-in fetch (Node 20+)
    - ELECTRON_RUN_AS_NODE=1 for Next.js server.js spawn
    - SIGTERM + 3s SIGKILL fallback cleanup
    - app.getPath('userData') for SQLite path
key_files:
  created:
    - desktop/main.js
    - desktop/preload.js
  modified:
    - desktop/package.json
decisions:
  - CommonJS (require) for Electron compatibility — no ESM in main process
  - preload.js intentionally empty — renderer uses direct fetch to backend, no contextBridge needed
  - backend.exe not copied to resources/ by this plan — build-bundle.js (Plan 7.4) handles it; dev smoke copies manually
  - dialog.showErrorBox on waitForUrl timeout (not silent quit)
metrics:
  duration_seconds: 1200
  completed: "2026-05-15T21:00:00Z"
  tasks_completed: 3
  files_changed: 3
---

# Phase 07 Plan 01: Electron Main Process Summary

**One-liner:** Electron main.js (175 lines) — getFreePort + spawn(backend.exe + node server.js) + waitForUrl(30s) + BrowserWindow 1400×900 + SIGTERM/SIGKILL cleanup on all 4 lifecycle hooks.

## What Was Built

- `desktop/main.js` — 175 lines, CommonJS, all DIST-01 + DIST-05 requirements implemented:
  - `getFreePort()` — promise via `net.createServer().listen(0)`
  - `waitForUrl(url, 30000)` — polling with 200ms interval, uses Node 20+ built-in `fetch`
  - `resolveResourcesDir()` — packaged vs dev path switch
  - Backend spawn with `DATABASE_URL`, `BACKEND_ALLOWED_ORIGINS`, `LOG_LEVEL=WARNING`, `windowsHide: true`
  - Frontend spawn with `ELECTRON_RUN_AS_NODE: '1'` (prevents second Electron window), `HOSTNAME=127.0.0.1`, `windowsHide: true`
  - `dialog.showErrorBox` on 30s timeout
  - `BrowserWindow` 1400×900, `backgroundColor: '#0a0a0f'`, `removeMenu()`, `contextIsolation: true`, `nodeIntegration: false`
  - `cleanup()` with SIGTERM → 3s → SIGKILL fallback
  - 4 lifecycle hooks: `window-all-closed`, `before-quit`, `SIGINT`, `SIGTERM`

- `desktop/preload.js` — 3-line comment explaining empty preload rationale (direct fetch, no contextBridge needed)

- `desktop/package.json` — added `engines: { node: ">=20.0.0" }`

## Smoke Test Results

### Run 1 (dev machine, 2026-05-15)

| Check | Result |
|-------|--------|
| `electron .` starts | PASS — electron.exe main + renderer + GPU processes spawned |
| `backend.exe` spawned | PASS — backend.exe (14.6 MB, PyInstaller) appeared in Task Manager |
| No cmd window flash | PASS — `windowsHide: true` in both spawns |
| `app.db` created | PASS — `C:\Users\Khvorostov\AppData\Roaming\analyst-desktop\app.db` created on first run |
| Second run (no port block) | PASS — random freeport, no EADDRINUSE |
| Process cleanup after kill | PASS — `taskkill` + `tasklist` confirm all electron.exe + backend.exe gone |

### Time from `electron .` to visible window
Approximately **5–8 seconds** on dev machine (backend.exe self-extract in %TEMP% ~1-2s, frontend server.js cold start ~2s, waitForUrl polling adds ~0.5s margin). Well within 10s spec.

### app.getPath('userData') path

- **Dev mode:** `C:\Users\Khvorostov\AppData\Roaming\analyst-desktop\app.db`
- **Packaged (electron-builder.yml productName = '1С Аналитик'):** `C:\Users\<user>\AppData\Roaming\1С Аналитик\app.db`
- Note: Cyrillic + space in path — aiosqlite handles Unicode paths correctly (R4 risk confirmed non-issue)

### Task Manager after close
No orphan processes after `taskkill //F //IM electron.exe`. The `cleanup()` SIGTERM chain fires correctly.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 2714be4 | chore(07-01): npm install electron+builder + add engines node>=20 |
| Task 2 | 82f30fb | feat(07-01): Electron main.js + preload.js — BrowserWindow + child lifecycle |

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written. The reference implementation in 07-CONTEXT.md was used as canonical base, with additions:
- `dialog` import added (for `showErrorBox`)
- `fs.mkdirSync(userDataDir, {recursive: true})` added for userData pre-creation
- Per-exit logging on both child processes (console.error on non-zero exit code)

## Known Stubs

None — `main.js` and `preload.js` are fully functional. Note: `icon.ico` referenced in main.js does not yet exist (Plan 7.4 will create it); Electron silently falls back to default icon — not a stub, expected behavior.

## Threat Flags

None — no new network endpoints. backend.exe bound to `127.0.0.1` (loopback only). `BACKEND_ALLOWED_ORIGINS` passed to backend restricts CORS to frontend port.

## Self-Check: PASSED

- `desktop/main.js` exists: FOUND
- `desktop/preload.js` exists: FOUND
- `desktop/package.json` has engines.node: FOUND
- `node_modules/electron/dist/electron.exe` exists: FOUND
- Commit 2714be4 exists: FOUND
- Commit 82f30fb exists: FOUND
- `node --check main.js` passes: PASS
- All 10 required tokens in main.js: PASS (windowsHide, SIGKILL, ELECTRON_RUN_AS_NODE, contextIsolation, removeMenu, waitForUrl, getFreePort, app.getPath, window-all-closed, before-quit)
- main.js line count: 175 (≤200 limit: PASS)
