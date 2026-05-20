"""Integration glue: MemoryManager + TrajectoryLogger ↔ orchestrator loop.

Вынесено отдельным модулем чтобы не раздувать loop.py. Каждый helper
делает ОДНУ вещь, ловит все exceptions (best-effort).

Sprint 1 — Hermes Memory Foundation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.learning import TrajectoryLogger
from app.memory import MemoryManager, MarkdownStore

logger = logging.getLogger(__name__)


def build_memory_manager(settings: Settings, channel_id: str) -> MemoryManager | None:
    """Создать MemoryManager с MarkdownStore для канала. None если disabled.

    Best-effort — exceptions logged, не raised. Memory не должна ронять loop.
    """
    if not settings.memory_enabled:
        return None
    try:
        manager = MemoryManager()
        store = MarkdownStore(root=settings.memory_root_path, channel_id=channel_id)
        manager.add_provider(store)
        return manager
    except Exception:
        logger.exception("Failed to initialize MemoryManager — continuing without memory")
        return None


def build_trajectory_logger(settings: Settings) -> TrajectoryLogger:
    """Возвращает TrajectoryLogger. Если learning_enabled=False — no-op версия."""
    return TrajectoryLogger(settings.trajectory_dir_path, enabled=settings.learning_enabled)


def memory_system_block(manager: MemoryManager | None) -> str:
    """Собрать memory block для инжекта в SYSTEM_PROMPT. '' если manager=None."""
    if manager is None:
        return ""
    try:
        return manager.build_system_prompt()
    except Exception:
        logger.exception("build_system_prompt failed — continuing without memory block")
        return ""


def memory_tool_schemas(manager: MemoryManager | None) -> list[dict]:
    """Список tool schemas от MemoryManager (для добавления к openai_tools)."""
    if manager is None:
        return []
    try:
        return manager.get_tool_schemas()
    except Exception:
        logger.exception("get_tool_schemas failed")
        return []


def is_memory_tool(tool_name: str) -> bool:
    """Heuristic: memory tool name starts with 'memory_'."""
    return tool_name.startswith("memory_")


def dispatch_memory_tool(
    manager: MemoryManager | None,
    tool_name: str,
    tool_args: dict,
) -> tuple[bool, Any, str | None]:
    """Вызвать memory tool через MemoryManager.

    Returns: (ok, result, error). Совместимо с _call_tool_with_retry сигнатурой.
    """
    if manager is None:
        return False, None, "memory subsystem disabled"
    try:
        result = manager.handle_tool_call(tool_name, tool_args)
        return True, {"status": "ok", "message": str(result)}, None
    except ValueError as exc:
        return False, None, f"unknown memory tool: {exc}"
    except Exception as exc:
        logger.exception("Memory tool %s failed", tool_name)
        return False, None, f"memory tool error: {exc}"


def sync_memory_post_turn(
    manager: MemoryManager | None,
    user_message: str,
    assistant_message: str,
) -> None:
    """Best-effort post-turn sync. Failures logged."""
    if manager is None:
        return
    try:
        manager.sync_all(user_message, assistant_message)
    except Exception:
        logger.exception("Memory sync_all failed (best-effort, ignored)")


def log_trajectory(
    trajectory: TrajectoryLogger,
    *,
    session_id: str,
    channel_id: str,
    messages: list[dict],
    tool_calls: list[dict],
    completed: bool,
    model: str,
    latency_ms: int | None = None,
) -> None:
    """Best-effort trajectory log. Failures logged."""
    try:
        trajectory.log_turn(
            session_id=session_id,
            channel_id=channel_id,
            messages=messages,
            tool_calls=tool_calls,
            completed=completed,
            model=model,
            latency_ms=latency_ms,
        )
    except Exception:
        logger.exception("Trajectory log failed (best-effort, ignored)")
