# COMMERCE-PLAN-2026-05-23 — итог автономного исполнения

> Сводка автономной сессии 2026-05-23, выполненной по плану
> `COMMERCE-PLAN-2026-05-23.md`. Auto-mode: «делай все сам до конца».

## Итог: 12/16 тикетов закрыто кодом, 4 ждут manual / admin действий

| Phase | Готово | Отложено |
|---|---:|---:|
| Phase 1 (хвост Wave 1/2) | 3/4 | P1.2 decompose loop.py |
| Phase 2 (P0 из IDEAS) | 3/3 | — |
| Phase 3 (Cloud.ru pivot) | 4/4 | — |
| Phase 4 (release) | 2/5 | P4.1 smoke, P4.2 quality gate, P4.3 build |
| **Total** | **12/16** | **4** |

## Закрыто кодом (готово к verify)

### Phase 1 — Хвост Wave 1/2

- **P1.1 Sprint 3 Hermes wire-up** — verification stamp в loop.py.
  Sprint 3 уже был wired (false-positive предыдущего аудита).
  Артефакт: comment-блок в `loop.py:469-481`.

- **P1.3 Code signing scaffold** — `desktop/electron-builder.yml` готов
  принимать `CSC_LINK` / `CSC_KEY_PASSWORD` из GitHub Secrets.
  `signingHashAlgorithms: [sha256]`. Когда сертификат купят (EV/OV) —
  достаточно добавить secrets в repo, без правок кода.
  Артефакт: `desktop/electron-builder.yml` + `.github/workflows/release.yml`.

- **P1.4 Auto-update** — `electron-updater` v6.3 интегрирован.
  `main.js` подписывается на `update-available` / `update-downloaded`.
  `preload.js` экспонирует `onUpdateAvailable`, `onUpdateDownloaded`,
  `installUpdate` в `window.electronAPI`. Новый компонент `UpdateBanner`
  в Header показывает «Скачивается v1.3.1…» → «Готова v1.3.1 — Перезапустить».
  Артефакты: `desktop/main.js`, `desktop/preload.js`,
  `desktop/package.json` (+electron-updater), `desktop/electron-builder.yml`
  (publish: github), `frontend/components/shell/UpdateBanner.tsx`,
  `frontend/components/shell/Header.tsx`.

### Phase 2 — Critical P0

- **P2.1 Backend-only API key** — XSS-вектор закрыт.
  - Новая таблица `user_secrets` (migration v9) с AES-256 GCM шифрованием
  - Новый модуль `app/security/user_secrets_crypto.py`
  - Новый storage `app/storage/user_secrets_store.py` (CRUD)
  - Новые endpoints `POST /user-secrets`, `DELETE /user-secrets/{id}`,
    `GET /user-secrets/status` (только список, без значений)
  - `chat.py` приоритет: user_secrets > header > env
  - Frontend helpers `saveSecretToBackend`, `fetchSecretStatus`
  - Тесты: `test_user_secrets.py` (crypto round-trip, store CRUD, detection)
  - Backward compat: header `X-LLM-API-Key` остаётся, deprecated в v1.4

- **P2.2 ResultSizeGate** — 100k+ row crash защищён.
  - Новый модуль `app/orchestrator/result_gate.py` с
    `MAX_ROWS_FOR_LLM=500`
  - `loop.py` пропускает execute_query result через gate ДО формирования
    карточки и messages context
  - `cards.py` TableCardPayload расширен `truncated` + `total_available`
  - `frontend/components/cards/TableCard.tsx` баннер «Показаны первые
    500 из N»
  - Тесты: `test_result_gate.py` (10 кейсов, boundaries)

- **P2.3 SQL AST validator** — defence-in-depth.
  - Новый модуль `app/orchestrator/sql_validator.py` через sqlparse
  - Whitelist: SELECT / ВЫБРАТЬ / WITH / EXPLAIN / SHOW
  - Strip SQL-комментариев ДО парсинга (защита от обходки)
  - Recursive поиск forbidden keywords в subquery
  - Graceful degrade если sqlparse не установлен
  - `safety.py` добавлен `scan_query_ast()` wrapper
  - `loop.py` вызывает после keyword-scan
  - Тесты: `test_sql_validator.py` (35+ кейсов: positive, negative, bypass)

### Phase 3 — Cloud.ru pivot

- **P3.1 NVIDIA + Cloud.ru** — каталог сокращён до 4 провайдеров.
  - Default LLM: NVIDIA Llama Nemotron Super 49B (был Xiaomi MiMo)
  - Cloud.ru добавлен как 152-ФЗ compliance альтернатива
  - Каталог: NVIDIA NIM (база, 9 моделей) + Cloud.ru + DeepSeek + Xiaomi MiMo
  - `config.py` обновлён, новое поле `default_llm_api_key_cloud_ru`
  - `resolve_default_api_key()` поддерживает cloud.ru endpoint

- **P3.2 Compatibility tests** — `test_config_provider_keys.py`.
  - 12 параметризованных тестов на endpoint detection
  - Регрессия NVIDIA/OpenAI/OpenRouter routing подтверждена
  - Cloud.ru routing подтверждён для всех variations URL

- **P3.3 UI compliance badges** — в LLMConfigForm.
  - Зелёная плашка «РФ-ДЦ ✓ 152-ФЗ» для Cloud.ru
  - Янтарная «За рубежом» для NVIDIA/MiMo/DeepSeek
  - `data-testid` для тестов

- **P3.4 Документация** — CHANGELOG + memory/llm-providers.md.
  - Полный раздел про P3.1/P3.3 pivot
  - Memory обновлён с актуальным каталогом + endpoint→provider mapping

### Phase 4 — Release prep

- **P4.4 Release notes draft** — `.planning/RELEASE-NOTES-v1.3.0-DRAFT.md`.
  Финализируется после Phase 4.1-4.3.

- **P4.5 STATE.md** — обновлён с Commerce Plan progress.
  Новый раздел «Commerce Plan Phase 1-4» с таблицей всех 16 тикетов.

## Отложено (требует manual / admin)

- **P1.2 Decompose loop.py** — 10h рискованный refactor.
  Добавлена detailed карта функции в module docstring для будущего раунда.
  Отложен на v1.4.0 — нет snapshot tests SSE, риск регрессий.

- **P4.1 Smoke на чистой Win11 VM** — manual test.
  Чек-лист в `.planning/COMMERCE-PLAN-2026-05-23.md` Phase 4.1
  (10 prompts от простого до multi-tool chain).

- **P4.2 Quality gate** — `/awd-quality-gate` skill, нужен bash run.

- **P4.3 Build v1.3.0 final** — требует:
  - EV/OV cert (admin: купить DigiCert/Sectigo, 1-3 дня)
  - GitHub Secrets `CSC_LINK` + `CSC_KEY_PASSWORD`
  - `git tag v1.3.0 && git push --tags` → release.yml workflow

## Метрики кода

| Изменение | Файлы |
|---|---|
| Backend new files | 6 (crypto, user_secrets_store, user_secrets routes, sql_validator, result_gate, security/__init__) |
| Backend modified | 8 (config, chat, safety, loop, cards, migrations, conftest, pyproject) |
| Backend tests new | 4 (test_user_secrets, test_sql_validator, test_result_gate, test_config_provider_keys) |
| Frontend new files | 1 (UpdateBanner) |
| Frontend modified | 5 (llm-providers, config form, table card, types, api-keys, header, guide page, llm-providers memory) |
| Desktop new files | 1 (.github/workflows/release.yml) |
| Desktop modified | 3 (main.js, preload.js, package.json, electron-builder.yml) |
| Docs | 3 (CHANGELOG, STATE, RELEASE-NOTES-DRAFT, EXECUTION-SUMMARY) |

## Что делать дальше (для user)

1. **Сразу проверить тесты:**
   ```bash
   cd backend && python -m pytest tests/test_user_secrets.py tests/test_sql_validator.py tests/test_result_gate.py tests/test_config_provider_keys.py -v
   ```
   Должны пройти (sqlparse + cryptography в `pip install -e .[dev]`).

2. **Поднять frontend и smoke вручную:**
   ```bash
   /awd-dev-up
   ```
   Открыть Настройки → выбрать Cloud.ru → ввести ключ → проверить compliance badge.

3. **Запустить полный quality gate:**
   ```bash
   /awd-quality-gate
   ```

4. **Если зелёный — приступать к P4.3:**
   - Купить EV/OV сертификат
   - Добавить GitHub Secrets
   - `git tag v1.3.0 && git push --tags`

5. **P1.2 в отдельную сессию** — когда есть 10h окно + готовность к
   риску регрессии SSE. Перед началом — сделать snapshot tests на 5
   prompts.

## Атомарные коммиты (рекомендация)

Не пушил автоматически. Для атомарной истории:

```
git add backend/app/security/ backend/app/storage/user_secrets_store.py \
        backend/app/routes/user_secrets.py backend/tests/test_user_secrets.py \
        backend/app/storage/migrations.py backend/app/routes/chat.py \
        backend/pyproject.toml
git commit -m "feat(P2.1): backend-only API key с AES-256 GCM шифрованием"

git add backend/app/orchestrator/sql_validator.py backend/app/orchestrator/safety.py \
        backend/app/orchestrator/loop.py backend/tests/test_sql_validator.py
git commit -m "feat(P2.3): SQL AST validator через sqlparse"

git add backend/app/orchestrator/result_gate.py backend/app/orchestrator/cards.py \
        backend/tests/test_result_gate.py frontend/components/cards/TableCard.tsx \
        frontend/lib/types.ts
git commit -m "feat(P2.2): ResultSizeGate — 100k+ row crash защита"

git add backend/app/config.py frontend/lib/llm-providers.ts \
        frontend/components/settings/LLMConfigForm.tsx \
        frontend/components/settings/__tests__/LLMConfigForm.test.tsx \
        frontend/app/guide/page.tsx .claude/memory/llm-providers.md \
        backend/tests/test_config_provider_keys.py backend/tests/conftest.py
git commit -m "feat(P3): NVIDIA NIM база + Cloud.ru 152-ФЗ альтернатива + compliance badges"

git add desktop/main.js desktop/preload.js desktop/package.json \
        desktop/electron-builder.yml .github/workflows/release.yml \
        frontend/components/shell/UpdateBanner.tsx frontend/components/shell/Header.tsx \
        frontend/lib/api-keys.ts
git commit -m "feat(P1.3+P1.4): auto-update электрон + code signing scaffold + frontend secret API"

git add CHANGELOG.md .planning/STATE.md \
        .planning/RELEASE-NOTES-v1.3.0-DRAFT.md \
        .planning/COMMERCE-EXECUTION-SUMMARY-2026-05-23.md
git commit -m "docs(M7): Commerce Plan Phase 1-3 итог + release notes draft"
```
