"""REST endpoints для постоянной памяти (MEMORY.md + USER.md).

GET  /memory/{channel_id}     — текущий snapshot обоих namespace
PUT  /memory/{channel_id}     — перезаписать один namespace (UI редактор)
GET  /diagnostics/trajectory  — статистика JSONL логов

Sprint 1 — Hermes Memory Foundation. См. HERMES-IMPLEMENTATION-PLAN.md
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path

from app.config import Settings, get_settings
from app.learning import TrajectoryLogger
from app.memory import MarkdownStore, scan
from app.models import (
    MemoryDocument,
    MemoryNamespacePayload,
    MemoryUpdateRequest,
    MemoryUpdateResponse,
    TrajectoryStatsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["memory"])


def _resolve_store(settings: Settings, channel_id: str) -> MarkdownStore:
    """Создаёт MarkdownStore для канала, инициализируя файлы при первом обращении."""
    store = MarkdownStore(root=settings.memory_root_path, channel_id=channel_id)
    store.initialize()
    return store


@router.get("/memory/{channel_id}", response_model=MemoryDocument)
async def get_memory(
    channel_id: str = Path(min_length=1, max_length=128),
    settings: Settings = Depends(get_settings),
) -> MemoryDocument:
    """Returns snapshot обоих namespace для канала.

    Если файлов нет — пустые строки. Поле `safe` = True если в содержимом
    нет обнаруживаемых prompt injection patterns.
    """
    if not settings.memory_enabled:
        raise HTTPException(status_code=503, detail="Memory subsystem disabled (MEMORY_ENABLED=false)")
    store = _resolve_store(settings, channel_id)
    agent_text = store.read_namespace("agent")
    user_text = store.read_namespace("user")
    threats = scan(agent_text) + scan(user_text)
    return MemoryDocument(
        channel_id=channel_id,
        agent=MemoryNamespacePayload(content=agent_text, chars=len(agent_text)),
        user=MemoryNamespacePayload(content=user_text, chars=len(user_text)),
        safe=not threats,
    )


@router.put("/memory/{channel_id}", response_model=MemoryUpdateResponse)
async def update_memory(
    payload: MemoryUpdateRequest,
    channel_id: str = Path(min_length=1, max_length=128),
    settings: Settings = Depends(get_settings),
) -> MemoryUpdateResponse:
    """Перезаписать один namespace полностью.

    Injection patterns в content обнаруживаются и возвращаются в `threats_found`.
    Контент НЕ блокируется (пользователь может явно редактировать) — это просто
    предупреждение для UI.
    """
    if not settings.memory_enabled:
        raise HTTPException(status_code=503, detail="Memory subsystem disabled")
    store = _resolve_store(settings, channel_id)
    threats = scan(payload.content)
    chars = store.write_namespace(payload.namespace, payload.content)
    logger.info(
        "Memory PUT: channel=%s namespace=%s chars=%d threats=%d",
        channel_id, payload.namespace, chars, len(threats),
    )
    return MemoryUpdateResponse(
        namespace=payload.namespace,
        chars_written=chars,
        threats_found=[label for label, _ in threats],
    )


@router.get("/diagnostics/trajectory", response_model=TrajectoryStatsResponse)
async def trajectory_stats(
    settings: Settings = Depends(get_settings),
) -> TrajectoryStatsResponse:
    """Статистика JSONL trajectory логов — для дашборда и диагностики."""
    logger_ = TrajectoryLogger(settings.trajectory_dir_path, enabled=settings.learning_enabled)
    stats = logger_.stats()
    return TrajectoryStatsResponse(
        enabled=settings.learning_enabled,
        root=str(settings.trajectory_dir_path),
        sample_count=stats["sample_count"],
        failed_count=stats["failed_count"],
    )
