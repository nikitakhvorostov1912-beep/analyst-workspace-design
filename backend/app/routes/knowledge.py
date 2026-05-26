"""Knowledge API routes — L1-L6 access endpoints.

M-K1.13: первый endpoint — GET /knowledge/{channel_id}/dossier/{object_path}
для use case «расскажи про объект».

M-K2.2: добавлены indexer endpoints:
- POST /knowledge/{channel_id}/index/start — запускает background indexer
- GET /knowledge/{channel_id}/index/status — последний run + текущий running

Будущие endpoints (M-K3+):
- GET /knowledge/{channel}/search?q=... — semantic L5 search
- GET /knowledge/{channel}/graph/{object} — L2 traversal
- POST /knowledge/{channel}/diagnose — L4 reasoning
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.knowledge.dossier import (
    DossierNotFoundError,
    ObjectDossier,
    get_dossier,
)
from app.knowledge.indexer import bulk_refresh_metadata_cache
from app.knowledge.indexer_state import (
    IndexerAlreadyRunningError,
    complete_run,
    fail_run_with_error,
    get_current_running,
    get_latest_run,
    start_run,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

# Module-level set для fire-and-forget background indexer tasks.
# Без сохранения ссылки GC может собрать task до завершения. Cleanup —
# через add_done_callback(.discard) после создания.
_INDEXER_TASKS: set[asyncio.Task] = set()


def _get_db(request: Request):
    """FastAPI dependency — отдаёт основной SQLite connection."""
    return request.app.state.db


async def _lookup_mcp_endpoint(db, channel_id: str) -> str | None:
    """Читает endpoint MCP канала из mcp_connections. None если канал не найден."""
    cursor = await db.execute(
        "SELECT endpoint FROM mcp_connections WHERE id = ? LIMIT 1",
        (channel_id,),
    )
    row = await cursor.fetchone()
    return row[0] if row else None


@router.get("/{channel_id}/dossier/{object_path:path}")
async def get_object_dossier(
    channel_id: Annotated[str, Path(description="ID MCP-канала")],
    object_path: Annotated[str, Path(description="Полный путь объекта (e.g. 'Документ.ОПП')")],
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Возвращает паспорт объекта 1С метаданных.

    M-K1.13: минимальная реализация — читает из metadata_cache (v5).
    Если объект не в кеше — 404 с подсказкой что выполнить /ping или
    /metadata-suggest для заполнения.

    Path-параметр `object_path` использует `:path` converter чтобы FastAPI
    не split'ил по точкам (e.g. 'Документ.ОПП' попадёт целиком).
    """
    try:
        dossier = await get_dossier(db, channel_id, object_path)
    except ValueError as exc:
        # ObjectPath.parse не справился — невалидный формат
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_object_path",
                "message": str(exc),
                "hint": "Формат: <Тип>.<Имя> (e.g. 'Документ.ОПП')",
            },
        ) from exc
    except DossierNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "not_found_in_cache",
                "message": str(exc),
                "hint": (
                    "Кеш метаданных пустой для этого канала. "
                    "Выполните POST /knowledge/{channel_id}/index/start "
                    "или /connections/{channel_id}/ping."
                ),
            },
        ) from exc

    return _dossier_to_response(dossier)


def _dossier_to_response(dossier: ObjectDossier) -> dict:
    """Сериализация ObjectDossier в JSON-friendly dict.

    Сохраняем frozen dataclass нетронутым — копируем нужные поля для API.
    """
    return {
        "object_path": dossier.object_path.full,
        "kind": dossier.kind,
        "name": dossier.object_path.name,
        "presentation": dossier.presentation,
        "channel_id": dossier.channel_id,
        "fetched_at": dossier.fetched_at.isoformat() if dossier.fetched_at else None,
        "source": dossier.source,
        "attributes": dossier.attributes,
        "tabular_sections": dossier.tabular_sections,
        "forms": dossier.forms,
        "subscriptions": dossier.subscriptions,
        "related_objects": dossier.related_objects,
    }


# ---------------- M-K2.2: Indexer endpoints ----------------


async def _run_indexer_background(
    db, channel_id: str, endpoint: str, run_id: int
) -> None:
    """Background task wrapper для bulk_refresh_metadata_cache.

    Запускается через asyncio.create_task. Никогда не raise'ит наружу —
    все ошибки попадают в index_runs row через fail_run_with_error /
    complete_run.

    Args:
        db: aiosqlite connection (shared with main loop — единая event loop)
        channel_id: канал
        endpoint: MCP URL
        run_id: ID row из index_runs созданной start_run() ранее
    """
    try:
        progress = await bulk_refresh_metadata_cache(db, channel_id, endpoint)
        await complete_run(db, run_id, progress)
        logger.info(
            "Indexer background task для канала %s завершён: %s, %d объектов",
            channel_id,
            progress.status,
            progress.objects_written,
        )
    except asyncio.CancelledError:
        # Loop отменился (shutdown / interrupt) — помечаем cancelled как failed
        await fail_run_with_error(db, run_id, "Indexer task отменён")
        raise
    except Exception as exc:  # noqa: BLE001 — last-resort граница background task
        logger.exception(
            "Indexer background task для канала %s упал неожиданно", channel_id
        )
        try:
            await fail_run_with_error(db, run_id, f"Unexpected error: {exc}")
        except Exception:
            logger.exception("Не удалось пометить index_runs failed для run_id=%d", run_id)


@router.post("/{channel_id}/index/start", status_code=202)
async def start_indexer(
    channel_id: Annotated[str, Path(description="ID MCP-канала")],
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Запускает полный indexing run для канала в background.

    Returns:
        202 Accepted с {run_id, channel_id, status, started_at}.

    Errors:
        404 — канал не найден в mcp_connections
        409 — уже есть активный (running) run для этого канала
    """
    endpoint = await _lookup_mcp_endpoint(db, channel_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "channel_not_found",
                "message": f"MCP канал {channel_id!r} не зарегистрирован",
                "hint": "Создайте подключение через POST /connections",
            },
        )

    try:
        run = await start_run(db, channel_id)
    except IndexerAlreadyRunningError as exc:
        running = await get_current_running(db, channel_id)
        raise HTTPException(
            status_code=409,
            detail={
                "error": "indexer_already_running",
                "message": str(exc),
                "current_run": running.to_response_dict() if running else None,
            },
        ) from exc

    # Стартуем background task. Храним ссылку в _INDEXER_TASKS чтобы GC
    # не собрал task до завершения. После завершения discard через callback.
    task = asyncio.create_task(
        _run_indexer_background(db, channel_id, endpoint, run.id),
        name=f"indexer-{channel_id}-{run.id}",
    )
    _INDEXER_TASKS.add(task)
    task.add_done_callback(_INDEXER_TASKS.discard)

    return {
        "run_id": run.id,
        "channel_id": channel_id,
        "status": run.status,
        "started_at": run.started_at,
        "message": "Indexer запущен в background. Прогресс — GET /knowledge/{channel_id}/index/status",
    }


@router.get("/{channel_id}/index/status")
async def get_indexer_status(
    channel_id: Annotated[str, Path(description="ID MCP-канала")],
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Возвращает статус indexer'а для канала.

    Returns:
        {
          "latest": IndexRun | null,    // последний run (любой статус)
          "running": IndexRun | null,   // текущий running (если есть)
          "channel_id": str
        }

    Errors:
        404 — канал не найден в mcp_connections
    """
    endpoint = await _lookup_mcp_endpoint(db, channel_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "channel_not_found",
                "message": f"MCP канал {channel_id!r} не зарегистрирован",
            },
        )

    latest = await get_latest_run(db, channel_id)
    running = await get_current_running(db, channel_id)

    return {
        "channel_id": channel_id,
        "latest": latest.to_response_dict() if latest else None,
        "running": running.to_response_dict() if running else None,
    }
