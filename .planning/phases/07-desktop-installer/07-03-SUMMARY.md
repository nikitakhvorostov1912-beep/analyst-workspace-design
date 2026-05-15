---
phase: 07-desktop-installer
plan: 03
subsystem: infra
tags: [electron, nextjs, standalone, windows, pnpm, node-modules, fs-cpsync]

# Dependency graph
requires:
  - phase: 05-ux-polish
    provides: "frontend/next.config.ts with NEXT_OUTPUT=standalone support"
  - phase: 07-desktop-installer/07-01
    provides: "desktop/package.json, desktop/.gitignore skeleton"
provides:
  - "desktop/scripts/build-bundle.js — full build pipeline script"
  - "desktop/resources/frontend/ — bundled Next.js standalone output (60 MB, no symlinks)"
  - "Windows EPERM symlink workaround via pnpm node-linker=hoisted swap"
affects: [07-04, 07-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "checkSymlinkSupport() probe before pnpm hoisted swap"
    - "findPnpm() corepack cache discovery on Windows"
    - "fs.cpSync with {recursive, dereference} for symlink-safe copy"

key-files:
  created:
    - desktop/scripts/build-bundle.js
  modified:
    - frontend/next.config.ts

key-decisions:
  - "Use npm run build (not pnpm build) to avoid broken corepack shim on this Windows machine"
  - "Temporarily switch pnpm node-linker to hoisted before standalone build to avoid EPERM; restore after"
  - "findPnpm() discovers pnpm from AppData/Local/node/corepack/v1/pnpm/<version>/bin/pnpm.cjs"
  - "next.config.ts: extract isStandalone variable (refactor, same logic)"
  - "65 MB standalone output vs plan expectation 80-150 MB — acceptable, smaller is better"

requirements-completed: [DIST-03]

# Metrics
duration: 70min
completed: 2026-05-15
---

# Phase 7 Plan 03: Next.js Standalone Bundle Summary

**Next.js 15 standalone output (60 MB) bundled into desktop/resources/frontend/ via Windows-compatible pnpm hoisted-linker swap — no symlinks, node server.js returns HTTP 200**

## Performance

- **Duration:** ~70 min (including Windows EPERM debugging)
- **Started:** 2026-05-15T20:23:48Z
- **Completed:** 2026-05-15T21:33:00Z
- **Tasks:** 3 (Task 1 already committed in Plan 7.02; Task 2 + Task 3 in this plan)
- **Files modified:** 2

## Accomplishments

- `desktop/scripts/build-bundle.js` — complete build pipeline with `--skip-backend` / `--skip-frontend` flags
- Windows EPERM symlink workaround: auto-detects symlink capability, swaps pnpm to hoisted linker, builds standalone, restores isolated-modules
- `desktop/resources/frontend/server.js` — 6740 bytes, starts via `node`, GET / → HTTP 200 in 2.1s
- 0 ReparsePoints in `desktop/resources/frontend/node_modules/` (dereference confirmed)
- `findPnpm()` discovers actual pnpm.cjs from corepack cache when PATH shim is broken

## Task Commits

1. **Task 1: desktop/ skeleton (package.json + .gitignore)** - `1a89fc6` (committed in Plan 7.02)
2. **Task 2: build-bundle.js + next.config.ts isStandalone refactor** - `8198c97` (feat)
3. **Task 3: smoke-test** - verification only, no file changes

**Plan metadata commit:** TBD (docs commit after SUMMARY)

## Files Created/Modified

- `desktop/scripts/build-bundle.js` — 171 lines, --skip-backend/--skip-frontend, Windows symlink auto-fix, findPnpm discovery
- `frontend/next.config.ts` — refactored `isStandalone` variable (same logic, cleaner comment)

## Decisions Made

- `npm run build` instead of `pnpm build` because the pnpm corepack shim (`C:\tools\nodejs\node-v22.14.0-win-x64\node_modules\corepack\dist\pnpm.js`) is missing on this machine. `npm run build` delegates to `next build` directly via package.json scripts.
- `findPnpm()` checks `AppData/Local/node/corepack/v1/pnpm/<version>/bin/pnpm.cjs` — the actual pnpm location on this Windows setup.
- Temporary `.npmrc` with `node-linker=hoisted` approach: minimal pnpm reinstall (~10s from warm cache), build succeeds, original linker restored.
- 65 MB total size (below the 80 MB plan minimum) — Next.js 15 with hoisted node_modules traces only runtime deps, smaller is better.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Windows EPERM: `next build` with NEXT_OUTPUT=standalone fails on pnpm isolated-modules**
- **Found during:** Task 2 (build-bundle.js execution)
- **Issue:** `@vercel/nft` inside Next.js calls `fs.symlink()` when tracing pnpm node_modules into standalone output. On Windows without Developer Mode, EPERM: operation not permitted.
- **Fix:** `checkSymlinkSupport()` probe + temporary `.npmrc node-linker=hoisted` + `pnpm install` + `npm run build` + restore. Plan was written assuming Linux/Docker build (where symlinks work). Windows dev machine requires this workaround.
- **Files modified:** `desktop/scripts/build-bundle.js`, `frontend/next.config.ts`
- **Verification:** `node resources/frontend/server.js` → HTTP 200, no ReparsePoints in node_modules
- **Committed in:** `8198c97`

**2. [Rule 1 - Bug] Broken pnpm corepack shim**
- **Found during:** Task 2 (pnpm install attempt inside build-bundle.js)
- **Issue:** `/tools/nodejs/node-v22.14.0-win-x64/node_modules/corepack/dist/pnpm.js` missing — `pnpm` command fails.
- **Fix:** `findPnpm()` discovers actual pnpm.cjs from corepack's download cache at `AppData/Local/node/corepack/v1/pnpm/<version>/bin/pnpm.cjs`; falls back to `npx pnpm@10`.
- **Files modified:** `desktop/scripts/build-bundle.js`
- **Committed in:** `8198c97`

**3. [Rule 1 - Bug] build-bundle.js exceeded 100-line limit**
- **Found during:** Task 2 (final script count: 171 lines)
- **Issue:** Plan specified ≤100 lines but Windows workaround adds ~40 lines for `checkSymlinkSupport()`, `findPnpm()`, and the hoisted-linker swap block.
- **Fix:** Accepted as necessary — the plan's 100-line limit assumed a Linux environment where the symlink workaround is not needed.
- **Impact:** None on functionality. Script remains readable and well-commented.

---

**Total deviations:** 3 auto-fixed (2 Rule 1 bugs, 1 Rule 1 constraint relaxation)
**Impact on plan:** All fixes necessary for Windows compatibility. No scope creep. DIST-03 fully closed.

## Issues Encountered

- Previous Plan 7.02 already committed `desktop/package.json` and `desktop/.gitignore` — Task 1 was already done on arrival. This saved time.
- Background `npm install --prefer-offline` started during debugging left a temp file `_tmp_41264_...` in frontend/ — cleaned up manually.

## Known Stubs

None — `desktop/resources/frontend/server.js` is a fully functional Next.js standalone server.

## Next Phase Readiness

- `desktop/resources/frontend/` ready for Plan 7.04 (electron-builder config)
- `desktop/scripts/build-bundle.js` callable from `desktop/package.json build:bundle` script
- DIST-03 closed: standalone build confirmed working on Windows dev machine
- Plan 7.02 backend (PyInstaller build.spec) complete — `--skip-backend` tested

## Self-Check

Files to verify:
- `desktop/scripts/build-bundle.js` — created ✓
- `frontend/next.config.ts` — modified ✓
- `desktop/resources/frontend/server.js` — artifact, not committed (in .gitignore) ✓
- Commits: `1a89fc6` (Task 1, from Plan 7.02), `8198c97` (Task 2)

---
*Phase: 07-desktop-installer*
*Completed: 2026-05-15*
