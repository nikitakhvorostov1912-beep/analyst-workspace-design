"""Tests for skill_provenance (Sprint 3 — Hermes A8)."""

from __future__ import annotations

import asyncio

import pytest

from app.learning.skill_provenance import current_provenance, provenance


def test_default_is_user() -> None:
    assert current_provenance() == "user"


def test_provenance_context_sets_and_restores() -> None:
    assert current_provenance() == "user"
    with provenance("agent"):
        assert current_provenance() == "agent"
    assert current_provenance() == "user"


def test_nested_contexts() -> None:
    with provenance("agent"):
        with provenance("user"):
            assert current_provenance() == "user"
        assert current_provenance() == "agent"
    assert current_provenance() == "user"


def test_invalid_value_raises() -> None:
    with pytest.raises(ValueError):
        with provenance("invalid"):  # type: ignore[arg-type]
            pass


def test_exception_inside_block_restores() -> None:
    class _Boom(Exception):
        pass

    try:
        with provenance("agent"):
            raise _Boom
    except _Boom:
        pass
    assert current_provenance() == "user"


@pytest.mark.asyncio
async def test_async_isolation() -> None:
    """ContextVar изолирован между asyncio.Task'ами."""

    async def worker(value: str) -> str:
        with provenance(value):  # type: ignore[arg-type]
            await asyncio.sleep(0.01)
            return current_provenance()

    # Запускаем параллельно user и agent — не должны интерферировать.
    results = await asyncio.gather(worker("user"), worker("agent"), worker("user"))
    assert results == ["user", "agent", "user"]
