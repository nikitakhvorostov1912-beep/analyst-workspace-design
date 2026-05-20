"""Tool result storage — persistence больших outputs вместо truncation.

Sprint 5 (Hermes D7): three-level defence:
1. per-tool cap (например, execute_query результат > 50KB)
2. per-result persistence (записать на диск + reference в LLM context)
3. per-turn budget (если общий объём tools > N, агрессивно прунить)

Файловая структура:
    <data_root>/tool_outputs/<session_id>/<tool_call_id>.json

LLM в context видит только короткий summary + ref на файл (UI может позже
показать «развернуть» — но это backlog).
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Лимиты.
PER_TOOL_BYTE_CAP = 50_000        # если результат > N — persistent + summary
PER_TURN_BYTE_BUDGET = 200_000     # суммарный лимит на один turn
SUMMARY_KEEP_BYTES = 2_000         # сколько символов «головы» оставляем в context


_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")


def _safe(part: str) -> str:
    return _UNSAFE_CHARS_RE.sub("_", part)


@dataclass(frozen=True)
class StoredResult:
    """Ссылка на сохранённый tool output."""

    tool_call_id: str
    session_id: str
    file_path: Path
    original_bytes: int
    stored_at: str  # ISO

    @property
    def reference_marker(self) -> str:
        """Текст для LLM context — короткий маркер ссылки."""
        return (
            f"[tool_output_stored: id={self.tool_call_id}, "
            f"bytes={self.original_bytes}, "
            f"path=<persisted>]"
        )


class ToolResultStorage:
    """Атомарная запись JSON-результатов с rotation.

    Args:
        root: <data_root>/tool_outputs/.
        per_tool_cap: байты ≥ этого числа → persist + summary.
        per_turn_budget: байты — суммарный лимит на 1 turn.
    """

    def __init__(
        self,
        root: Path,
        *,
        per_tool_cap: int = PER_TOOL_BYTE_CAP,
        per_turn_budget: int = PER_TURN_BYTE_BUDGET,
    ) -> None:
        self._root = Path(root)
        self._per_tool_cap = per_tool_cap
        self._per_turn_budget = per_turn_budget
        self._turn_used = 0
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        return self._root

    def reset_turn(self) -> None:
        """Сбросить счётчик turn-budget. Вызывать в начале каждой итерации."""
        with self._lock:
            self._turn_used = 0

    def should_persist(self, content: str) -> bool:
        size = len(content.encode("utf-8")) if isinstance(content, str) else 0
        return size >= self._per_tool_cap

    def remaining_budget(self) -> int:
        with self._lock:
            return max(0, self._per_turn_budget - self._turn_used)

    def persist(
        self,
        *,
        session_id: str,
        tool_call_id: str,
        content: str,
    ) -> StoredResult:
        """Сохраняет content в файл и возвращает ссылку.

        Не проверяет should_persist — caller решает.
        """
        if not session_id or not tool_call_id:
            raise ValueError("session_id и tool_call_id обязательны")

        session_dir = self._root / _safe(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        file_path = session_dir / f"{_safe(tool_call_id)}.json"

        # Сохраняем как plain JSON если parseable, иначе как text wrapper.
        original_bytes = len(content.encode("utf-8"))
        try:
            data = json.loads(content)
            payload = {
                "tool_call_id": tool_call_id,
                "stored_at": datetime.now(UTC).isoformat(),
                "size_bytes": original_bytes,
                "kind": "json",
                "data": data,
            }
        except (ValueError, TypeError):
            payload = {
                "tool_call_id": tool_call_id,
                "stored_at": datetime.now(UTC).isoformat(),
                "size_bytes": original_bytes,
                "kind": "text",
                "data": content,
            }

        tmp = file_path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(file_path)

        with self._lock:
            self._turn_used += original_bytes

        return StoredResult(
            tool_call_id=tool_call_id,
            session_id=session_id,
            file_path=file_path,
            original_bytes=original_bytes,
            stored_at=payload["stored_at"],
        )

    def make_summary(self, content: str, stored: StoredResult) -> str:
        """Возвращает краткий summary для LLM context.

        Стратегия: первые N байтов исходного content + reference marker.
        """
        head = content[:SUMMARY_KEEP_BYTES]
        return f"{head}\n...\n{stored.reference_marker}"

    def load(self, session_id: str, tool_call_id: str) -> dict[str, Any] | None:
        """Читает сохранённый файл по id. None если не найден."""
        file_path = self._root / _safe(session_id) / f"{_safe(tool_call_id)}.json"
        if not file_path.exists():
            return None
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Не удалось прочитать %s", file_path)
            return None
