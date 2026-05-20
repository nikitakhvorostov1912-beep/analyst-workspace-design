"""Tests for prompt_caching (Sprint 5 — Hermes H4)."""

from __future__ import annotations

from app.orchestrator.prompt_caching import (
    MIN_CACHE_BLOCK_CHARS,
    apply_cache_breakpoints,
    is_caching_supported,
)


def test_openai_noop() -> None:
    """GPT не поддерживает caching — messages не меняются."""
    msgs = [
        {"role": "system", "content": "x" * (MIN_CACHE_BLOCK_CHARS + 100)},
        {"role": "user", "content": "hello"},
    ]
    out = apply_cache_breakpoints(msgs, "gpt-4o-mini")
    # Контент остался плоским string
    assert isinstance(out[0]["content"], str)


def test_anthropic_marks_system() -> None:
    msgs = [
        {"role": "system", "content": "x" * (MIN_CACHE_BLOCK_CHARS + 100)},
        {"role": "user", "content": "hi"},
    ]
    out = apply_cache_breakpoints(msgs, "claude-sonnet-4-6")
    # System content конвертирован в list with cache_control
    sys_content = out[0]["content"]
    assert isinstance(sys_content, list)
    assert sys_content[0].get("cache_control") is not None


def test_anthropic_small_system_skipped() -> None:
    msgs = [
        {"role": "system", "content": "small"},
        {"role": "user", "content": "x" * (MIN_CACHE_BLOCK_CHARS + 100)},
    ]
    out = apply_cache_breakpoints(msgs, "claude-sonnet-4-6")
    # Small system остался string
    assert isinstance(out[0]["content"], str)


def test_anthropic_marks_last_messages() -> None:
    big = "y" * (MIN_CACHE_BLOCK_CHARS + 100)
    msgs = [
        {"role": "system", "content": big},
        {"role": "user", "content": big},
        {"role": "assistant", "content": big},
        {"role": "user", "content": big},
    ]
    out = apply_cache_breakpoints(msgs, "claude-sonnet-4-6")
    # Минимум 2 breakpoint'а (system + хотя бы 1 из last 3)
    cache_count = 0
    for m in out:
        c = m["content"]
        if isinstance(c, list):
            for part in c:
                if part.get("cache_control"):
                    cache_count += 1
    assert cache_count >= 2


def test_max_4_breakpoints() -> None:
    """Anthropic hard limit = 4."""
    big = "z" * (MIN_CACHE_BLOCK_CHARS + 100)
    msgs = [{"role": "system", "content": big}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": big}
        for i in range(10)
    ]
    out = apply_cache_breakpoints(msgs, "claude-sonnet-4-6")
    cache_count = sum(
        1
        for m in out
        if isinstance(m["content"], list)
        for part in m["content"]
        if part.get("cache_control")
    )
    assert cache_count <= 4


def test_input_immutable() -> None:
    msgs = [{"role": "system", "content": "x" * (MIN_CACHE_BLOCK_CHARS + 100)}]
    apply_cache_breakpoints(msgs, "claude-sonnet-4-6")
    # Original не изменён
    assert isinstance(msgs[0]["content"], str)


def test_is_caching_supported() -> None:
    assert is_caching_supported("claude-sonnet-4-6") is True
    assert is_caching_supported("gpt-4o-mini") is False
    assert is_caching_supported("mimo-v2.5-pro") is False
