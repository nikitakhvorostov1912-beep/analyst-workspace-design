# Distribution: Electron + auto-update (MSG #12)

## Цитата пользователя
> приложение мое может стоять у разных людей, мне важно чтобы оно было рабочее всегда, мб я как разрабочик смогу смогу выпускать обновения для них. Почему веб у нас же электрон приложение. ... Админ права будут

## Решено
- **Electron** — основной формат поставки (НЕ веб). Phase 7 уже сделана: `analyst-setup-v1.0.0.exe` 105.9 MB
- **Multi-user** — разные люди ставят на свои машины
- **Auto-update** — разработчик (Никита) выпускает обновления, у клиентов прилетает
- **Admin rights** — у пользователей админ права на их машинах есть

## Текущее состояние v1.1.0
- ✅ Electron skeleton (Phase 7.1)
- ✅ electron-builder + NSIS installer (Phase 7.4)
- ✅ Desktop+StartMenu shortcuts «1С Аналитик» (Phase 7.4)
- ✅ perMachine=false (no UAC при установке)
- ❌ **electron-updater автообновление** — не реализовано (open в backlog)
- ❌ **Code signing** — не реализовано (Windows SmartScreen warn)
