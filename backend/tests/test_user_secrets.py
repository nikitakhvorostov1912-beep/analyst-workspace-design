"""Тесты для P2.1 backend-only API key storage.

Покрывает:
- crypto round-trip (encrypt → decrypt равно plaintext)
- store CRUD (save/get/delete/list)
- crypto не падает на разных длинах ключа
- decrypt с неверным app_secret → возвращает None из get_secret
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import aiosqlite
import pytest

from app.security.user_secrets_crypto import (
    decrypt_secret,
    encrypt_secret,
    get_or_create_app_secret,
    roundtrip,
)
from app.storage.user_secrets_store import (
    delete_secret,
    get_provider_ids_with_secret,
    get_secret,
    save_secret,
)

# ===== Crypto =====


class TestCrypto:
    def setup_method(self) -> None:
        """Делаем app_secret в tmp каталоге чтобы не загрязнять home."""
        self._tmpdir = tempfile.mkdtemp(prefix="user-secrets-")
        os.environ["APP_SECRET_PATH"] = str(Path(self._tmpdir) / ".app-secret")

    def teardown_method(self) -> None:
        del os.environ["APP_SECRET_PATH"]
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_get_or_create_returns_32_bytes(self) -> None:
        secret = get_or_create_app_secret()
        assert len(secret) == 32

    def test_get_or_create_is_idempotent(self) -> None:
        """Второй вызов читает тот же файл."""
        first = get_or_create_app_secret()
        second = get_or_create_app_secret()
        assert first == second

    def test_roundtrip_simple_key(self) -> None:
        assert roundtrip("sk-proj-abc123") == "sk-proj-abc123"

    def test_roundtrip_nvidia_key(self) -> None:
        assert roundtrip("nvapi-abcdef0123456789abcdef") == "nvapi-abcdef0123456789abcdef"

    def test_roundtrip_unicode(self) -> None:
        """Ключи иногда содержат не-ASCII (хотя редко)."""
        assert roundtrip("key-с-кириллицей-€") == "key-с-кириллицей-€"

    def test_encrypt_returns_different_ciphertext_each_call(self) -> None:
        """Nonce должен быть random — повторное шифрование того же plaintext
        даёт разный ciphertext (защита от replay)."""
        a = encrypt_secret("same-plaintext")
        b = encrypt_secret("same-plaintext")
        assert a.ciphertext != b.ciphertext
        assert a.nonce != b.nonce

    def test_decrypt_with_wrong_app_secret_raises(self) -> None:
        from cryptography.exceptions import InvalidTag

        encrypted = encrypt_secret("secret-value")
        wrong_secret = bytes(32)  # all zeros — невалидный, но 32 байта
        with pytest.raises(InvalidTag):
            decrypt_secret(encrypted, app_secret=wrong_secret)

    def test_encrypt_rejects_empty_string(self) -> None:
        with pytest.raises(ValueError):
            encrypt_secret("")


# ===== Store CRUD =====


@pytest.mark.asyncio
class TestUserSecretsStore:
    """Использует фикстуру `db` из conftest.py (in-memory SQLite + migrations)."""

    def setup_method(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="user-secrets-store-")
        os.environ["APP_SECRET_PATH"] = str(Path(self._tmpdir) / ".app-secret")

    def teardown_method(self) -> None:
        del os.environ["APP_SECRET_PATH"]
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    async def test_save_and_get_secret(self, db: aiosqlite.Connection) -> None:
        await save_secret(db, "nvidia-nim", "nvapi-test-key-12345")
        result = await get_secret(db, "nvidia-nim")
        assert result == "nvapi-test-key-12345"

    async def test_get_missing_provider_returns_none(self, db: aiosqlite.Connection) -> None:
        assert await get_secret(db, "non-existent-provider") is None

    async def test_save_upserts(self, db: aiosqlite.Connection) -> None:
        """Повторный save для того же provider — обновляет."""
        await save_secret(db, "openai", "sk-first")
        await save_secret(db, "openai", "sk-second")
        result = await get_secret(db, "openai")
        assert result == "sk-second"

    async def test_save_different_providers_independent(self, db: aiosqlite.Connection) -> None:
        await save_secret(db, "nvidia-nim", "nvapi-aaa")
        await save_secret(db, "cloud-ru-qwen3", "sk-bbb")
        assert await get_secret(db, "nvidia-nim") == "nvapi-aaa"
        assert await get_secret(db, "cloud-ru-qwen3") == "sk-bbb"

    async def test_delete_existing_returns_true(self, db: aiosqlite.Connection) -> None:
        await save_secret(db, "deepseek", "sk-deepseek")
        assert await delete_secret(db, "deepseek") is True
        assert await get_secret(db, "deepseek") is None

    async def test_delete_missing_returns_false(self, db: aiosqlite.Connection) -> None:
        assert await delete_secret(db, "never-saved") is False

    async def test_get_provider_ids_with_secret_lists_only_saved(
        self, db: aiosqlite.Connection
    ) -> None:
        await save_secret(db, "nvidia-nim", "nvapi-1")
        await save_secret(db, "cloud-ru-qwen3", "sk-2")
        ids = await get_provider_ids_with_secret(db)
        assert sorted(ids) == ["cloud-ru-qwen3", "nvidia-nim"]

    async def test_get_provider_ids_empty(self, db: aiosqlite.Connection) -> None:
        assert await get_provider_ids_with_secret(db) == []


# ===== Endpoint→provider_id detection =====


class TestProviderDetection:
    """_detect_provider_id из chat.py."""

    def test_cloud_ru_detected(self) -> None:
        from app.routes.chat import _detect_provider_id

        assert (
            _detect_provider_id("https://foundation-models.api.cloud.ru/v1")
            == "cloud-ru-qwen3"
        )

    def test_nvidia_detected(self) -> None:
        from app.routes.chat import _detect_provider_id

        assert (
            _detect_provider_id("https://integrate.api.nvidia.com/v1")
            == "nvidia-nim"
        )

    def test_openai_detected(self) -> None:
        from app.routes.chat import _detect_provider_id

        assert _detect_provider_id("https://api.openai.com/v1") == "openai"

    def test_unknown_returns_none(self) -> None:
        from app.routes.chat import _detect_provider_id

        assert _detect_provider_id("https://my-private-llm.local/v1") is None
        assert _detect_provider_id("") is None
