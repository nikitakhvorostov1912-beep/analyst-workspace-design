"""Skill provenance — отличаем agent-sediment от user-directed writes.

Sprint 3 (Hermes A8): ContextVar различает кто сейчас пишет skill —
сам агент (через background_review) или явное действие пользователя.

Curator работает ТОЛЬКО с agent-created skills:
- Они автоматически архивируются при низком usage.
- User-created skills неприкосновенны без явного действия пользователя.

API:
    with provenance("agent"):
        skill_store.write(skill_id, content)  # → provenance="agent"

    skill_store.write(skill_id, content)  # → provenance="user" (default)
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Literal

Provenance = Literal["agent", "user"]

_PROVENANCE: ContextVar[Provenance] = ContextVar("skill_provenance", default="user")


def current_provenance() -> Provenance:
    """Возвращает текущий контекст провенанса. Default = 'user'."""
    return _PROVENANCE.get()


@contextmanager
def provenance(value: Provenance) -> Iterator[None]:
    """Контекст-менеджер: устанавливает провенанс для блока кода.

    Usage:
        with provenance("agent"):
            ... все write операции внутри будут помечены как agent ...

    Корректно работает с asyncio: ContextVar изолирован per-task.
    """
    if value not in ("agent", "user"):
        raise ValueError(f"provenance must be 'agent' or 'user', got {value!r}")
    token = _PROVENANCE.set(value)
    try:
        yield
    finally:
        _PROVENANCE.reset(token)
