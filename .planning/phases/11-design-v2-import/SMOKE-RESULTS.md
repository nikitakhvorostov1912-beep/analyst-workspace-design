# Smoke Verification Results — analyst-setup-v1.2.0.exe

**Date:** 2026-05-18
**Phase:** 11 (Design v2 Import)
**Installer:** `desktop/dist/analyst-setup-v1.2.0.exe` (105.9 MB / 111,006,698 bytes)
**SHA256:** `E48673483123115B5EA3EA02C0BF091FF95E27B55650CC2B14C3BE7EC52564CB`

---

## Build artifacts

| Artifact | Size | Path |
|---|---|---|
| Installer | **105.9 MB** | `desktop/dist/analyst-setup-v1.2.0.exe` |
| Block map | 113 KB | `desktop/dist/analyst-setup-v1.2.0.exe.blockmap` |
| Unpacked dir | ~280 MB | `desktop/dist/win-unpacked/` |
| Backend exe | 14.6 MB | `desktop/resources/backend.exe` (внутри installer) |
| Frontend standalone | 60 MB | `desktop/resources/frontend/` (внутри installer) |

## Build environment

| Параметр | Значение |
|---|---|
| OS | Windows 10/11 (10.0.19043) |
| Node.js | 22.14.0 |
| pnpm | 10.33.2 |
| Python (build) | 3.11.9 (через `.venv-build`) |
| PyInstaller | 6.20.0 |
| Electron | 33.4.11 |
| electron-builder | 25.1.8 |
| NSIS | 3.0.4.1 + nsis-resources-3.4.1 |

## Build pipeline (chronological)

1. **PyInstaller** → `backend/dist/backend.exe` (14.6 MB) → copy → `desktop/resources/backend.exe`
2. **Next.js standalone build** (через temp `hoisted` pnpm linker, Windows symlink workaround) → `frontend/.next/standalone/`
3. **Copy** standalone + node_modules + .next/static + public → `desktop/resources/frontend/` (60 MB)
4. **electron-builder** packaging → `dist/win-unpacked/1С Аналитик.exe` + resources
5. **NSIS** target → `dist/analyst-setup-v1.2.0.exe` (105.9 MB)
6. **Block map** → `dist/analyst-setup-v1.2.0.exe.blockmap` (для differential update)

Build time: ~4-5 минут на dev-машине.

## Что внутри installer (v1.2.0)

Полный список изменений vs v1.1.0 → см. `RELEASE-NOTES.md` в этой папке.

Ключевое для smoke:
- Brand mark «1С» в accent-08 квадрате (Phase 11.3)
- Версия в header: `v1.2.0`
- AnonymizationToggle amber pill (Phase 11.3)
- ModelBadge Sparkles (Phase 11.3)
- Onboarding 4-step с Learn opt-in (Phase 11.3)
- 5 cards refactored через `<CardHeader/>` (Phase 11.4)
- ToolTrace mini chips + accordion (Phase 11.4)
- Streaming stages с иконками (Phase 11.4)
- animate-fade-up на mount cards (Phase 11.5)

## Smoke checklist для пользователя (manual)

После запуска installer:

- [ ] Установка через wizard на русском (ru_RU NSIS)
- [ ] perMachine=false → нет UAC prompt, ставится в `%LOCALAPPDATA%\Programs\1С Аналитик`
- [ ] Ярлык «1С Аналитик» на Desktop + Start Menu
- [ ] Клик → splash window → backend.exe старт на random порту → frontend на random порту
- [ ] Окно 1400×900 показывает Header с brand mark «1С» в синем квадрате
- [ ] Version chip показывает `v1.2.0`
- [ ] Onboarding (если первый запуск): 4 шага (MCP → LLM → Learn opt-in → Готово)
- [ ] AnonymizationToggle: переключение ВКЛ → amber pill (warning palette)
- [ ] ModelBadge: Sparkles + mono model name
- [ ] Channel selector: dropdown работает
- [ ] Закрытие окна → backend процесс корректно kill'ится (нет orphan)
- [ ] Uninstall через Control Panel → чистое удаление

## Известные ограничения

- **Не подписан** (`no signing info identified, signing is skipped`). Windows SmartScreen покажет «Неизвестный издатель» — нужно «Подробнее → Выполнить в любом случае» или RightClick → Properties → Unblock.
- **VM smoke не выполнен** на чистой Windows VM (без Python/Node/pnpm в системе). Phase 11 visual покрыт vitest 278/278 + Playwright design-v2 5/5, но full Electron stack на чистой VM — deferred → M6.
- **Signing certificate** — отсутствует. Off-band распространение через прямую передачу .exe файла.

## Прежний installer (v1.1.0) — оставлен для отката

`desktop/dist/analyst-setup-v1.0.0.exe` (106 MB, 16 мая 2026) — содержит v1.1.0 код. Не удалён — оставлен на случай если нужен откат к Phase 7 desktop bundle. Не путать с v1.2.0!

## Команда сборки (для воспроизведения)

```powershell
# Активировать venv-build для backend
$env:Path = "C:\CLOUDE_PR\projects\analyst-workspace-design\backend\.venv-build\Scripts;" + $env:Path

# Запустить полный pipeline
cd C:\CLOUDE_PR\projects\analyst-workspace-design\desktop
npm run build
# → dist/analyst-setup-v1.2.0.exe + dist/analyst-setup-v1.2.0.exe.blockmap
```
