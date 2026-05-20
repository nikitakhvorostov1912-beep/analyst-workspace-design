"""Tests for POST /chat/{session_id}/interrupt (Sprint 2 — Hermes C9)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.orchestrator.interrupt import INTERRUPTS


@pytest.fixture(autouse=True)
def clear_interrupts():
    """Очищаем реестр interrupt до и после каждого теста."""
    # Полная очистка (нет helper'а — лезем в protected, для теста ОК).
    INTERRUPTS._interrupted.clear()  # noqa: SLF001
    yield
    INTERRUPTS._interrupted.clear()  # noqa: SLF001


@pytest.mark.asyncio
async def test_interrupt_sets_flag(client: AsyncClient):
    """POST /chat/{id}/interrupt → 202 + флаг установлен в реестре."""
    response = await client.post("/chat/sess-1/interrupt")
    assert response.status_code == 202
    body = response.json()
    assert body["session_id"] == "sess-1"
    assert body["interrupted"] is True
    assert INTERRUPTS.should_interrupt("sess-1") is True


@pytest.mark.asyncio
async def test_interrupt_idempotent(client: AsyncClient):
    """Повторный запрос — то же что один."""
    await client.post("/chat/sess-2/interrupt")
    response = await client.post("/chat/sess-2/interrupt")
    assert response.status_code == 202
    # Один и тот же session_id не растит реестр (set-based).
    assert INTERRUPTS.active_count() == 1


@pytest.mark.asyncio
async def test_interrupt_other_session_not_affected(client: AsyncClient):
    """Прерывание session A не влияет на session B."""
    await client.post("/chat/sess-A/interrupt")
    assert INTERRUPTS.should_interrupt("sess-A") is True
    assert INTERRUPTS.should_interrupt("sess-B") is False


@pytest.mark.asyncio
async def test_interrupt_empty_session_id_400(client: AsyncClient):
    """Пустой session_id или whitespace → 400."""
    # FastAPI matches пустой path сегмент как 404
    response_blank = await client.post("/chat/ /interrupt")
    assert response_blank.status_code == 400
