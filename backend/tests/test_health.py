import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient):
    """GET /health возвращает 200 и db=ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["db"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_version_matches(client: AsyncClient):
    """GET /health возвращает корректную версию."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_root_returns_name(client: AsyncClient):
    """GET / возвращает name и version."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "1c-analyst-backend"
    assert data["version"] == "0.1.0"
