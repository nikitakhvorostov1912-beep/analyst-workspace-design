$ErrorActionPreference = 'Stop'

# 1. Stop existing processes on :8010 / :3010 (if any)
Get-NetTCPConnection -LocalPort 8010, 3010 -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

# 2. Resolve project paths (4 levels up from this script: .claude/skills/awd-dev-up/scripts/)
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$venvPython = Join-Path $backendDir '.venv\Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
    Write-Error "FAIL: $venvPython not found. Run: cd backend && python -m venv .venv && .venv\Scripts\pip install -e ."
    exit 1
}

# 2b. Grounding prod DB = pilot.db (4 channels: typical-object cards + L2 graph).
# Backend default reads /data/app.db (no typical tables -> cards/graph/trace_typical_*
# are empty in chat). For the working product we point backend at pilot.db when present.
# Passed to the uvicorn child via env inheritance (Start-Process inherits parent $env).
# Durable: applied on every /awd-dev-up.
$pilotDb = Join-Path $root 'data\pilot.db'
if (Test-Path $pilotDb) {
    $env:DATABASE_URL = 'sqlite+aiosqlite:///' + ($pilotDb -replace '\\', '/')
    Write-Output "DB: pilot.db -> $($env:DATABASE_URL)"
} else {
    Write-Output "WARN: pilot.db not found ($pilotDb) - backend uses default DB (cards/graph will be empty)"
}

# 2c. Справочник BSL (bsl-context aux MCP) требует java. В dev нет bundled-JRE
# и java часто не в PATH -> _find_system_java() возвращает "" -> справочник не
# стартует ("не удалось запустить — ."). Пробрасываем JDK в backend через env
# (Settings.bsl_context_java читает BSL_CONTEXT_JAVA). Кандидаты -> PATH.
if (-not $env:BSL_CONTEXT_JAVA) {
    foreach ($jc in @('C:\CLOUDE_PR\tools\jdk-17\bin\java.exe', 'C:\CLOUDE_PR\tools\jdk-21\bin\java.exe')) {
        if (Test-Path $jc) { $env:BSL_CONTEXT_JAVA = $jc; break }
    }
    if (-not $env:BSL_CONTEXT_JAVA) {
        $sysJava = (Get-Command java -ErrorAction SilentlyContinue).Source
        if ($sysJava) { $env:BSL_CONTEXT_JAVA = $sysJava }
    }
}
if ($env:BSL_CONTEXT_JAVA) {
    Write-Output "JAVA: bsl-context -> $($env:BSL_CONTEXT_JAVA)"
} else {
    Write-Output "WARN: java не найден - Справочник BSL не подключится"
}

# 3. Start backend (background, hidden)
# БЕЗ --reload намеренно: uvicorn --reload на Windows => use_subprocess=True =>
# воркер получает SelectorEventLoop, который НЕ умеет asyncio subprocess
# (create_subprocess_exec -> NotImplementedError с пустым сообщением). Это
# ломает stdio-aux MCP (Справочник BSL / bsl-context). Без --reload на Windows
# uvicorn берёт ProactorEventLoop => subprocess работает. Prod (exe) тоже без
# --reload, так что dev=prod. Цена: нет hot-reload бэка (рестарт через /awd-dev-up).
Start-Process -FilePath $venvPython `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--port', '8010' `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden -PassThru | Out-Null

# 4. Start frontend (background, hidden) - npx via .cmd
$npxCmd = $null
$cmd = Get-Command npx.cmd -ErrorAction SilentlyContinue
if ($cmd) { $npxCmd = $cmd.Source }
if (-not $npxCmd) {
    $cmd2 = Get-Command npx -ErrorAction SilentlyContinue
    if ($cmd2) { $npxCmd = $cmd2.Source }
}
if (-not $npxCmd) {
    Write-Error "FAIL: npx not found. Install Node.js 22+"
    exit 1
}

Start-Process -FilePath $npxCmd `
    -ArgumentList 'next', 'dev', '-p', '3010' `
    -WorkingDirectory $frontendDir `
    -WindowStyle Hidden -PassThru | Out-Null

# 5. Poll for readiness (max 60s)
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 2
    try {
        $h = (Invoke-WebRequest http://127.0.0.1:8010/health -UseBasicParsing -TimeoutSec 2).Content
        $f = (Invoke-WebRequest http://127.0.0.1:3010 -UseBasicParsing -TimeoutSec 2).Content
        if ($h -match '"status"\s*:\s*"ok"' -and $f -match '<title>') {
            $ok = $true
            break
        }
    } catch {
        # Not ready yet - keep polling
    }
}

if ($ok) {
    Write-Output "PASS Backend:  http://127.0.0.1:8010"
    Write-Output "PASS Frontend: http://localhost:3010"
    exit 0
} else {
    Write-Error "FAIL: servers did not respond within 60s. Check backend/.venv and pnpm install."
    exit 1
}
