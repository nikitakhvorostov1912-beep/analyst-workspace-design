"""Тесты POST /chat/confirm — 204 / 404 / 422."""

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def clear_pending():
    """Очищаем _pending dict до и после каждого теста."""
    import app.orchestrator.safety as safety_mod

    safety_mod._pending.clear()
    yield
    safety_mod._pending.clear()


@pytest.mark.asyncio
async def test_post_chat_confirm_approved_returns_204(client: AsyncClient):
    """POST /chat/confirm с зарегистрированным id → 204."""
    from app.orchestrator.safety import register_pending_confirmation

    register_pending_confirmation("tool-call-abc")

    response = await client.post(
        "/chat/confirm",
        json={"tool_call_id": "tool-call-abc", "approved": True},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_post_chat_confirm_unknown_id_returns_404(client: AsyncClient):
    """POST /chat/confirm с неизвестным id → 404."""
    response = await client.post(
        "/chat/confirm",
        json={"tool_call_id": "non-existent-id", "approved": True},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_post_chat_confirm_validates_strict_field(client: AsyncClient):
    """POST /chat/confirm с approved='yes' (строка вместо bool) → 422 (strict=True)."""
    response = await client.post(
        "/chat/confirm",
        json={"tool_call_id": "x", "approved": "yes"},
    )
    assert response.status_code == 422
