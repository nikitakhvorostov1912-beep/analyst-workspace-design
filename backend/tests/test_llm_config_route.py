"""Регрессионные тесты CRUD /llm-config + /llm-config/test."""

import pytest
from httpx import AsyncClient

_BASE_BODY = {
    "endpoint": "http://localhost:1234/v1",
    "model": "test-model",
    "temperature": 0.3,
}

# ---------------------------------------------------------------------------
# GET /llm-config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_empty_returns_null(client: AsyncClient):
    """GET /llm-config с пустой БД → 200, body null."""
    response = await client.get("/llm-config")
    assert response.status_code == 200
    assert response.json() is None


# ---------------------------------------------------------------------------
# POST /llm-config
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_creates_returns_response_without_api_key(client: AsyncClient):
    """POST /llm-config → 201, id='default', без поля api_key (T-05-01)."""
    response = await client.post("/llm-config", json=_BASE_BODY)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "default"
    assert data["endpoint"] == _BASE_BODY["endpoint"]
    assert data["model"] == _BASE_BODY["model"]
    assert data["temperature"] == _BASE_BODY["temperature"]
    assert "api_key" not in data


@pytest.mark.asyncio
async def test_post_upserts_existing(client: AsyncClient):
    """Два POST подряд — в БД одна строка, последняя выигрывает."""
    await client.post("/llm-config", json=_BASE_BODY)
    second_body = {**_BASE_BODY, "model": "new-model", "temperature": 0.7}
    response = await client.post("/llm-config", json=second_body)
    assert response.status_code == 201
    data = response.json()
    assert data["model"] == "new-model"
    assert data["temperature"] == 0.7

    # Только одна запись в БД
    get_response = await client.get("/llm-config")
    assert get_response.status_code == 200
    assert get_response.json()["model"] == "new-model"


@pytest.mark.asyncio
async def test_get_returns_saved(client: AsyncClient):
    """POST → GET → возвращает те же данные."""
    await client.post("/llm-config", json=_BASE_BODY)
    response = await client.get("/llm-config")
    assert response.status_code == 200
    data = response.json()
    assert data["endpoint"] == _BASE_BODY["endpoint"]
    assert data["model"] == _BASE_BODY["model"]
    assert data["temperature"] == _BASE_BODY["temperature"]
    assert data["id"] == "default"


# ---------------------------------------------------------------------------
# PATCH /llm-config/default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_updates_partial(client: AsyncClient):
    """PATCH {model: 'new'} → 200, model обновлён, endpoint прежний."""
    await client.post("/llm-config", json=_BASE_BODY)
    response = await client.patch("/llm-config/default", json={"model": "updated-model"})
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "updated-model"
    assert data["endpoint"] == _BASE_BODY["endpoint"]
    assert data["id"] == "default"


@pytest.mark.asyncio
async def test_patch_unknown_id_404(client: AsyncClient):
    """PATCH /llm-config/other → 404."""
    response = await client.patch("/llm-config/other", json={"model": "x"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /llm-config/default
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_removes(client: AsyncClient):
    """POST → DELETE → 204, GET → null."""
    await client.post("/llm-config", json=_BASE_BODY)
    del_response = await client.delete("/llm-config/default")
    assert del_response.status_code == 204

    get_response = await client.get("/llm-config")
    assert get_response.status_code == 200
    assert get_response.json() is None


@pytest.mark.asyncio
async def test_delete_not_found_404(client: AsyncClient):
    """DELETE без записей → 404."""
    response = await client.delete("/llm-config/default")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Pydantic strict/extra validation (T-05-02)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_strict_rejects_extra_field(client: AsyncClient):
    """POST с лишним полем api_key → 422 (extra=forbid)."""
    body = {**_BASE_BODY, "api_key": "sk-secret"}
    response = await client.post("/llm-config", json=body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_invalid_endpoint_rejected(client: AsyncClient):
    """POST с endpoint='ftp://x' → 422."""
    body = {**_BASE_BODY, "endpoint": "ftp://not-allowed"}
    response = await client.post("/llm-config", json=body)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /llm-config/test
# ---------------------------------------------------------------------------


class _FakeLLMOK:
    """Заглушка: симулирует 200 OK от LLM провайдера."""

    def __init__(self, endpoint: str, model: str, api_key: str) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key

    async def post(self, url: str, **kwargs) -> "_FakeResponse":
        return _FakeResponse(200)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


@pytest.mark.asyncio
async def test_test_endpoint_ok(client: AsyncClient, monkeypatch):
    """Mock LLMClient 200 → ok=True."""

    class _MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def post(self, url: str, **kwargs) -> _FakeResponse:
            return _FakeResponse(200)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr("app.routes.llm_config.httpx.AsyncClient", _MockAsyncClient)

    response = await client.post(
        "/llm-config/test",
        json={"endpoint": "http://localhost:1234/v1", "model": "test-model"},
        headers={"X-LLM-API-Key": "sk-test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["error_code"] is None


@pytest.mark.asyncio
async def test_test_endpoint_invalid_key(client: AsyncClient, monkeypatch):
    """Mock 401 → ok=False, error_code='invalid_key'."""

    class _MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def post(self, url: str, **kwargs) -> _FakeResponse:
            return _FakeResponse(401)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr("app.routes.llm_config.httpx.AsyncClient", _MockAsyncClient)

    response = await client.post(
        "/llm-config/test",
        json={"endpoint": "http://localhost:1234/v1", "model": "test-model"},
        headers={"X-LLM-API-Key": "sk-bad"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["error_code"] == "invalid_key"


@pytest.mark.asyncio
async def test_test_endpoint_network_error(client: AsyncClient, monkeypatch):
    """Mock ConnectError → error_code='network_error'."""
    import httpx

    class _MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def post(self, url: str, **kwargs):
            raise httpx.ConnectError("Connection refused")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr("app.routes.llm_config.httpx.AsyncClient", _MockAsyncClient)

    response = await client.post(
        "/llm-config/test",
        json={"endpoint": "http://localhost:1234/v1", "model": "test-model"},
        headers={"X-LLM-API-Key": "sk-test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["error_code"] == "network_error"


@pytest.mark.asyncio
async def test_test_endpoint_timeout(client: AsyncClient, monkeypatch):
    """Mock TimeoutException → error_code='timeout'."""
    import httpx

    class _MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def post(self, url: str, **kwargs):
            raise httpx.TimeoutException("Timed out")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

    monkeypatch.setattr("app.routes.llm_config.httpx.AsyncClient", _MockAsyncClient)

    response = await client.post(
        "/llm-config/test",
        json={"endpoint": "http://localhost:1234/v1", "model": "test-model"},
        headers={"X-LLM-API-Key": "sk-test"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["error_code"] == "timeout"
