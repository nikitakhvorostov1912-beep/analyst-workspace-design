"""REST endpoints для backend-only хранения API-ключей (P2.1, 2026-05-23).

Маршруты:
    POST   /user-secrets               — upsert ключа провайдера
    DELETE /user-secrets/{provider_id} — удалить
    GET    /user-secrets/status        — список провайдеров с сохранёнными ключами

GET НЕ возвращает значение ключа. Это by design — UI знает только что «ключ
задан», но не может его прочитать (защита от XSS exfiltration).

При сохранении проверяем минимальную длину 12 символов (Hardcoded API key
shorter — почти наверняка некорректный).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.storage.user_secrets_store import (
    delete_secret,
    get_provider_ids_with_secret,
    save_secret,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user-secrets", tags=["user-secrets"])


class UserSecretCreate(BaseModel):
    """Body POST /user-secrets."""

    provider_id: str = Field(..., min_length=1, max_length=64)
    api_key: str = Field(..., min_length=12, max_length=512)


class UserSecretStatus(BaseModel):
    """Status report: какие провайдеры имеют сохранённые ключи."""

    providers: list[str]


def _get_db(request: Request):
    return request.app.state.db


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def save_user_secret(body: UserSecretCreate, request: Request) -> None:
    """Сохраняет (или обновляет) API-ключ провайдера. Тело ответа пустое."""
    db = _get_db(request)
    try:
        await save_secret(db, body.provider_id, body.api_key)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Не удалось сохранить user_secret")
        raise HTTPException(
            status_code=500, detail=f"Не удалось сохранить ключ: {type(exc).__name__}"
        ) from exc


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_secret(provider_id: str, request: Request) -> None:
    """Удаляет ключ. 404 если для provider_id ключа нет."""
    db = _get_db(request)
    existed = await delete_secret(db, provider_id)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Ключ для '{provider_id}' не найден")


@router.get("/status", response_model=UserSecretStatus)
async def get_status(request: Request) -> UserSecretStatus:
    """Возвращает список provider_id с сохранёнными ключами.

    Значения ключей НЕ раскрываются — это by design (XSS-защита).
    """
    db = _get_db(request)
    providers = await get_provider_ids_with_secret(db)
    return UserSecretStatus(providers=providers)
