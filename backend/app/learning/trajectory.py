"""TrajectoryLogger — append-only ShareGPT JSONL для будущего fine-tuning.

Каждый завершённый turn → одна строка JSON в trajectory_samples.jsonl
(completed=True) или failed_trajectories.jsonl (completed=False).

После накопления 1000+ trajectories можно дообучить собственную модель
на 1С-задачах. Пока — write-only, без чтения.

Port of Hermes `agent/trajectory.py`. ShareGPT format:
    {
      "conversations": [{"from": "human|gpt|system|tool", "value": "..."}],
      "metadata": {...}
    }
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Глобальный lock — гарантирует что concurrent writes из разных
# orchestrator-задач не перемешают строки в одном JSONL файле.
_WRITE_LOCK = threading.Lock()


class TrajectoryLogger:
    """Append-only ShareGPT-format JSONL logger.

    Args:
        root: каталог где лежат файлы trajectories. Создаётся при первой записи.
        enabled: глобальный feature flag. False = no-op (для тестов).
    """

    SAMPLE_FILE = "trajectory_samples.jsonl"
    FAILED_FILE = "failed_trajectories.jsonl"

    def __init__(self, root: Path, *, enabled: bool = True) -> None:
        self.root = Path(root)
        self.enabled = enabled

    def log_turn(
        self,
        *,
        session_id: str,
        channel_id: str,
        messages: list[dict],
        tool_calls: list[dict],
        completed: bool,
        model: str,
        latency_ms: int | None = None,
    ) -> None:
        """Записать один turn. Best-effort — exceptions logged, не raised."""
        if not self.enabled:
            return
        try:
            self._write(
                session_id=session_id,
                channel_id=channel_id,
                messages=messages,
                tool_calls=tool_calls,
                completed=completed,
                model=model,
                latency_ms=latency_ms,
            )
        except Exception:
            logger.exception("TrajectoryLogger.log_turn failed (best-effort, ignored)")

    def _write(
        self,
        *,
        session_id: str,
        channel_id: str,
        messages: list[dict],
        tool_calls: list[dict],
        completed: bool,
        model: str,
        latency_ms: int | None,
    ) -> None:
        filename = self.SAMPLE_FILE if completed else self.FAILED_FILE
        target = self.root / filename
        target.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "conversations": self._to_sharegpt(messages, tool_calls),
            "metadata": {
                "session_id": session_id,
                "channel_id": channel_id,
                "model": model,
                "completed": completed,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "latency_ms": latency_ms,
                "message_count": len(messages),
                "tool_call_count": len(tool_calls),
            },
        }

        # Compact (single-line) JSON для удобного `wc -l` / streaming чтения.
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with _WRITE_LOCK:
            with target.open("a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
        logger.debug("Trajectory logged: session=%s completed=%s → %s", session_id, completed, filename)

    @staticmethod
    def _to_sharegpt(
        messages: list[dict],
        tool_calls: list[dict],
    ) -> list[dict[str, Any]]:
        """Преобразовать список OpenAI-format messages в ShareGPT entries.

        ShareGPT roles: human / gpt / system / tool.
        """
        out: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            # Multimodal: пропускаем image_url parts, оставляем только текст
            if isinstance(content, list):
                text_parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = "\n".join(text_parts).strip() or "[multimodal content omitted]"
            if not content:
                continue
            mapped_role = {
                "system": "system",
                "user": "human",
                "assistant": "gpt",
                "tool": "tool",
            }.get(role, "system")
            out.append({"from": mapped_role, "value": str(content)})
        return out

    def stats(self) -> dict[str, int]:
        """Возвращает {sample_count, failed_count} — для UI/диагностики.

        Считает строки в файлах. Файлы могут быть большие — для миллионов
        строк нужно sqlite или index. Пока — простой подсчёт.
        """
        return {
            "sample_count": self._count_lines(self.root / self.SAMPLE_FILE),
            "failed_count": self._count_lines(self.root / self.FAILED_FILE),
        }

    @staticmethod
    def _count_lines(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            with path.open("rb") as f:
                return sum(1 for _ in f)
        except OSError:
            return 0
