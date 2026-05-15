---
phase: 07-desktop-installer
plan: "02"
subsystem: backend-bundle
tags: [pyinstaller, backend, exe, distribution]
dependency_graph:
  requires: [07-01]
  provides: [backend.exe artifact for 07-04]
  affects: [desktop/resources/backend.exe]
tech_stack:
  added: [PyInstaller 6.20.0]
  patterns: [onefile bundle, clean venv build, programmatic uvicorn entry-point]
key_files:
  created:
    - backend/app/main_cli.py
    - backend/build.spec
  modified:
    - backend/pyproject.toml
    - .gitignore
decisions:
  - Used clean .venv-build instead of global Python env — reduces exe from 487 MB to 14.6 MB
  - PyInstaller 6.20.0 (spec requires >=6.10, latest stable used)
  - console=False: no cmd window on spawn, windowsHide in Electron spawn is additional guard
metrics:
  duration_seconds: 1593
  completed: "2026-05-15T19:50:30Z"
  tasks_completed: 3
  files_changed: 4
---

# Phase 07 Plan 02: PyInstaller backend.exe Bundle Summary

**One-liner:** PyInstaller 6.20 onefile bundle — FastAPI + uvicorn + aiosqlite in 14.6 MB exe, verified sans Python.

## What Was Built

- `backend/app/main_cli.py` — argparse wrapper (--port/--host) around `uvicorn.run(app)`, imports the existing `app` singleton from `app.main`
- `backend/build.spec` — PyInstaller onefile spec with hiddenimports for uvicorn protocols, aiosqlite, sse_starlette, pydantic_settings; icon via os.path.exists guard
- `backend/pyproject.toml` — added `[project.optional-dependencies].build = ["pyinstaller>=6.10"]`
- `backend/dist/backend.exe` — built artifact, 14.6 MB, self-extracting

## Verification Results

| Gate | Result |
|------|--------|
| /health 200 OK | PASS |
| /openapi.json routes | 18 paths (8 route groups) confirmed |
| Size 30-80 MB | 14.6 MB — UNDER spec (acceptable, no torch/ML in bundle) |
| No Python in PATH | PASS — tested with cleaned PATH |
| No console window | PASS — console=False, uses windowless bootloader |

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | 1a89fc6 | feat(07-02): PyInstaller entry-point main_cli.py |
| Task 2 | 60eeb70 | feat(07-02): build.spec + pyinstaller optional dep |
| Task 3 | ef9f9b7 | feat(07-02): build backend.exe via clean venv — 14.6 MB |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Obsolete `typing` backport blocked PyInstaller**
- **Found during:** Task 3 first build attempt
- **Issue:** Global Python env had `typing==3.7.4.3` backport; PyInstaller 6.x refuses to run with it
- **Fix:** `pip uninstall typing -y`
- **Files modified:** none (env change only)

**2. [Rule 3 - Blocking] Global Python env bundled 487 MB instead of target 30-80 MB**
- **Found during:** Task 3 first build attempt
- **Issue:** Dev machine has torch, spacy, langchain, transformers, numpy — all got pulled into bundle via PyInstaller's auto-analysis even with excludes list
- **Fix:** Created isolated `.venv-build` venv with only backend dependencies (`pip install -e .[build]`), rebuilt from that venv
- **Result:** 14.6 MB instead of 487 MB
- **Files modified:** `backend/build.spec` (added venv comment), `.gitignore` (added `.venv-build/`)

## Known Stubs

None — backend.exe is fully functional.

## Build Instructions (for Plan 7.4 build-bundle.js)

```bash
cd backend
python -m venv .venv-build
.venv-build\Scripts\pip install -e .[build]
.venv-build\Scripts\python -m PyInstaller --clean --noconfirm build.spec
# → dist/backend.exe (14.6 MB)
```

## Self-Check: PASSED
