# Phase 9: Sessions DB Init — Context

**Gathered:** 2026-05-18
**Status:** Ready for planning
**Source:** MSG #10 — «все сесии записывались в базу банных которая будет связана с приложением нашим автоматом при установке»

<domain>
## Phase Boundary

**Что делает эта фаза:**
Привязывает SQLite БД сессий к Electron-приложению так, чтобы:
1. При установке через `.exe` БД автоматически создаётся в **правильном** месте (`%APPDATA%\1С Аналитик\app.db`)
2. Миграции прокатываются при первом запуске backend.exe
3. БД сохраняется при reinstall (userData не очищается NSIS-инсталлером)
4. Пользователь может **вручную сбросить** БД через Settings (privacy escape hatch)

**Текущее состояние (что есть):**
- ✅ Backend имеет миграции v1-v5 (из Phase 1-4)
- ✅ Backend.exe собирается через PyInstaller (Phase 7.2)
- ❌ Electron main.js НЕ выставляет `DATABASE_URL` → backend.exe пишет в **текущую** директорию (внутри resources/ или %TEMP% после --onefile extract)
- ❌ Нет smoke-теста install → uninstall → reinstall

**Outcome (для аналитика):**
1. Ставит `analyst-setup-v1.0.0.exe`
2. Запускает приложение → создаётся `%APPDATA%\1С Аналитик\app.db`
3. 5 сессий чата → данные в БД
4. Uninstall через Программы и компоненты → удаляются файлы приложения, но `%APPDATA%\1С Аналитик\` **остаётся**
5. Reinstall → запускает → старые 5 сессий видны в sidebar
6. В Settings нажимает «Сбросить локальную базу» → AlertDialog confirm → БД truncated → пустой sidebar

**Что НЕ доставляется:**
- Шифрование БД (SQLCipher) — Phase 11+ security task
- Cloud-sync БД между машинами одного пользователя — Out of Roadmap
- Multi-user одной БД — Out of Roadmap
</domain>

<decisions>
## Implementation Decisions

### Архитектура

```
┌──────────────────────────────────────┐
│ Electron main.js (1)                 │
│ const userDataDir = app.getPath(     │
│   'userData');                       │
│ const dbPath = path.join(            │
│   userDataDir, 'app.db');            │
│ process.env.DATABASE_URL =           │
│   `sqlite+aiosqlite:///`             │
│   + dbPath.replace(/\\/g, '/');      │
│ // ↓ spawn                           │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│ backend.exe (2)                      │
│ aiosqlite.connect(DATABASE_URL)      │
│ → создаёт файл если не существует    │
│ → миграции v1..v5 (idempotent)       │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│ Frontend (3)                         │
│ /sessions UI работает с DB через     │
│ backend HTTP API (как сейчас)        │
└──────────────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────┐
│ Settings → Сбросить локальную базу   │
│ POST /admin/reset-local-db           │
│ X-Confirm-Reset: true                │
│ → TRUNCATE messages, sessions,       │
│   tool_calls, anon_tokens,           │
│   metadata_cache, card_states        │
│ → llm_settings, connections          │
│   ОСТАВИТЬ (это не сессионные данные)│
└──────────────────────────────────────┘
```

### Что меняется в коде

**`desktop/main.js`** (Edit перед spawn backend):
```js
const path = require('path');
const userDataDir = app.getPath('userData');
const dbPath = path.join(userDataDir, 'app.db');

backendProc = spawn(backendExe, ['--port', String(backendPort)], {
  env: {
    ...process.env,
    BACKEND_PORT: String(backendPort),
    DATABASE_URL: `sqlite+aiosqlite:///${dbPath.replace(/\\/g, '/')}`,
  },
  windowsHide: true,
});
```

**`backend/app/config.py`** (Edit — приоритет env):
```python
class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    # env DATABASE_URL переопределяет default — уже работает через Pydantic Settings
```
(Если уже работает — verify; если нет — `model_config = SettingsConfigDict(env_prefix="", env_file=...)`)

**`backend/app/routes/admin.py`** (NEW):
```python
from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/reset-local-db")
async def reset_local_db(
    x_confirm_reset: str = Header(...),
    db: DB = Depends(get_db),
):
    if x_confirm_reset != "true":
        raise HTTPException(400, "Missing X-Confirm-Reset: true header")
    await db.execute("DELETE FROM messages")
    await db.execute("DELETE FROM sessions")
    await db.execute("DELETE FROM tool_calls")
    await db.execute("DELETE FROM anon_tokens")
    await db.execute("DELETE FROM metadata_cache")
    await db.execute("DELETE FROM card_states")
    # llm_settings, connections — сохраняются
    await db.commit()
    return {"status": "ok", "cleared": ["sessions", "messages", "tool_calls", "anon_tokens", "metadata_cache", "card_states"]}
```

**`backend/app/main.py`** — зарегистрировать router.

**`frontend/components/settings/LocalDataSection.tsx`** (NEW):
```tsx
"use client";
import { useState } from "react";
import { AlertDialog, ... } from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { resetLocalDb } from "@/lib/api";
import { toast } from "sonner";

export function LocalDataSection() {
  const [open, setOpen] = useState(false);
  async function handleReset() {
    const r = await resetLocalDb();
    if (r.ok) toast.success("Локальная база сброшена");
    else toast.error("Не удалось сбросить БД");
    setOpen(false);
  }
  return (
    <section>
      <h3>Локальные данные</h3>
      <p>Все сессии чата, токены анонимизации и кеш метаданных будут удалены. Настройки MCP и LLM сохранятся.</p>
      <Button variant="destructive" onClick={() => setOpen(true)}>Сбросить локальную базу</Button>
      <AlertDialog open={open} onOpenChange={setOpen}>...</AlertDialog>
    </section>
  );
}
```

**`frontend/lib/api.ts`** — добавить `resetLocalDb()`:
```ts
export async function resetLocalDb(): Promise<{ ok: boolean }> {
  const r = await fetch(`${BACKEND_URL}/admin/reset-local-db`, {
    method: "POST",
    headers: { "X-Confirm-Reset": "true" },
  });
  return { ok: r.ok };
}
```

### Open question — uninstall behavior

**Claude's discretion:** **БД остаётся** при uninstall.

Reason:
- NSIS по умолчанию не трогает `%APPDATA%\<AppName>\` — только удаляет программные файлы
- Пользователь может намеренно reinstall (обновление версии) — терять данные плохо UX
- Privacy escape hatch уже есть через UI (Settings → Сбросить)
- Если пользователь ХОЧЕТ полное удаление — может вручную удалить `%APPDATA%\1С Аналитик\`

Документация: в README раздел «Удаление приложения» с инструкцией ручного очищения.
</decisions>

<canonical_refs>
## Canonical References

### Project
- `phases/07-desktop-installer/07-CONTEXT.md` — Storage paths секция (упоминание userData) — продолжение этой идеи
- `phases/07-desktop-installer/07-04-SUMMARY.md` — electron-builder config (где сейчас perMachine=false)
- `backend/app/storage/db.py` — миграции v1-v5
- `backend/app/config.py` — Settings

### External
- Electron `app.getPath('userData')`: <https://www.electronjs.org/docs/latest/api/app#appgetpathname>
- NSIS appData cleanup: <https://nsis.sourceforge.io/Docs/Chapter4.html>
- aiosqlite connection: <https://aiosqlite.omnilib.dev/>
</canonical_refs>

<specifics>
## Specifics

### Smoke сценарий на чистой VM

```powershell
# 1. Pre-install: VM Windows 10 без Python/Node
Test-Path "$env:APPDATA\1С Аналитик\app.db"  # должно быть False

# 2. Install
Start-Process .\analyst-setup-v1.0.0.exe -Wait
Test-Path "C:\Users\<user>\AppData\Local\Programs\analyst-desktop"  # True
Test-Path "$env:APPDATA\1С Аналитик\app.db"  # ещё False до первого запуска

# 3. First launch
Start-Process "$env:USERPROFILE\Desktop\1С Аналитик.lnk"
Start-Sleep -Seconds 15
Test-Path "$env:APPDATA\1С Аналитик\app.db"  # True
(Get-Item "$env:APPDATA\1С Аналитик\app.db").Length  # > 0

# 4. Создать 3 сессии через UI (manual или Playwright)
# ... браузер ... 3 чата ...

# 5. Verify в БД
sqlite3 "$env:APPDATA\1С Аналитик\app.db" "SELECT COUNT(*) FROM sessions;"  # 3
sqlite3 "$env:APPDATA\1С Аналитик\app.db" "SELECT COUNT(*) FROM messages;"  # ≥ 6

# 6. Uninstall
Start-Process "$env:LOCALAPPDATA\Programs\analyst-desktop\Uninstall*.exe" -Wait
Test-Path "$env:LOCALAPPDATA\Programs\analyst-desktop"  # False
Test-Path "$env:APPDATA\1С Аналитик\app.db"  # ✅ True (важно!)

# 7. Reinstall
Start-Process .\analyst-setup-v1.0.0.exe -Wait
Start-Process "$env:USERPROFILE\Desktop\1С Аналитик.lnk"
Start-Sleep -Seconds 15

# 8. Verify сессии видны
# открыть приложение → sidebar → 3 сессии должны быть
sqlite3 "$env:APPDATA\1С Аналитик\app.db" "SELECT COUNT(*) FROM sessions;"  # всё ещё 3
```

### Caveat: PyInstaller --onefile extract

`backend.exe --onefile` распаковывает себя в `%TEMP%\_MEI*` при каждом запуске. Это **runtime extract**, не data. Наши данные — в `%APPDATA%`. Главное чтобы `DATABASE_URL` показывал на `%APPDATA%`, не на `%TEMP%` извлечённый путь.

### Caveat: Windows кириллица в путях

`%APPDATA%\1С Аналитик\` содержит кириллицу + non-ASCII. SQLite + Windows + Python ОК работают если использовать `path.replace(/\\/g, '/')` (forward slash) в `sqlite:///` URL. Тестируем явно.

### Caveat: миграции должны быть idempotent

`backend/app/storage/db.py` миграции v1..v5 уже idempotent через `CREATE TABLE IF NOT EXISTS` + `schema_version` tracking. Verify на новой БД — миграции прокатываются ровно один раз.
</specifics>

<deferred>
## Deferred (НЕ в Phase 9)

- SQLCipher шифрование БД — Phase 11+ security
- Cloud-sync (одна машина → другая) — Out of Roadmap
- Auto-backup БД (раз в день в `backups/`) — v1.3+
- Export БД целиком в JSON для миграции — v1.3+
- Pre-seed демо-данных при первой установке — отдельная фича для demos
</deferred>

---
*Phase: 09-sessions-db-init*
*Context gathered: 2026-05-18 — yolo mode, default: БД сохраняется при uninstall*
