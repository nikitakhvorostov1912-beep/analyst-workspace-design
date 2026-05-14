# GitHub Actions CI

Три джобы выполняются на каждый `pull_request` в `main` и на `push` в `main`.

## Джобы

| Джоба | Окружение | Шаги |
|-------|-----------|------|
| `backend` | Python 3.12 | ruff check → pytest --cov-fail-under=80 |
| `frontend` | Node 22 + pnpm | lint → type-check → vitest → build |
| `e2e` | Node 22 + pnpm + Chromium | playwright install → playwright test |

`e2e` запускается только после прохождения `backend` и `frontend` (needs).

## Запуск локально

```bash
# Backend тесты
cd backend
pip install -e .[dev]
python -m pytest -v --cov-fail-under=80

# Frontend unit тесты
cd frontend
pnpm install
pnpm lint && pnpm type-check && pnpm test --run && pnpm build

# E2E тесты (требует запущенный Next.js dev)
cd frontend
pnpm exec playwright install chromium  # без --with-deps для локальной установки
pnpm exec playwright test
```

## Traces при failure

При падении e2e джобы трейсы загружаются как artifact `playwright-traces`.
Для просмотра скачайте artifact из GitHub Actions UI и откройте через:

```bash
pnpm exec playwright show-trace trace.zip
```

## Что НЕ покрывается CI

- Smoke-тесты с реальной 1С базой — требуют ручной проверки
- Lighthouse / accessibility аудиты — запланировано v2
- Security scanning (CodeQL, Snyk) — запланировано v2
- Deploy в staging/prod — вне scope
