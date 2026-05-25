"""GET /diagnostics/aux — статус вспомогательных MCP-серверов (bsl-context).

Основные подключения (HTTP MCP к 1С) видны через /connections + ping. Aux MCP
(stdio) не персистятся в БД — настраиваются через env vars. Этот endpoint
показывает их состояние аналитику, чтобы /status видел весь стек, а не только
основную базу.

POST /diagnostics/connection/{conn_id} — полный отчёт по конкретному
подключению, для UI «Собрать диагностику». Возвращает JSON со всеми полями
которые нужны разработчику чтобы понять что у клиента сломалось — без
необходимости лезть в backend.log.
"""

import logging
import platform as pyplatform
import sys
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from pydantic import BaseModel, Field

from app.clients.mcp import (
    MCPClient,
    MCPDisconnectedError,
    is_local_endpoint,
    normalize_local_endpoint,
)
from app.clients.mcp_errors import classify_ping_error, collect_local_diagnostics
from app.config import Settings, get_settings
from app.log_setup import get_log_dir, get_log_file_path
from app.models import (
    AuxDiagnosticsResponse,
    AuxMCPStatus,
    EnvDiagnosticsResponse,
)
from app.orchestrator.mcp_pool import build_aux_clients


class LogPathResponse(BaseModel):
    """Путь к логам backend для UI «Открыть папку с логами»."""

    log_dir: str
    log_file: str
    exists: bool


class ConnectionDiagnosticsReport(BaseModel):
    """Полный диагностический отчёт по MCP-подключению.

    Собирается одним вызовом POST /diagnostics/connection/{id} — аналитик
    скачивает его как JSON и присылает разработчику без необходимости
    лезть в backend.log и набирать команды netstat.

    Структура намеренно плоская — чтобы при просмотре в текстовом редакторе
    разработчик увидел всё сразу: endpoint, класс ошибки, hint, DNS, прокси,
    probe соседних портов.
    """

    conn_id: str
    conn_name: str
    raw_endpoint: str
    normalized_endpoint: str
    is_local: bool

    # Результаты ping
    ping_ok: bool
    ping_duration_ms: int
    server_name: str | None = None
    tool_count: int | None = None

    # Классификация ошибки (None если ping_ok=True)
    error_class: str | None = None
    hint: str | None = None
    exception_type: str | None = None
    exception_message: str | None = None

    # Локальная сетевая диагностика (только для is_local=True)
    resolved_addresses: list[str] = Field(default_factory=list)
    proxy_env: dict[str, str] = Field(default_factory=dict)
    probe_ports_local: dict[str, bool] = Field(default_factory=dict)

    # Контекст системы
    platform: dict[str, str] = Field(default_factory=dict)
    app_version: str
    generated_at: str


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/aux", response_model=AuxDiagnosticsResponse)
async def aux_diagnostics(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuxDiagnosticsResponse:
    """Возвращает статус вспомогательных MCP-серверов (bsl-context и другие).

    Для каждого aux:
    - not_configured — env vars пустые, сервер не используется (это норма)
    - ok — initialize прошёл, tools получены
    - error — субпроцесс не стартовал / pipe оборвался; error_hint объясняет
      аналитику что проверить
    """
    aux_clients = build_aux_clients(settings)

    if not aux_clients:
        # Известный aux — bsl-context. Если он не настроен, показываем явно
        # «не подключён» вместо пустого списка — аналитик должен понимать,
        # что справочник BSL опционален и его можно подключить.
        return AuxDiagnosticsResponse(
            aux=[
                AuxMCPStatus(
                    name="bsl-context",
                    configured=False,
                    status="not_configured",
                    tool_count=0,
                    error_hint=(
                        "Справочник BSL опционален. Чтобы подключить — "
                        "укажите BSL_CONTEXT_JAR_PATH и BSL_CONTEXT_PLATFORM_PATH "
                        "в переменных окружения backend."
                    ),
                )
            ]
        )

    results: list[AuxMCPStatus] = []
    for client in aux_clients:
        name = client.config.name
        try:
            await client.initialize()
            tools = await client.list_tools()
            results.append(
                AuxMCPStatus(
                    name=name,
                    configured=True,
                    status="ok",
                    tool_count=len(tools),
                )
            )
        except MCPDisconnectedError as exc:
            results.append(
                AuxMCPStatus(
                    name=name,
                    configured=True,
                    status="error",
                    tool_count=0,
                    error_hint=(
                        f"Не удалось запустить {name}: {str(exc)[:200]}. "
                        "Проверьте путь к jar/platform и наличие Java."
                    ),
                )
            )
        except Exception as exc:  # pragma: no cover — защитный catch
            logger.exception("aux diagnostics failed for %s", name)
            results.append(
                AuxMCPStatus(
                    name=name,
                    configured=True,
                    status="error",
                    tool_count=0,
                    error_hint=f"Сбой инициализации {name}: {str(exc)[:200]}",
                )
            )
        finally:
            # Закрываем subprocess — диагностика разовая, orchestrator поднимет
            # свой экземпляр при следующем /chat запросе.
            try:
                await client.aclose()
            except Exception:
                pass

    return AuxDiagnosticsResponse(aux=results)


@router.get("/env", response_model=EnvDiagnosticsResponse)
async def env_diagnostics(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EnvDiagnosticsResponse:
    """Sanitized снимок окружения backend.

    Содержит только то, что аналитик должен видеть для контроля среды:
    адреса, пути, версии. API ключи и пароли НЕ включаются.
    """
    # Возвращаем resolved_* (с учётом bundled JAR + auto-detected Java/платформы)
    # чтобы пользователь видел что РЕАЛЬНО будет использовано, а не только
    # explicit env vars. Если env пустые и auto-detect ничего не нашёл — будут
    # пустые строки (UI показывает «не задан»).
    return EnvDiagnosticsResponse(
        app_version=settings.app_version,
        environment=settings.environment,
        default_llm_endpoint=settings.default_llm_endpoint,
        default_llm_model=settings.default_llm_model,
        bsl_context_jar=settings.resolved_bsl_jar,
        bsl_context_java=settings.resolved_bsl_java,
        bsl_context_platform_path=settings.resolved_bsl_platform_path,
        cors_origins=settings.cors_origins_list,
        sqlite_path=settings.sqlite_path,
        env_var_names={
            "default_llm_endpoint": "DEFAULT_LLM_ENDPOINT",
            "default_llm_model": "DEFAULT_LLM_MODEL",
            "bsl_context_jar": "BSL_CONTEXT_JAR_PATH",
            "bsl_context_java": "BSL_CONTEXT_JAVA",
            "bsl_context_platform_path": "BSL_CONTEXT_PLATFORM_PATH",
            "cors_origins": "BACKEND_ALLOWED_ORIGINS",
            "environment": "ENVIRONMENT",
        },
    )


@router.get("/log-path", response_model=LogPathResponse)
async def log_path() -> LogPathResponse:
    """Путь к файлу логов backend для UI «Открыть папку с логами».

    Используется коллегами при репорте багов: открыть папку, приложить
    последний backend.log. Файл может ещё не существовать если backend
    только что стартанул и не успел ничего записать — поле exists об этом
    сигнализирует.
    """
    file_path = get_log_file_path()
    return LogPathResponse(
        log_dir=str(get_log_dir()),
        log_file=str(file_path),
        exists=file_path.exists(),
    )


@router.post("/connection/{conn_id}", response_model=ConnectionDiagnosticsReport)
async def connection_diagnostics(
    conn_id: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConnectionDiagnosticsReport:
    """Полный диагностический отчёт по MCP-подключению.

    Делает то же что POST /connections/{id}/ping, но НЕ бросает HTTP 502 при
    ошибке: возвращает структурированный JSON с классификацией для UI
    «Собрать диагностику». Это значит endpoint всегда отвечает 200, даже если
    ping упал.

    Для local endpoints дополнительно собирает:
        - resolved_addresses (что socket.getaddrinfo возвращает для хоста)
        - proxy_env (значения *_PROXY env vars пользователя)
        - probe_ports_local (какие из стандартных портов 6003/6010/6080 слушаются)

    Аналитик скачивает отчёт как JSON и присылает разработчику одним файлом.
    """
    db = request.app.state.db
    async with db.execute(
        "SELECT name, endpoint FROM mcp_connections WHERE id = ?",
        (conn_id,),
    ) as cursor:
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Подключение '{conn_id}' не найдено",
        )

    name = row[0]
    endpoint = row[1]
    normalized = normalize_local_endpoint(endpoint)
    local = is_local_endpoint(normalized)
    local_diag = collect_local_diagnostics(normalized) if local else {}

    started_at = time.monotonic()
    ping_ok = False
    server_name: str | None = None
    tool_count: int | None = None
    error_class: str | None = None
    hint: str | None = None
    exception_type: str | None = None
    exception_message: str | None = None

    try:
        async with MCPClient(endpoint) as client:
            session = await client.initialize()
            tools = await client.list_tools()
        ping_ok = True
        server_name = session.server_name or None
        tool_count = len(tools)
    except Exception as exc:  # noqa: BLE001 — нам нужно поймать ЛЮБОЕ
        failure = classify_ping_error(exc, normalized)
        error_class = failure.error_class
        hint = failure.hint
        exception_type = failure.exception_type
        exception_message = failure.exception_message

    duration_ms = int((time.monotonic() - started_at) * 1000)

    return ConnectionDiagnosticsReport(
        conn_id=conn_id,
        conn_name=name,
        raw_endpoint=endpoint,
        normalized_endpoint=normalized,
        is_local=local,
        ping_ok=ping_ok,
        ping_duration_ms=duration_ms,
        server_name=server_name,
        tool_count=tool_count,
        error_class=error_class,
        hint=hint,
        exception_type=exception_type,
        exception_message=exception_message,
        resolved_addresses=local_diag.get("resolved_addresses", []),
        proxy_env=local_diag.get("proxy_env", {}),
        probe_ports_local=local_diag.get("probe_ports_local", {}),
        platform={
            "system": pyplatform.system(),
            "release": pyplatform.release(),
            "version": pyplatform.version(),
            "machine": pyplatform.machine(),
            "python": sys.version.split()[0],
        },
        app_version=settings.app_version,
        generated_at=datetime_utcnow_iso(),
    )


def datetime_utcnow_iso() -> str:
    """Текущее UTC время в ISO-формате, без зависимости от timezone-aware datetime."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
