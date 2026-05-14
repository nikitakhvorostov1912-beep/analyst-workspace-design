"""Тесты MCPClient — JSON-RPC initialize, list_tools, call_tool, SSE parsing."""

import json

import httpx
import pytest

from app.clients.mcp import MCPClient, MCPError


def _json_response(body: dict, headers: dict | None = None) -> httpx.Response:
    """Создаёт mock JSON httpx.Response."""
    h = {"content-type": "application/json"}
    if headers:
        h.update(headers)
    return httpx.Response(200, json=body, headers=h)


def _sse_response(body: dict, session_id: str = "test-sid") -> httpx.Response:
    """Создаёт mock SSE httpx.Response с одним data-чанком."""
    sse_body = f"event: message\ndata: {json.dumps(body)}\n\n"
    return httpx.Response(
        200,
        content=sse_body.encode(),
        headers={"content-type": "text/event-stream", "Mcp-Session-Id": session_id},
    )


@pytest.mark.asyncio
async def test_initialize_extracts_session_id_from_header():
    """initialize() сохраняет Mcp-Session-Id из response header."""
    rpc_result = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-03-26",
            "serverInfo": {"name": "test-server"},
        },
    }
    transport = httpx.MockTransport(
        lambda req: _json_response(rpc_result, headers={"Mcp-Session-Id": "test-sid"})
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    session = await client.initialize()

    assert client.session_id == "test-sid"
    assert session.session_id == "test-sid"
    assert session.mcp_version == "2025-03-26"
    assert session.server_name == "test-server"

    await client.close()


@pytest.mark.asyncio
async def test_list_tools_uses_session_id():
    """list_tools() передаёт Mcp-Session-Id в заголовке запроса."""
    captured_headers: dict = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured_headers.update(dict(req.headers))
        return _json_response({
            "jsonrpc": "2.0",
            "id": 2,
            "result": {"tools": [{"name": "foo", "description": "bar"}]},
        })

    transport = httpx.MockTransport(handler)
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)
    client.session_id = "saved-sid"  # эмулируем уже выполненный initialize

    tools = await client.list_tools()

    assert captured_headers.get("mcp-session-id") == "saved-sid"
    assert len(tools) == 1
    assert tools[0]["name"] == "foo"

    await client.close()


@pytest.mark.asyncio
async def test_initialize_handles_sse_response():
    """initialize() корректно парсит SSE-ответ (content-type: text/event-stream)."""
    rpc_result = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": "2025-03-26",
            "serverInfo": {"name": "sse-server"},
        },
    }
    transport = httpx.MockTransport(
        lambda req: _sse_response(rpc_result, session_id="sse-sid")
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)

    session = await client.initialize()

    assert client.session_id == "sse-sid"
    assert session.mcp_version == "2025-03-26"
    assert session.server_name == "sse-server"

    await client.close()


@pytest.mark.asyncio
async def test_call_tool_raises_on_jsonrpc_error():
    """call_tool() бросает MCPError при JSON-RPC error в ответе."""
    error_response = {
        "jsonrpc": "2.0",
        "id": 3,
        "error": {"code": -32601, "message": "method not found"},
    }
    transport = httpx.MockTransport(
        lambda req: _json_response(error_response)
    )
    client = MCPClient(endpoint="http://mock/mcp")
    client._http = httpx.AsyncClient(transport=transport, timeout=5.0)
    client.session_id = "sid"

    with pytest.raises(MCPError) as exc_info:
        await client.call_tool("nonexistent", {})

    assert exc_info.value.code == -32601
    assert "method not found" in str(exc_info.value)

    await client.close()
