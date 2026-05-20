"""Persistent memory subsystem (Sprint 1 — Hermes pattern).

См. `.planning/research/hermes-2026-05-20/HERMES-IMPLEMENTATION-PLAN.md`,
раздел 7 «Спринт 1 — Memory Foundation».

Provider abstraction позволяет в Sprint 3 добавить Honcho-style external
provider не трогая core orchestrator. Сейчас единственный провайдер —
MarkdownStore (MEMORY.md + USER.md).
"""

from .injection_scan import sanitize_for_prompt, scan
from .manager import MemoryManager
from .markdown_store import MarkdownStore
from .provider import MemoryProvider

__all__ = [
    "MemoryManager",
    "MemoryProvider",
    "MarkdownStore",
    "scan",
    "sanitize_for_prompt",
]
