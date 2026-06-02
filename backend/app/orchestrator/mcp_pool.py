"""MCP Pool — управляет несколькими MCP-серверами одновременно.

Основной (primary) MCP — к живой 1С базе (HTTP). Опционально подключаются
aux MCP-серверы (stdio) — например bsl-context для справочника API платформы.

LLM видит инструменты от всех источников в едином списке. tool_call роутится
по mapping name → client.

Конфликты имён tools: приоритет за primary. При коллизии aux MCP игнорируется
с предупреждением в лог.
"""

import logging
from types import SimpleNamespace
from typing import Any

from app.clients.mcp import MCPClient, MCPDisconnectedError
from app.clients.mcp_stdio import StdioMCPClient, StdioMCPConfig
from app.config import Settings
from app.knowledge import buddy_monitor

logger = logging.getLogger(__name__)


class BuddyAuxClient:
    """HTTP aux MCP-клиент 1С:Напарник с namespace-префиксом `buddy.` + телеметрией #40.

    Зачем префикс `buddy.`:
    - Напарник экспонирует `search_its` / `fetch_its` — теми же именами, что и
      статический ИТС RAG (`search_its`). Без префикса диспетчер чата (loop.py)
      поймал бы `search_its` в static-ветке (`is_its_tool`) и реальный Напарник
      НИКОГДА бы не вызвался — ровно этот баг и наблюдался.
    - С префиксом `buddy.search_its`: `is_its_tool()` == False → tool падает в
      MCP-ветку диспетчера → `pool.client_for()` возвращает этот клиент →
      `call_tool()` снимает префикс перед делегированием реальному серверу.

    Телеметрия (#40): `buddy_monitor.record_call(ok)` на каждый вызов питает
    `/health` (calls_total / ok / fail).

    Совместимость с MCPPool: имеет `config.name` (для логов) и `_is_http_aux=True`
    (MCPPool.list_all_tools пропускает _proc-проверку для HTTP-aux).
    """

    _PREFIX = "buddy."

    def __init__(self, endpoint: str) -> None:
        self._inner = MCPClient(endpoint)
        self.config = SimpleNamespace(name="1c-buddy")
        self._is_http_aux = True

    async def initialize(self) -> Any:
        return await self._inner.initialize()

    async def list_tools(self) -> list[dict]:
        tools = await self._inner.list_tools()
        prefixed: list[dict] = []
        for tool in tools:
            name = str(tool.get("name", "")).strip()
            if not name:
                continue
            t2 = dict(tool)
            t2["name"] = self._PREFIX + name
            prefixed.append(t2)
        return prefixed

    async def call_tool(self, name: str, arguments: dict) -> dict:
        raw = name[len(self._PREFIX):] if name.startswith(self._PREFIX) else name
        try:
            result = await self._inner.call_tool(raw, arguments)
        except Exception:
            buddy_monitor.record_call(False)
            raise
        buddy_monitor.record_call(True)
        return result

    async def aclose(self) -> None:
        await self._inner.aclose()


class MCPPool:
    """Управляет primary + aux MCP клиентами как единым набором tools."""

    def __init__(self, primary: MCPClient, aux_clients: list[StdioMCPClient]) -> None:
        self.primary = primary
        self.aux_clients = aux_clients
        # tool_name → MCP client (primary | StdioMCPClient)
        self._tool_router: dict[str, Any] = {}
        self._merged_tools: list[dict] = []

    async def initialize_all(self) -> None:
        """Инициализирует все MCP-серверы. Сбой aux не валит основной flow."""
        await self.primary.initialize()
        for aux in self.aux_clients:
            try:
                await aux.initialize()
                logger.info("Aux MCP '%s' initialized", aux.config.name)
            except MCPDisconnectedError as e:
                logger.warning(
                    "Aux MCP '%s' не удалось инициализировать — пропускаем. %s",
                    aux.config.name, e,
                )
            except Exception:
                logger.exception("Aux MCP '%s' init failed", aux.config.name)

    async def list_all_tools(self) -> list[dict]:
        """Собирает tools от primary + всех aux. Заполняет _tool_router.

        Конфликты имён: primary выигрывает, aux логируется и игнорируется.
        """
        self._tool_router.clear()
        merged: list[dict] = []

        # Primary tools
        try:
            primary_tools = await self.primary.list_tools()
        except Exception:
            logger.exception("Primary MCP list_tools failed")
            primary_tools = []
        for tool in primary_tools:
            name = tool.get("name", "")
            if not name:
                continue
            self._tool_router[name] = self.primary
            merged.append(tool)

        # Aux tools
        for aux in self.aux_clients:
            # HTTP aux (buddy): нет _proc — готовность определяется через
            # initialize_all (если упал — list_tools ниже бросит → except → continue).
            # stdio aux: пропускаем если процесс не запущен/умер.
            if not getattr(aux, "_is_http_aux", False):
                if aux._proc is None or aux._proc.returncode is not None:
                    continue
            try:
                aux_tools = await aux.list_tools()
            except Exception:
                logger.exception("Aux MCP '%s' list_tools failed", aux.config.name)
                continue
            for tool in aux_tools:
                name = tool.get("name", "")
                if not name:
                    continue
                if name in self._tool_router:
                    logger.warning(
                        "Aux MCP '%s' tool '%s' конфликтует с primary — пропускаем",
                        aux.config.name, name,
                    )
                    continue
                self._tool_router[name] = aux
                merged.append(tool)

        self._merged_tools = merged
        return merged

    def client_for(self, tool_name: str):
        """Возвращает MCPClient/StdioMCPClient для данного tool_name.

        Fallback на primary если name не найден в роутере (защита от race).
        """
        return self._tool_router.get(tool_name, self.primary)

    async def aclose(self) -> None:
        try:
            await self.primary.aclose()
        except Exception:
            pass
        for aux in self.aux_clients:
            try:
                await aux.aclose()
            except Exception:
                pass


def build_aux_clients(settings: Settings) -> list[Any]:
    """Собирает список aux MCP-клиентов на основе настроек.

    Поддерживаются:
    - bsl-context (stdio) — справочник API платформы 1С;
    - 1С:Напарник (HTTP, BuddyAuxClient) — живая ИТС/БСП документация (L5),
      если `settings.buddy_mcp_enabled` и задан endpoint.
    """
    aux: list[Any] = []

    # --- 1С:Напарник (живая ИТС, primary L5) ---
    if settings.buddy_mcp_enabled:
        endpoint = (settings.buddy_mcp_endpoint or "").strip()
        if endpoint:
            aux.append(BuddyAuxClient(endpoint))
            logger.info("Aux MCP buddy (1С:Напарник) configured: %s", endpoint)
        else:
            logger.info("Aux MCP buddy пропущен: buddy_mcp_endpoint пустой")
    else:
        logger.info("Aux MCP buddy пропущен: buddy_mcp_enabled=false")

    # Используем resolved_* — они подставляют bundled JAR / системный java /
    # auto-detected платформу 1С, если env vars не заданы. Только когда все
    # три источника доступны, поднимаем aux. Иначе тихо пропускаем (а
    # /diagnostics/aux отдельно покажет «не подключён» с подсказкой).
    jar = settings.resolved_bsl_jar
    java = settings.resolved_bsl_java
    platform = settings.resolved_bsl_platform_path
    if jar and java and platform:
        cfg = StdioMCPConfig(
            name="bsl-context",
            command=java,
            args=[
                "-Dfile.encoding=UTF-8",
                "-jar",
                jar,
                "--platform-path",
                platform,
                "--mode",
                "stdio",
            ],
        )
        aux.append(StdioMCPClient(cfg))
        logger.info(
            "Aux MCP bsl-context configured: jar=%s java=%s platform=%s",
            jar, java, platform,
        )
    else:
        # Видимо в логе будет проще диагностировать у пользователя
        missing = []
        if not jar:
            missing.append("JAR (resources/bsl/mcp-bsl-context-*.jar)")
        if not java:
            missing.append("Java (java.exe не найден в PATH)")
        if not platform:
            missing.append("платформа 1С (C:\\Program Files\\1cv8\\*)")
        logger.info("Aux MCP bsl-context пропущен. Не найдено: %s", ", ".join(missing))

    return aux
