"""Tests for app.types.capabilities.

G10 (M-K0.10): smoke-проверка типизированного capability registry.
Используется в M-K1 для capability discovery (ADR-004).
"""

from __future__ import annotations

import pytest

from app.types.capabilities import (
    ALL_CAPABILITIES,
    CAPABILITIES_BASE,
    CAPABILITIES_CFE,
    CAPABILITIES_CONDITIONAL,
    Capability,
    ChannelMode,
    filter_capabilities_for_mode,
    validate_capability_list,
)


def test_all_capabilities_count_is_23() -> None:
    """ADR-004: ровно 23 capabilities (8 base + 3 conditional + 12 cfe)."""
    assert len(ALL_CAPABILITIES) == 23
    assert len(CAPABILITIES_BASE) == 8
    assert len(CAPABILITIES_CONDITIONAL) == 3
    assert len(CAPABILITIES_CFE) == 12


def test_capability_namespaces_distinct() -> None:
    """Сетсы не пересекаются (each capability в exactly one bucket)."""
    assert CAPABILITIES_BASE.isdisjoint(CAPABILITIES_CONDITIONAL)
    assert CAPABILITIES_BASE.isdisjoint(CAPABILITIES_CFE)
    assert CAPABILITIES_CONDITIONAL.isdisjoint(CAPABILITIES_CFE)


def test_naming_convention() -> None:
    """Q1: все имена в формате `<namespace>.<feature>`."""
    for cap in ALL_CAPABILITIES:
        assert "." in cap, f"Capability {cap} нарушает namespace convention"
        namespace = cap.split(".", 1)[0]
        assert namespace in {"mcp", "tools_ui", "cfe", "epf"}, (
            f"Unknown namespace: {namespace}"
        )


def test_filter_capabilities_mcp_only_mode() -> None:
    """Raw MCP канал — только 8 base."""
    caps = filter_capabilities_for_mode("mcp_only")
    assert caps == CAPABILITIES_BASE


def test_filter_capabilities_epf_mode() -> None:
    """EPF — 8 base + 3 conditional."""
    caps = filter_capabilities_for_mode("epf")
    assert caps == CAPABILITIES_BASE | CAPABILITIES_CONDITIONAL
    assert "cfe.activity_stream" not in caps


def test_filter_capabilities_cfe_mode() -> None:
    """CFE — все 23."""
    caps = filter_capabilities_for_mode("cfe")
    assert caps == ALL_CAPABILITIES


def test_filter_capabilities_unknown_mode_raises() -> None:
    with pytest.raises(ValueError, match="Unknown channel mode"):
        filter_capabilities_for_mode("invalid")  # type: ignore[arg-type]


def test_validate_capability_list_filters_unknown() -> None:
    """Forward-compat: unknown capabilities игнорируются."""
    incoming = [
        "mcp.execute_query",        # valid
        "cfe.activity_stream",       # valid
        "totally.unknown",           # ignored
        "mcp.future_feature_v99",   # ignored
    ]
    result = validate_capability_list(incoming)
    assert result == ["mcp.execute_query", "cfe.activity_stream"]


def test_validate_capability_list_preserves_order() -> None:
    incoming = ["cfe.activity_stream", "mcp.execute_query", "cfe.posting_trace"]
    result = validate_capability_list(incoming)
    assert result == incoming  # порядок сохранён


def test_validate_capability_list_empty_input() -> None:
    assert validate_capability_list([]) == []
