"""Tests for clarify (Sprint 4 — Hermes D1)."""

from __future__ import annotations

import asyncio

import pytest

from app.orchestrator.clarify import (
    CLARIFY,
    MAX_OPTIONS,
    is_clarify_tool,
    new_clarify_id,
    validate_args,
)


@pytest.fixture(autouse=True)
def clear_clarify():
    CLARIFY._items.clear()  # noqa: SLF001
    yield
    CLARIFY._items.clear()  # noqa: SLF001


def test_is_clarify_tool() -> None:
    assert is_clarify_tool("clarify_question") is True
    assert is_clarify_tool("execute_query") is False


def test_new_clarify_id_unique() -> None:
    ids = {new_clarify_id() for _ in range(50)}
    assert len(ids) == 50
    assert all(i.startswith("clr_") for i in ids)


def test_validate_args_ok() -> None:
    q, opts, multi = validate_args(
        {"question": "За какой период?", "options": ["сегодня", "вчера", "неделя"]}
    )
    assert q == "За какой период?"
    assert opts == ["сегодня", "вчера", "неделя"]
    assert multi is False


def test_validate_args_multi() -> None:
    _, _, multi = validate_args(
        {"question": "Q?", "options": ["a", "b"], "multi": True}
    )
    assert multi is True


def test_validate_args_too_many_options() -> None:
    with pytest.raises(ValueError, match="не должно превышать"):
        validate_args(
            {"question": "?", "options": [str(i) for i in range(MAX_OPTIONS + 1)]}
        )


def test_validate_args_missing_question() -> None:
    with pytest.raises(ValueError):
        validate_args({"options": ["a"]})


def test_validate_args_empty_options() -> None:
    with pytest.raises(ValueError):
        validate_args({"question": "Q?", "options": []})


def test_validate_args_option_too_long() -> None:
    _, opts, _ = validate_args(
        {"question": "Q?", "options": ["a" * 200]}
    )
    # Кап на 100
    assert len(opts[0]) == 100


@pytest.mark.asyncio
async def test_register_and_resolve() -> None:
    clarify_id = new_clarify_id()
    pending = CLARIFY.register(clarify_id, "Q?", ["a", "b"])

    async def resolver():
        await asyncio.sleep(0.05)
        CLARIFY.resolve(clarify_id, "a")

    asyncio.create_task(resolver())
    result = await asyncio.wait_for(pending.future, timeout=1.0)
    assert result == "a"


@pytest.mark.asyncio
async def test_cancel_releases_future() -> None:
    clarify_id = new_clarify_id()
    pending = CLARIFY.register(clarify_id, "Q?", ["a"])
    CLARIFY.cancel(clarify_id)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pending.future, timeout=0.5)


@pytest.mark.asyncio
async def test_resolve_unknown_returns_false() -> None:
    assert CLARIFY.resolve("ghost", "x") is False


@pytest.mark.asyncio
async def test_active_count() -> None:
    CLARIFY.register("a", "?", ["1"])
    CLARIFY.register("b", "?", ["1"])
    assert CLARIFY.active_count() == 2
