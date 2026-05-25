"""Резолвер `provider_id` из endpoint URL для fallback на user_secrets.

Зачем: API-ключи LLM сохраняются в `user_secrets` под именем provider_id
(`nvidia-nim`, `cloud-ru-qwen3`, `deepseek`, `xiaomi-mimo`). Если frontend
не передал ключ в header X-LLM-API-Key и env-fallback тоже пустой — backend
должен сам сходить в `user_secrets` по этому имени.

Каталог дублирует frontend `lib/llm-providers.ts` (поле `provider.id`).
Синхронизировать руками при добавлении новых провайдеров. Источник истины —
frontend, потому что именно его UI определяет под каким `provider_id`
сохраняется ключ через `saveSecretToBackend(provider_id, api_key)`.

Используется в:
    - `routes/chat.py` — основной поток отправки сообщения
    - `routes/llm_config.py` — тест ключа из Settings

Раньше этот mapping жил в `chat.py` под именем `_detect_provider_id`.
Вынесен в отдельный модуль 2026-05-25 чтобы `llm_config.py` мог тоже им
пользоваться без cross-route import'а.
"""

from __future__ import annotations

# Синхронизировано с `frontend/lib/llm-providers.ts` по состоянию 2026-05-25.
# Ключ — подстрока хоста (subdomain match), значение — provider_id.
# Subdomain match выбран потому что некоторые endpoints имеют разные пути
# на одном хосте (`/v1`, `/v1/chat/completions`), но host у них одинаковый.
_HOST_TO_PROVIDER: dict[str, str] = {
    "foundation-models.api.cloud.ru": "cloud-ru-qwen3",
    "integrate.api.nvidia.com": "nvidia-nim",
    "api.openai.com": "openai",
    "openrouter.ai": "openrouter",
    "api.deepseek.com": "deepseek",
    "api.xiaomimimo.com": "xiaomi-mimo",
    "api.groq.com": "groq",
    "api.mistral.ai": "mistral",
    "api.x.ai": "xai",
}


def detect_provider_id(endpoint: str | None) -> str | None:
    """Возвращает `provider_id` для известного провайдера или None для custom.

    None означает: «не из стандартного каталога, fallback на user_secrets
    по этому provider_id невозможен — frontend должен явно сохранить ключ
    под кастомным именем». Caller дальше пробует header / env fallback.
    """
    if not endpoint:
        return None
    lower = endpoint.lower()
    for host, provider_id in _HOST_TO_PROVIDER.items():
        if host in lower:
            return provider_id
    return None
