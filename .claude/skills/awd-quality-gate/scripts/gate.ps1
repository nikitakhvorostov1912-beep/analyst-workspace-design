$ErrorActionPreference = 'Continue'

$root = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
$results = [ordered]@{}

# 1. Backend pytest
Push-Location (Join-Path $root 'backend')
$venvPytest = Join-Path (Get-Location) '.venv\Scripts\pytest.exe'
if (Test-Path $venvPytest) {
    & $venvPytest tests --tb=short -q 2>&1 | Out-Null
    $results['pytest'] = $LASTEXITCODE -eq 0
} else {
    Write-Warning "pytest not found in .venv — skipping"
    $results['pytest'] = $false
}
Pop-Location

# 2-3-4. Frontend
Push-Location (Join-Path $root 'frontend')

pnpm vitest run 2>&1 | Out-Null
$results['vitest'] = $LASTEXITCODE -eq 0

pnpm build 2>&1 | Out-Null
$results['build'] = $LASTEXITCODE -eq 0

pnpm playwright test --reporter=line 2>&1 | Out-Null
$results['playwright'] = $LASTEXITCODE -eq 0

Pop-Location

# Output
Write-Output ""
Write-Output "============================================"
Write-Output "  Quality Gate Results (analyst-workspace)"
Write-Output "============================================"
foreach ($k in $results.Keys) {
    $status = if ($results[$k]) { 'PASS' } else { 'FAIL' }
    Write-Output "  [$status]  $k"
}
$allOk = -not ($results.Values | Where-Object { -not $_ })
Write-Output "--------------------------------------------"
if ($allOk) {
    Write-Output "  OVERALL: PASS"
    Write-Output ""
    exit 0
} else {
    Write-Output "  OVERALL: FAIL"
    Write-Output ""
    exit 1
}
