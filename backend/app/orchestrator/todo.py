"""TodoTool — in-memory task list per-session, re-injected after compression.

Sprint 3 (Hermes D3): agent decomposes complex tasks, tracks progress.

Дизайн:
- State хранится in-process в TodoRegistry: session_id → list[TodoItem].
- Sustains across compression — system prompt получает render() блока с активными
  задачами при каждом LLM-вызове.
- Tool schemas:
    todo_add(items: list[str]) — добавить N задач (status=pending)
    todo_complete(ids: list[str]) — пометить выполнено
    todo_list() — возвращает текущее состояние
- Не персистируется в БД (per-session, теряется на restart) — для долгосрочного
  планирования есть MEMORY.md.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

TodoStatus = Literal["pending", "in_progress", "completed", "cancelled"]


@dataclass
class TodoItem:
    id: str
    text: str
    status: TodoStatus = "pending"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None


MAX_TODOS_PER_SESSION = 50


class TodoRegistry:
    """Per-process хранилище списков задач по сессиям.

    Thread-safe. Каждая сессия имеет свой список TodoItem.
    """

    def __init__(self) -> None:
        self._items: dict[str, list[TodoItem]] = {}
        self._lock = threading.Lock()

    def add(self, session_id: str, texts: list[str]) -> list[TodoItem]:
        """Добавляет N задач со status=pending. Возвращает добавленные элементы."""
        if not session_id:
            raise ValueError("session_id is required")
        if not texts:
            return []
        with self._lock:
            current = self._items.setdefault(session_id, [])
            free = max(0, MAX_TODOS_PER_SESSION - len(current))
            added: list[TodoItem] = []
            for text in texts[:free]:
                txt = (text or "").strip()
                if not txt:
                    continue
                item = TodoItem(id=f"t{uuid.uuid4().hex[:6]}", text=txt[:300])
                current.append(item)
                added.append(item)
            return added

    def update_status(
        self, session_id: str, todo_id: str, status: TodoStatus
    ) -> TodoItem | None:
        if not session_id:
            return None
        with self._lock:
            for item in self._items.get(session_id, []):
                if item.id == todo_id:
                    item.status = status
                    if status == "completed":
                        item.completed_at = datetime.now(UTC).isoformat()
                    return item
            return None

    def complete(self, session_id: str, todo_ids: list[str]) -> list[str]:
        """Bulk-complete. Возвращает реально завершённые id."""
        out: list[str] = []
        for tid in todo_ids:
            if self.update_status(session_id, tid, "completed") is not None:
                out.append(tid)
        return out

    def list(self, session_id: str) -> list[TodoItem]:
        with self._lock:
            return list(self._items.get(session_id, []))

    def clear(self, session_id: str) -> int:
        """Удаляет все задачи сессии (например, при /reset). Возвращает count."""
        with self._lock:
            items = self._items.pop(session_id, [])
            return len(items)

    def active_count(self, session_id: str) -> int:
        return sum(
            1 for i in self.list(session_id) if i.status in ("pending", "in_progress")
        )


# Глобальный singleton — один реестр на процесс.
TODOS = TodoRegistry()


# ── Tool schemas для LLM (включаются в openai_tools) ──


TODO_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "todo_add",
            "description": (
                "Добавить задачи в текущий план разбора. Используй для декомпозиции "
                "сложных запросов (3+ шага) — это помогает не забыть подшаги после "
                "длинного tool-цикла. Сохраняется на время сессии."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список текстов задач, 1-300 символов каждый.",
                    },
                },
                "required": ["items"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_complete",
            "description": (
                "Пометить задачи выполненными (по id из todo_list/todo_add result)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Список id задач.",
                    },
                },
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_list",
            "description": "Получить текущий список задач сессии с их статусами.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


TODO_TOOL_NAMES = frozenset({"todo_add", "todo_complete", "todo_list"})


def is_todo_tool(name: str) -> bool:
    return name in TODO_TOOL_NAMES


def dispatch_todo_tool(
    session_id: str, name: str, args: dict
) -> tuple[bool, Any, str | None]:
    """Вызывает todo_* tool. Возвращает (ok, result, error)."""
    if not session_id:
        return False, None, "session_id отсутствует"

    if name == "todo_add":
        items = args.get("items") or []
        if not isinstance(items, list):
            return False, None, "items должен быть массивом строк"
        added = TODOS.add(session_id, [str(x) for x in items])
        return True, {"added": [_serialize(i) for i in added]}, None

    if name == "todo_complete":
        ids = args.get("ids") or []
        if not isinstance(ids, list):
            return False, None, "ids должен быть массивом строк"
        completed = TODOS.complete(session_id, [str(x) for x in ids])
        return True, {"completed": completed}, None

    if name == "todo_list":
        items = TODOS.list(session_id)
        return True, {"items": [_serialize(i) for i in items]}, None

    return False, None, f"Неизвестный todo tool: {name}"


def _serialize(item: TodoItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "text": item.text,
        "status": item.status,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
    }


def render_todos_for_prompt(session_id: str) -> str:
    """Возвращает блок текущих задач для system prompt.

    Re-injected после compression — модель не теряет план.
    Пустой блок если нет активных задач.
    """
    items = TODOS.list(session_id)
    active = [i for i in items if i.status in ("pending", "in_progress")]
    if not active:
        return ""

    lines = ["### Текущий план задач (todo)"]
    for item in items:
        marker = {
            "pending": "[ ]",
            "in_progress": "[~]",
            "completed": "[x]",
            "cancelled": "[-]",
        }.get(item.status, "[ ]")
        lines.append(f"{marker} {item.id}: {item.text}")
    return "\n".join(lines)
