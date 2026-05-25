"""Knowledge Layer — per-configuration knowledge базы данных, эмбеддингов и графа.

Knowledge Layer обеспечивает 6 уровней понимания 1С-системы:
- L1 Metadata (passport объектов из metadata_cache) — M-K1
- L2 Relational (KG через TreeSitter + SQLite + CTE, ADR-002) — M-K3
- L3 Conventional (антипаттерны A1-A11 + БСП patterns) — M-K3
- L4 Behavioral (Diagnose Engine YAML rulebook) — M-K3+M-K4
- L5 Knowledge (Triple RAG: v8std + БСП + .hbk fallback) — M-K2
- L6 Predictive (vs Типовой, temporal, 8.5-Ready) — M-K5

**Per-configuration layout** (см. storage.py):
- `~/.analyst-1c/knowledge/<fingerprint>/` — один каталог на одну
  типовую конфигурацию (УТ 11.5 на БСП 3.1.10 → один fingerprint)
- Внутри: metadata/ embeddings/ graph/ cache/ logs/

**Architecture decisions:** см. `.planning/knowledge-layer-2026-05-24/adr/`:
- ADR-001 vector-db (sqlite-vec)
- ADR-002 graph-db (SQLite + CTE)
- ADR-003 embeddings-runtime (FastEmbed + BGE-M3)
- ADR-004 capability-discovery (MCP initialize experimental)
- ADR-005 migrations-strategy (DDL, не alembic)

**Public API:** этот пакет экспортирует только базовые типы и фабрики.
Конкретная логика — в подмодулях (storage.py, fingerprint.py, etc.).
"""

from __future__ import annotations

from app.knowledge.fingerprint import (
    ConfigurationFingerprint,
    compute_fingerprint,
    fingerprint_from_string,
)
from app.knowledge.storage import (
    KnowledgeStorage,
    KnowledgeStorageError,
    get_storage,
)
from app.knowledge.types import (
    KnowledgeMode,
    ObjectPath,
    PlatformVersion,
)

__all__ = [
    # types
    "KnowledgeMode",
    "ObjectPath",
    "PlatformVersion",
    "ConfigurationFingerprint",
    # storage
    "KnowledgeStorage",
    "KnowledgeStorageError",
    "get_storage",
    # fingerprint
    "compute_fingerprint",
    "fingerprint_from_string",
]
