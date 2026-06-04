"""Admin endpoints — privacy escape hatches.

Phase 9.1: POST /admin/reset-local-db — очищает все данные пользовательских
сессий (messages, sessions, card_states, metadata_cache), сохраняя настройки
подключений (mcp_connections) и LLM (llm_settings).

Requires explicit `X-Confirm-Reset: true` header to prevent accidental calls.

SEC-7 (M-K0, 2026-05-25): добавлен rate-limit 3/hour. Destructive endpoint
не должен вызываться часто — это backup/restore сценарий, не «нажми кнопку
если запутался». Защита от:
- автоматический re-trigger при UI-баге
- случайный double-submit (нажал кнопку, страница reload)
- worst-case: атакующий через ngrok/RDP / в корп-сети находит endpoint
  и пытается заDDoS-ить wipe operation.
"""

import logging
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

# SEC-7: используем тот же Limiter что и /chat — slowapi регистрирует один
# Limiter per app.state.limiter, разные эндпоинты вешают разные `limit(...)`
# на тот же инстанс. Это позволяет иметь @chat_limiter.limit("30/minute") на
# /chat и @chat_limiter.limit("3/hour") на /admin/reset-local-db
# без конфликтов и без двойной регистрации в main.py.
from app.routes.chat import chat_limiter
from app.storage.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# Список таблиц, которые очищаются при reset.
# Сохраняем: schema_version, mcp_connections, llm_settings.
RESET_TABLES: tuple[str, ...] = (
    "messages",
    "sessions",
    "card_states",
    "metadata_cache",
)


@router.post("/reset-local-db", status_code=status.HTTP_200_OK)
@chat_limiter.limit("3/hour")
async def reset_local_db(
    request: Request,  # slowapi key_func(remote_address) + B-05 localhost-guard
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
    x_confirm_reset: Annotated[
        str,
        Header(
            alias="X-Confirm-Reset",
            description="Должен быть 'true' для защиты от случайных вызовов",
        ),
    ],
) -> dict:
    """Очищает локальные данные сессий, сохраняя настройки подключений.

    Очищаются: messages, sessions, card_states, metadata_cache.
    Сохраняются: mcp_connections, llm_settings, schema_version.

    Rate-limit: 3 вызова в час с одного IP (SEC-7).

    Returns:
        {"status": "ok", "cleared": [список реально очищенных таблиц]}
    """
    # B-05 (audit, OWASP API5): endpoint без аутентификации (desktop single-user).
    # Defence-in-depth: разрешаем только с локальной машины. Если backend случайно
    # окажется доступен по сети (ngrok / LAN / RDP), удалённый клиент не сотрёт данные.
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="reset-local-db разрешён только с локальной машины (127.0.0.1)",
        )

    if x_confirm_reset != "true":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing or invalid X-Confirm-Reset header (must be 'true')",
        )

    cleared: list[str] = []
    for table in RESET_TABLES:
        try:
            await db.execute(f"DELETE FROM {table}")  # noqa: S608 — table from whitelist
            cleared.append(table)
        except Exception as exc:
            # Таблица может отсутствовать в старой БД (миграции не выполнены)
            logger.warning("reset_table_failed: %s (%s)", table, exc)

    await db.commit()
    logger.info("local_db_reset: cleared=%s", cleared)
    return {"status": "ok", "cleared": cleared}
