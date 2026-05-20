"""Self-learning subsystem (Sprint 1: только trajectory logging, dev-stub).

В Sprint 3 здесь появятся:
- background_review.py — daemon thread review fork
- curator.py — skill lifecycle maintenance
- skill_provenance.py — agent vs foreground tracking
- skill_usage.py — telemetry
- curator_backup.py — snapshot/rollback

См. `.planning/research/hermes-2026-05-20/HERMES-IMPLEMENTATION-PLAN.md`.
"""

from .trajectory import TrajectoryLogger

__all__ = ["TrajectoryLogger"]
