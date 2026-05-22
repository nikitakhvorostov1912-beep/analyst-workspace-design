"""AES-256 GCM шифрование для user_secrets (P2.1, 2026-05-23).

Зачем:
    В v1.2.x API-ключ LLM хранился в browser localStorage, что делало его
    уязвимым к XSS (один прорванный Markdown / Prism span → ключи всех
    пользователей). v1.3.0 переносит ключи на backend:
    - frontend POST'ит ключ → шифруется AES-256 GCM → пишется в user_secrets
    - frontend больше не видит ключ обратно (ни через GET, ни через header)
    - в chat-pipeline ключ расшифровывается, используется для LLM call,
      нигде не логируется

Ключ шифрования (app_secret):
    Генерируется один раз при первом запуске backend через `cryptography
    Fernet.generate_key()`-style 32-байтовое случайное число. Сохраняется
    в `<userData>/.app-secret` (Electron) или `~/.analyst-1c/.app-secret`
    (dev). При компрометации файла .app-secret — можно стереть, тогда
    user_secrets перешифровываются заново (пользователь введёт ключи
    повторно через UI).

Зависимость:
    `cryptography` lib (industry standard, FIPS-validated). При отсутствии
    модуль падает при импорте — production должен ставить через pip.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Hard-fail импорт. Если cryptography не установлен — secret-storage не работает.
# (Альтернатива через stdlib не достаточно безопасна для secrets.)
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Модуль cryptography не установлен. Добавьте в pyproject.toml "
        "и запустите `pip install -e .`. См. P2.1 в COMMERCE-PLAN-2026-05-23."
    ) from exc


# AES-GCM constants
_KEY_BYTES = 32  # AES-256
_NONCE_BYTES = 12  # GCM recommended nonce length
_APP_SECRET_FILENAME = ".app-secret"


@dataclass(frozen=True)
class EncryptedSecret:
    """Encrypted payload tuple для записи в user_secrets."""

    nonce: bytes
    ciphertext: bytes  # = AESGCM(key).encrypt(nonce, plaintext, None)


def _resolve_app_secret_path() -> Path:
    """Путь к файлу app_secret.

    Приоритет:
      1) env `APP_SECRET_PATH` — для тестов / явного override
      2) `<userData>/.app-secret` через USER_DATA_DIR env (Electron main.js
         задаёт перед спавном backend)
      3) `~/.analyst-1c/.app-secret` (dev fallback)
    """
    override = os.environ.get("APP_SECRET_PATH")
    if override:
        return Path(override).expanduser()
    user_data = os.environ.get("USER_DATA_DIR")
    if user_data:
        return Path(user_data) / _APP_SECRET_FILENAME
    return Path.home() / ".analyst-1c" / _APP_SECRET_FILENAME


def get_or_create_app_secret() -> bytes:
    """Возвращает 32-байтовый app_secret. Создаёт если не существует.

    File-locking не делаем — race condition при первом запуске unlikely
    (один backend на одну установку). При двойной записи файл будет
    overwritten одним из них, второй прочитает финальный — оба live ключи
    останутся валидны.
    """
    path = _resolve_app_secret_path()
    if path.exists():
        try:
            data = path.read_bytes()
            if len(data) == _KEY_BYTES:
                return data
            logger.warning(
                "app_secret имеет неправильную длину (%d ≠ %d), пересоздаю",
                len(data),
                _KEY_BYTES,
            )
        except OSError as exc:
            logger.warning("Не удалось прочитать app_secret: %s, пересоздаю", exc)

    path.parent.mkdir(parents=True, exist_ok=True)
    new_secret = secrets.token_bytes(_KEY_BYTES)
    # Атомарная запись через tmp + replace.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(new_secret)
    try:
        # Try to restrict permissions (best-effort, ignored on Windows ACL).
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    tmp.replace(path)
    logger.info("Создан новый app_secret в %s", path)
    return new_secret


def encrypt_secret(plaintext: str, app_secret: bytes | None = None) -> EncryptedSecret:
    """Шифрует строку (API-ключ) через AES-256 GCM.

    Args:
        plaintext: что шифруем (обычно ключ LLM провайдера).
        app_secret: 32-байтовый ключ. Если None — читается из файла.

    Returns:
        EncryptedSecret(nonce, ciphertext). Tuple хранится в БД отдельно
        в колонках nonce + api_key_encrypted.
    """
    if not isinstance(plaintext, str):
        raise TypeError("plaintext должен быть str")
    if not plaintext:
        raise ValueError("plaintext не может быть пустым")

    if app_secret is None:
        app_secret = get_or_create_app_secret()
    if len(app_secret) != _KEY_BYTES:
        raise ValueError(f"app_secret должен быть {_KEY_BYTES} байт, получено {len(app_secret)}")

    aesgcm = AESGCM(app_secret)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return EncryptedSecret(nonce=nonce, ciphertext=ciphertext)


def decrypt_secret(
    encrypted: EncryptedSecret,
    app_secret: bytes | None = None,
) -> str:
    """Расшифровывает EncryptedSecret обратно в строку.

    При повреждённом ciphertext / неверном nonce / неверном app_secret
    cryptography бросит InvalidTag — пробрасываем как есть, caller решит
    как реагировать (например, потребовать переввода ключа).
    """
    if app_secret is None:
        app_secret = get_or_create_app_secret()
    aesgcm = AESGCM(app_secret)
    plaintext_bytes = aesgcm.decrypt(encrypted.nonce, encrypted.ciphertext, None)
    return plaintext_bytes.decode("utf-8")


# ===== Convenience: round-trip helper для тестов =====


def roundtrip(plaintext: str) -> str:
    """Быстрая проверка: encrypt → decrypt должны вернуть исходное."""
    encrypted = encrypt_secret(plaintext)
    return decrypt_secret(encrypted)
