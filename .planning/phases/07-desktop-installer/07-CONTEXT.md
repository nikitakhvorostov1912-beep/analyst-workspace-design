# Phase 7: Desktop Installer (Electron) — Context

**Gathered:** 2026-05-15
**Status:** Ready for planning
**Source:** Direct extraction (yolo) — пользователь явно сказал «Electron» после обсуждения Tauri vs Electron vs Inno Setup

<domain>
## Phase Boundary

**Что эта фаза делает:**
Превращает web-приложение (Phase 1-6: Python backend на :8010 + Next.js frontend на :3010, нужны установленные Python+Node+pnpm) в **standalone Windows desktop приложение**.

Аналитик получает один файл `analyst-setup-v1.0.exe` (~180 MB), кликает → ставится → на рабочем столе появляется ярлык «1С Аналитик» → двойной клик → открывается окно приложения (выглядит как нативное desktop). НЕ требует Python, Node, pnpm, Docker.

**Outcome (для аналитика):**
1. Скачал `analyst-setup-v1.0.exe` (~180 MB)
2. Двойной клик → "Установка 1С Аналитик" → "Далее" → "Установить" → "Готово"
3. На рабочем столе ярлык. Двойной клик → окно приложения с onboarding wizard.
4. Закрыл окно → процессы завершены, ничего в памяти не висит.

**Что НЕ доставляется в Phase 7:**
- macOS / Linux версии (только Windows для MVP, кросс-платформа в v2)
- Auto-update механизм (через electron-updater) — v2
- Code-signing certificate (Windows SmartScreen будет ругаться при первом запуске — Phase 7 v2)
- Trail в системном tray — v2
- Системные глобальные hotkeys — v2

</domain>

<decisions>
## Implementation Decisions

### Архитектура (3 слоя)

```
┌────────────────────────────────────────────────┐
│  Electron Main Process (Node.js)               │
│  - main.js: spawn backend + frontend           │
│  - waitFor /health 200 → open BrowserWindow    │
│  - on('close') → kill children                 │
└────────────────────────────────────────────────┘
           │ spawn                  │ spawn
           ▼                        ▼
┌──────────────────────┐  ┌──────────────────────┐
│ backend.exe          │  │ node server.js       │
│ (PyInstaller bundle) │  │ (Next.js standalone) │
│ FastAPI + Python 3.12│  │ port: random N+1     │
│ port: random N       │  │ env: BACKEND_URL=N   │
└──────────────────────┘  └──────────────────────┘
```

### Plan 7.1 — Electron main process

**Структура `desktop/`:**
```
desktop/
├── main.js           — Electron entry, spawn children, manage window
├── preload.js        — minimal preload (no node integration in renderer)
├── package.json      — electron + electron-builder зависимости
├── electron-builder.yml — build config
├── icon.ico          — иконка приложения (1С-стиль, тёмно-зелёный/синий)
├── resources/        — будет заполнен на build шаге
│   ├── backend.exe   ← из Plan 7.2
│   └── frontend/     ← из Plan 7.3 (Next standalone)
└── scripts/
    └── build-bundle.js — pre-build hook: PyInstaller + next build
```

**main.js логика:**
```js
const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const net = require('net');
const path = require('path');

let backendProc = null;
let frontendProc = null;
let mainWindow = null;

async function getFreePort() {
  return new Promise((resolve) => {
    const srv = net.createServer().listen(0, () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
  });
}

async function waitForUrl(url, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const r = await fetch(url);
      if (r.ok) return true;
    } catch {}
    await new Promise(r => setTimeout(r, 200));
  }
  return false;
}

app.whenReady().then(async () => {
  const backendPort = await getFreePort();
  const frontendPort = await getFreePort();

  // resourcesPath set by Electron at runtime
  const resourcesDir = app.isPackaged
    ? process.resourcesPath
    : path.join(__dirname, 'resources');

  // 1. Spawn backend
  const backendExe = path.join(resourcesDir, 'backend.exe');
  backendProc = spawn(backendExe, ['--port', String(backendPort)], {
    env: { ...process.env, BACKEND_PORT: String(backendPort) },
    windowsHide: true,
  });

  // 2. Spawn frontend (Next.js standalone)
  const serverJs = path.join(resourcesDir, 'frontend', 'server.js');
  frontendProc = spawn(process.execPath, [serverJs], {
    env: {
      ...process.env,
      PORT: String(frontendPort),
      HOSTNAME: '127.0.0.1',
      NEXT_PUBLIC_BACKEND_URL: `http://127.0.0.1:${backendPort}`,
      BACKEND_ALLOWED_ORIGINS: `http://127.0.0.1:${frontendPort}`,
    },
    cwd: path.dirname(serverJs),
    windowsHide: true,
  });

  // 3. Wait for both
  const ok = await waitForUrl(`http://127.0.0.1:${frontendPort}`, 30000);
  if (!ok) {
    // show error window
    return;
  }

  // 4. Open main window
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1280,
    minHeight: 768,
    backgroundColor: '#0a0a0f',
    title: '1С Аналитик',
    icon: path.join(__dirname, 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.removeMenu();
  mainWindow.loadURL(`http://127.0.0.1:${frontendPort}`);
});

function cleanup() {
  if (backendProc) { try { backendProc.kill('SIGTERM'); } catch {} }
  if (frontendProc) { try { frontendProc.kill('SIGTERM'); } catch {} }
  setTimeout(() => {
    if (backendProc) { try { backendProc.kill('SIGKILL'); } catch {} }
    if (frontendProc) { try { frontendProc.kill('SIGKILL'); } catch {} }
  }, 3000);
}

app.on('window-all-closed', () => {
  cleanup();
  if (process.platform !== 'darwin') app.quit();
});
app.on('before-quit', cleanup);
process.on('SIGINT', () => { cleanup(); process.exit(0); });
process.on('SIGTERM', () => { cleanup(); process.exit(0); });
```

**package.json desktop/:**
```json
{
  "name": "analyst-desktop",
  "version": "1.0.0",
  "description": "1С Аналитик — Desktop приложение",
  "main": "main.js",
  "scripts": {
    "dev": "electron .",
    "build": "node scripts/build-bundle.js && electron-builder --win"
  },
  "devDependencies": {
    "electron": "^33.0.0",
    "electron-builder": "^25.0.0"
  }
}
```

**preload.js — минимальный (security best practice):**
```js
// Empty — нет необходимости в IPC bridge для нашего use case
// (renderer общается с backend напрямую через fetch)
```

### Plan 7.2 — PyInstaller backend bundle

**`backend/build.spec`:**
```python
# PyInstaller spec для упаковки backend.exe
a = Analysis(
    ['app/main_cli.py'],  # NEW entry — wraps uvicorn programmatically
    pathex=['.'],
    binaries=[],
    datas=[
        ('app', 'app'),  # включаем весь пакет
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'aiosqlite',
        'sse_starlette',
        'pydantic',
        'pydantic_settings',
    ],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas,
    name='backend',
    console=False,  # No console window
    onefile=True,
    icon='../desktop/icon.ico',
)
```

**`backend/app/main_cli.py` (новый файл):**
```python
"""Entry-point for PyInstaller — embeds uvicorn invocation."""
import argparse
import uvicorn

from app.main import app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level='warning',
    )


if __name__ == '__main__':
    main()
```

**Build команда (для разработчика):**
```bash
cd backend
.venv\Scripts\activate
pip install pyinstaller
pyinstaller --clean --noconfirm build.spec
# → dist/backend.exe (~50 MB)
```

Verify: temporarily remove Python from PATH → `dist\backend.exe --port 9999` → `curl http://127.0.0.1:9999/health` → должно работать.

**Каверзы:**
- SQLite файл — backend пишет в текущую директорию через `DATABASE_URL`. Electron main выставляет `DATABASE_URL=sqlite+aiosqlite:///<userData>/app.db` (стандартная Electron app data dir).
- aiosqlite + pyinstaller иногда не находит native binary → hiddenimports выше + `--collect-all aiosqlite` если нужно.

### Plan 7.3 — Next.js standalone build

**Уже подготовлено** (config с env-флагом в `next.config.ts`):
```ts
...(process.env.NEXT_OUTPUT === "standalone" ? { output: "standalone" as const } : {}),
```

**Команда сборки:**
```bash
cd frontend
NEXT_OUTPUT=standalone pnpm build
# → frontend/.next/standalone/ + .next/static/

# Bundle для Electron resources:
node scripts/bundle-standalone.js
# - copies .next/standalone/frontend/* → desktop/resources/frontend/
# - copies .next/static → desktop/resources/frontend/.next/static
# - copies public/ → desktop/resources/frontend/public
```

**Каверза Windows + Tauri/standalone:** symlinks. Решение — copy вместо symlinks через `--config publicHoistPattern[]` в pnpm или через post-build node script.

### Plan 7.4 — electron-builder config

**`desktop/electron-builder.yml`:**
```yaml
appId: com.analyst.desktop
productName: 1С Аналитик
copyright: Copyright (c) 2026 analyst-workspace-design
artifactName: analyst-setup-v${version}.${ext}

directories:
  output: dist
  buildResources: build

files:
  - main.js
  - preload.js
  - package.json
  - "!**/.git"
  - "!**/.DS_Store"

extraResources:
  - from: resources
    to: .
    filter:
      - "**/*"

win:
  target:
    - target: nsis
      arch: [x64]
  icon: icon.ico
  publisherName: analyst-workspace-design

nsis:
  oneClick: false
  perMachine: false  # install per user, no admin required
  allowToChangeInstallationDirectory: true
  createDesktopShortcut: true
  createStartMenuShortcut: true
  shortcutName: 1С Аналитик
  installerLanguages: [ru_RU, en_US]
  language: 1049  # Russian
```

**Build команда:**
```bash
cd desktop
pnpm install
node scripts/build-bundle.js   # PyInstaller + next build + copy resources
pnpm dlx electron-builder build --win --x64
# → dist/analyst-setup-v1.0.exe (~180 MB)
```

### Plan 7.5 — Verification + release

**Manual smoke на чистой VM:**
1. Windows 10/11 без Python, Node, Docker, pnpm
2. Загрузить `analyst-setup-v1.0.exe` (через USB или скачать)
3. Двойной клик → NSIS wizard на русском
4. Выбрать путь установки → Установить → Готово
5. Двойной клик ярлыка «1С Аналитик» на Desktop
6. Окно открывается за < 10 сек, видна страница онбординга
7. Закрыть окно → проверить Task Manager → backend.exe и node.exe child процессы исчезли
8. Запустить ещё раз → работает

**README обновить** — добавить раздел «Скачать готовый Windows installer» с прямой ссылкой на GitHub Release.

### Stack additions (over Phase 6)

- **electron** (~120 MB на машине разработчика) — desktop wrapper
- **electron-builder** (~50 MB) — installer builder
- **pyinstaller** (~15 MB) — backend → exe
- В runtime/installer — всё уже встроено, аналитик ничего отдельно не ставит

### Out of scope для Phase 7

- macOS / Linux installers (только Windows для v1.1)
- Auto-update через electron-updater (v2)
- Code signing certificate (платно, $200/год) — без него Win SmartScreen будет ругаться при первом запуске
- Tray icon + системные hotkeys (v2)
- Auto-launch on system boot (v2)

### Claude's Discretion

- Иконка `.ico` — генерирую placeholder (текст «1С» на dark blue), пользователь может заменить позже
- NSIS language — русский primary
- Per-user install (не per-machine) — не требует админских прав. Большинство аналитиков не имеют admin
- Backend SQLite path — Electron's `app.getPath('userData')` → `%APPDATA%\1C-Analyst\app.db`
- При уже занятых портах (что-то другое слушает) — random freeport. main.js не привязан к 8010/3010

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project documentation
- `PROJECT.md`, `ARCHITECTURE.md`, `CLAUDE.md`
- `REQUIREMENTS.md` (DIST-01..05 добавлены)
- `ROADMAP.md` (Phase 7 секция)

### Phase 1-6 артефакты
- `.planning/phases/05-ux-polish/05-04-SUMMARY.md` — backend как source-of-truth, `fetchChat` signature with llm param
- `frontend/next.config.ts` — уже подготовлен `output: "standalone"` через env `NEXT_OUTPUT=standalone`
- `frontend/Dockerfile` — уже multi-stage с standalone build (reference для bundle логики)
- `backend/app/main.py` — FastAPI app instance
- `backend/app/config.py` — env-driven config (PORT, DATABASE_URL, BACKEND_ALLOWED_ORIGINS)

### External docs (для researcher если запустим)
- electron-builder NSIS: https://www.electron.build/configuration/nsis
- PyInstaller spec files: https://pyinstaller.org/en/stable/spec-files.html
- Next.js standalone: https://nextjs.org/docs/app/api-reference/config/next-config-js/output

</canonical_refs>

<specifics>
## Specific Ideas

### Storage paths (Electron managed)
```js
// main.js
const userDataDir = app.getPath('userData');
// → Windows: C:\Users\<user>\AppData\Roaming\1С Аналитик\

const dbPath = path.join(userDataDir, 'app.db');
process.env.DATABASE_URL = `sqlite+aiosqlite:///${dbPath.replace(/\\/g, '/')}`;
```

При первом запуске backend сам создаст таблицы через migrations.

### Build pipeline (один скрипт)

`desktop/scripts/build-bundle.js`:
```js
import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

const ROOT = path.resolve(__dirname, '..', '..');
const DESKTOP = path.resolve(__dirname, '..');
const RES = path.join(DESKTOP, 'resources');

// 1. PyInstaller backend
console.log('[1/3] Building backend.exe...');
execSync('python -m PyInstaller --clean --noconfirm build.spec', {
  cwd: path.join(ROOT, 'backend'),
  stdio: 'inherit',
});
fs.copyFileSync(
  path.join(ROOT, 'backend', 'dist', 'backend.exe'),
  path.join(RES, 'backend.exe'),
);

// 2. Next.js standalone
console.log('[2/3] Building Next.js standalone...');
execSync('pnpm build', {
  cwd: path.join(ROOT, 'frontend'),
  env: { ...process.env, NEXT_OUTPUT: 'standalone' },
  stdio: 'inherit',
});
// Copy standalone + static + public
const STANDALONE_SRC = path.join(ROOT, 'frontend', '.next', 'standalone', 'frontend');
const STATIC_SRC = path.join(ROOT, 'frontend', '.next', 'static');
const PUBLIC_SRC = path.join(ROOT, 'frontend', 'public');
const FE_DEST = path.join(RES, 'frontend');
fs.rmSync(FE_DEST, { recursive: true, force: true });
fs.cpSync(STANDALONE_SRC, FE_DEST, { recursive: true });
fs.cpSync(STATIC_SRC, path.join(FE_DEST, '.next', 'static'), { recursive: true });
if (fs.existsSync(PUBLIC_SRC)) {
  fs.cpSync(PUBLIC_SRC, path.join(FE_DEST, 'public'), { recursive: true });
}

console.log('[3/3] Resources ready. Run: pnpm dlx electron-builder --win');
```

### Caveat: Symlink на Windows для standalone

Next.js standalone использует symlinks для node_modules. На Windows без admin это падает.
**Решение:** В `build-bundle.js` использовать `fs.cpSync` с `{ recursive: true, dereference: true }` — копирует резолвлённые ссылки как файлы.

### Caveat: Window-hide для child процессов

Без `windowsHide: true` cmd окна backend.exe и node.exe будут моргать на старте. Обязательно.

### Caveat: backend.exe размер

PyInstaller `--onefile` создаёт self-extracting exe который при первом запуске распаковывает себя в `%TEMP%` (медленно, ~1-2 сек). Альтернатива — `--onedir` (быстрый запуск, но папка с кучей файлов). Для нашего случая `--onefile` лучше для упаковки в installer.

### Acceptance command (manual smoke)
```powershell
# На чистой Windows VM:
Start-Process .\analyst-setup-v1.0.exe -Wait
Get-Process | Where-Object {$_.Name -match "(backend|node|analyst)"} | Format-Table Name,Id,WorkingSet
# Должно показать: backend.exe + node.exe + 1С Аналитик (electron) после клика ярлыка

# После закрытия окна — повторить, должно быть пусто
```

</specifics>

<deferred>
## Deferred Ideas (НЕ в Phase 7)

- macOS / Linux installers — v2 (electron-builder поддерживает, но нужны Mac для подписи)
- Auto-update через electron-updater (требует publish endpoint, certificate) — v2
- Code signing для Win SmartScreen (~$200/год EV cert) — v2
- Tray icon + minimize-to-tray — v2
- Auto-launch on Windows boot — v2
- Системные hotkeys (Cmd+Shift+A открыть окно) — v2
- Multi-window support (два чата параллельно) — v2

</deferred>

---

*Phase: 07-desktop-installer*
*Context gathered: 2026-05-15 — yolo mode, after manual user redirect (Electron over .bat)*
