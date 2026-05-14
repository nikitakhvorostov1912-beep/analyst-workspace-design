"""MCP-клиент edge cases — SSE response, Mcp-Session-Id rotation, malformed JSON, 4xx/5xx."""

import json

import httpx
import pytest

from app.clients.mcp import MCPClient, MCPError


def _json_response(body: dict, headers: dict | None = None, status: int = 200) -> httpx.Response:
    """Создаёт mock JSON httpx.Response."""
    h = {"content-type": "application/json"}
    if headers:
        h.update(headers)
    return httpx.Response(status, json=body, headers=h)


def _sse_response(body: dict, session_id: str = "sse-sid") -> httpx.Response:
    """Создаёт mock SSE httpx.Response с одним data-чанком."""
    sse_body = f"event: message\ndata: {json.dumps(body)}\n\n"
    return httpx.Response(
        200,
        content=sse_body.encode(),
        headers={"content-type": "text/event-stream", "Mcp-Session-Id": session_id},
    )


# ---------------------------------------------------------------------------
# 1. initialize() парсит SSE-ответ
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_client_initialize_sse_response_parses():
    """initialize() с Content-Type text/event-stream корректно парсит и возвращает MCPSession."""
    rpc_result = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-03-26",
            "serverInfo": {"name": "sse-server"},
        },
    }
    transport = httpx.MockTransport(
        lambda req: _sse_response(rpc_result, session_id="sse-sid-42")
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    session = await client.initialize()

    assert session.mcp_version == "2025-03-26"
    assert session.server_name == "sse-server"
    assert client.session_id == "sse-sid-42"

    await client.aclose()


# ---------------------------------------------------------------------------
# 2. Mcp-Session-Id rotation — первый initialize даёт "s1", второй call_tool шлёт "s1"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_client_session_id_rotation():
    """После initialize session_id='s1'; call_tool передаёт Mcp-Session-Id: s1."""
    captured_headers_on_call: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        body_bytes = req.content
        body = json.loads(body_bytes.decode())
        if body.get("method") == "initialize":
            result = {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"protocolVersion": "2025-03-26", "serverInfo": {"name": "srv"}},
            }
            return _json_response(result, headers={"Mcp-Session-Id": "s1"})
        else:
            # tools/call — захватываем заголовки
            captured_headers_on_call.update(dict(req.headers))
            result = {
                "jsonrpc": "2.0",
                "id": body["id"],
                "result": {"content": []},
            }
            return _json_response(result)

    transport = httpx.MockTransport(handler)
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    await client.initialize()
    assert client.session_id == "s1"

    await client.call_tool("execute_query", {"query": "SELECT 1"})

    # call_tool должен передать Mcp-Session-Id: s1
    assert captured_headers_on_call.get("mcp-session-id") == "s1"

    await client.aclose()


# ---------------------------------------------------------------------------
# 3. malformed JSON в SSE → MCPError(-32700)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_client_malformed_json_in_sse_raises_mcperror():
    """SSE stream с data: {bad json} → MCPError(-32700)."""
    bad_sse = "event: message\ndata: {not valid json}\n\n"
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            content=bad_sse.encode(),
            headers={"content-type": "text/event-stream"},
        )
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    with pytest.raises(MCPError) as exc_info:
        await client.initialize()

    assert exc_info.value.code == -32700

    await client.aclose()


# ---------------------------------------------------------------------------
# 4. JSON-RPC error в ответе → MCPError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_client_jsonrpc_error_response_raises():
    """JSON-RPC {"error":{"code":-32601,"message":"Method not found"}} → MCPError."""
    error_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32601, "message": "Method not found"},
    }
    transport = httpx.MockTransport(
        lambda req: _json_response(error_response)
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    with pytest.raises(MCPError) as exc_info:
        await client.initialize()

    assert exc_info.value.code == -32601
    assert "Method not found" in str(exc_info.value)

    await client.aclose()


# ---------------------------------------------------------------------------
# 5. HTTP 400 → httpx.HTTPStatusError (не MCPError)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_client_4xx_propagates_httpstatus():
    """HTTP 400 → httpx.HTTPStatusError бросается наружу."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(400, json={"detail": "bad request"})
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.call_tool("foo", {})

    assert exc_info.value.response.status_code == 400

    await client.aclose()


# ---------------------------------------------------------------------------
# 6. HTTP 500 → httpx.HTTPStatusError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_client_5xx_propagates_httpstatus():
    """HTTP 500 → httpx.HTTPStatusError."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(500, json={"detail": "server error"})
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await client.call_tool("bar", {})

    assert exc_info.value.response.status_code == 500

    await client.aclose()


# ---------------------------------------------------------------------------
# 7. aclose() идемпотентен — вызов дважды не падает
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_client_aclose_idempotent():
    """close() дважды не падает (тест на идемпотентность)."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    await client.aclose()
    # Второй вызов не должен падать
    await client.aclose()
