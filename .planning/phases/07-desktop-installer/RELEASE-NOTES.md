# Release Notes — v1.1.0 Desktop Installer (Windows)

**Date:** 2026-05-16
**Type:** Feature Release
**Tag:** v1.1.0

---

## What's New

### Phase 7: Desktop Installer (Windows)

1С Аналитик теперь доступен как **Windows installer** — аналитик больше не ставит Python, Node.js, Docker или pnpm.

- **`analyst-setup-v1.0.0.exe`** (105.9 MB) — NSIS installer, без административных прав
- **Ярлыки** Desktop + Start Menu «1С Аналитик» создаются автоматически
- **Electron wrapper** — окно приложения без cmd-консолей и внешних браузеров
- **PyInstaller backend** — Python 3.12 runtime + FastAPI + uvicorn embedded в один exe
- **Next.js standalone** — frontend запускается через Node.js без npm install
- **Auto-cleanup** — закрытие окна убивает все child процессы (SIGTERM + SIGKILL fallback)

### Ключевые технические решения

- Electron 33.x с random freeport (нет конфликтов с занятыми 8010/3010)
- `windowsHide: true` для обоих child-процессов — нет мелькания cmd-консолей
- `perMachine: false` (per-user install, установка в `%LOCALAPPDATA%\Programs\1С Аналитик\`)
- `ELECTRON_RUN_AS_NODE=1` для запуска Next.js server.js (без второго окна Electron)
- SQLite в `%APPDATA%\1С Аналитик\app.db` — пережил деинсталляцию (user data)
- Startup time: 5–8 сек на dev-машине (< 10 сек spec)

---

## Известные ограничения

1. **SmartScreen warning** — Windows показывает предупреждение при запуске installer. Нажать «Подробнее» → «Выполнить в любом случае». Причина: нет EV code signing certificate.
2. **Antivirus false-positive** — PyInstaller onefile может триггерить Kaspersky/ESET. Workaround: whitelist в корпоративном АВ.
3. **Dev machine smoke** — полный smoke выполнен на dev-машине. Чистая VM — рекомендована перед v2.

---

## Что вошло (vs v1.0)

| Component | v1.0 (docker) | v1.1.0 (desktop) |
|-----------|--------------|-----------------|
| Запуск | `docker compose up` | Двойной клик ярлыка |
| Python нужен аналитику | Да (или Docker) | Нет (embedded) |
| Node.js нужен аналитику | Да (или Docker) | Нет (embedded) |
| Installer | Нет | `analyst-setup-v1.0.0.exe` (105.9 MB) |
| Ярлык Desktop | Нет | Да |
| Start Menu | Нет | Да |

Веб-версия (docker compose) не удалена — работает параллельно.

---

## Артефакт

| Property | Value |
|----------|-------|
| Файл | `desktop/dist/analyst-setup-v1.0.0.exe` |
| Размер | 105.9 MB |
| SHA256 | 2B96AA66542DAF32CC2130FEFCF982485DD1902A9CAF8E01CA2940E17D13F863 |
| Electron | 33.4.11 |
| electron-builder | 25.1.8 |

---

## Roadmap v2

- Code signing EV certificate (убрать SmartScreen)
- Auto-update через electron-updater
- macOS / Linux installer
- Tray icon + minimize-to-tray
- Portable single-exe (без wizard)

---

*Phase 7 Plans: 07-01 (Electron), 07-02 (PyInstaller), 07-03 (Next standalone), 07-04 (NSIS), 07-05 (Verification)*
