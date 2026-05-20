"""Tests for jittered retry (Sprint 2 — Hermes E2)."""

from __future__ import annotations

import random

import pytest

from app.orchestrator.retry import (
    RetryConfig,
    compute_jittered_delay,
    retry_async,
    retry_sync,
)


def test_jittered_delay_within_bounds() -> None:
    """Delay должен быть в [0, base * 2^attempt], не превышать max."""
    rng = random.Random(42)
    for attempt in range(5):
        for _ in range(100):
            d = compute_jittered_delay(attempt, base_delay_s=0.1, max_delay_s=2.0, rng=rng)
            assert 0 <= d <= 2.0
            assert d <= 0.1 * (2 ** attempt) or d <= 2.0


def test_jittered_delay_uses_max_cap() -> None:
    """При больших attempts срабатывает max cap."""
    rng = random.Random(0)
    d = compute_jittered_delay(attempt=20, base_delay_s=0.1, max_delay_s=1.0, rng=rng)
    assert d <= 1.0


def test_jittered_delay_negative_attempt() -> None:
    with pytest.raises(ValueError):
        compute_jittered_delay(attempt=-1, base_delay_s=0.1, max_delay_s=1.0)


def test_retry_config_invalid_max_attempts() -> None:
    with pytest.raises(ValueError):
        RetryConfig(max_attempts=0)


def test_retry_config_invalid_delays() -> None:
    with pytest.raises(ValueError):
        RetryConfig(base_delay_s=-0.1)
    with pytest.raises(ValueError):
        RetryConfig(base_delay_s=1.0, max_delay_s=0.5)


@pytest.mark.asyncio
async def test_retry_async_success_first_attempt() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    result = await retry_async(fn, config=RetryConfig(max_attempts=3))
    assert result == "ok"
    assert calls == 1


@pytest.mark.asyncio
async def test_retry_async_recovers_after_failures() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError(f"attempt {calls}")
        return "ok"

    slept: list[float] = []

    async def fake_sleep(d: float) -> None:
        slept.append(d)

    result = await retry_async(
        fn,
        config=RetryConfig(max_attempts=5, base_delay_s=0.01, max_delay_s=0.1),
        sleep=fake_sleep,
    )
    assert result == "ok"
    assert calls == 3
    assert len(slept) == 2  # 2 retries → 2 sleeps


@pytest.mark.asyncio
async def test_retry_async_exhausts_attempts() -> None:
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise RuntimeError(f"fail {calls}")

    async def fake_sleep(_d: float) -> None:
        pass

    with pytest.raises(RuntimeError, match="fail 3"):
        await retry_async(fn, config=RetryConfig(max_attempts=3), sleep=fake_sleep)
    assert calls == 3


@pytest.mark.asyncio
async def test_retry_async_respects_should_retry() -> None:
    """should_retry=False прерывает попытки сразу."""
    calls = 0

    async def fn() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("permanent")

    async def fake_sleep(_d: float) -> None:
        pass

    with pytest.raises(ValueError):
        await retry_async(
            fn,
            config=RetryConfig(max_attempts=5),
            should_retry=lambda _exc: False,
            sleep=fake_sleep,
        )
    assert calls == 1  # без retry


def test_retry_sync_recovers() -> None:
    calls = 0

    def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise RuntimeError("transient")
        return "ok"

    slept: list[float] = []
    result = retry_sync(
        fn,
        config=RetryConfig(max_attempts=3, base_delay_s=0.01, max_delay_s=0.05),
        sleep=lambda d: slept.append(d),
    )
    assert result == "ok"
    assert calls == 2
    assert len(slept) == 1


def test_retry_sync_exhausts() -> None:
    def fn() -> str:
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError):
        retry_sync(
            fn,
            config=RetryConfig(max_attempts=2, base_delay_s=0.001, max_delay_s=0.01),
            sleep=lambda _d: None,
        )
