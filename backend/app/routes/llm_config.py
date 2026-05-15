"""REST CRUD endpoints для LLM конфигурации: GET/POST/PATCH/DELETE /llm-config + POST /llm-config/test."""

import logging
import time
from typing import Annotated

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

from app.models import (
    LLMConfigCreate,
    LLMConfigResponse,
    LLMConfigTestRequest,
    LLMConfigTestResponse,
    LLMConfigUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/llm-config", tags=["llm-config"])

# Singleton id в БД. Таблица llm_settings имеет INTEGER PK.
# В рамках MVP используем id=1; в API-ответах возвращаем алиас "default".
_SINGLETON_ID = 1
_DEFAULT_ALIAS = "default"

# T-05-03: жёсткий таймаут на исходящий httpx-запрос в test endpoint
_TEST_TIMEOUT_S = 10.0

# T-05-05: обрезаем error_message до 200 символов
_ERROR_MSG_MAX = 200


def _get_db(request: Request):
    return request.app.state.db


def _row_to_response(row: tuple) -> LLMConfigResponse:
    """Конвертирует строку SQLite (id, endpoint, model, temperature, updated_at) в LLMConfigResponse."""
    return LLMConfigResponse(
        id=_DEFAULT_ALIAS,
        endpoint=row[1],
        model=row[2],
        temperature=row[3],
        updated_at=row[4],
    )


@router.get("", response_model=LLMConfigResponse | None)
async def get_llm_config(request: Request) -> LLMConfigResponse | None:
    """Возвращает сохранённый LLM-конфиг или null если не задан."""
    db = _get_db(request)
    async with db.execute(
        "SELECT id, endpoint, model, temperature, updated_at FROM llm_settings WHERE id = ?",
        (_SINGLETON_ID,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_response(row)


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
    x_llm_api_key: Annotated[str, Header()],
) -> LLMConfigTestResponse:
    """Валидирует LLM endpoint+model+ключ через 1-token completion.

    API ключ принимается только через header X-LLM-API-Key (T-05-04).
    Таймаут T-05-03: 10 секунд.
    error_message обрезается до 200 символов (T-05-05).
    """
    started_at = time.monotonic()

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
                    "Authorization": f"Bearer {x_llm_api_key}",
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
