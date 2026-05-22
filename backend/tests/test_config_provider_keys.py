"""Тесты resolve_default_api_key — корректный per-provider env-fallback.

P3.1/P3.2 (2026-05-23): после добавления Cloud.ru как 152-ФЗ альтернативы
проверяем что endpoint detection срабатывает на новый домен и не ломает
существующие маршруты (NVIDIA / OpenAI / OpenRouter / прочие).
"""

from __future__ import annotations

import pytest

from app.config import Settings


def _settings(**overrides) -> Settings:
    """Создаёт Settings с пустыми ключами + явными override."""
    base = {
        "default_llm_api_key": "",
        "default_llm_api_key_nvidia": "",
        "default_llm_api_key_openai": "",
        "default_llm_api_key_openrouter": "",
        "default_llm_api_key_cloud_ru": "",
    }
    base.update(overrides)
    return Settings(**base)


class TestResolveDefaultApiKey:
    """resolve_default_api_key подбирает ключ по endpoint."""

    def test_empty_endpoint_returns_universal_key(self) -> None:
        s = _settings(default_llm_api_key="universal-fallback")
        assert s.resolve_default_api_key("") == "universal-fallback"

    def test_cloud_ru_endpoint_uses_cloud_ru_key(self) -> None:
        s = _settings(default_llm_api_key_cloud_ru="cloud-key-123")
        assert (
            s.resolve_default_api_key("https://foundation-models.api.cloud.ru/v1")
            == "cloud-key-123"
        )

    def test_cloud_ru_subdomain_variations(self) -> None:
        """Любой URL с cloud.ru хост-частью попадает на cloud_ru-ключ."""
        s = _settings(default_llm_api_key_cloud_ru="cloud-key-123")
        # endpoint может быть с разными путями/портами — главное хост
        assert s.resolve_default_api_key("https://foundation-models.api.cloud.ru/v1/chat") == "cloud-key-123"
        assert s.resolve_default_api_key("https://api.cloud.ru/v2") == "cloud-key-123"

    def test_cloud_ru_falls_back_to_universal_when_specific_empty(self) -> None:
        """Если default_llm_api_key_cloud_ru пуст — берётся универсальный."""
        s = _settings(default_llm_api_key="universal-fallback")
        # cloud_ru ключ пуст → falls back на universal
        assert (
            s.resolve_default_api_key("https://foundation-models.api.cloud.ru/v1")
            == "universal-fallback"
        )

    def test_nvidia_endpoint_unchanged_after_cloud_ru_added(self) -> None:
        """Регрессия: после добавления Cloud.ru NVIDIA-routing не сломан."""
        s = _settings(
            default_llm_api_key_nvidia="nvapi-456",
            default_llm_api_key_cloud_ru="cloud-key-123",
        )
        assert (
            s.resolve_default_api_key("https://integrate.api.nvidia.com/v1")
            == "nvapi-456"
        )

    def test_openai_endpoint_unchanged(self) -> None:
        s = _settings(default_llm_api_key_openai="sk-openai")
        assert s.resolve_default_api_key("https://api.openai.com/v1") == "sk-openai"

    def test_openrouter_endpoint_unchanged(self) -> None:
        s = _settings(default_llm_api_key_openrouter="sk-or-v1")
        assert (
            s.resolve_default_api_key("https://openrouter.ai/api/v1") == "sk-or-v1"
        )

    def test_mimo_uses_universal(self) -> None:
        """MiMo читает универсальный ключ (исторически — backwards-compat)."""
        s = _settings(default_llm_api_key="mimo-key")
        assert s.resolve_default_api_key("https://api.xiaomimimo.com/v1") == "mimo-key"

    def test_endpoint_case_insensitive(self) -> None:
        """resolve_default_api_key игнорирует регистр в URL."""
        s = _settings(default_llm_api_key_cloud_ru="cloud-key-123")
        assert (
            s.resolve_default_api_key("https://Foundation-Models.API.Cloud.RU/v1")
            == "cloud-key-123"
        )

    def test_priority_order_specific_over_universal(self) -> None:
        """Когда есть и универсальный, и specific — берётся specific."""
        s = _settings(
            default_llm_api_key="universal-fallback",
            default_llm_api_key_cloud_ru="cloud-specific",
        )
        assert (
            s.resolve_default_api_key("https://foundation-models.api.cloud.ru/v1")
            == "cloud-specific"
        )


class TestDefaultEndpointAndModel:
    """Проверка что P3.1 rev3 дефолты — NVIDIA NIM DeepSeek V4 Flash.

    Endpoint остался NVIDIA, поменялась только модель (rev2 → rev3 пивот
    моделей весны 2026 после web search 22.05.2026).
    """

    def test_default_endpoint_is_nvidia_nim(self) -> None:
        s = _settings()
        assert s.default_llm_endpoint == "https://integrate.api.nvidia.com/v1"

    def test_default_model_is_deepseek_v4_flash(self) -> None:
        """P3.1 rev3: дефолтная модель — DeepSeek V4 Flash через NVIDIA NIM."""
        s = _settings()
        assert s.default_llm_model == "deepseek-ai/deepseek-v4-flash"

    def test_cloud_ru_field_exists(self) -> None:
        """default_llm_api_key_cloud_ru — обязательное поле Settings."""
        s = _settings()
        assert hasattr(s, "default_llm_api_key_cloud_ru")
        assert s.default_llm_api_key_cloud_ru == ""


class TestCloudRuCompatibilityHint:
    """P3.2: smoke что Cloud.ru работает с тем же payload что и NVIDIA.

    Реальный roundtrip требует ключа — закроется в P4.1 (smoke VM).
    Здесь — проверяем что resolver правильно собирает endpoint+key tuple,
    без расхождений с другими OpenAI-compat провайдерами.
    """

    @pytest.mark.parametrize(
        "endpoint,expected_key_field",
        [
            ("https://foundation-models.api.cloud.ru/v1", "default_llm_api_key_cloud_ru"),
            ("https://integrate.api.nvidia.com/v1", "default_llm_api_key_nvidia"),
            ("https://api.openai.com/v1", "default_llm_api_key_openai"),
            ("https://openrouter.ai/api/v1", "default_llm_api_key_openrouter"),
            ("https://api.xiaomimimo.com/v1", "default_llm_api_key"),
        ],
    )
    def test_endpoint_routes_to_correct_key_field(
        self, endpoint: str, expected_key_field: str
    ) -> None:
        s = _settings(**{expected_key_field: "test-key-routed"})
        assert s.resolve_default_api_key(endpoint) == "test-key-routed"
