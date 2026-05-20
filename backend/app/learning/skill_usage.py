"""Skill usage telemetry — счётчик использования каждого skill.

Sprint 3 (Hermes A9): `~/.analyst-1c/skills/<channel>/.usage.json` —
counter на каждый skill. Curator читает derived activity timestamp для
lifecycle decisions (auto-archive при низком usage за период).

Дизайн:
- Один JSON-файл на channel: {"skill_id": {"count": int, "last_used": iso8601}}
- Атомарная запись: write to .tmp → os.replace().
- Thread-safe через file lock (single-process модель, fcntl/msvcrt не нужны —
  достаточно threading.Lock на уровне процесса).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


USAGE_FILE_NAME = ".usage.json"


@dataclass(frozen=True)
class UsageStats:
    """Снимок статистики одного skill."""

    skill_id: str
    count: int
    last_used_iso: str | None  # ISO 8601 UTC или None если ни разу не использован


class SkillUsageStore:
    """Telemetry для skill usage.

    Args:
        root: путь к каталогу channel (обычно <memory_root>/skills/<channel_id>/).
            Файл .usage.json лежит здесь же.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._file = self._root / USAGE_FILE_NAME
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict]:
        if not self._file.exists():
            return {}
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, dict]) -> None:
        self._root.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self._file)

    def increment(self, skill_id: str) -> int:
        """Инкрементирует count и обновляет last_used. Возвращает новое значение."""
        if not skill_id:
            raise ValueError("skill_id must be non-empty")
        with self._lock:
            data = self._read()
            entry = data.get(skill_id) or {"count": 0, "last_used": None}
            entry["count"] = int(entry.get("count") or 0) + 1
            entry["last_used"] = datetime.now(UTC).isoformat()
            data[skill_id] = entry
            self._write(data)
            return entry["count"]

    def get(self, skill_id: str) -> UsageStats:
        """Возвращает stats. Если skill ни разу не использован — count=0."""
        with self._lock:
            data = self._read()
        entry = data.get(skill_id) or {}
        return UsageStats(
            skill_id=skill_id,
            count=int(entry.get("count") or 0),
            last_used_iso=entry.get("last_used"),
        )

    def all_stats(self) -> dict[str, UsageStats]:
        """Все статистики из файла. Возвращает skill_id → UsageStats."""
        with self._lock:
            data = self._read()
        return {
            sid: UsageStats(
                skill_id=sid,
                count=int(entry.get("count") or 0),
                last_used_iso=entry.get("last_used"),
            )
            for sid, entry in data.items()
        }

    def remove(self, skill_id: str) -> bool:
        """Удаляет запись о skill (используется когда skill удалён).

        Возвращает True если запись была.
        """
        with self._lock:
            data = self._read()
            if skill_id in data:
                del data[skill_id]
                self._write(data)
                return True
            return False
