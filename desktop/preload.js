// contextIsolation=true изолирует renderer от Node.js. Через contextBridge
// пробрасываем минимальный API: открыть папку в Проводнике + listeners
// для auto-update (P1.4).
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Открыть путь (файл или папку) средствами ОС. Возвращает пустую строку
   * при успехе или сообщение об ошибке.
   * Из renderer: window.electronAPI.openPath('C:/path/to/folder')
   */
  openPath: (targetPath) => ipcRenderer.invoke('shell:open-path', targetPath),

  /**
   * P1.4 (2026-05-23): auto-update API.
   * Подписка на события electron-updater:
   *   updater:available → новая версия найдена (в info — version, releaseDate)
   *   updater:downloaded → installer скачан, готов к перезапуску
   * Вызов quitAndInstall — закрывает приложение, ставит обновление и
   * перезапускает с новой версией.
   *
   * Пример renderer:
   *   const cleanup = window.electronAPI.onUpdateDownloaded((info) => {
   *     // показать banner «Обновление готово — перезапустить»
   *   });
   *   // потом
   *   await window.electronAPI.installUpdate();
   */
  onUpdateAvailable: (callback) => {
    const handler = (_event, info) => {
      try { callback(info); } catch {}
    };
    ipcRenderer.on('updater:available', handler);
    return () => ipcRenderer.removeListener('updater:available', handler);
  },
  onUpdateDownloaded: (callback) => {
    const handler = (_event, info) => {
      try { callback(info); } catch {}
    };
    ipcRenderer.on('updater:downloaded', handler);
    return () => ipcRenderer.removeListener('updater:downloaded', handler);
  },
  installUpdate: () => ipcRenderer.invoke('updater:install'),
});
