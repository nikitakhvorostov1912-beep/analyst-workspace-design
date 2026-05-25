"""Tests for app.orchestrator.mcp_factory (M-K1.15)."""

from __future__ import annotations

from app.config import Settings
from app.orchestrator.mcp_factory import build_orchestrator


def _make_settings(**overrides) -> Settings:
    """Создаёт Settings с минимально-валидными значениями + overrides."""
    defaults = {
        "buddy_mcp_endpoint": "http://127.0.0.1:6002/mcp",
        "buddy_mcp_enabled": True,
        "buddy_mcp_healthcheck_interval_s": 30,
        "bsl_context_jar": "",
        "bsl_context_java": "",
        "bsl_context_platform_path": "",
    }
    defaults.update(overrides)
    # Settings — Pydantic, кастомные поля передаются через env override
    # или прямой construct. Используем construct() чтобы избежать пере-чтения env.
    return Settings.model_construct(**defaults)


def test_factory_without_toolkit_endpoint_skips_toolkit() -> None:
    settings = _make_settings()
    result = build_orchestrator(settings)  # toolkit_endpoint=None
    assert result.toolkit_registered is False
    skipped_names = [n for n, _ in result.skipped]
    assert "toolkit" in skipped_names
    # toolkit пропущен но orchestrator всё равно создан
    assert not result.orchestrator.has_namespace("toolkit")


def test_factory_with_toolkit_endpoint_registers_toolkit() -> None:
    settings = _make_settings(buddy_mcp_enabled=False)
    result = build_orchestrator(
        settings,
        toolkit_endpoint="http://127.0.0.1:6010/mcp",
    )
    assert result.toolkit_registered is True
    assert result.orchestrator.has_namespace("toolkit") is True


def test_factory_buddy_disabled_skips_buddy() -> None:
    settings = _make_settings(buddy_mcp_enabled=False)
    result = build_orchestrator(settings)
    assert result.buddy_registered is False
    assert not result.orchestrator.has_namespace("buddy")
    reasons = dict(result.skipped)
    assert "buddy_mcp_enabled=false" in reasons["buddy"]


def test_factory_buddy_enabled_registers_buddy() -> None:
    settings = _make_settings(buddy_mcp_enabled=True)
    result = build_orchestrator(settings)
    assert result.buddy_registered is True
    assert result.orchestrator.has_namespace("buddy") is True


def test_factory_buddy_empty_endpoint_skips() -> None:
    settings = _make_settings(
        buddy_mcp_enabled=True,
        buddy_mcp_endpoint="",
    )
    result = build_orchestrator(settings)
    assert result.buddy_registered is False
    reasons = dict(result.skipped)
    assert "пустой" in reasons["buddy"]


def test_factory_context_not_configured_skips() -> None:
    settings = _make_settings()  # все bsl_context_* пустые
    result = build_orchestrator(settings)
    assert result.context_registered is False
    reasons = dict(result.skipped)
    assert "context" in reasons
    assert "не настроены" in reasons["context"]


def test_factory_context_configured_but_deferred_to_mk3(tmp_path) -> None:
    """Даже когда bsl-context настроен — пока deferred (stdio в M-K3)."""
    fake_jar = tmp_path / "bsl-context.jar"
    fake_jar.write_text("not really a jar")
    fake_java = tmp_path / "java.exe"
    fake_java.write_text("not really java")
    fake_platform = tmp_path / "1cv8"
    fake_platform.mkdir()

    settings = _make_settings(
        bsl_context_jar=str(fake_jar),
        bsl_context_java=str(fake_java),
        bsl_context_platform_path=str(fake_platform),
    )
    result = build_orchestrator(settings)
    assert result.context_registered is False
    reasons = dict(result.skipped)
    assert "stdio" in reasons["context"]


def test_factory_full_setup_three_registered() -> None:
    """Toolkit endpoint + buddy enabled + context skipped = 2 из 3 registered."""
    settings = _make_settings(buddy_mcp_enabled=True)
    result = build_orchestrator(
        settings,
        toolkit_endpoint="http://127.0.0.1:6010/mcp",
    )
    assert result.toolkit_registered is True
    assert result.buddy_registered is True
    assert result.context_registered is False  # deferred to M-K3
    assert sorted(result.orchestrator.namespaces()) == ["buddy", "toolkit"]


def test_factory_returns_frozen_result() -> None:
    """FactoryResult — frozen dataclass, нельзя мутировать."""
    settings = _make_settings(buddy_mcp_enabled=False)
    result = build_orchestrator(settings)
    import pytest
    with pytest.raises(Exception):  # FrozenInstanceError
        result.toolkit_registered = True  # type: ignore[misc]
