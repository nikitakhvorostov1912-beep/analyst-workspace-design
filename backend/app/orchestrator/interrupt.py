"""Interrupt registry — graceful cancellation per session.

Sprint 2 (Hermes C9): механизм прерывания tool-calling loop пользователем.

Контекст:
- В Hermes `interrupt.py` использует thread-scoped tracking (ContextVar).
- У нас async orchestrator → используем asyncio-aware version + session-scoped key.

Поток событий:
1. Пользователь жмёт «Стоп» в UI.
2. Frontend → POST /chat/{session_id}/interrupt.
3. Backend ставит флаг в registry: `request_interrupt(session_id)`.
4. Loop проверяет `should_interrupt(session_id)` после каждого LLM-чанка / tool-call.
5. Если флаг — loop завершается gracefully: сохраняет частичный результат, шлёт
   `done` SSE event с пометкой interrupted=True.

Дизайн:
- Не используем asyncio.Event (слишком тяжёлый для broadcast).
- Простой set-based registry с lock.
- Idempotent: request_interrupt дважды — то же что один раз.
- Auto-cleanup: clear() вызывается в finally блоке loop'а после ответа.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager


class InterruptRegistry:
    """Реестр запросов на прерывание по session_id."""

    def __init__(self) -> None:
        self._interrupted: set[str] = set()
        self._lock = threading.Lock()

    def request_interrupt(self, session_id: str) -> None:
        """Пометить сессию как требующую прерывания."""
        if not session_id:
            return
        with self._lock:
            self._interrupted.add(session_id)

    def should_interrupt(self, session_id: str) -> bool:
        """Проверить, требуется ли прервать loop этой сессии."""
        if not session_id:
            return False
        with self._lock:
            return session_id in self._interrupted

    def clear(self, session_id: str) -> bool:
        """Снять флаг прерывания. Возвращает True если флаг был установлен.

        Вызывается в finally блоке loop'а — даже если interrupt был запрошен
        в самом конце, реестр не разрастается.
        """
        if not session_id:
            return False
        with self._lock:
            if session_id in self._interrupted:
                self._interrupted.discard(session_id)
                return True
            return False

    def active_count(self) -> int:
        """Сколько сессий сейчас имеют флаг interrupt — для диагностики."""
        with self._lock:
            return len(self._interrupted)

    @contextmanager
    def scope(self, session_id: str) -> Iterator[None]:
        """Context manager: гарантирует clear() в finally.

        Usage:
            with INTERRUPTS.scope(session_id):
                ... run loop ...
                # Inside loop: INTERRUPTS.should_interrupt(session_id) → check
            # После with — флаг гарантированно снят
        """
        try:
            yield
        finally:
            self.clear(session_id)


# Глобальный singleton — один реестр на процесс.
# В тестах подменяем через monkeypatch.setattr(...).
INTERRUPTS = InterruptRegistry()


class InterruptedByUser(Exception):
    """Loop был прерван пользователем — генерируем done(interrupted=True), не error."""
