"""Clarify tool — structured multiple-choice вопросы пользователю.

Sprint 4 (Hermes D1): когда LLM нужно уточнение — она не пишет «уточните»
в свободной форме (тянется долгий free-text ответ), а вызывает clarify(
question, options) → backend генерит SSE event `clarify_required`, frontend
рисует radio + кнопку «Свой ответ», пользователь выбирает, ответ возвращается
в loop как assistant tool result.

Концепция: structured channel вместо free-text. Это ускоряет диалог в 3-5 раз
для типовых ситуаций.

Дизайн:
- Tool schema clarify_question(question: str, options: list[str], multi: bool=false)
- LLM может предложить до 4 опций; 5-я «Свой ответ» добавляется автоматически
  через `allow_custom=true` (default).
- Backend регистрирует pending clarify в registry, шлёт SSE clarify_required,
  ждёт ответ через POST /chat/clarify (как confirm) или таймаут.
- Loop получает ответ → возвращает в LLM как tool_result.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


CLARIFY_TIMEOUT_S = 600.0  # 10 минут — даём пользователю время подумать
MAX_OPTIONS = 4


@dataclass
class PendingClarify:
    """Состояние одного pending уточнения."""

    id: str
    question: str
    options: list[str]
    allow_custom: bool
    multi: bool
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    future: asyncio.Future | None = None


class ClarifyRegistry:
    """Реестр pending clarify по session_id.

    Подобно safety._pending, но с future-based ожиданием ответа.
    """

    def __init__(self) -> None:
        self._items: dict[str, PendingClarify] = {}
        self._lock = threading.Lock()

    def register(
        self,
        clarify_id: str,
        question: str,
        options: list[str],
        *,
        allow_custom: bool = True,
        multi: bool = False,
    ) -> PendingClarify:
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        with self._lock:
            pending = PendingClarify(
                id=clarify_id,
                question=question,
                options=options,
                allow_custom=allow_custom,
                multi=multi,
                future=future,
            )
            self._items[clarify_id] = pending
            return pending

    def resolve(self, clarify_id: str, answer: str | list[str]) -> bool:
        """Записывает ответ пользователя — pending Future становится done."""
        with self._lock:
            pending = self._items.pop(clarify_id, None)
        if pending is None:
            return False
        if pending.future and not pending.future.done():
            pending.future.set_result(answer)
            return True
        return False

    def cancel(self, clarify_id: str) -> bool:
        with self._lock:
            pending = self._items.pop(clarify_id, None)
        if pending is None:
            return False
        if pending.future and not pending.future.done():
            pending.future.cancel()
            return True
        return False

    def active_count(self) -> int:
        with self._lock:
            return len(self._items)


# Глобальный реестр.
CLARIFY = ClarifyRegistry()


CLARIFY_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "clarify_question",
        "description": (
            "Задать пользователю уточняющий вопрос с предзаданными вариантами ответа. "
            "Используй когда вопрос аналитика неоднозначен (например, «покажи последние "
            "документы» — каких? за какой период?). Вместо угадывания вызывай этот tool. "
            "До 4 опций + автоматическая 5-я «Свой ответ»."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Короткий вопрос на русском, 1 предложение.",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "1-4 короткие варианта ответа. Каждый — до 100 символов.",
                    "minItems": 1,
                    "maxItems": MAX_OPTIONS,
                },
                "multi": {
                    "type": "boolean",
                    "description": "Можно ли выбрать несколько вариантов. Default: false.",
                    "default": False,
                },
            },
            "required": ["question", "options"],
        },
    },
}


CLARIFY_TOOL_NAME = "clarify_question"


def is_clarify_tool(name: str) -> bool:
    return name == CLARIFY_TOOL_NAME


def validate_args(args: dict[str, Any]) -> tuple[str, list[str], bool]:
    """Парсит и валидирует args. Возвращает (question, options, multi).

    Raises:
        ValueError при невалидном вводе.
    """
    question = args.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be non-empty string")
    options = args.get("options")
    if not isinstance(options, list) or not options:
        raise ValueError("options must be non-empty list of strings")
    if len(options) > MAX_OPTIONS:
        raise ValueError(f"options не должно превышать {MAX_OPTIONS}")
    clean_options: list[str] = []
    for opt in options:
        if not isinstance(opt, str) or not opt.strip():
            raise ValueError("each option must be non-empty string")
        clean_options.append(opt.strip()[:100])
    multi = bool(args.get("multi", False))
    return question.strip()[:300], clean_options, multi


def new_clarify_id() -> str:
    return f"clr_{uuid.uuid4().hex[:12]}"
