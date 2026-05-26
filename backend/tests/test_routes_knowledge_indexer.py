"""Tests for POST/GET /knowledge/{channel_id}/index/* endpoints (M-K2.2).

Покрытие:
- POST /index/start
  - 404 если канала нет в mcp_connections
  - 202 при первом запуске — возвращает run_id + status='running'
  - 409 при двойном запуске — возвращает current_run
  - background task действительно делает работу (через monkeypatched MCP)
- GET /index/status
  - 404 если канала нет
  - 200 с {latest:null, running:null} для свежего канала
  - 200 с latest+running после start_indexer

Использует ASGITransport + AsyncClient (см. conftest.py::client fixture).
MCP замокан через monkeypatch на уровне модуля.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest


async def _seed_channel(app, channel_id: str, endpoint: str) -> None:
    """Регистрирует MCP-канал в app.state.db (после lifespan)."""
    db = app.state.db
    await db.execute(
        """
        INSERT INTO mcp_connections (id, name, endpoint, channel, anon_enabled, kind, mode)
        VALUES (?, ?, ?, ?, 0, 'embedded', 'mcp_only')
        """,
        (channel_id, channel_id, endpoint, channel_id),
    )
    await db.commit()


def _patch_mcp(monkeypatch, *, tools: list[dict], result: object):
    """Подменяет MCPClient в indexer.py на fake context manager."""

    class _Fake:
        async def initialize(self):
            pass

        async def list_tools(self):
            return tools

        async def call_tool(self, name: str, arguments: dict):  # noqa: ARG002
            return result

    @asynccontextmanager
    async def fake_client(endpoint: str, headers=None):  # noqa: ARG001
        yield _Fake()

    monkeypatch.setattr("app.knowledge.indexer.MCPClient", fake_client)


async def _wait_for_done(client, channel_id: str, timeout_s: float = 3.0) -> dict:
    """Поллит /index/status пока latest.status не станет done | failed."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(f"/knowledge/{channel_id}/index/status")
        assert resp.status_code == 200
        body = resp.json()
        latest = body.get("latest")
        if latest and latest["status"] in ("done", "failed"):
            return body
        await asyncio.sleep(0.05)
    raise AssertionError(
        f"Indexer не завершился за {timeout_s}s: last status = {body}"
    )


# ---------------- POST /index/start ----------------


@pytest.mark.asyncio
async def test_start_indexer_404_when_channel_unknown(client):
    resp = await client.post("/knowledge/ghost/index/start")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "channel_not_found"


@pytest.mark.asyncio
async def test_start_indexer_returns_202_with_run_id(client, monkeypatch):
    from app.main import app
    await _seed_channel(app, "ch-1", "http://fake-mcp/mcp")
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}],
        result=[{"name": "ОПП", "type": "Документ"}],
    )

    resp = await client.post("/knowledge/ch-1/index/start")
    assert resp.status_code == 202
    body = resp.json()
    assert body["channel_id"] == "ch-1"
    assert body["status"] == "running"
    assert isinstance(body["run_id"], int)
    assert "started_at" in body
    assert "message" in body

    # Ждём пока background task завершится — чтобы не оставить running run
    # активным между тестами (и проверить done path).
    final = await _wait_for_done(client, "ch-1")
    assert final["latest"]["status"] == "done"
    assert final["latest"]["objects_written"] == 1


@pytest.mark.asyncio
async def test_start_indexer_409_when_already_running(client, monkeypatch):
    from app.main import app
    await _seed_channel(app, "ch-1", "http://fake-mcp/mcp")

    # Делаем «зависший» MCP — call_tool блокируется на event так что run
    # не успеет завершиться до второго POST.
    block_event = asyncio.Event()

    class _Stuck:
        async def initialize(self):
            pass

        async def list_tools(self):
            return [{"name": "get_metadata"}]

        async def call_tool(self, name, arguments):  # noqa: ARG002
            await block_event.wait()
            return []

    @asynccontextmanager
    async def stuck(endpoint, headers=None):  # noqa: ARG001
        yield _Stuck()

    monkeypatch.setattr("app.knowledge.indexer.MCPClient", stuck)

    first = await client.post("/knowledge/ch-1/index/start")
    assert first.status_code == 202

    second = await client.post("/knowledge/ch-1/index/start")
    assert second.status_code == 409
    body = second.json()
    assert body["detail"]["error"] == "indexer_already_running"
    assert body["detail"]["current_run"]["status"] == "running"

    # Разблокируем, чтобы тестовый task завершился gracefully.
    block_event.set()
    await _wait_for_done(client, "ch-1", timeout_s=2.0)


# ---------------- GET /index/status ----------------


@pytest.mark.asyncio
async def test_status_returns_404_for_unknown_channel(client):
    resp = await client.get("/knowledge/ghost/index/status")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_status_returns_null_when_no_runs(client):
    from app.main import app
    await _seed_channel(app, "ch-2", "http://fake-mcp/mcp")

    resp = await client.get("/knowledge/ch-2/index/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["channel_id"] == "ch-2"
    assert body["latest"] is None
    assert body["running"] is None


@pytest.mark.asyncio
async def test_status_returns_done_latest_after_run(client, monkeypatch):
    from app.main import app
    await _seed_channel(app, "ch-3", "http://fake-mcp/mcp")
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "get_metadata"}],
        result=[
            {"name": "ОПП", "type": "Документ"},
            {"name": "Контрагенты", "type": "Справочник"},
        ],
    )

    start = await client.post("/knowledge/ch-3/index/start")
    assert start.status_code == 202

    final = await _wait_for_done(client, "ch-3")
    assert final["latest"]["status"] == "done"
    assert final["latest"]["objects_written"] == 2
    assert final["running"] is None  # после done — running нет


@pytest.mark.asyncio
async def test_status_records_failed_when_mcp_lacks_get_metadata(client, monkeypatch):
    from app.main import app
    await _seed_channel(app, "ch-4", "http://fake-mcp/mcp")
    _patch_mcp(
        monkeypatch,
        tools=[{"name": "execute_query"}],  # нет get_metadata
        result=[],
    )

    start = await client.post("/knowledge/ch-4/index/start")
    assert start.status_code == 202

    final = await _wait_for_done(client, "ch-4")
    assert final["latest"]["status"] == "failed"
    assert "get_metadata" in (final["latest"]["error"] or "")
