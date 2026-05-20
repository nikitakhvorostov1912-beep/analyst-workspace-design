"""REST endpoints для Sprint 3 (Hermes): skills + curator + todos."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.learning.curator import Curator
from app.learning.curator_backup import CuratorBackup
from app.learning.skill_store import MAX_SKILL_BYTES, Skill, SkillStore
from app.learning.skill_usage import SkillUsageStore
from app.orchestrator.todo import TODOS, dispatch_todo_tool

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Pydantic models ───


class SkillDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    body: str
    provenance: str
    tags: list[str]
    created_at: str
    updated_at: str
    pinned: bool
    archived: bool
    chars: int
    usage_count: int = 0
    last_used_iso: str | None = None


class SkillListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel_id: str
    active: list[SkillDTO]
    archived: list[SkillDTO]


class SkillCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None  # auto-generate если None
    body: str = Field(min_length=1, max_length=MAX_SKILL_BYTES)
    tags: list[str] = Field(default_factory=list)
    pinned: bool = False


class CuratorRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = False


class CuratorReportDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inspected: int
    archived: list[str]
    skipped_pinned: list[str]
    skipped_user: list[str]
    skipped_recent: list[str]
    backup_label: str | None = None


class TodoDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    status: str
    created_at: str
    completed_at: str | None = None


class TodoListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    items: list[TodoDTO]
    active_count: int


# ─── Helpers ───


def _skill_to_dto(skill: Skill, usage: SkillUsageStore | None) -> SkillDTO:
    usage_count = 0
    last_used = None
    if usage is not None:
        stats = usage.get(skill.id)
        usage_count = stats.count
        last_used = stats.last_used_iso
    return SkillDTO(
        id=skill.id,
        body=skill.body,
        provenance=skill.provenance,
        tags=list(skill.tags),
        created_at=skill.created_at,
        updated_at=skill.updated_at,
        pinned=skill.pinned,
        archived=skill.archived,
        chars=skill.chars,
        usage_count=usage_count,
        last_used_iso=last_used,
    )


def _build_store(channel_id: str) -> tuple[SkillStore, SkillUsageStore]:
    settings = get_settings()
    if not settings.memory_enabled:
        raise HTTPException(status_code=503, detail="Skills отключены (memory_enabled=false)")
    skills_root = settings.memory_root_path / "skills"
    store = SkillStore(skills_root, channel_id)
    usage = SkillUsageStore(store.directory)
    return store, usage


# ─── Routes: skills ───


@router.get("/skills/{channel_id}", response_model=SkillListResponse)
async def list_skills(channel_id: str) -> SkillListResponse:
    store, usage = _build_store(channel_id)
    active = [_skill_to_dto(s, usage) for s in store.list_active()]
    archived = [_skill_to_dto(s, usage) for s in store.list_archived()]
    return SkillListResponse(channel_id=channel_id, active=active, archived=archived)


@router.post("/skills/{channel_id}", response_model=SkillDTO, status_code=201)
async def create_skill(channel_id: str, body: SkillCreateRequest) -> SkillDTO:
    store, usage = _build_store(channel_id)
    skill_id = body.id or store.generate_skill_id()
    try:
        skill = Skill(
            id=skill_id,
            body=body.body,
            provenance="user",  # user-explicit через REST
            tags=list(body.tags),
            pinned=body.pinned,
        )
        store.write(skill)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _skill_to_dto(skill, usage)


@router.post("/skills/{channel_id}/{skill_id}/archive", status_code=204)
async def archive_skill(channel_id: str, skill_id: str) -> None:
    store, _ = _build_store(channel_id)
    if not store.archive(skill_id):
        # Не найден или pinned
        existing = store.read(skill_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Skill не найден")
        if existing.pinned:
            raise HTTPException(status_code=409, detail="Pinned skill нельзя архивировать")
        raise HTTPException(status_code=500, detail="Не удалось архивировать")


@router.post("/skills/{channel_id}/{skill_id}/unarchive", status_code=204)
async def unarchive_skill(channel_id: str, skill_id: str) -> None:
    store, _ = _build_store(channel_id)
    if not store.unarchive(skill_id):
        raise HTTPException(status_code=404, detail="Skill в архиве не найден")


@router.delete("/skills/{channel_id}/{skill_id}", status_code=204)
async def delete_skill(channel_id: str, skill_id: str) -> None:
    store, usage = _build_store(channel_id)
    existing = store.read(skill_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Skill не найден")
    if existing.pinned:
        raise HTTPException(status_code=409, detail="Pinned skill нельзя удалить")
    if not store.delete(skill_id):
        raise HTTPException(status_code=500, detail="Не удалось удалить")
    usage.remove(skill_id)


# ─── Routes: curator ───


@router.post("/skills/{channel_id}/curator/run", response_model=CuratorReportDTO)
async def run_curator(channel_id: str, body: CuratorRunRequest) -> CuratorReportDTO:
    store, usage = _build_store(channel_id)
    backup = CuratorBackup(store.directory)
    curator = Curator(store=store, usage=usage, backup=backup)
    report = curator.run(dry_run=body.dry_run)
    return CuratorReportDTO(
        inspected=report.inspected,
        archived=list(report.archived),
        skipped_pinned=list(report.skipped_pinned),
        skipped_user=list(report.skipped_user),
        skipped_recent=list(report.skipped_recent),
        backup_label=report.backup.timestamp if report.backup else None,
    )


# ─── Routes: todos ───


@router.get("/todos/{session_id}", response_model=TodoListResponse)
async def list_todos(session_id: str) -> TodoListResponse:
    items = TODOS.list(session_id)
    return TodoListResponse(
        session_id=session_id,
        items=[
            TodoDTO(
                id=i.id,
                text=i.text,
                status=i.status,
                created_at=i.created_at,
                completed_at=i.completed_at,
            )
            for i in items
        ],
        active_count=TODOS.active_count(session_id),
    )


class TodoActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str  # "add" | "complete" | "clear"
    items: list[str] | None = None
    ids: list[str] | None = None


@router.post("/todos/{session_id}/action")
async def todo_action(session_id: str, body: TodoActionRequest) -> dict[str, Any]:
    if body.action == "add":
        ok, result, err = dispatch_todo_tool(session_id, "todo_add", {"items": body.items or []})
        if not ok:
            raise HTTPException(status_code=400, detail=err or "ошибка добавления")
        return result
    if body.action == "complete":
        ok, result, err = dispatch_todo_tool(session_id, "todo_complete", {"ids": body.ids or []})
        if not ok:
            raise HTTPException(status_code=400, detail=err or "ошибка завершения")
        return result
    if body.action == "clear":
        cleared = TODOS.clear(session_id)
        return {"cleared": cleared}
    raise HTTPException(status_code=400, detail=f"Неизвестное действие: {body.action}")
