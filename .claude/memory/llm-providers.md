# LLM-провайдеры (MSG #11/12 + COMMERCE-PLAN-2026-05-23)

## Цитаты пользователя
> 1с это проект онли для 1с, ... все должно быть в приложении с возможностью подключения к разным моделям по апи
— MSG #11

> Я же явно сказал что это может быть любая можель которая рабочает через апи, в моем варианте это мимо от сяоми, локальные модели пока откинем
— MSG #12

## Решено

### Активный каталог (P3.1 rev2, 2026-05-23)

| Провайдер | Статус | endpoint | 152-ФЗ | embed key? |
|---|---|---|---|---|
| **NVIDIA NIM** | **default база** | `integrate.api.nvidia.com/v1` | ❌ | ✓ (вшит в installer) |
| **Cloud.ru Foundation Models** | 152-ФЗ альтернатива | `foundation-models.api.cloud.ru/v1` | ✓ РФ-ДЦ | ❌ (per-company) |
| DeepSeek (прямой) | дешёвый китайский | `api.deepseek.com/v1` | ❌ | ❌ |
| Xiaomi MiMo (китайский) | дешёвый bargain | `api.xiaomimimo.com/v1` | ❌ | ❌ |

### Compliance флаги

UI badge `compliance: { russian_dc, fz152 }` (P3.3) — зелёная «РФ-ДЦ ✓ 152-ФЗ»
для Cloud.ru, янтарная «За рубежом» для остальных.

### Убрано из UI dropdown (доступно через «Свой endpoint»)

- OpenAI direct (`api.openai.com/v1`)
- Anthropic Claude через OpenRouter
- OpenRouter (Gemini/Llama прочее)
- Groq
- Mistral direct
- xAI Grok

### Ollama / локальные модели

NO — «откинем пока» (MSG #12). Если когда-то — Phase 12+, через универсальный
custom endpoint (OpenAI-compat).

## Текущее состояние

- **Default LLM** — `nvidia/llama-3.3-nemotron-super-49b-v1.5` (Llama Nemotron Super 49B).
  Цель: один зашитый ключ + широкий каталог моделей платформы NIM.
- **152-ФЗ путь** — Cloud.ru Foundation Models, `Qwen/Qwen3-Coder-480B-A35B-Instruct`.
- **Backend env-key fallback** через `resolve_default_api_key(endpoint)`:
  - `cloud.ru` → `DEFAULT_LLM_API_KEY_CLOUD_RU`
  - `nvidia.com` → `DEFAULT_LLM_API_KEY_NVIDIA`
  - `api.openai.com` → `DEFAULT_LLM_API_KEY_OPENAI`
  - `openrouter.ai` → `DEFAULT_LLM_API_KEY_OPENROUTER`
  - прочие → `DEFAULT_LLM_API_KEY` (универсальный)
- **API ключи** — sessionStorage browser (P2.1 готовит переезд на backend `user_secrets`
  с AES-256 GCM, защита от XSS).
