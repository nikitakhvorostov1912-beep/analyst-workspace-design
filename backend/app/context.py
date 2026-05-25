"""Request-scoped context для structured logging — ARCH-2 (M-K0.6).

ContextVar — стандартный Python механизм для **per-task** state в asyncio.
В отличие от module-level globals (которые shared между всеми корутинами),
ContextVar изолирует значение per-asyncio.Task — каждый запрос получает
свою копию, даже если они выполняются параллельно.

Использование:
1. **Middleware** в main.py — на каждый incoming HTTP запрос ставит request_id.
2. **Orchestrator loop** в loop.py — на старте run_chat_loop ставит session_id.
3. **Logging filter** (ContextFilter) — автоматически добавляет оба значения
   в каждую LogRecord → они попадают в JSON формат логов.

Результат: при параллельном чате 3 пользователей в логах не нужно вручную
передавать session_id/request_id в каждый logger.info(...) — они там сами.
"""

from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar


# Дефолты — пустые строки, чтобы JSON formatter не падал когда context
# не установлен (например, при импорте модуля или background tasks без request).
session_id_var: ContextVar[str] = ContextVar("session_id", default="")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def generate_request_id() -> str:
    """Короткий request_id для трейсинга — 12 hex chars uuid4."""
    return uuid.uuid4().hex[:12]


def get_session_id() -> str:
    """Текущий session_id из context. '' если не установлен."""
    return session_id_var.get()


def get_request_id() -> str:
    """Текущий request_id из context. '' если не установлен."""
    return request_id_var.get()


class ContextFilter(logging.Filter):
    """Logging filter — инжектирует session_id и request_id в каждую LogRecord.

    После добавления этого filter'а к handler, в LogRecord появляются
    атрибуты `session_id` и `request_id` — formatter может их использовать
    через `%(session_id)s` / `%(request_id)s`.

    Идемпотентен — повторное добавление того же filter'а к handler'у
    Python автоматически не дублирует.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = session_id_var.get()
        record.request_id = request_id_var.get()
        return True  # не фильтруем ничего, только обогащаем
