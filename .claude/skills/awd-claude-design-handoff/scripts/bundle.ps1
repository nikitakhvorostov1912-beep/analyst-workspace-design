$ErrorActionPreference = 'Stop'

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
$ts = Get-Date -Format 'yyyyMMdd-HHmmss'
$bundleDir = Join-Path $root "temp\design-bundle-$ts"

New-Item -ItemType Directory -Path $bundleDir -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $bundleDir 'screenshots') -Force | Out-Null

# 1. Copy context files
$contextFiles = @(
    'CLAUDE.md',
    'PROJECT.md',
    'REQUIREMENTS.md'
)
foreach ($f in $contextFiles) {
    $src = Join-Path $root $f
    if (Test-Path $src) {
        Copy-Item $src $bundleDir
    }
}

$designConstraints = Join-Path $root '.claude\memory\design-constraints.md'
if (Test-Path $designConstraints) {
    Copy-Item $designConstraints $bundleDir
}

# 2. Verify servers up (call awd-dev-up if not)
$frontendUp = $false
try {
    $null = Invoke-WebRequest http://127.0.0.1:3010 -UseBasicParsing -TimeoutSec 2
    $frontendUp = $true
} catch {
    Write-Output "Frontend не отвечает — вызываю awd-dev-up..."
    $upScript = Join-Path $PSScriptRoot '..\..\awd-dev-up\scripts\up.ps1'
    & $upScript
    if ($LASTEXITCODE -eq 0) { $frontendUp = $true }
}

# 3. Playwright screenshots
if ($frontendUp) {
    $pwScript = Join-Path $bundleDir 'screenshot.mjs'
    @'
import { chromium } from "playwright";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const targets = [
  { url: "http://localhost:3010", path: "screenshots/01-main.png" },
  { url: "http://localhost:3010/settings", path: "screenshots/02-settings.png" },
  { url: "http://localhost:3010/status", path: "screenshots/03-status.png" },
];
for (const t of targets) {
  try {
    await page.goto(t.url, { waitUntil: "networkidle", timeout: 10000 });
    await page.screenshot({ path: t.path, fullPage: true });
    console.log("OK", t.path);
  } catch (e) {
    console.error("FAIL", t.url, e.message);
  }
}
await browser.close();
'@ | Out-File -FilePath $pwScript -Encoding UTF8

    Push-Location $bundleDir
    npx playwright install chromium 2>&1 | Out-Null
    node screenshot.mjs
    Pop-Location
} else {
    Write-Warning "Frontend недоступен — скриншоты пропущены"
}

# 4. PROMPT.md (verbatim из CLAUDE.md "не делать" + стек + референсы)
@'
# Промпт для Claude Design — 1С Аналитик v1.2.0

Итерируй UI этого приложения. Сохрани концепцию **«чат во главе»** — единственный workflow:
NL → LLM → tool_calls → cards.

## Стек (LOCKED — не предлагать другое)

Next.js 15 + React 19 + shadcn/ui + Tailwind 4 + IBM Plex Sans/Mono.
Тёмная тема by default. Русский UI. Desktop ≥ 1280px.

## Палитра v1.2.0 (тёмно-синий accent)

- Фон: #0a0a0a (root), #141414 (surface)
- Текст: #e5e5e5 (primary), #8a8a8a (muted)
- Accent: #3b82f6 (Tailwind blue-500)
- Borders: #1f1f1f (subtle), #2a2a2a (emphasis)
- Success/Warning/Error: #4ade80 / #fbbf24 / #f87171

## Что НЕ делать (verbatim из design-constraints.md)

- ❌ «Work-modes» Discovery/Triage/Investigate/Mapping/Knowledge — v0 mistake
- ❌ Object-centric IDE с tree метаданных слева — v0 mistake
- ❌ Workflow editor с карточками операций — v0b mistake
- ❌ AI right-rail с «инсайтами»
- ❌ Inter font, purple-cyan gradients, glass morphism, decorative emoji
- ❌ Mobile-first вёрстка (desktop only ≥ 1280px)
- ❌ Светлая тема как опция
- ❌ 8 экранов wizard в концепциях
- ❌ Накидывание 6+ LLM провайдеров в UI верхнего уровня

## Референсы (для inspiration)

Claude.ai · ChatGPT · Perplexity (НЕ Linear/Cursor/Hex/Notion)

## Контекст (приложены файлы)

- `CLAUDE.md` — общая концепция (chat-first, MCP-first)
- `PROJECT.md` — vision, personas, success criteria
- `REQUIREMENTS.md` — 22 v1 requirements
- `design-constraints.md` — все запреты verbatim
- `screenshots/` — текущий look (3 экрана)

## Задача

[Опиши конкретное изменение что хочешь итерировать]
'@ | Out-File -FilePath (Join-Path $bundleDir 'PROMPT.md') -Encoding UTF8

# 5. Summary output
Write-Output ""
Write-Output "============================================"
Write-Output "  Bundle создан"
Write-Output "============================================"
Write-Output "  Путь: $bundleDir"
Write-Output "  Файлов: $((Get-ChildItem $bundleDir -Recurse -File).Count)"
Write-Output ""
Write-Output "Открой claude.ai/design, перетащи папку, скопируй PROMPT.md"
Write-Output ""
