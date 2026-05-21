"""MCP Pool — управляет несколькими MCP-серверами одновременно.

Основной (primary) MCP — к живой 1С базе (HTTP). Опционально подключаются
aux MCP-серверы (stdio) — например bsl-context для справочника API платформы.

LLM видит инструменты от всех источников в едином списке. tool_call роутится
по mapping name → client.

Конфликты имён tools: приоритет за primary. При коллизии aux MCP игнорируется
с предупреждением в лог.
"""

import logging
from typing import Any

from app.clients.mcp import MCPClient, MCPDisconnectedError
from app.clients.mcp_stdio import StdioMCPClient, StdioMCPConfig
from app.config import Settings

logger = logging.getLogger(__name__)


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
            # Если aux не инициализирован — пропускаем (initialize_all уже залогировал)
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


def build_aux_clients(settings: Settings) -> list[StdioMCPClient]:
    """Собирает список aux MCP-клиентов на основе настроек.

    Сейчас поддерживается только bsl-context. В будущем — другие справочники.
    """
    aux: list[StdioMCPClient] = []

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
