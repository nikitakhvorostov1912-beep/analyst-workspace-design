"""Knowledge Storage — per-configuration layout управление.

M-K1.4 pre-flight. Управляет физическим размещением knowledge данных
на диске пользователя.

**Layout:**
```
$ANALYST_HOME/knowledge/<fingerprint>/
├── metadata/        ← L1 metadata cache (JSON) + dossier snapshots
├── embeddings/      ← L5 sqlite-vec БД (ADR-001)
├── graph/           ← L2 SQLite граф (ADR-002)
├── cache/           ← Temporary cache (TTL-based eviction)
└── logs/            ← Debug logs per канал
```

`$ANALYST_HOME` определяется как:
1. env var `ANALYST_HOME` если задан
2. `~/.analyst-1c` по умолчанию

**Безопасность:**
- Path traversal: все paths валидируются что находятся внутри root
- Encoding: file writes принудительно UTF-8 без BOM
- Permissions: на Unix — `0o700` (только owner)
- Concurrency: на уровне процесса (по одному `KnowledgeStorage` per
  fingerprint cached в module-level dict)
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from app.knowledge.fingerprint import ConfigurationFingerprint
from app.knowledge.types import KNOWLEDGE_SUBDIRS, KnowledgeSubdir

logger = logging.getLogger(__name__)


class KnowledgeStorageError(RuntimeError):
    """Базовая ошибка для Knowledge Storage операций (path traversal, permissions, etc.)."""


# Default root: ~/.analyst-1c
_DEFAULT_ROOT_NAME = ".analyst-1c"
_KNOWLEDGE_DIR = "knowledge"


def _resolve_analyst_home() -> Path:
    """Resolve $ANALYST_HOME или ~/.analyst-1c."""
    explicit = os.environ.get("ANALYST_HOME", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return Path.home().joinpath(_DEFAULT_ROOT_NAME).resolve()


class KnowledgeStorage:
    """Per-fingerprint каталог knowledge данных.

    Не выполняет I/O при создании. Каталоги создаются ленивыми вызовами
    `ensure_subdir(name)` либо явным `initialize()` (создаёт все subdirs
    сразу — удобно для kickoff).

    **Read-only by default:** методы знают как читать. Запись — через
    отдельные writer-классы которые будут добавлены в M-K2 (vector_store,
    graph_store), они получают `KnowledgeStorage` как DI и пишут в свои
    subdirs.
    """

    def __init__(
        self,
        fingerprint: ConfigurationFingerprint,
        *,
        analyst_home: Path | None = None,
    ) -> None:
        self._fingerprint = fingerprint
        self._home = (analyst_home or _resolve_analyst_home()).resolve()
        # root_per_fp = $ANALYST_HOME/knowledge/<slug>
        self._root = self._home.joinpath(_KNOWLEDGE_DIR, fingerprint.slug).resolve()

    @property
    def fingerprint(self) -> ConfigurationFingerprint:
        return self._fingerprint

    @property
    def root(self) -> Path:
        """Корень storage для этого fingerprint."""
        return self._root

    @property
    def analyst_home(self) -> Path:
        return self._home

    def subdir(self, name: KnowledgeSubdir) -> Path:
        """Возвращает путь к subdir БЕЗ создания.

        Гарантирует что результат — strict child от `self.root`.
        Защита от path traversal (если name содержит '..' / абсолютный путь).
        """
        candidate = (self._root / name).resolve()
        # strict subset проверка (Python 3.9+: Path.is_relative_to)
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise KnowledgeStorageError(
                f"Path traversal blocked: {name!r} resolves outside {self._root!r}"
            ) from exc
        return candidate

    def ensure_subdir(self, name: KnowledgeSubdir) -> Path:
        """Создаёт subdir если нет. Возвращает путь."""
        path = self.subdir(name)
        try:
            path.mkdir(parents=True, exist_ok=True)
            # Unix-only: ограничить права (на Windows os.chmod игнорируется
            # для большинства флагов, что нормально)
            if os.name == "posix":
                try:
                    os.chmod(path, 0o700)
                except OSError as chmod_exc:
                    logger.warning(
                        "Не удалось установить 0o700 на %s: %s",
                        path,
                        chmod_exc,
                    )
        except OSError as exc:
            raise KnowledgeStorageError(
                f"Не удалось создать {path}: {exc}"
            ) from exc
        return path

    def initialize(self) -> None:
        """Создаёт все 5 subdirs одним вызовом.

        Idempotent — повторный вызов без эффекта если все subdirs уже есть.
        Используется при первой регистрации канала / `/connections/{id}/ping`
        после успешного MCP initialize.
        """
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            if os.name == "posix":
                try:
                    os.chmod(self._root, 0o700)
                except OSError as chmod_exc:
                    logger.warning(
                        "Не удалось установить 0o700 на root %s: %s",
                        self._root,
                        chmod_exc,
                    )
        except OSError as exc:
            raise KnowledgeStorageError(
                f"Не удалось создать root {self._root}: {exc}"
            ) from exc

        for subdir in KNOWLEDGE_SUBDIRS:
            self.ensure_subdir(subdir)

        logger.info(
            "KnowledgeStorage initialized: fingerprint=%s root=%s",
            self._fingerprint.slug,
            self._root,
        )

    def exists(self) -> bool:
        """True если root уже создан (хотя бы initialize() был вызван)."""
        return self._root.exists() and self._root.is_dir()

    def __repr__(self) -> str:
        return (
            f"<KnowledgeStorage fingerprint={self._fingerprint.slug!r} "
            f"root={self._root!s}>"
        )


# ---------------------------------------------------------------------------
# Module-level cache (one KnowledgeStorage per fingerprint slug)
# ---------------------------------------------------------------------------

_STORAGE_CACHE: dict[str, KnowledgeStorage] = {}
_STORAGE_LOCK = threading.Lock()


def get_storage(
    fingerprint: ConfigurationFingerprint,
    *,
    analyst_home: Path | None = None,
) -> KnowledgeStorage:
    """Factory с module-level кэшем.

    Возвращает тот же KnowledgeStorage instance для одного fingerprint slug
    в рамках одного процесса. Это безопасно — KnowledgeStorage stateless
    (не держит open file handles, не кеширует данные внутри).
    """
    key = fingerprint.slug
    with _STORAGE_LOCK:
        cached = _STORAGE_CACHE.get(key)
        if cached is None:
            cached = KnowledgeStorage(fingerprint, analyst_home=analyst_home)
            _STORAGE_CACHE[key] = cached
        return cached


def _reset_cache_for_tests() -> None:
    """Сброс module-level кэша. Только для тестов!"""
    with _STORAGE_LOCK:
        _STORAGE_CACHE.clear()
