"""Тесты капа search_typical_objects за ход (Phase 5.5)."""
from app.orchestrator.loop import (
    MAX_TYPICAL_SEARCH_CALLS_PER_TURN,
    _typical_search_budget_exceeded,
)


def test_cap_constant_reasonable():
    assert 1 <= MAX_TYPICAL_SEARCH_CALLS_PER_TURN <= 10


def test_budget_not_exceeded_below_cap():
    calls = [{"name": "search_typical_objects"}] * (MAX_TYPICAL_SEARCH_CALLS_PER_TURN - 1)
    assert _typical_search_budget_exceeded(calls) is False


def test_budget_exceeded_at_cap():
    calls = [{"name": "search_typical_objects"}] * MAX_TYPICAL_SEARCH_CALLS_PER_TURN
    assert _typical_search_budget_exceeded(calls) is True


def test_other_tools_do_not_count():
    calls = [{"name": "execute_query"}] * 20 + [{"name": "search_typical_objects"}]
    assert _typical_search_budget_exceeded(calls) is False
