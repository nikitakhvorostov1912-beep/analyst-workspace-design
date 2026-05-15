// Пустой preload — renderer общается с backend напрямую через fetch.
// contextIsolation=true изолирует renderer от Node.js.
// Никакие contextBridge API не нужны для нашего use case.
