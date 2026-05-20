"""Tests for /skills/{channel_id} REST routes (Sprint 3)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import get_settings


@pytest.fixture(autouse=True)
def clear_memory_root(tmp_path, monkeypatch):
    """Изолируем memory_root через monkeypatch."""
    monkeypatch.setenv("MEMORY_ROOT", str(tmp_path / "memory"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_list_empty_skills(client: AsyncClient):
    response = await client.get("/skills/test-channel")
    assert response.status_code == 200
    data = response.json()
    assert data["channel_id"] == "test-channel"
    assert data["active"] == []
    assert data["archived"] == []


@pytest.mark.asyncio
async def test_create_and_list_skill(client: AsyncClient):
    body = {
        "body": "Это содержимое skill длиной достаточно символов для теста",
        "tags": ["query", "opp"],
        "pinned": False,
    }
    response = await client.post("/skills/test-channel", json=body)
    assert response.status_code == 201
    created = response.json()
    assert created["body"] == body["body"]
    assert created["provenance"] == "user"
    assert "query" in created["tags"]

    # List
    listing = (await client.get("/skills/test-channel")).json()
    assert len(listing["active"]) == 1


@pytest.mark.asyncio
async def test_archive_and_unarchive(client: AsyncClient):
    body = {"id": "archivable", "body": "skill text " * 5}
    await client.post("/skills/test-channel", json=body)

    arch = await client.post("/skills/test-channel/archivable/archive")
    assert arch.status_code == 204

    listing = (await client.get("/skills/test-channel")).json()
    assert listing["active"] == []
    assert len(listing["archived"]) == 1

    unarch = await client.post("/skills/test-channel/archivable/unarchive")
    assert unarch.status_code == 204
    listing = (await client.get("/skills/test-channel")).json()
    assert len(listing["active"]) == 1


@pytest.mark.asyncio
async def test_archive_pinned_returns_409(client: AsyncClient):
    body = {"id": "pinned-one", "body": "content " * 10, "pinned": True}
    await client.post("/skills/test-channel", json=body)
    response = await client.post("/skills/test-channel/pinned-one/archive")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_skill(client: AsyncClient):
    body = {"id": "deletable", "body": "x " * 20}
    await client.post("/skills/test-channel", json=body)
    delete = await client.delete("/skills/test-channel/deletable")
    assert delete.status_code == 204
    listing = (await client.get("/skills/test-channel")).json()
    assert listing["active"] == []


@pytest.mark.asyncio
async def test_curator_dry_run(client: AsyncClient):
    # Создадим skill (свежий → не должен архивироваться)
    await client.post("/skills/test-channel", json={"body": "x " * 20})
    response = await client.post(
        "/skills/test-channel/curator/run", json={"dry_run": True}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["inspected"] >= 1
    # Свежий skill — скорее всего в skipped_recent или skipped_user (provenance=user)
    assert data["archived"] == []


@pytest.mark.asyncio
async def test_todos_list_empty(client: AsyncClient):
    response = await client.get("/todos/sess-fresh")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["active_count"] == 0


@pytest.mark.asyncio
async def test_todos_add_complete_clear(client: AsyncClient):
    add = await client.post(
        "/todos/sess-fresh/action",
        json={"action": "add", "items": ["task1", "task2"]},
    )
    assert add.status_code == 200
    added_ids = [i["id"] for i in add.json()["added"]]
    assert len(added_ids) == 2

    listing = (await client.get("/todos/sess-fresh")).json()
    assert listing["active_count"] == 2

    comp = await client.post(
        "/todos/sess-fresh/action",
        json={"action": "complete", "ids": [added_ids[0]]},
    )
    assert comp.status_code == 200

    clear = await client.post(
        "/todos/sess-fresh/action", json={"action": "clear"}
    )
    assert clear.status_code == 200
    assert clear.json()["cleared"] == 2


@pytest.mark.asyncio
async def test_todos_action_unknown(client: AsyncClient):
    response = await client.post(
        "/todos/sess-x/action", json={"action": "nope"}
    )
    assert response.status_code == 400
