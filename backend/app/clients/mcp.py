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


class MCPDisconnectedError(Exception):
    """MCP-сервер недоступен после исчерпания попыток.

    Поднимается из _call_tool_with_retry когда ConnectError/Timeout не устраняется.
    Ловится в run_chat_loop и маппируется в event:error code=mcp_disconnected.
    """


@dataclass
class MCPSession:
    """Результат MCP initialize.

    M-K1.7 (ADR-004): добавлено `experimental` поле для capability discovery.
    Хранит весь experimental dict из server response — парсинг по
    namespaces (`analyst-1c.features`, `analyst-1c.mode`, etc.) делается
    в `app.services.capability_discovery`.
    """

    session_id: str
    mcp_version: str
    server_name: str
    tools: list[dict] = field(default_factory=list)
    experimental: dict[str, object] = field(default_factory=dict)


_LOCAL_HOSTS = ("127.0.0.1", "localhost", "0.0.0.0", "::1")


def _normalize_local_endpoint(endpoint: str) -> str:
    """Приводит localhost к 127.0.0.1 для надёжности.

    На Windows резолв `localhost` иногда уходит сначала в IPv6 (`::1`),
    1С Native MCP слушает только IPv4 → connection refused. Также NO_PROXY
    у пользователя часто содержит `127.*`, но не `localhost` — это вторая
    причина по которой именно числовой адрес безопаснее.
    """
    if not endpoint:
        return endpoint
    if "://localhost" in endpoint or endpoint.startswith("localhost"):
        return endpoint.replace("localhost", "127.0.0.1", 1)
    return endpoint


def _is_local_endpoint(endpoint: str) -> bool:
    """True если endpoint обращается к этой же машине."""
    if not endpoint:
        return False
    url = endpoint.lower()
    return any(host in url for host in _LOCAL_HOSTS)


# Публичные алиасы — для использования в `app.clients.mcp_errors`,
# `app.routes.connections`, `app.routes.diagnostics`. Приватные имена
# с подчёркиванием оставлены для обратной совместимости с тестами.
normalize_local_endpoint = _normalize_local_endpoint
is_local_endpoint = _is_local_endpoint


class MCPClient:
    """MCP Streamable HTTP клиент.

    Поддерживает JSON и SSE ответы на initialize.
    Сохраняет Mcp-Session-Id после initialize и переиспользует его.

    Для локального MCP (1С на той же машине) принудительно отключаем
    `trust_env`, иначе httpx наследует системный прокси (Hiddify, корп.
    прокси) и пытается ходить к localhost через него → прокси отдаёт
    502 Bad Gateway. Удалённые MCP (HF Spaces proxy) — наоборот могут
    требовать прокси, для них оставляем дефолтное поведение.
    """

    def __init__(
        self,
        endpoint: str,
        headers: dict | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = _normalize_local_endpoint(endpoint)
        self._extra_headers = headers or {}
        is_local = _is_local_endpoint(self.endpoint)
        self._http = httpx.AsyncClient(
            timeout=timeout,
            trust_env=not is_local,
        )
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
        """Извлекает первый JSON-RPC результат из SSE-потока.

        Согласно SSE-спецификации, multi-line data-блоки конкатенируются через \\n.
        MCP Toolkit (Native) форматирует pretty-printed JSON, разбивая на много строк
        с префиксом `data:` каждая → нельзя парсить построчно, нужно собирать в event.
        """
        events: list[list[str]] = []
        current: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.rstrip("\r")
            if line == "":
                # Пустая строка = разделитель events
                if current:
                    events.append(current)
                    current = []
                continue
            if line.startswith("data:"):
                # SSE спек: "data: foo" или "data:foo" (пробел опционален)
                payload = line[len("data:"):].lstrip(" ")
                current.append(payload)
        if current:
            events.append(current)

        for event_lines in events:
            joined = "\n".join(event_lines)
            if joined.strip() in ("[DONE]", ""):
                continue
            try:
                return json.loads(joined)
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
        # M-K1.7: парсинг experimental field (ADR-004 Capability Discovery)
        # MCP spec разрешает vendor-specific extensions в `experimental.*`.
        # Сервер может вернуть `experimental.analyst-1c.features`/.mode/.configuration
        # — это используется в capability_discovery.py для UPDATE mcp_connections.
        # Старые серверы (без support) вернут пустой dict — graceful degradation.
        experimental_raw = result.get("experimental", {})
        experimental = experimental_raw if isinstance(experimental_raw, dict) else {}
        return MCPSession(
            session_id=self.session_id or "",
            mcp_version=result.get("protocolVersion", ""),
            server_name=result.get("serverInfo", {}).get("name", ""),
            tools=[],
            experimental=experimental,
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
