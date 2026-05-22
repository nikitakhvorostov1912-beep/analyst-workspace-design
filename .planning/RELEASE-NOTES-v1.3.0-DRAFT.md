# 1С Аналитик v1.3.0 — Commerce Readiness (draft, 2026-05-23)

> Draft release notes для финального git tag v1.3.0. После Phase 4 (smoke + build)
> финализируется в `1C-Analyst-v1.3.0/RELEASE-NOTES.md` + GitHub Release body.

## Главное

v1.3.0 — первая коммерчески-готовая версия продукта. Релиз закрывает 4
P0-уязвимости из глубокого ревью 2026-05-21/22, переходит на новый pivot LLM
провайдеров (NVIDIA NIM + Cloud.ru для 152-ФЗ) и подготавливает инфраструктуру
distribution (auto-update, code signing).

## Что нового для пользователя

### Безопасность

- **API-ключи теперь хранятся на сервере** (AES-256 GCM шифрование). Раньше
  ключ жил в `localStorage` браузера — один уязвимый скрипт мог утечь все
  пользовательские ключи. Теперь даже XSS через Markdown / Prism не открывает
  доступ к ключам.
- **SQL запросы проверяются дважды** перед отправкой в 1С: regex-сканер +
  AST-парсер (sqlparse). DELETE/UPDATE/INSERT/DROP/ALTER блокируются на уровне
  структуры запроса, даже если LLM «закодирует» их через комментарии или
  encoded строки.
- **Защита от 100k-row crash'ей.** Раньше большой `execute_query` (например,
  «дай все заказы за год») мог вернуть 50 MB JSON — LLM захлёбывалась, UI
  виснул. Теперь backend урезает результат до 500 строк перед отправкой в
  модель и UI. Карточка показывает баннер «Показаны первые 500 из N»,
  пользователь сужает запрос или скачивает CSV.

### LLM провайдеры

- **NVIDIA NIM (по умолчанию)** — один ключ покрывает 9 моделей: Llama
  Nemotron Super 49B (рекомендуется), DeepSeek R1/V3.1, Qwen3-Coder 480B,
  Llama 3.3 70B, Mistral Large 3 / Medium 3.5, Nemotron Nano 9B. Ключ
  встроен в installer — аналитик не вводит его руками.
- **Cloud.ru Foundation Models** — добавлен как 152-ФЗ compliance
  альтернатива (РФ-ДЦ, данные не пересекают границу). Бесплатный
  Qwen3-Coder-480B для корп-клиентов с jur-требованием.
- **Compliance badges** в Настройках: при выборе провайдера показывается
  «РФ-ДЦ ✓ 152-ФЗ» или «За рубежом — требует согласие». Админ видит риск
  до отправки данных в LLM.
- **Сокращён каталог** под коммерческую стратегию: NVIDIA, Cloud.ru, DeepSeek,
  Xiaomi MiMo. OpenAI/Anthropic/Groq/Mistral/Grok доступны через «Свой
  endpoint» по необходимости.

### Distribution

- **Auto-update**: после установки новой версии в GitHub Release аналитик
  получит уведомление прямо в Header («Готова v1.3.1 — Перезапустить»).
  Никаких ручных скачиваний — клик → перезапуск.
- **Code signing scaffold**: installer готов к подписи EV/OV сертификатом
  (когда сертификат купят — SmartScreen warning исчезнет).

### Self-Learning Hermes теперь реально работает

В v1.2.x был bug — модуль self-learning (skills, background_review) был
«wired» в коде но скрытая dependency `aux_compressor_client` создавалась
только если `compression_enabled=True`. Теперь зависимость развязана —
самообучение работает независимо от компрессии. End-to-end тест подтверждает:
2 похожих вопроса в одном канале → во втором turn `skills` block виден в
system prompt.

## Технические изменения

### Backend

- Новая таблица `user_secrets` (migration v9) с `app_secret`-шифрованием
- Новые endpoints `/user-secrets` (POST/DELETE, GET status — без раскрытия)
- Новый модуль `app/security/user_secrets_crypto.py` — AES-256 GCM wrapper
- Новый модуль `app/orchestrator/sql_validator.py` — sqlparse AST validation
- Новый модуль `app/orchestrator/result_gate.py` — row-level cap для LLM/UI
- Default LLM в `config.py` — NVIDIA Llama Nemotron Super 49B (было MiMo)
- `resolve_default_api_key` теперь поддерживает Cloud.ru endpoint
- `chat.py` приоритизирует ключ из БД (`user_secrets`) над header `X-LLM-API-Key`
- `cards.py` TableCardPayload расширен `truncated` + `total_available`

### Frontend

- `lib/llm-providers.ts` сокращён до NVIDIA/Cloud.ru/DeepSeek/MiMo, новое
  поле `ProviderCompliance` + дефолт переключён на Nemotron Super 49B
- `LLMConfigForm` показывает compliance badge рядом с провайдером
- `TableCard` показывает баннер «Показаны первые N из total_available»
  при `truncated=true`
- `lib/api-keys.ts` — новые helpers `saveSecretToBackend` + `fetchSecretStatus`
- `UpdateBanner` компонент в Header для auto-update UX
- `app/guide/page.tsx` обновлён под новый каталог провайдеров

### Desktop

- `electron-updater` v6.3 добавлен, интегрирован в `main.js`
- `preload.js` экспонирует `onUpdateAvailable`, `onUpdateDownloaded`,
  `installUpdate` в `window.electronAPI`
- `electron-builder.yml` — secrets-driven code signing + `publish: github`
- `.github/workflows/release.yml` — auto-build signed installer на git tag

## Migration guide

### Для аналитиков

Никаких действий. При первом запуске v1.3.0:
- Старые сессии и сообщения сохраняются.
- API-ключ из localStorage остаётся работать через backward-compat header
  до тех пор пока пользователь не введёт ключ заново через Настройки.
- Когда введён через UI — ключ автоматически переедет в backend AES-GCM
  storage.

### Для админов

- Обновить переменную окружения: добавить `DEFAULT_LLM_API_KEY_CLOUD_RU` если
  используется Cloud.ru для всех коллег.
- При первом запуске backend создаст `<userData>/.app-secret` (32 байта).
  **Бэкапить!** Без этого файла все user_secrets перестанут расшифровываться.
- В CI добавить GitHub Secrets:
  - `CSC_LINK` — base64 EV/OV cert (если есть)
  - `CSC_KEY_PASSWORD` — пароль PFX

## Технический долг (НЕ закрыт)

- **P1.2 Decompose loop.py** (10h) — God-функция 1222 строки. Отложен на v1.4.0,
  риск регрессий SSE-протокола без snapshot tests.
- **W2.6 Test coverage** — 26.58% на критичных модулях, цель 60%.
- **W2.5 E2E coverage** — 3/5 Playwright spec'ов skipped.
- **Multi-tenant per-channel isolation** — `INTERRUPTS`/`_pending`/`CLARIFY`
  глобальные, не per-channel.
- **152-ФЗ регистрация в реестре операторов ПД** — формальность под первого
  корп-клиента (Decision log #3 COMMERCE-PLAN-2026-05-23).
- **Presidio PII Shield** — нужен только если LLM не в РФ (Decision log #2).

## Decision log (зачем эти решения)

Полный — `.planning/COMMERCE-PLAN-2026-05-23.md` секция Decision log.
Топ-3 для будущих ревьюеров:

1. **NVIDIA NIM как база, Cloud.ru как 152-ФЗ альтернатива.** NVIDIA — один
   ключ покрывает 9 моделей, удобно для пилотов. Cloud.ru — путь для
   корп-клиентов которым нужен «не за границей» по jur-требованию.
2. **Хирургическая декомпозиция loop.py отложена.** Архитектурный rewrite
   30h vs 10h хирургия. На v1.3.0 решили НЕ трогать, чтобы не задерживать
   security/distribution фиксы.
3. **Backend-only API key вместо Presidio.** Если LLM в РФ — PII shield
   снижает риск, но не решает первопроблему (XSS уносил ключи). Сначала
   закрыли ключи, потом если нужно — Presidio добавим.

---

Финализируется после Phase 4 (Smoke VM + Build + Release).
