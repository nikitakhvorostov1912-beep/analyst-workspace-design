"""MCP stdio клиент — общается с MCP-сервером через stdin/stdout subprocess.

Используется для подключения вспомогательных MCP-серверов помимо основного
1C MCP-Toolkit на HTTP (например, bsl-context — справочник API платформы 1С).

Протокол: JSON-RPC 2.0, newline-delimited. Каждое сообщение — одна строка JSON.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field

from app.clients.mcp import MCPDisconnectedError, MCPError, MCPSession

logger = logging.getLogger(__name__)


@dataclass
class StdioMCPConfig:
    """Конфиг запуска stdio MCP-сервера."""

    name: str  # Имя для логов и отладки (например, "bsl-context")
    command: str  # Исполняемый файл (java.exe / mcp-1c.exe)
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


class StdioMCPClient:
    """MCP клиент через stdin/stdout subprocess.

    Имеет тот же интерфейс что HTTP MCPClient (initialize / list_tools / call_tool / aclose),
    чтобы orchestrator мог работать единообразно.
    """

    def __init__(self, config: StdioMCPConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._lock = asyncio.Lock()
        self._stderr_task: asyncio.Task | None = None

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _spawn(self) -> None:
        """Запускает subprocess MCP-сервера если ещё не запущен."""
        if self._proc is not None and self._proc.returncode is None:
            return
        logger.info("StdioMCP '%s' spawn: %s %s", self.config.name, self.config.command, " ".join(self.config.args))
        try:
            import os
            full_env = {**os.environ, **self.config.env}
            self._proc = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=full_env,
            )
        except FileNotFoundError as e:
            raise MCPDisconnectedError(
                f"StdioMCP '{self.config.name}': не найден исполняемый файл {self.config.command}"
            ) from e
        except Exception as e:
            raise MCPDisconnectedError(
                f"StdioMCP '{self.config.name}': не удалось запустить — {e}"
            ) from e

        # Фоновая задача чтения stderr — для отладки. Не блокирует основной flow.
        self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def _drain_stderr(self) -> None:
        """Читаем stderr subprocess в фоне, чтобы не было backpressure."""
        if self._proc is None or self._proc.stderr is None:
            return
        try:
            while True:
                line = await self._proc.stderr.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    logger.debug("StdioMCP '%s' stderr: %s", self.config.name, text[:200])
        except Exception:
            pass

    async def _send_recv(self, req: dict) -> dict:
        """Отправляет JSON-RPC запрос, ждёт строку-ответ. Под локом — stdio не thread-safe."""
        async with self._lock:
            await self._spawn()
            if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
                raise MCPDisconnectedError(f"StdioMCP '{self.config.name}': pipe недоступен")

            line = (json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8")
            try:
                self._proc.stdin.write(line)
                await self._proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as e:
                raise MCPDisconnectedError(
                    f"StdioMCP '{self.config.name}': pipe закрыт"
                ) from e

            # Notification (без id) — ответа не ждём
            if "id" not in req:
                return {}

            # Читаем строки пока не получим JSON с нужным id (skip notifications)
            target_id = req["id"]
            for _ in range(50):
                try:
                    raw = await asyncio.wait_for(
                        self._proc.stdout.readline(), timeout=self.timeout
                    )
                except asyncio.TimeoutError as e:
                    raise MCPDisconnectedError(
                        f"StdioMCP '{self.config.name}': таймаут чтения {self.timeout}с"
                    ) from e
                if not raw:
                    raise MCPDisconnectedError(
                        f"StdioMCP '{self.config.name}': EOF от subprocess"
                    )
                try:
                    decoded = raw.decode("utf-8", errors="replace").strip()
                    if not decoded:
                        continue
                    msg = json.loads(decoded)
                except json.JSONDecodeError:
                    logger.warning("StdioMCP '%s': bad JSON line: %s", self.config.name, decoded[:200])
                    continue
                if msg.get("id") == target_id:
                    return msg
                # Notification от сервера — игнорируем, читаем дальше
                continue

            raise MCPDisconnectedError(
                f"StdioMCP '{self.config.name}': не получен ответ за 50 строк"
            )

    def _check_error(self, response: dict) -> None:
        if "error" in response:
            err = response["error"]
            raise MCPError(err.get("code", -1), err.get("message", "unknown"))

    async def initialize(self) -> MCPSession:
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
        response = await self._send_recv(body)
        self._check_error(response)

        # Notify initialized — обязательно по протоколу
        await self._send_recv({"jsonrpc": "2.0", "method": "notifications/initialized"})

        result = response.get("result", {})
        return MCPSession(
            session_id=f"stdio-{self.config.name}",
            mcp_version=result.get("protocolVersion", ""),
            server_name=result.get("serverInfo", {}).get("name", ""),
            tools=[],
        )

    async def list_tools(self) -> list[dict]:
        body = {"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list"}
        response = await self._send_recv(body)
        self._check_error(response)
        return response.get("result", {}).get("tools", [])

    async def call_tool(self, name: str, arguments: dict) -> dict:
        body = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        response = await self._send_recv(body)
        self._check_error(response)
        return response.get("result", {})

    async def aclose(self) -> None:
        if self._proc is None:
            return
        if self._proc.returncode is None:
            try:
                if self._proc.stdin and not self._proc.stdin.is_closing():
                    self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.terminate()
                await asyncio.wait_for(self._proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                self._proc.kill()
            except Exception:
                pass
        if self._stderr_task:
            self._stderr_task.cancel()
        self._proc = None
