"""Tests for model_metadata (Sprint 5 — Hermes H5)."""

from __future__ import annotations

from app.orchestrator.model_metadata import (
    DEFAULT_FALLBACK,
    ModelMetadata,
    estimate_remaining_budget,
    get_metadata,
    register_model,
)


def test_known_model_returns_meta() -> None:
    meta = get_metadata("mimo-v2.5-pro")
    assert meta.context_window > 0
    assert meta.max_output > 0


def test_unknown_model_returns_fallback() -> None:
    meta = get_metadata("totally-unknown-xyz")
    assert meta == DEFAULT_FALLBACK


def test_prefix_match() -> None:
    meta = get_metadata("claude-sonnet-4-6-20250929")
    assert meta.context_window == 200_000


def test_anthropic_supports_caching() -> None:
    meta = get_metadata("claude-sonnet-4-6")
    assert meta.supports_caching is True


def test_openai_not_supports_caching() -> None:
    meta = get_metadata("gpt-4o-mini")
    assert meta.supports_caching is False


def test_vision_flag() -> None:
    assert get_metadata("gpt-4o-mini").supports_vision is True
    assert get_metadata("mimo-v2-flash").supports_vision is False


def test_register_model() -> None:
    register_model(
        ModelMetadata(name="test-meta-xyz", context_window=32_000, max_output=4_000)
    )
    meta = get_metadata("test-meta-xyz")
    assert meta.context_window == 32_000


def test_estimate_remaining_budget() -> None:
    budget = estimate_remaining_budget(
        model="mimo-v2.5-pro", used_tokens=10_000, desired_output=2_000,
    )
    # 128_000 - 10_000 - 2_000 - 5% safety = 128_000 - 12_000 - 6400 = ~109_600
    assert 100_000 <= budget <= 116_000


def test_budget_exhausted_returns_zero() -> None:
    budget = estimate_remaining_budget(
        model="mimo-v2.5-pro", used_tokens=200_000, desired_output=10_000,
    )
    assert budget == 0
