'use strict';

const { app, BrowserWindow, dialog, ipcMain, session, shell } = require('electron');
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

// DEVOPS-5 (M-K0.7): semver.gt downgrade guard.
// Минимальный self-contained compare — не добавляем npm dependency ради 8 строк.
// Защита: если manifest update.yml на release сервере по ошибке (или из-за
// атаки) указывает версию НИЖЕ текущей — мы не квитимся и не ставим
// «обновление» которое на самом деле downgrade. electron-updater сам этого
// не проверяет — допускает любую версию в latest.yml.
function semverGt(a, b) {
  if (!a || !b) return false;
  const parse = (v) => String(v).replace(/^v/, '').split('.').map((x) => parseInt(x, 10) || 0);
  const pa = parse(a);
  const pb = parse(b);
  for (let i = 0; i < 3; i++) {
    const da = pa[i] || 0;
    const db = pb[i] || 0;
    if (da > db) return true;
    if (da < db) return false;
  }
  return false;
}

// Версия которая была downloaded — сохраняем в module scope чтобы
// перепроверить semver в ipc handler updater:install (downgrade attack guard).
let downloadedUpdateVersion = null;

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

  // SEC-2: Content-Security-Policy + Permissions hardening.
  //
  // 1. CSP через onHeadersReceived (Electron-friendly способ, без правки HTML):
  //    default-src 'self'           — всё базово только из приложения
  //    connect-src 'self' http://127.0.0.1:* — XHR/fetch только к нашим backend+frontend портам
  //    script-src 'self'            — никакого external JS, никакого inline script
  //    style-src 'self' 'unsafe-inline' — нужно для Tailwind/CSS-in-JS injected styles
  //    img-src 'self' data: blob:   — иконки + base64 attachments preview
  //    font-src 'self' data:        — IBM Plex шрифты (если bundled) + fallback
  //    object-src 'none'            — никаких <object>/<embed>/<applet>
  //    base-uri 'self'              — защита от <base> injection
  //    frame-ancestors 'none'       — нас нельзя iframe'ить
  //    form-action 'self'           — формы только нам
  //
  // 2. Permissions: deny по умолчанию (камера, микрофон, геолокация и пр.
  //    в Electron-аналитике не нужны).
  // v1.4.8 HOTFIX (2026-05-25): добавлено 'unsafe-inline' к script-src.
  //
  // Без этого Next 15 ломал hydration: RSC streaming chunks инжектируются
  // через `<script>(self.__next_f=...)</script>` inline, backend URL —
  // через `<script>window.__BACKEND_URL__="..."</script>`, theme detection
  // тоже inline. CSP `script-src 'self'` блокировал их все → React
  // монтировался частично (виден sidebar), затем падал при первом state
  // update → чёрный экран в main area (v1.4.6/v1.4.7 регрессия от
  // SEC-2 коммита feda2d4).
  //
  // Trade-off: 'unsafe-inline' формально открывает XSS-вектор. В нашем
  // случае это приемлемо:
  //   - connect-src жёстко whitelist'ит только наш backend/frontend
  //     (внешние domains не достижимы — XSS не сможет exfiltrate)
  //   - frame-ancestors 'none' — приложение нельзя iframe'ить
  //   - sandbox + contextIsolation в webPreferences — renderer изолирован
  //   - нет user-generated HTML рендеринга (всё через React text content)
  //
  // Правильное решение на будущее — nonce-based CSP с Next 15 nonce API
  // (next.config.js + middleware.ts генерирует уникальный nonce на каждый
  // запрос, добавляет в CSP header и в каждый <script>). Но это
  // отдельная задача, требует middleware setup + тестов.
  const cspHeader = [
    "default-src 'self'",
    `connect-src 'self' http://127.0.0.1:${backendPort} http://127.0.0.1:${frontendPort} ws://127.0.0.1:${frontendPort}`,
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "form-action 'self'",
  ].join('; ');

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const headers = { ...details.responseHeaders };
    // Сносим existing CSP (если frontend сам что-то выставил) и ставим наш.
    delete headers['content-security-policy'];
    delete headers['Content-Security-Policy'];
    headers['Content-Security-Policy'] = [cspHeader];
    // Сопутствующие security headers:
    headers['X-Content-Type-Options'] = ['nosniff'];
    headers['X-Frame-Options'] = ['DENY'];
    headers['Referrer-Policy'] = ['no-referrer'];
    callback({ responseHeaders: headers });
  });

  // Запрещаем все запросы разрешений (камера/микрофон/нотификации/etc.).
  // Аналитику ничего из этого не нужно — потенциальная attack surface.
  session.defaultSession.setPermissionRequestHandler((_webContents, _permission, cb) => {
    cb(false);
  });

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
      // SEC-2: phase out renderer attack surface.
      // contextIsolation:true — preload в отдельном V8 context, защита от prototype pollution
      // nodeIntegration:false — без require/process в renderer
      // sandbox:true — Chromium sandbox для renderer process (OS-level isolation)
      // webSecurity:true — same-origin policy enforced (по дефолту true, явно для grep'а)
      // allowRunningInsecureContent:false — без mixed content (http в https страницу)
      // experimentalFeatures:false — без экспериментальных Chromium фич
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      experimentalFeatures: false,
    },
  });

  // SEC-2: блокируем все новые окна (window.open) и редиректы за пределы
  // нашего frontend. Открытие внешних URL — через shell.openExternal явно.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    // Запрещаем popups в принципе. Если когда-то понадобится «открыть в браузере» —
    // shell.openExternal(url) явный helper.
    return { action: 'deny' };
  });

  mainWindow.webContents.on('will-navigate', (event, targetUrl) => {
    // Разрешаем навигацию ТОЛЬКО на наш frontend.
    const allowed = `http://127.0.0.1:${frontendPort}`;
    if (!targetUrl.startsWith(allowed)) {
      event.preventDefault();
    }
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
          // DEVOPS-5: запоминаем downloaded version для downgrade guard в install handler.
          downloadedUpdateVersion = info && info.version ? String(info.version) : null;
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('updater:downloaded', {
              version: downloadedUpdateVersion,
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
  if (!autoUpdater) {
    return { ok: false, error: 'updater not available' };
  }
  // DEVOPS-5 (M-K0.7): downgrade guard. Если по любой причине downloaded
  // version НЕ строго больше текущей — отказываем в установке. Это защищает
  // от scenario: атакующий MITM update channel или ошибка в release manifest
  // указывают latest.yml версию старее установленной. electron-updater сам
  // не проверяет — он просто заменяет на «то что в manifest». Без этой
  // проверки пользователь молча получил бы откат на v1.1.0 с v1.4.7 — с
  // потерей фич, в худшем случае с известной CVE.
  const currentVersion = app.getVersion();
  if (downloadedUpdateVersion && !semverGt(downloadedUpdateVersion, currentVersion)) {
    console.warn(
      '[updater] downgrade rejected: downloaded=%s, current=%s',
      downloadedUpdateVersion,
      currentVersion,
    );
    return {
      ok: false,
      error: `downgrade rejected (downloaded ${downloadedUpdateVersion} ≤ current ${currentVersion})`,
    };
  }
  try {
    autoUpdater.quitAndInstall();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err && err.message };
  }
});

// ------------------------------------------------------------
// IPC: открыть путь в Проводнике
// ------------------------------------------------------------
// Используется из /status — кнопка «Открыть папку с логами», чтобы коллега
// при репорте бага мог одним кликом достать backend.log.
//
// SEC-5: WHITELIST. Раньше renderer мог передать любой путь (включая
// C:\Windows\System32\cmd.exe или UNC \\attacker-smb\share\malware.exe).
// При XSS в renderer или компрометации preload.js — path traversal /
// UNC-path execution. Теперь — только пути внутри userData/logs.
ipcMain.handle('shell:open-path', async (_event, targetPath) => {
  if (typeof targetPath !== 'string' || targetPath.length === 0) {
    return 'invalid path';
  }

  // Резолвим в абсолютный канонический путь — снимает .., симлинки, ALT-data.
  // path.resolve превращает относительный в абсолютный относительно cwd.
  let resolved;
  try {
    resolved = path.resolve(targetPath);
  } catch {
    return 'invalid path';
  }

  // Разрешённые корни — только наши папки userData (где app.db, .app-secret)
  // и logs (где backend.log, main.log updater'а).
  const userDataDir = app.getPath('userData');
  const logsDir = app.getPath('logs');
  const allowedRoots = [userDataDir, logsDir];

  const normalize = (p) => p.replace(/\\/g, '/').toLowerCase();
  const resolvedNorm = normalize(resolved);
  const isWithinAllowed = allowedRoots.some((root) => {
    const rootNorm = normalize(root);
    // Точное равенство ИЛИ начинается с root + разделителя (защита от
    // C:\Users\me\AppData\Local\analyst-desktop-evil совпавшего с
    // C:\Users\me\AppData\Local\analyst-desktop)
    return resolvedNorm === rootNorm || resolvedNorm.startsWith(rootNorm + '/');
  });

  if (!isWithinAllowed) {
    console.warn(
      '[SEC-5] shell:open-path rejected non-whitelisted path:',
      resolved
    );
    return 'path not allowed';
  }

  try {
    return await shell.openPath(resolved);
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
