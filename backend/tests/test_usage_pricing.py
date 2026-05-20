"""Tests for usage_pricing (Sprint 5 — Hermes I4)."""

from __future__ import annotations

from app.orchestrator.usage_pricing import (
    ModelPrice,
    add_model_price,
    aggregate_costs,
    compute_turn_cost,
    get_price,
)


def test_known_model_returns_price() -> None:
    price = get_price("mimo-v2.5-pro")
    assert price is not None
    assert price.input_per_m > 0
    assert price.output_per_m > 0


def test_unknown_model_returns_none() -> None:
    assert get_price("totally-unknown-model") is None


def test_prefix_match() -> None:
    """date-suffix вариация: claude-sonnet-4-6-20250929 → находит claude-sonnet-4-6."""
    price = get_price("claude-sonnet-4-6-20250929")
    assert price is not None


def test_compute_turn_cost_known_model() -> None:
    cost = compute_turn_cost(
        model="gpt-4o-mini", input_tokens=10_000, output_tokens=2_000,
    )
    assert cost.status == "actual"
    # 10k * 0.15/M + 2k * 0.60/M = 0.0015 + 0.0012 = 0.0027
    assert abs(cost.total_cost_usd - 0.0027) < 0.0001


def test_compute_turn_cost_unknown_model() -> None:
    cost = compute_turn_cost(
        model="custom-model", input_tokens=1000, output_tokens=500,
    )
    assert cost.status == "unknown"
    assert cost.total_cost_usd == 0.0


def test_compute_turn_cost_cached() -> None:
    cost = compute_turn_cost(
        model="claude-sonnet-4-6",
        input_tokens=5_000,
        output_tokens=1_000,
        cached_input_tokens=10_000,
    )
    # input: 5k * 3.00/M = 0.015
    # output: 1k * 15.00/M = 0.015
    # cached: 10k * 0.30/M = 0.003
    assert cost.cached_input_cost_usd > 0
    assert cost.total_cost_usd > cost.input_cost_usd + cost.output_cost_usd


def test_aggregate_costs() -> None:
    t1 = compute_turn_cost(model="gpt-4o-mini", input_tokens=1000, output_tokens=200)
    t2 = compute_turn_cost(model="gpt-4o-mini", input_tokens=2000, output_tokens=500)
    agg = aggregate_costs([t1, t2])
    assert agg.input_tokens == 3000
    assert agg.output_tokens == 700
    assert agg.total_cost_usd == t1.total_cost_usd + t2.total_cost_usd


def test_aggregate_empty_list() -> None:
    agg = aggregate_costs([])
    assert agg.total_cost_usd == 0.0
    assert agg.input_tokens == 0


def test_add_model_price() -> None:
    add_model_price(
        "test-model-xyz", ModelPrice(input_per_m=1.0, output_per_m=2.0),
    )
    cost = compute_turn_cost(
        model="test-model-xyz", input_tokens=1000, output_tokens=500,
    )
    # 1000 * 1.0/M + 500 * 2.0/M = 0.001 + 0.001 = 0.002
    assert abs(cost.total_cost_usd - 0.002) < 1e-6


def test_as_dict_serializable() -> None:
    cost = compute_turn_cost(model="gpt-4o-mini", input_tokens=100, output_tokens=50)
    d = cost.as_dict()
    assert d["model"] == "gpt-4o-mini"
    assert "total_cost_usd" in d
    assert d["status"] == "actual"
