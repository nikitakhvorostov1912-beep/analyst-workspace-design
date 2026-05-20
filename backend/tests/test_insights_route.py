"""Tests for /insights и /chat/clarify routes (Sprint 4)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.orchestrator.clarify import CLARIFY


@pytest.fixture(autouse=True)
def clear_clarify():
    CLARIFY._items.clear()  # noqa: SLF001
    yield
    CLARIFY._items.clear()  # noqa: SLF001


@pytest.mark.asyncio
async def test_insights_default_period(client: AsyncClient):
    response = await client.get("/insights")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "7d"
    assert isinstance(data["sessions"], int)
    assert isinstance(data["top_channels"], list)
    assert isinstance(data["top_tools"], list)


@pytest.mark.asyncio
async def test_insights_period_24h(client: AsyncClient):
    response = await client.get("/insights?period=24h")
    assert response.status_code == 200
    assert response.json()["period"] == "24h"


@pytest.mark.asyncio
async def test_insights_invalid_period(client: AsyncClient):
    response = await client.get("/insights?period=invalid")
    assert response.status_code == 422  # pydantic validation


@pytest.mark.asyncio
async def test_clarify_unknown_id_404(client: AsyncClient):
    response = await client.post(
        "/chat/clarify", json={"clarify_id": "missing", "answer": "x"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_clarify_resolve_existing(client: AsyncClient):
    import asyncio

    from app.orchestrator.clarify import new_clarify_id

    cid = new_clarify_id()
    pending = CLARIFY.register(cid, "?", ["a"])
    response = await client.post(
        "/chat/clarify", json={"clarify_id": cid, "answer": "a"}
    )
    assert response.status_code == 204
    # Future был закрыт
    result = await asyncio.wait_for(pending.future, timeout=0.5)
    assert result == "a"


@pytest.mark.asyncio
async def test_clarify_list_answer(client: AsyncClient):
    import asyncio
    from app.orchestrator.clarify import new_clarify_id

    cid = new_clarify_id()
    pending = CLARIFY.register(cid, "?", ["a", "b"], multi=True)
    response = await client.post(
        "/chat/clarify", json={"clarify_id": cid, "answer": ["a", "b"]}
    )
    assert response.status_code == 204
    result = await asyncio.wait_for(pending.future, timeout=0.5)
    assert result == ["a", "b"]
