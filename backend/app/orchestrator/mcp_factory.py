"""MCP Factory — конструктор MCPOrchestrator из настроек.

M-K1.15 (M6 Phase 12.10 + G1 1c-buddy seed).

Один публичный метод `build_orchestrator(settings, endpoint, ...)` создаёт
unified registry с тремя MCP-источниками:

1. **`toolkit`** — основной MCP (1С Toolkit, endpoint из параметра)
   Регистрируется всегда (если endpoint валидный)

2. **`buddy`** — 1С:Напарник (если `settings.buddy_mcp_enabled=true`)
   Endpoint из `settings.buddy_mcp_endpoint` (default `http://127.0.0.1:6002/mcp`)
   Q-NEW resolved: primary L5 источник (бесплатно до 01.10.2026)

3. **`context`** — mcp-bsl-context (если `settings.bsl_context_*` все 3 заданы)
   Java subprocess для справочника BSL API. Lazy creation —
   factory вернёт orchestrator без `context` namespace если JAR/Java/platform
   не настроены (graceful degradation).

METR и EDT-MCP — **disabled by default** (см. INTEGRATION-DECISIONS.md
§Reject 3). Активируются если пользователь добавит в Settings (M-K3+).

**Не делает:**
- Не вызывает initialize() — это делает caller (e.g. при `/connections/{id}/ping`
  для toolkit, при startup task для buddy/context). Factory только создаёт.
- Не проверяет healthcheck — это M-K3 (circuit breaker pattern).
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from app.clients.mcp import MCPClient
from app.config import Settings
from app.knowledge import buddy_monitor
from app.orchestrator.mcp_orchestrator import MCPOrchestrator


class _BuddyTelemetryClient:
    """Обёртка над buddy MCPClient: считает вызовы (#40 lifecycle-телеметрия).

    Делегирует всё во внутренний клиент, перехватывая только call_tool для
    `buddy_monitor.record_call(ok)`. Остальные атрибуты (aclose и пр.) — passthrough.
    """

    def __init__(self, inner: MCPClient) -> None:
        self._inner = inner

    async def call_tool(self, name: str, arguments: dict) -> dict:
        try:
            result = await self._inner.call_tool(name, arguments)
        except Exception:
            buddy_monitor.record_call(False)
            raise
        buddy_monitor.record_call(True)
        return result

    def __getattr__(self, item):  # passthrough (aclose, и т.п.)
        return getattr(self._inner, item)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FactoryResult:
    """Результат фабрики.

    Attrs:
        orchestrator: построенный MCPOrchestrator с зарегистрированными клиентами
        toolkit_registered: основной MCP подключён (всегда True если endpoint валиден)
        buddy_registered: 1c-buddy подключён (зависит от settings.buddy_mcp_enabled)
        context_registered: bsl-context подключён (зависит от bsl_context_jar/java/platform)
        skipped: list namespace'ов которые НЕ были зарегистрированы + reason
    """

    orchestrator: MCPOrchestrator
    toolkit_registered: bool
    buddy_registered: bool
    context_registered: bool
    skipped: list[tuple[str, str]]


def _is_bsl_context_configured(settings: Settings) -> bool:
    """Все 3 пути bsl-context должны существовать на диске для работы.

    JAR + java executable + path к платформе 1С. Если хоть один не задан
    или путь не существует — пропускаем регистрацию.
    """
    jar = (settings.bsl_context_jar or "").strip()
    java = (settings.bsl_context_java or "").strip()
    platform = (settings.bsl_context_platform_path or "").strip()
    if not (jar and java and platform):
        return False
    # Проверка существования — best-effort, не критично если ошибочно False
    # (factory просто skip регистрацию context, orchestrator без него работает)
    return os.path.isfile(jar) and os.path.isfile(java) and os.path.isdir(platform)


def build_orchestrator(
    settings: Settings,
    *,
    toolkit_endpoint: str | None = None,
) -> FactoryResult:
    """Создаёт MCPOrchestrator с зарегистрированными MCP клиентами.

    Args:
        settings: app.config.Settings (имеет buddy_mcp_*, bsl_context_*)
        toolkit_endpoint: endpoint основного MCP канала. Если None — пропускаем
            регистрацию `toolkit` (e.g. для случая когда factory создаётся
            до того как пользователь выбрал канал). Обычно передаётся из
            `mcp_connections.endpoint` для активного канала.

    Returns:
        FactoryResult с orchestrator и флагами что было зарегистрировано.

    Не raise. Если какой-то MCP не настроен — просто skip с пометкой в
    `skipped` list. Это позволяет приложению стартовать без некоторых MCP
    источников (graceful degradation).
    """
    orchestrator = MCPOrchestrator()
    skipped: list[tuple[str, str]] = []
    toolkit_registered = False
    buddy_registered = False
    context_registered = False

    # 1. Toolkit — основной MCP канала
    if toolkit_endpoint:
        try:
            toolkit_client = MCPClient(toolkit_endpoint)
            orchestrator.register("toolkit", toolkit_client)
            toolkit_registered = True
            logger.info("MCPFactory: toolkit зарегистрирован → %s", toolkit_endpoint)
        except Exception as exc:
            skipped.append(("toolkit", f"client init failed: {exc}"))
            logger.warning(
                "MCPFactory: toolkit skip — client init failed: %s", exc
            )
    else:
        skipped.append(("toolkit", "endpoint не задан (нет активного канала)"))

    # 2. buddy (1С:Напарник) — primary L5
    if settings.buddy_mcp_enabled:
        endpoint = (settings.buddy_mcp_endpoint or "").strip()
        if endpoint:
            try:
                buddy_client = _BuddyTelemetryClient(MCPClient(endpoint))
                orchestrator.register("buddy", buddy_client)
                buddy_registered = True
                logger.info(
                    "MCPFactory: buddy зарегистрирован → %s (healthcheck %ds)",
                    endpoint,
                    settings.buddy_mcp_healthcheck_interval_s,
                )
            except Exception as exc:
                skipped.append(("buddy", f"client init failed: {exc}"))
                logger.warning(
                    "MCPFactory: buddy skip — client init failed: %s", exc
                )
        else:
            skipped.append(("buddy", "buddy_mcp_endpoint пустой"))
    else:
        skipped.append(("buddy", "buddy_mcp_enabled=false"))

    # 3. context (mcp-bsl-context, опциональный)
    if _is_bsl_context_configured(settings):
        # NB: реальная регистрация stdio MCP клиента требует subprocess spawn,
        # что не реализовано в текущем MCPClient (HTTP only). Этот блок —
        # placeholder для M-K3 когда добавим stdio transport. Пока skip.
        skipped.append((
            "context",
            "bsl-context configured но stdio transport не реализован (M-K3)",
        ))
        logger.info(
            "MCPFactory: context configured (jar=%s) но deferred до M-K3 (stdio)",
            settings.bsl_context_jar,
        )
    else:
        skipped.append((
            "context",
            "bsl_context_jar/java/platform не настроены или файлы отсутствуют",
        ))

    return FactoryResult(
        orchestrator=orchestrator,
        toolkit_registered=toolkit_registered,
        buddy_registered=buddy_registered,
        context_registered=context_registered,
        skipped=skipped,
    )
