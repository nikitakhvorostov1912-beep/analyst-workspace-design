"""IterationBudget — thread-safe счётчик итераций для tool-calling loop.

Sprint 2 (Hermes C1): защита от runaway loop.

Концепция Hermes:
- per-agent counter (parent=90, subagent=50 в Hermes; у нас один уровень → 100)
- консумируется на каждом round LLM-вызова
- refund при "programmatic tool calling" (нам не нужно — у нас нет PTC)
- exhausted → graceful stop с понятным сообщением

Текущий loop.py использует константу MAX_TOOL_ITERATIONS=100. Этот модуль
заменяет её гибким объектом с явным API остатка/потребления, который
плюс-минус 1-в-1 повторяет sentinel логику без лишнего шума.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass


# Дефолт совпадает с прежней константой MAX_TOOL_ITERATIONS в loop.py:
# 100 — soft safety net. Главная защита всё ещё DUPLICATE_TOOL_CALL_THRESHOLD.
DEFAULT_BUDGET = 100


class BudgetExhausted(Exception):
    """Бюджет итераций исчерпан — loop должен gracefully завершиться."""


@dataclass
class BudgetState:
    """Снимок состояния бюджета для UI/логов."""

    total: int
    used: int

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.used)


class IterationBudget:
    """Thread-safe счётчик итераций.

    Использование:
        budget = IterationBudget(total=100)
        while True:
            try:
                budget.consume()
            except BudgetExhausted:
                break
            ... do work ...

    Свойства:
    - Безопасен под многопоточным доступом (хотя orchestrator у нас async,
      auxiliary worker threads — есть).
    - Идемпотентен: после exhausted остаётся exhausted, повторный consume()
      продолжает бросать BudgetExhausted (используем для теста).
    """

    def __init__(self, total: int = DEFAULT_BUDGET) -> None:
        if total <= 0:
            raise ValueError(f"total must be positive, got {total}")
        self._total = total
        self._used = 0
        self._lock = threading.Lock()

    @property
    def total(self) -> int:
        return self._total

    @property
    def used(self) -> int:
        with self._lock:
            return self._used

    @property
    def remaining(self) -> int:
        with self._lock:
            return max(0, self._total - self._used)

    @property
    def exhausted(self) -> bool:
        with self._lock:
            return self._used >= self._total

    def consume(self, n: int = 1) -> int:
        """Списать n итераций. Возвращает остаток.

        Raises:
            BudgetExhausted: если после списания used > total.
        """
        if n <= 0:
            raise ValueError(f"n must be positive, got {n}")
        with self._lock:
            if self._used + n > self._total:
                self._used = self._total
                raise BudgetExhausted(
                    f"Iteration budget exhausted: total={self._total}, "
                    f"already used={self._used}"
                )
            self._used += n
            return self._total - self._used

    def refund(self, n: int = 1) -> int:
        """Вернуть n итераций — для PTC-сценариев.

        У нас нет programmatic tool calling, но API на будущее.
        Не может вернуть больше чем использовано.
        """
        if n <= 0:
            raise ValueError(f"n must be positive, got {n}")
        with self._lock:
            self._used = max(0, self._used - n)
            return self._total - self._used

    def snapshot(self) -> BudgetState:
        with self._lock:
            return BudgetState(total=self._total, used=self._used)
