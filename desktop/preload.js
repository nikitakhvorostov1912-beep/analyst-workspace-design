// contextIsolation=true изолирует renderer от Node.js. Через contextBridge
// пробрасываем минимальный API — нужно только открывать папки в Проводнике
// (для кнопки «Открыть папку с логами» на /status).
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * Открыть путь (файл или папку) средствами ОС. Возвращает пустую строку
   * при успехе или сообщение об ошибке.
   * Из renderer: window.electronAPI.openPath('C:/path/to/folder')
   */
  openPath: (targetPath) => ipcRenderer.invoke('shell:open-path', targetPath),
});
