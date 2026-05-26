"""Knowledge API routes — L1-L6 access endpoints.

M-K1.13: первый endpoint — GET /knowledge/{channel_id}/dossier/{object_path}
для use case «расскажи про объект».

M-K2.2: добавлены indexer endpoints:
- POST /knowledge/{channel_id}/index/start — запускает background indexer
- GET /knowledge/{channel_id}/index/status — последний run + текущий running

M-K2.7: ИТС RAG endpoints:
- POST /knowledge/its/reload — переиндексация ИТС-корпуса (sync, идемпотентно)
- GET /knowledge/its/status — счётчики chunks/docs

M-K2.8: БСП Pattern Index endpoints:
- POST /knowledge/bsp/reload — переиндексация ssl_3_1/3_2 (sync, идемпотентно)
- GET /knowledge/bsp/status — счётчики methods/modules + разбивка по версиям

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

from app.config import get_settings
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
from app.knowledge.bsp_indexer import (
    count_bsp_by_version,
    count_bsp_methods,
    count_bsp_modules,
    index_bsp_corpus,
)
from app.knowledge.its_indexer import (
    count_its_chunks,
    count_its_documents,
    index_its_corpus,
)
from app.knowledge.its_tool import get_embedding_client
from app.knowledge.typical.card_storage import (
    count_cards_by_channel,
    get_card_by_qname,
)
from app.knowledge.typical.storage import list_configurations
from app.knowledge.graph_storage import count_by_kind, find_node
from app.knowledge.graph_storage import NodeKind

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


# ---------------- M-K2.7: ИТС RAG endpoints ----------------


@router.get("/its/status")
async def get_its_status(
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Возвращает счётчики ИТС-индекса + готовность embedding-клиента.

    Returns:
        {
          "chunks": int,           // фрагментов в its_chunks
          "documents": int,        // уникальных doc_id
          "enabled": bool,         // settings.its_enabled
          "ready": bool,           // settings.is_its_ready (есть API key)
          "provider": str,         // 'openai' | 'mock'
          "model": str,            // 'text-embedding-3-small'
          "dim": int,              // 1536
          "docs_root": str,        // resolved path
        }

    Не делает MCP-вызовов, безопасно дергать часто.
    """
    settings = get_settings()
    try:
        chunks = await count_its_chunks(db)
        docs = await count_its_documents(db)
    except Exception:  # noqa: BLE001 — endpoint должен возвращать всё что может
        logger.exception("ITS status: count failed")
        chunks = 0
        docs = 0

    return {
        "chunks": chunks,
        "documents": docs,
        "enabled": settings.its_enabled,
        "ready": settings.is_its_ready,
        "provider": settings.its_embedding_provider,
        "model": settings.its_embedding_model,
        "dim": settings.its_embedding_dim,
        "docs_root": str(settings.its_docs_root_path),
    }


@router.post("/its/reload")
async def reload_its(
    request: Request,
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Запускает (синхронно) полный re-index ИТС-корпуса.

    Idempotent: уже актуальные чанки skip'аются по chunk_hash. Полная
    re-index можно форсировать через `?force=true` query param.

    Сложность времени:
      - mock provider: < 1 сек на корпус.
      - openai provider: ≈ 30-90 сек на полный v8std (~1200 doc, ~2500 chunks).
        Включает ~50 batch embedding calls по 50 chunks.

    Returns:
        ITSIndexProgress dict (status, docs/chunks counters, duration, error).

    Errors:
        400 — settings.is_its_ready == False (нет API key / disabled)
        500 — критическая ошибка indexer'а (loader / DB / embedding)
    """
    settings = get_settings()
    if not settings.is_its_ready:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "its_not_ready",
                "message": "ITS RAG отключен или embedding-провайдер не настроен",
                "hint": (
                    "Задайте ITS_EMBEDDING_API_KEY (или DEFAULT_LLM_API_KEY_OPENAI) "
                    "и ITS_ENABLED=true в .env."
                ),
            },
        )

    force = request.query_params.get("force", "").lower() in ("1", "true", "yes")

    docs_root = settings.its_docs_root_path
    if not docs_root.exists():
        raise HTTPException(
            status_code=500,
            detail={
                "error": "its_docs_root_missing",
                "message": f"ITS docs root не найден: {docs_root}",
                "hint": "Задайте ITS_DOCS_ROOT в .env или клонируйте zeegin/v8std в tools/v8std.",
            },
        )

    try:
        client = await get_embedding_client(settings)
    except Exception as exc:  # noqa: BLE001 — endpoint граница
        logger.exception("ITS reload: не удалось построить embedding-клиент")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "embedding_client_init_failed",
                "message": str(exc),
            },
        ) from exc

    progress = await index_its_corpus(
        db, client, docs_root, force_reindex=force,
    )
    return {
        "status": progress.status,
        "docs_total": progress.docs_total,
        "docs_processed": progress.docs_processed,
        "chunks_total": progress.chunks_total,
        "chunks_embedded": progress.chunks_embedded,
        "chunks_skipped": progress.chunks_skipped,
        "duration_ms": progress.duration_ms,
        "started_at": progress.started_at,
        "finished_at": progress.finished_at,
        "error": progress.error,
    }


# ---------------- M-K2.8: БСП RAG endpoints ----------------


@router.get("/bsp/status")
async def get_bsp_status(
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Возвращает счётчики БСП-индекса + готовность embedding-клиента.

    Returns:
        {
          "methods": int,
          "modules": int,
          "by_version": {"3.1": int, "3.2": int},
          "enabled": bool,
          "ready": bool,
          "ssl_roots": [str, ...],
        }
    """
    settings = get_settings()
    try:
        methods = await count_bsp_methods(db)
        modules = await count_bsp_modules(db)
        by_version = await count_bsp_by_version(db)
    except Exception:  # noqa: BLE001
        logger.exception("BSP status: count failed")
        methods = 0
        modules = 0
        by_version = {}

    return {
        "methods": methods,
        "modules": modules,
        "by_version": by_version,
        "enabled": settings.bsp_enabled,
        "ready": settings.is_bsp_ready,
        "ssl_roots": [str(p) for p in settings.bsp_ssl_roots_paths],
    }


@router.post("/bsp/reload")
async def reload_bsp(
    request: Request,
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Запускает (синхронно) полный re-index ssl_3_1 + ssl_3_2 корпусов.

    Idempotent: уже актуальные методы (по chunk_hash) skip'аются.
    force=true в query — переэмбедить всё.

    Returns:
        BSPIndexProgress dict.

    Errors:
        400 — settings.is_bsp_ready=False
        500 — критическая ошибка indexer'а
    """
    settings = get_settings()
    if not settings.is_bsp_ready:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bsp_not_ready",
                "message": "BSP RAG отключен или embedding-провайдер не настроен",
                "hint": (
                    "Задайте ITS_EMBEDDING_API_KEY (или DEFAULT_LLM_API_KEY_OPENAI), "
                    "BSP_ENABLED=true и (опционально) BSP_SSL_ROOTS=path1,path2 в .env."
                ),
            },
        )

    force = request.query_params.get("force", "").lower() in ("1", "true", "yes")

    ssl_roots = settings.bsp_ssl_roots_paths
    # Filter to existing roots — indexer всё равно best-effort, но дадим
    # пользователю явный feedback если ни одного пути нет.
    existing_roots = [p for p in ssl_roots if p.exists()]
    if not existing_roots:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "bsp_ssl_roots_missing",
                "message": (
                    f"Ни один из БСП-каталогов не найден: {[str(p) for p in ssl_roots]}"
                ),
                "hint": (
                    "Клонируйте zeegin/ssl_3_1 и/или ssl_3_2 в tools/ или "
                    "укажите явный путь через BSP_SSL_ROOTS."
                ),
            },
        )

    try:
        client = await get_embedding_client(settings)
    except Exception as exc:  # noqa: BLE001
        logger.exception("BSP reload: embedding client init failed")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "embedding_client_init_failed",
                "message": str(exc),
            },
        ) from exc

    progress = await index_bsp_corpus(
        db, client, existing_roots, force_reindex=force,
    )
    return {
        "status": progress.status,
        "roots_total": progress.roots_total,
        "methods_total": progress.methods_total,
        "methods_embedded": progress.methods_embedded,
        "methods_skipped": progress.methods_skipped,
        "duration_ms": progress.duration_ms,
        "started_at": progress.started_at,
        "finished_at": progress.finished_at,
        "error": progress.error,
    }


# ── M-K2.5.7: Typical Configurations endpoints ────────────────────────


@router.get("/typical/configurations")
async def list_typical_configs(db=Depends(_get_db)) -> dict:  # noqa: B008
    """Возвращает список загруженных в БД типовых конфигураций.

    Используется фронтендом для селектора «Сравнить с типовой».
    Не зависит от channel_id MCP — типовые namespace'нуты отдельно
    (`_ut115_*`, `_bp30_*`, ...).

    Включает счётчики nodes + cards чтобы UI мог показать готовность:
    «БП 3.0.138.24 — граф 60k, карточки 10/8525».
    """
    configs = await list_configurations(db)
    result: list[dict] = []
    for cfg in configs:
        node_counts = await count_by_kind(db, cfg.channel_id)
        card_counts = await count_cards_by_channel(db, cfg.channel_id)
        result.append({
            "channel_id": cfg.channel_id,
            "config_kind": cfg.config_kind,
            "config_version": cfg.config_version,
            "display_name": cfg.display_name,
            "status": cfg.status,
            "indexed_at": cfg.indexed_at,
            "source_path": cfg.source_path,
            "node_counts": node_counts,
            "card_counts": card_counts,
            "total_nodes": sum(node_counts.values()),
            "total_cards": sum(card_counts.values()),
        })
    return {
        "configurations": result,
        "total": len(result),
    }


@router.get("/typical/{channel_id}/object/{object_qualified_name:path}")
async def get_typical_object(
    channel_id: Annotated[str, Path(description="ID типовой (например _bp30_138_24)")],
    object_qualified_name: Annotated[str, Path(description="Полное имя объекта")],
    db=Depends(_get_db),  # noqa: B008
) -> dict:
    """Возвращает описание объекта типовой: карточка (если есть) + базовый узел графа.

    UI использует этот endpoint для раскрывающейся `TypicalObjectCard`
    в чат-потоке (когда LLM вызвал `explain_typical_object`).

    404 если объект не найден в графе.
    """
    node = await find_node(
        db,
        channel_id=channel_id,
        qualified_name=object_qualified_name,
        node_kind=NodeKind.METADATA_OBJECT.value,
    )
    if node is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "typical_object_not_found",
                "channel_id": channel_id,
                "object_qualified_name": object_qualified_name,
                "hint": "Проверь что типовая загружена через /knowledge/typical/configurations.",
            },
        )

    card_rec = await get_card_by_qname(
        db,
        channel_id=channel_id,
        object_qualified_name=object_qualified_name,
    )

    return {
        "channel_id": channel_id,
        "object_qualified_name": object_qualified_name,
        "object_kind": node.attributes.get("kind"),
        "name": node.attributes.get("name"),
        "comment": node.attributes.get("comment", ""),
        "source_path": node.source_path,
        "card": card_rec.card.to_dict() if card_rec else None,
        "card_status": card_rec.status if card_rec else "not_generated",
        "card_updated_at": card_rec.updated_at if card_rec else None,
    }
