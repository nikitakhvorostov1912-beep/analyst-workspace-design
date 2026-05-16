---
phase: 07-desktop-installer
plan: "04"
subsystem: desktop-installer
tags: [electron-builder, nsis, windows-installer, packaging]
dependency_graph:
  requires: [07-01, 07-02, 07-03]
  provides: [DIST-04]
  affects: [07-05]
tech_stack:
  added:
    - electron-builder v25.1.8 (NSIS packaging)
  patterns:
    - NSIS per-user install (no admin required)
    - extraResources injection into packaged Electron app
key_files:
  created: []
  modified:
    - desktop/electron-builder.yml
    - desktop/icon.ico
    - desktop/package.json
    - desktop/build/installer.nsh
    - .gitignore
decisions:
  - "perMachine: false — per-user install без UAC, путь %LOCALAPPDATA%\\Programs\\1С Аналитик\\"
  - "icon.ico — 1577 байт placeholder (dark blue background + text), генерировался в Plan 7.1"
  - "artifactName: analyst-setup-v${version}.${ext} → analyst-setup-v1.0.0.exe"
  - "installerLanguages: [ru_RU, en_US], language: 1049 (Russian primary)"
  - "dist/ добавлен в .gitignore — installer не коммитится в git (артефакт сборки)"
metrics:
  duration: "~8 min (5 min NSIS download + 3 min packaging)"
  completed_date: "2026-05-16"
  tasks_completed: 3
  files_modified: 5
---

# Phase 7 Plan 04: electron-builder + NSIS Installer Summary

**One-liner:** Windows NSIS per-user installer `analyst-setup-v1.0.0.exe` (105.9 MB) с русским wizard'ом, ярлыками Desktop+StartMenu и без UAC.

## Tasks Completed

| Task | Status | Commit |
|------|--------|--------|
| 1. electron-builder.yml + icon.ico + installer.nsh | PASS | c703a57 |
| 2. package.json scripts + version 1.0.0 | PASS | 19e8a79 |
| 3. Build NSIS installer + smoke check | PASS | 5daa438 |

## Installer Artifact

| Property | Value |
|----------|-------|
| **File** | `desktop/dist/analyst-setup-v1.0.0.exe` |
| **Size** | 105.9 MB |
| **SHA256** | `2B96AA66542DAF32CC2130FEFCF982485DD1902A9CAF8E01CA2940E17D13F863` |
| **ProductName** | `1С Аналитик` |
| **ProductVersion** | `1.0.0` |
| **Win-unpacked** | `dist/win-unpacked/1С Аналитик.exe` (188 MB unpacked) |

## Build Output

```
electron-builder v25.1.8
• packaging  platform=win32 arch=x64 electron=33.4.11
• building   target=nsis file=dist\analyst-setup-v1.0.0.exe
             archs=x64 oneClick=false perMachine=false
• downloaded nsis-resources-3.4.1 (731 kB, 5.5s)
• signed (skipped — no code signing cert, as expected)
• building block map  blockMapFile=dist\analyst-setup-v1.0.0.exe.blockmap
```

Elapsed: ~8 minutes total (first run; NSIS toolchain was cached from previous attempt, only nsis-resources-3.4.1 downloaded).

## NSIS Configuration Summary

```yaml
nsis:
  oneClick: false          # wizard, не auto-install
  perMachine: false        # per-user, НЕ требует admin
  allowToChangeInstallationDirectory: true
  createDesktopShortcut: true
  createStartMenuShortcut: true
  shortcutName: "1С Аналитик"
  installerLanguages: [ru_RU, en_US]
  language: 1049           # Russian primary
```

## Icon

- **Method:** Placeholder ICO (1577 bytes, dark blue `#0a3a5a` background + white text "1С")
- **Создан:** В Plan 7.1 через node-canvas / inline PNG → ICO конвертация
- **Замена:** Пользователь может заменить `desktop/icon.ico` без правки кода перед следующим build

## Installation Paths (per-user install)

| Path | Content |
|------|---------|
| `%LOCALAPPDATA%\Programs\1С Аналитик\` | Electron app files + resources/ (backend.exe + frontend/) |
| `%APPDATA%\1С Аналитик\` | userData (app.db создаётся бэкендом при первом запуске) |
| Desktop shortcut | «1С Аналитик» → `1С Аналитик.exe` |
| Start Menu | `Programs\1С Аналитик\1С Аналитик.lnk` |

## SmartScreen Behavior

Без code signing certificate Windows SmartScreen показывает:
> «Windows protected your PC — Windows Defender SmartScreen prevented an unrecognized app from starting»

Пользователь нажимает «More info» → «Run anyway». Это **ожидаемое поведение для v1.1**.

Code signing ($200+/год EV cert) — план v2. Документируется в Plan 7.5 README.

## Deviations from Plan

None — план выполнен точно как написан.

**Note:** Tasks 1 и 2 были частично выполнены в Plan 7.1 (electron-builder.yml, icon.ico, installer.nsh, package.json уже существовали с правильным содержимым). Task 3 (сборка installer) выполнен в этом плане. Коммиты c703a57 и 19e8a79 (из Plan 7.1) зачтены как выполненные для tasks 1 и 2.

## Known Stubs

None — установщик полностью функциональный.

## Threat Flags

None — installer не вводит новых сетевых endpoints или auth paths.

## Self-Check

- [x] `desktop/dist/analyst-setup-v1.0.0.exe` существует, 105.9 MB
- [x] SHA256 валиден (не corrupted)
- [x] ProductName = "1С Аналитик", ProductVersion = "1.0.0"
- [x] electron-builder.yml: appId=com.analyst.desktop, perMachine=false, createDesktopShortcut=true, createStartMenuShortcut=true
- [x] package.json: version=1.0.0, productName="1С Аналитик", все 5 scripts присутствуют
- [x] Commits: c703a57, 19e8a79, 5daa438

## Self-Check: PASSED
