"""Knowledge API routes — L1-L6 access endpoints.

M-K1.13: первый endpoint — GET /knowledge/{channel_id}/dossier/{object_path}
для use case «расскажи про объект».

Будущие endpoints (M-K2+):
- GET /knowledge/{channel}/search?q=... — semantic L5 search
- GET /knowledge/{channel}/graph/{object} — L2 traversal
- POST /knowledge/{channel}/diagnose — L4 reasoning
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request

from app.knowledge.dossier import (
    DossierNotFoundError,
    ObjectDossier,
    get_dossier,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _get_db(request: Request):
    """FastAPI dependency — отдаёт основной SQLite connection."""
    return request.app.state.db


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

    Response shape (минимум):
    ```json
    {
        "object_path": "Документ.ОПП",
        "kind": "Документ",
        "name": "ОПП",
        "presentation": "Отгрузка под перевозку",
        "channel_id": "abc-123",
        "fetched_at": "2026-05-25T22:00:00",
        "source": "cache",
        "attributes": [],
        "tabular_sections": [],
        "forms": [],
        "subscriptions": [],
        "related_objects": []
    }
    ```
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
                    "Выполните POST /connections/{channel_id}/ping "
                    "или GET /connections/{channel_id}/metadata-suggest?q="
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
