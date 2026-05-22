'use strict';

const { app, BrowserWindow, dialog, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const net = require('net');
const path = require('path');
const fs = require('fs');

// P1.4 (2026-05-23): electron-updater для auto-update.
// Опциональный require: если модуль не установлен (dev environment без npm i),
// auto-update просто не работает, остальное приложение функционирует.
let autoUpdater = null;
try {
  autoUpdater = require('electron-updater').autoUpdater;
} catch (err) {
  console.warn('[updater] electron-updater не установлен, auto-update отключён');
}

let backendProc = null;
let frontendProc = null;
let mainWindow = null;

// ------------------------------------------------------------
// Helpers
// ------------------------------------------------------------

function getFreePort() {
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
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  return false;
}

function resolveResourcesDir() {
  return app.isPackaged
    ? process.resourcesPath
    : path.join(__dirname, 'resources');
}

// ------------------------------------------------------------
// Cleanup
// ------------------------------------------------------------

function cleanup() {
  for (const proc of [backendProc, frontendProc]) {
    if (proc && !proc.killed) {
      try { proc.kill('SIGTERM'); } catch {}
    }
  }
  setTimeout(() => {
    for (const proc of [backendProc, frontendProc]) {
      if (proc && !proc.killed) {
        try { proc.kill('SIGKILL'); } catch {}
      }
    }
  }, 3000);
}

// ------------------------------------------------------------
// Main
// ------------------------------------------------------------

app.whenReady().then(async () => {
  const backendPort = await getFreePort();
  const frontendPort = await getFreePort();

  const resourcesDir = resolveResourcesDir();

  // Ensure userData directory exists (SQLite DB will live here)
  const userDataDir = app.getPath('userData');
  fs.mkdirSync(userDataDir, { recursive: true });

  // Forward slashes required for SQLite URL on all platforms
  const dbPath = path.join(userDataDir, 'app.db');
  const dbUrl = `sqlite+aiosqlite:///${dbPath.replace(/\\/g, '/')}`;

  // 1. Spawn backend.exe
  // cwd = resourcesDir, чтобы pydantic-settings нашёл `resources/.env` рядом
  // с backend.exe и подхватил оттуда DEFAULT_LLM_API_KEY (зашитый при сборке)
  // и другие seed-дефолты (DEFAULT_MCP_*, DEFAULT_LLM_*).
  const backendExe = path.join(resourcesDir, 'backend.exe');
  backendProc = spawn(
    backendExe,
    ['--port', String(backendPort)],
    {
      cwd: resourcesDir,
      env: {
        ...process.env,
        DATABASE_URL: dbUrl,
        BACKEND_ALLOWED_ORIGINS: `http://127.0.0.1:${frontendPort}`,
        LOG_LEVEL: 'WARNING',
        ENVIRONMENT: 'prod',
      },
      windowsHide: true,
    }
  );
  backendProc.on('exit', (code, signal) => {
    if (code !== 0 && code !== null) {
      console.error(`[backend] exited with code=${code} signal=${signal}`);
    }
  });

  // 2. Spawn frontend (Next.js standalone via ELECTRON_RUN_AS_NODE)
  // CRITICAL: ELECTRON_RUN_AS_NODE=1 makes electron.exe behave like node.
  // Without it, Electron would try to open a second window instead of running server.js.
  const serverJs = path.join(resourcesDir, 'frontend', 'server.js');
  frontendProc = spawn(
    process.execPath,
    [serverJs],
    {
      env: {
        ...process.env,
        ELECTRON_RUN_AS_NODE: '1',
        PORT: String(frontendPort),
        HOSTNAME: '127.0.0.1',
        NEXT_PUBLIC_BACKEND_URL: `http://127.0.0.1:${backendPort}`,
        NODE_ENV: 'production',
      },
      cwd: path.dirname(serverJs),
      windowsHide: true,
    }
  );
  frontendProc.on('exit', (code, signal) => {
    if (code !== 0 && code !== null) {
      console.error(`[frontend] exited with code=${code} signal=${signal}`);
    }
  });

  // 3. Wait for frontend to be ready (backend will be ready before first user request)
  const ok = await waitForUrl(`http://127.0.0.1:${frontendPort}`, 30000);
  if (!ok) {
    dialog.showErrorBox(
      'Ошибка запуска',
      'Frontend не ответил за 30 секунд. Проверьте логи или переустановите приложение.'
    );
    app.quit();
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
    // icon.ico will be created in Plan 7.4; Electron silently falls back to default if missing
    icon: path.join(__dirname, 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.removeMenu();
  mainWindow.loadURL(`http://127.0.0.1:${frontendPort}`);

  // P1.4 (2026-05-23): запускаем проверку обновлений через ~5 сек после
  // окна (даём UI прогреться). Не блокируем main flow если updater отсутствует
  // или GitHub недоступен — auto-update fallthrough.
  if (autoUpdater && app.isPackaged) {
    setTimeout(() => {
      try {
        // Логи updater'а в %APPDATA%/<productName>/logs/main.log для дебага.
        autoUpdater.logger = console;
        autoUpdater.autoDownload = true;
        autoUpdater.autoInstallOnAppQuit = true;

        autoUpdater.on('update-available', (info) => {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('updater:available', {
              version: info && info.version,
              releaseDate: info && info.releaseDate,
            });
          }
        });
        autoUpdater.on('update-downloaded', (info) => {
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('updater:downloaded', {
              version: info && info.version,
            });
          }
        });
        autoUpdater.on('error', (err) => {
          console.warn('[updater] error:', err && err.message);
        });

        autoUpdater.checkForUpdatesAndNotify().catch((err) => {
          console.warn('[updater] check failed:', err && err.message);
        });
      } catch (err) {
        console.warn('[updater] init failed:', err && err.message);
      }
    }, 5000);
  }
});

// P1.4: renderer triggers quit & install через preload IPC bridge.
// UI shows banner «Обновление готово — перезапустить», клик → этот хендлер
// → electron-updater закрывает приложение, ставит новую версию и
// автоматически запускает её.
ipcMain.handle('updater:install', () => {
  if (autoUpdater) {
    try {
      autoUpdater.quitAndInstall();
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err && err.message };
    }
  }
  return { ok: false, error: 'updater not available' };
});

// ------------------------------------------------------------
// IPC: открыть путь в Проводнике
// ------------------------------------------------------------
// Используется из /status — кнопка «Открыть папку с логами», чтобы коллега
// при репорте бага мог одним кликом достать backend.log. shell.openPath
// валидирует путь сам — переданный из renderer случайный путь не сломает
// контейнер (открывает максимум папку, которая не существует).
ipcMain.handle('shell:open-path', async (_event, targetPath) => {
  if (typeof targetPath !== 'string' || targetPath.length === 0) {
    return 'invalid path';
  }
  try {
    return await shell.openPath(targetPath);
  } catch (err) {
    return err && err.message ? err.message : 'open failed';
  }
});

// ------------------------------------------------------------
// Lifecycle hooks — all four required for DIST-05
// ------------------------------------------------------------

app.on('window-all-closed', () => {
  cleanup();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', cleanup);

process.on('SIGINT', () => { cleanup(); process.exit(0); });
process.on('SIGTERM', () => { cleanup(); process.exit(0); });
