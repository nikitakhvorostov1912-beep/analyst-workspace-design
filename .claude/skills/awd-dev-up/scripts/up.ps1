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

# 3. Start backend (background, hidden)
Start-Process -FilePath $venvPython `
    -ArgumentList '-m', 'uvicorn', 'app.main:app', '--reload', '--port', '8010' `
    -WorkingDirectory $backendDir `
    -WindowStyle Hidden -PassThru | Out-Null

# 4. Start frontend (background, hidden) — npx через .cmd
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
        # Not ready yet — keep polling
    }
}

if ($ok) {
    Write-Output "PASS Backend:  http://127.0.0.1:8010"
    Write-Output "PASS Frontend: http://localhost:3010"
    exit 0
} else {
    Write-Error "FAIL: серверы не отвечают за 60 сек. Проверь backend/.venv и pnpm install."
    exit 1
}
