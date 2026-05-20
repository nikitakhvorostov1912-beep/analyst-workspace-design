"""Tests for IterationBudget (Sprint 2 — Hermes C1)."""

from __future__ import annotations

import threading

import pytest

from app.orchestrator.iteration_budget import (
    DEFAULT_BUDGET,
    BudgetExhausted,
    IterationBudget,
)


def test_default_total() -> None:
    budget = IterationBudget()
    assert budget.total == DEFAULT_BUDGET
    assert budget.used == 0
    assert budget.remaining == DEFAULT_BUDGET
    assert budget.exhausted is False


def test_consume_decreases_remaining() -> None:
    budget = IterationBudget(total=10)
    assert budget.consume() == 9
    assert budget.used == 1
    assert budget.remaining == 9


def test_consume_n() -> None:
    budget = IterationBudget(total=10)
    assert budget.consume(3) == 7
    assert budget.used == 3


def test_exhausted_raises() -> None:
    budget = IterationBudget(total=2)
    budget.consume()
    budget.consume()
    with pytest.raises(BudgetExhausted):
        budget.consume()
    assert budget.exhausted is True


def test_exhausted_stays_exhausted() -> None:
    budget = IterationBudget(total=1)
    budget.consume()
    with pytest.raises(BudgetExhausted):
        budget.consume()
    # Повторный consume тоже raises (idempotent state).
    with pytest.raises(BudgetExhausted):
        budget.consume()


def test_refund_restores_remaining() -> None:
    budget = IterationBudget(total=10)
    budget.consume(5)
    budget.refund(2)
    assert budget.used == 3
    assert budget.remaining == 7


def test_refund_cant_go_below_zero() -> None:
    budget = IterationBudget(total=10)
    budget.consume(2)
    budget.refund(100)  # пытаемся вернуть больше чем использовали
    assert budget.used == 0


def test_invalid_total() -> None:
    with pytest.raises(ValueError):
        IterationBudget(total=0)
    with pytest.raises(ValueError):
        IterationBudget(total=-1)


def test_invalid_consume_n() -> None:
    budget = IterationBudget(total=10)
    with pytest.raises(ValueError):
        budget.consume(0)
    with pytest.raises(ValueError):
        budget.consume(-1)


def test_snapshot() -> None:
    budget = IterationBudget(total=10)
    budget.consume(3)
    snap = budget.snapshot()
    assert snap.total == 10
    assert snap.used == 3
    assert snap.remaining == 7


def test_thread_safety_consume() -> None:
    """100 потоков по 10 consume — итог должен быть ровно 1000 usage."""
    budget = IterationBudget(total=2000)
    threads: list[threading.Thread] = []

    def worker() -> None:
        for _ in range(10):
            try:
                budget.consume()
            except BudgetExhausted:
                pass

    for _ in range(100):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    assert budget.used == 1000
