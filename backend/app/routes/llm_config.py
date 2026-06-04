"""REST CRUD endpoints для LLM конфигурации: GET/POST/PATCH/DELETE /llm-config + POST /llm-config/test."""

import logging
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.clients.llm_provider_resolver import detect_provider_id
from app.config import get_settings
from app.models import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestRequest,
    LLMConfigTestResponse,
    LLMConfigUpdate,
)
from app.routes.connections import _validate_endpoint_ssrf
from app.storage.user_secrets_store import get_secret as get_user_secret

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm-config", tags=["llm-config"])

# Singleton id в БД. Таблица llm_settings имеет INTEGER PK.
# В рамках MVP используем id=1; в API-ответах возвращаем алиас "default".
_SINGLETON_ID = 1
_DEFAULT_ALIAS = "default"

# T-05-03: таймаут на исходящий httpx-запрос в test endpoint.
# 2026-05-23: поднят с 10s до 30s — NVIDIA NIM при cold start на больших MoE
# моделях (DeepSeek V4 Pro 1.6T, GLM-5.1, Mistral Large 3) первый запрос
# отвечает 12-25 секунд. 10s давало false-negative «timeout» на валидных ключах.
# 2026-05-24 (FINDING-15+): поднят 30s → 180s — после переключения дефолта
# на Nemotron Super 49B (warm) тяжёлые модели (DeepSeek V4 Pro 1.6T, MiniMax M2.7,
# Llama 4 Maverick) остались доступны как опции. Их cold-start доходит до 60-90s,
# и Тест в Settings должен дождаться ответа, иначе пользователь видит false
# negative и думает что модель сломана. 180s покрывает реальный cold-start.
_TEST_TIMEOUT_S = 180.0

# T-05-05: обрезаем error_message до 200 символов
_ERROR_MSG_MAX = 200


def _get_db(request: Request):
    return request.app.state.db


def _has_env_api_key_for(endpoint: str) -> bool:
    """True если backend имеет зашитый env-ключ для конкретного endpoint.

    Per-provider: для api.xiaomimimo.com → DEFAULT_LLM_API_KEY, для NVIDIA →
    DEFAULT_LLM_API_KEY_NVIDIA, и т.д. UI использует флаг чтобы не требовать
    ввод ключа когда подходящий ключ зашит в дистрибутиве.
    """
    return bool(get_settings().resolve_default_api_key(endpoint))


def _row_to_response(row: tuple) -> LLMConfigResponse:
    """Конвертирует строку SQLite (id, endpoint, model, temperature, updated_at) в LLMConfigResponse."""
    return LLMConfigResponse(
        id=_DEFAULT_ALIAS,
        endpoint=row[1],
        model=row[2],
        temperature=row[3],
        updated_at=row[4],
        has_env_api_key=_has_env_api_key_for(row[1]),
    )


@router.get("", response_model=LLMConfigResponse | None)
async def get_llm_config(request: Request) -> LLMConfigResponse | None:
    """Возвращает сохранённый LLM-конфиг или дефолт из settings.

    2026-05-24 (UX fix): если в БД пусто И в env есть зашитый ключ для
    дефолтного endpoint (NVIDIA NIM с DeepSeek V4 Flash из embedded.env) —
    возвращаем дефолтную конфигурацию вместо null. Это даёт «работа из
    коробки»: пользователь установил → подключил 1С базу → сразу
    отправляет запрос, без ручного выбора модели.

    Возвращает null только когда:
    - БД пуста И
    - env ключ для дефолтного endpoint НЕ зашит (нестандартная сборка)
    В этом случае frontend ведёт пользователя в onboarding для ручного
    ввода ключа.
    """
    db = _get_db(request)
    async with db.execute(
        "SELECT id, endpoint, model, temperature, updated_at FROM llm_settings WHERE id = ?",
        (_SINGLETON_ID,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is not None:
        return _row_to_response(row)

    # БД пуста — пробуем seed-default из settings (зашитый NVIDIA NIM).
    settings = get_settings()
    if _has_env_api_key_for(settings.default_llm_endpoint):
        return LLMConfigResponse(
            id=_DEFAULT_ALIAS,
            endpoint=settings.default_llm_endpoint,
            model=settings.default_llm_model,
            temperature=settings.default_llm_temperature,
            updated_at=None,
            has_env_api_key=True,
        )
    return None


@router.post("", response_model=LLMConfigResponse, status_code=201)
async def save_llm_config(
    body: LLMConfigCreate,
    request: Request,
) -> LLMConfigResponse:
    """UPSERT LLM-конфига (один профиль в MVP). API ключ не хранится."""
    db = _get_db(request)
    await db.execute(
        "INSERT OR REPLACE INTO llm_settings (id, endpoint, model, temperature, updated_at) "
        "VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
        (_SINGLETON_ID, body.endpoint, body.model, body.temperature),
    )
    await db.commit()

    async with db.execute(
        "SELECT id, endpoint, model, temperature, updated_at FROM llm_settings WHERE id = ?",
        (_SINGLETON_ID,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Ошибка сохранения LLM-конфига")

    return _row_to_response(row)


@router.patch("/{config_id}", response_model=LLMConfigResponse)
async def update_llm_config(
    config_id: str,
    body: LLMConfigUpdate,
    request: Request,
) -> LLMConfigResponse:
    """Частичное обновление LLM-конфига. config_id должен быть 'default'."""
    if config_id != _DEFAULT_ALIAS:
        raise HTTPException(status_code=404, detail=f"LLM-конфиг '{config_id}' не найден")

    db = _get_db(request)

    async with db.execute(
        "SELECT id FROM llm_settings WHERE id = ?",
        (_SINGLETON_ID,),
    ) as cursor:
        existing = await cursor.fetchone()

    if existing is None:
        raise HTTPException(status_code=404, detail="LLM-конфиг не найден")

    updates: dict[str, object] = {}
    if body.endpoint is not None:
        updates["endpoint"] = body.endpoint
    if body.model is not None:
        updates["model"] = body.model
    if body.temperature is not None:
        updates["temperature"] = body.temperature

    if updates:
        updates["updated_at"] = "CURRENT_TIMESTAMP"
        # updated_at — функция SQLite, не параметр; строим запрос отдельно
        set_parts = []
        values = []
        for k, v in updates.items():
            if k == "updated_at":
                set_parts.append("updated_at = CURRENT_TIMESTAMP")
            else:
                set_parts.append(f"{k} = ?")
                values.append(v)
        values.append(_SINGLETON_ID)
        set_clause = ", ".join(set_parts)
        await db.execute(
            f"UPDATE llm_settings SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

    async with db.execute(
        "SELECT id, endpoint, model, temperature, updated_at FROM llm_settings WHERE id = ?",
        (_SINGLETON_ID,),
    ) as cursor:
        row = await cursor.fetchone()

    return _row_to_response(row)


@router.delete("/{config_id}", status_code=204)
async def delete_llm_config(
    config_id: str,
    request: Request,
) -> None:
    """Удаляет LLM-конфиг. 204 при успехе, 404 если не найден или config_id != 'default'."""
    if config_id != _DEFAULT_ALIAS:
        raise HTTPException(status_code=404, detail=f"LLM-конфиг '{config_id}' не найден")

    db = _get_db(request)

    async with db.execute(
        "SELECT id FROM llm_settings WHERE id = ?",
        (_SINGLETON_ID,),
    ) as cursor:
        existing = await cursor.fetchone()

    if existing is None:
        raise HTTPException(status_code=404, detail="LLM-конфиг не найден")

    await db.execute("DELETE FROM llm_settings WHERE id = ?", (_SINGLETON_ID,))
    await db.commit()


@router.post("/test", response_model=LLMConfigTestResponse)
async def test_llm_config(
    body: LLMConfigTestRequest,
    request: Request,
    x_llm_api_key: Annotated[str | None, Header()] = None,
) -> LLMConfigTestResponse:
    """Валидирует LLM endpoint+model+ключ через 1-token completion.

    Резолв ключа (приоритет сверху-вниз, 2026-05-25):
        1. header `X-LLM-API-Key` — если фронт явно передал
        2. POST /user-secrets — backend-only AES-GCM ключ из БД
           (Фронт пишет через `saveSecretToBackend(provider_id, ...)`)
        3. env DEFAULT_LLM_API_KEY_* — embed-ключ из installer

    Раньше шага 2 не было, и тест после перезахода падал «invalid_key»
    даже если ключ был сохранён в `user_secrets` через POST /user-secrets.
    """
    started_at = time.monotonic()
    # B-01 (SSRF / OWASP API10): endpoint задаёт пользователь и backend делает
    # к нему исходящий httpx-запрос. Без этой проверки можно нацелить тест на
    # 169.254.169.254 (cloud metadata) / internal сервисы. Тот же guard, что на
    # POST /connections. Бросает HTTPException(400, unsafe_endpoint) до сетевого
    # вызова. Localhost (127.0.0.1) разрешён — как и для MCP.
    await _validate_endpoint_ssrf(body.endpoint)
    api_key = (x_llm_api_key or "").strip()
    if not api_key:
        # 2026-05-25: fallback на user_secrets — был только env-fallback,
        # из-за чего «Тест» в Settings после перезахода падал на 'invalid_key'
        # даже когда ключ зашифрован и лежит в БД.
        provider_id = detect_provider_id(body.endpoint)
        if provider_id:
            db = request.app.state.db
            try:
                stored = await get_user_secret(db, provider_id)
                if stored:
                    api_key = stored
            except Exception as exc:  # noqa: BLE001 — БД может быть недоступна
                logger.warning("get_user_secret(%s) failed in /llm-config/test: %s", provider_id, exc)
    if not api_key:
        api_key = get_settings().resolve_default_api_key(body.endpoint)
    if not api_key:
        return LLMConfigTestResponse(
            ok=False,
            error_code="invalid_key",
            error_message="API ключ не задан (ни через header, ни в user_secrets, ни в .env)",
            duration_ms=0,
        )

    try:
        endpoint = body.endpoint.rstrip("/")
        async with httpx.AsyncClient(timeout=_TEST_TIMEOUT_S) as http_client:
            response = await http_client.post(
                f"{endpoint}/chat/completions",
                json={
                    "model": body.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                    "temperature": 0.0,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
    except httpx.ConnectError as exc:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        return LLMConfigTestResponse(
            ok=False,
            error_code="network_error",
            error_message=str(exc)[:_ERROR_MSG_MAX],
            duration_ms=duration_ms,
        )
    except httpx.TimeoutException as exc:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        return LLMConfigTestResponse(
            ok=False,
            error_code="timeout",
            error_message=str(exc)[:_ERROR_MSG_MAX],
            duration_ms=duration_ms,
        )
    except ValueError as exc:
        duration_ms = int((time.monotonic() - started_at) * 1000)
        return LLMConfigTestResponse(
            ok=False,
            error_code="invalid_endpoint",
            error_message=str(exc)[:_ERROR_MSG_MAX],
            duration_ms=duration_ms,
        )

    duration_ms = int((time.monotonic() - started_at) * 1000)

    if response.status_code == 200:
        return LLMConfigTestResponse(ok=True, duration_ms=duration_ms)

    if response.status_code in (401, 403):
        return LLMConfigTestResponse(
            ok=False,
            error_code="invalid_key",
            error_message=f"HTTP {response.status_code}"[:_ERROR_MSG_MAX],
            duration_ms=duration_ms,
        )

    # 5xx и прочие коды
    return LLMConfigTestResponse(
        ok=False,
        error_code="server_error",
        error_message=f"HTTP {response.status_code}"[:_ERROR_MSG_MAX],
        duration_ms=duration_ms,
    )
