"""MCP Streamable HTTP клиент (JSON-RPC 2.0)."""

import json
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


class MCPError(Exception):
    """Ошибка JSON-RPC от MCP-сервера."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"MCP error {code}: {message}")
        self.code = code
        self.mcp_message = message


@dataclass
class MCPSession:
    """Результат MCP initialize."""

    session_id: str
    mcp_version: str
    server_name: str
    tools: list[dict] = field(default_factory=list)


class MCPClient:
    """MCP Streamable HTTP клиент.

    Поддерживает JSON и SSE ответы на initialize.
    Сохраняет Mcp-Session-Id после initialize и переиспользует его.
    """

    def __init__(
        self,
        endpoint: str,
        headers: dict | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint
        self._extra_headers = headers or {}
        self._http = httpx.AsyncClient(timeout=timeout)
        self._request_id = 0
        self.session_id: str | None = None
        self._tools_cache: list[dict] = []

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _post(self, body: dict, extra_headers: dict | None = None) -> dict:
        """Отправляет JSON-RPC запрос, парсит ответ (JSON или SSE)."""
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            **self._extra_headers,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if extra_headers:
            headers.update(extra_headers)

        response = await self._http.post(self.endpoint, json=body, headers=headers)
        response.raise_for_status()

        # Сохраняем Mcp-Session-Id из ответа
        if "mcp-session-id" in response.headers:
            self.session_id = response.headers["mcp-session-id"]
        elif "Mcp-Session-Id" in response.headers:
            self.session_id = response.headers["Mcp-Session-Id"]

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse_response(response.text)
        return response.json()

    def _parse_sse_response(self, text: str) -> dict:
        """Извлекает первый JSON-RPC результат из SSE-потока."""
        for line in text.splitlines():
            if line.startswith("data: "):
                raw = line[len("data: "):]
                if raw.strip() in ("[DONE]", ""):
                    continue
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    continue
        msg = "Не удалось найти JSON в SSE-ответе"
        raise MCPError(-32700, msg)

    def _check_error(self, response: dict) -> None:
        """Проверяет наличие JSON-RPC error в ответе."""
        if "error" in response:
            err = response["error"]
            raise MCPError(err.get("code", -1), err.get("message", "unknown"))

    async def initialize(self) -> MCPSession:
        """Выполняет JSON-RPC initialize и сохраняет Mcp-Session-Id.

        Returns:
            MCPSession с mcp_version, server_name, пустым tools (до list_tools).
        """
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "clientInfo": {"name": "1c-analyst", "version": "0.1.0"},
                "capabilities": {},
            },
        }
        response = await self._post(body)
        self._check_error(response)

        result = response.get("result", {})
        return MCPSession(
            session_id=self.session_id or "",
            mcp_version=result.get("protocolVersion", ""),
            server_name=result.get("serverInfo", {}).get("name", ""),
            tools=[],
        )

    async def list_tools(self) -> list[dict]:
        """Выполняет tools/list, кеширует и возвращает схемы инструментов.

        Требует предварительного вызова initialize().
        """
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
        }
        response = await self._post(body)
        self._check_error(response)

        tools = response.get("result", {}).get("tools", [])
        self._tools_cache = tools
        return tools

    async def call_tool(self, name: str, arguments: dict) -> dict:
        """Вызывает MCP инструмент по имени.

        Args:
            name: имя инструмента (напр. "execute_query")
            arguments: аргументы в виде dict

        Returns:
            result из JSON-RPC ответа (содержит content array).
        """
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        response = await self._post(body)
        self._check_error(response)
        return response.get("result", {})

    async def close(self) -> None:
        """Закрывает внутренний httpx.AsyncClient."""
        await self._http.aclose()

    async def aclose(self) -> None:
        """Alias для close() — симметрично с LLMClient."""
        await self.close()

    async def __aenter__(self) -> "MCPClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
