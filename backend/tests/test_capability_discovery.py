"""Tests for app.services.capability_discovery (M-K1.7)."""

from __future__ import annotations

from app.clients.mcp import MCPSession
from app.services.capability_discovery import (
    CapabilityDiscoveryResult,
    discover_capabilities,
)
from app.types.capabilities import CAPABILITIES_BASE


# ---------------------------------------------------------------------------
# Fallback path: empty experimental
# ---------------------------------------------------------------------------


def test_discover_empty_experimental_returns_fallback() -> None:
    """Raw 1C MCP Toolkit без поддержки analyst-1c — fallback на 8 base caps."""
    session = MCPSession(
        session_id="test-session",
        mcp_version="2025-03-26",
        server_name="1C MCP Toolkit",
        experimental={},
    )
    result = discover_capabilities(session)
    assert result.mode == "mcp_only"
    assert result.configuration is None
    assert result.platform is None
    assert result.fingerprint is None
    assert result.source == "fallback"
    assert set(result.capabilities) == set(CAPABILITIES_BASE)


def test_discover_missing_experimental_handled() -> None:
    """experimental=None (по умолчанию для legacy) → fallback."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
    )  # experimental default = {}
    result = discover_capabilities(session)
    assert result.source == "fallback"


# ---------------------------------------------------------------------------
# Full experimental — happy path (CFE)
# ---------------------------------------------------------------------------


def test_discover_cfe_mode_full_experimental() -> None:
    """CFE АналитикПлюс возвращает все 23 capabilities + metadata."""
    session = MCPSession(
        session_id="cfe-test",
        mcp_version="2025-03-26",
        server_name="АналитикПлюс CFE",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.configuration": "УТ 11.5",
            "analyst-1c.configuration_version": "11.5.18.123",
            "analyst-1c.platform": "8.3.27.1989",
            "analyst-1c.bsp_version": "3.1.10",
            "analyst-1c.extension_version": "1.0.0",
            "analyst-1c.features": [
                "mcp.execute_query",
                "mcp.get_metadata",
                "cfe.activity_stream",
                "cfe.posting_trace",
            ],
        },
    )
    result = discover_capabilities(session)
    assert result.mode == "cfe"
    assert result.configuration == "УТ 11.5"
    assert result.platform == "8.3.27.1989"
    assert result.ext_version == "1.0.0"
    assert result.source == "experimental"
    assert "cfe.activity_stream" in result.capabilities
    assert "mcp.execute_query" in result.capabilities
    assert result.fingerprint is not None
    assert len(result.fingerprint.slug) == 12


def test_discover_epf_mode() -> None:
    session = MCPSession(
        session_id="epf-test",
        mcp_version="2025-03-26",
        server_name="АналитикLite EPF",
        experimental={
            "analyst-1c.mode": "epf",
            "analyst-1c.configuration": "ERP 2.5",
            "analyst-1c.platform": "8.3.27.1989",
            "analyst-1c.features": ["mcp.execute_query", "mcp.get_metadata"],
        },
    )
    result = discover_capabilities(session)
    assert result.mode == "epf"
    assert result.configuration == "ERP 2.5"


# ---------------------------------------------------------------------------
# Forward-compat: unknown capabilities/modes ignored
# ---------------------------------------------------------------------------


def test_discover_unknown_capabilities_filtered() -> None:
    """Будущий сервер вернёт новые caps — мы их игнорируем без падений."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="future",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.features": [
                "mcp.execute_query",  # known
                "totally.new.future_cap_v99",  # unknown
                "cfe.activity_stream",  # known
            ],
        },
    )
    result = discover_capabilities(session)
    assert "mcp.execute_query" in result.capabilities
    assert "cfe.activity_stream" in result.capabilities
    assert "totally.new.future_cap_v99" not in result.capabilities


def test_discover_unknown_mode_defaults_to_mcp_only() -> None:
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="future",
        experimental={
            "analyst-1c.mode": "future_mode_v99",
            "analyst-1c.features": [],
        },
    )
    result = discover_capabilities(session)
    assert result.mode == "mcp_only"


# ---------------------------------------------------------------------------
# Fingerprint conditional
# ---------------------------------------------------------------------------


def test_discover_no_fingerprint_without_configuration() -> None:
    """Если configuration отсутствует — fingerprint не вычисляем."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.platform": "8.3.27.1989",
            # configuration отсутствует
            "analyst-1c.features": ["mcp.execute_query"],
        },
    )
    result = discover_capabilities(session)
    assert result.fingerprint is None


def test_discover_no_fingerprint_without_platform() -> None:
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.configuration": "УТ 11.5",
            # platform отсутствует
            "analyst-1c.features": ["mcp.execute_query"],
        },
    )
    result = discover_capabilities(session)
    assert result.fingerprint is None


def test_discover_fingerprint_with_extensions() -> None:
    """Расширения (extension_uids) учитываются в fingerprint."""
    session_no_ext = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.configuration": "УТ 11.5",
            "analyst-1c.platform": "8.3.27.1989",
            "analyst-1c.features": ["mcp.execute_query"],
        },
    )
    session_with_ext = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.configuration": "УТ 11.5",
            "analyst-1c.platform": "8.3.27.1989",
            "analyst-1c.extension_uids": ["aaaa-bbbb"],
            "analyst-1c.features": ["mcp.execute_query"],
        },
    )
    r1 = discover_capabilities(session_no_ext)
    r2 = discover_capabilities(session_with_ext)
    assert r1.fingerprint is not None
    assert r2.fingerprint is not None
    assert r1.fingerprint.slug != r2.fingerprint.slug


# ---------------------------------------------------------------------------
# Edge cases / coercion
# ---------------------------------------------------------------------------


def test_discover_features_not_list_returns_empty() -> None:
    """Malformed experimental.features (string вместо list) — empty caps."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.features": "not-a-list",  # битый формат
        },
    )
    result = discover_capabilities(session)
    # Для cfe — empty list (не fallback на CAPABILITIES_BASE)
    assert result.capabilities == []


def test_discover_mcp_only_empty_features_falls_back_to_base() -> None:
    """mcp_only без явных features → берёт 8 base."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "mcp_only",
            # features отсутствует
        },
    )
    result = discover_capabilities(session)
    assert set(result.capabilities) == set(CAPABILITIES_BASE)


def test_capability_strings_property() -> None:
    """capability_strings — plain list для JSON serialization."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.features": ["mcp.execute_query", "cfe.activity_stream"],
        },
    )
    result = discover_capabilities(session)
    assert isinstance(result.capability_strings, list)
    assert all(isinstance(c, str) for c in result.capability_strings)


def test_result_is_frozen_dataclass() -> None:
    """CapabilityDiscoveryResult immutable (защита от случайных мутаций)."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={},
    )
    result = discover_capabilities(session)
    import pytest
    with pytest.raises(Exception):  # FrozenInstanceError
        result.mode = "cfe"  # type: ignore[misc]


def test_string_coercion_trim_and_empty() -> None:
    """Whitespace-only configuration → None (не пустая строка)."""
    session = MCPSession(
        session_id="x",
        mcp_version="2025-03-26",
        server_name="x",
        experimental={
            "analyst-1c.mode": "cfe",
            "analyst-1c.configuration": "   ",  # только whitespace
            "analyst-1c.platform": "8.3.27.1989",
        },
    )
    result = discover_capabilities(session)
    assert result.configuration is None
    assert result.fingerprint is None  # нет configuration → нет fingerprint
