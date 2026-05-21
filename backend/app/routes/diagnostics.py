"""GET /diagnostics/aux — статус вспомогательных MCP-серверов (bsl-context).

Основные подключения (HTTP MCP к 1С) видны через /connections + ping. Aux MCP
(stdio) не персистятся в БД — настраиваются через env vars. Этот endpoint
показывает их состояние аналитику, чтобы /status видел весь стек, а не только
основную базу.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from pydantic import BaseModel

from app.clients.mcp import MCPDisconnectedError
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
    return EnvDiagnosticsResponse(
        app_version=settings.app_version,
        environment=settings.environment,
        default_llm_endpoint=settings.default_llm_endpoint,
        default_llm_model=settings.default_llm_model,
        bsl_context_jar=settings.bsl_context_jar,
        bsl_context_java=settings.bsl_context_java,
        bsl_context_platform_path=settings.bsl_context_platform_path,
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
