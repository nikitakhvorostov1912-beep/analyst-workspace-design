"""CRUD для user_secrets (P2.1, 2026-05-23).

Backend-only хранение API-ключей LLM провайдеров. См.
`app/security/user_secrets_crypto.py` для деталей шифрования.

Контракт:
    - один ключ на provider_id (UNIQUE index в migrations.py V9)
    - upsert через ON CONFLICT REPLACE
    - read возвращает расшифрованный plaintext (or None)
    - delete возвращает True если строка существовала, False если no-op
    - get_provider_ids() возвращает список провайдеров с сохранёнными ключами
      (для UI отображения «✓ ключ задан»)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import aiosqlite

from app.security.user_secrets_crypto import (
    EncryptedSecret,
    decrypt_secret,
    encrypt_secret,
)

logger = logging.getLogger(__name__)


async def save_secret(
    db: aiosqlite.Connection,
    provider_id: str,
    api_key: str,
) -> None:
    """Сохраняет (или обновляет) ключ для провайдера. Не возвращает ключ.

    Раньше тут был INSERT OR REPLACE — но это сбрасывало created_at.
    Делаем явный upsert:
    """
    encrypted = encrypt_secret(api_key)

    # Проверка существования (для разделения created_at / updated_at)
    async with db.execute(
        "SELECT 1 FROM user_secrets WHERE provider_id = ?", (provider_id,)
    ) as cursor:
        existing = await cursor.fetchone()

    now = datetime.now(UTC).isoformat()
    if existing is None:
        await db.execute(
            "INSERT INTO user_secrets "
            "(provider_id, api_key_encrypted, nonce, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (provider_id, encrypted.ciphertext, encrypted.nonce, now, now),
        )
    else:
        await db.execute(
            "UPDATE user_secrets SET api_key_encrypted = ?, nonce = ?, updated_at = ? "
            "WHERE provider_id = ?",
            (encrypted.ciphertext, encrypted.nonce, now, provider_id),
        )
    await db.commit()


async def get_secret(
    db: aiosqlite.Connection,
    provider_id: str,
) -> str | None:
    """Возвращает расшифрованный ключ или None если для провайдера нет ключа.

    При InvalidTag (повреждённый шифр / неверный app_secret) логирует ошибку
    и возвращает None — caller интерпретирует как «нужно ввести ключ заново».
    """
    async with db.execute(
        "SELECT api_key_encrypted, nonce FROM user_secrets WHERE provider_id = ?",
        (provider_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        return None

    encrypted = EncryptedSecret(nonce=row[1], ciphertext=row[0])
    try:
        return decrypt_secret(encrypted)
    except Exception as exc:  # noqa: BLE001 — cryptography InvalidTag, ValueError
        logger.warning(
            "Не удалось расшифровать ключ для provider=%s: %s. "
            "Пользователь должен переввести ключ.",
            provider_id,
            type(exc).__name__,
        )
        return None


async def delete_secret(db: aiosqlite.Connection, provider_id: str) -> bool:
    """Удаляет ключ. Возвращает True если строка существовала."""
    async with db.execute(
        "SELECT 1 FROM user_secrets WHERE provider_id = ?", (provider_id,)
    ) as cursor:
        existed = (await cursor.fetchone()) is not None

    if existed:
        await db.execute(
            "DELETE FROM user_secrets WHERE provider_id = ?", (provider_id,)
        )
        await db.commit()

    return existed


async def get_provider_ids_with_secret(
    db: aiosqlite.Connection,
) -> list[str]:
    """Возвращает список provider_id для которых задан ключ.

    Используется UI чтобы показать badge «✓ ключ задан» рядом с провайдером
    без раскрытия самого ключа.
    """
    async with db.execute(
        "SELECT provider_id FROM user_secrets ORDER BY provider_id"
    ) as cursor:
        rows = await cursor.fetchall()
    return [row[0] for row in rows]
