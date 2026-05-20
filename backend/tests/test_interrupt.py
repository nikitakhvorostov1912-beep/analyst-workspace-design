"""Tests for InterruptRegistry (Sprint 2 — Hermes C9)."""

from __future__ import annotations

import threading

from app.orchestrator.interrupt import InterruptRegistry


def test_initial_state() -> None:
    reg = InterruptRegistry()
    assert reg.active_count() == 0
    assert reg.should_interrupt("any") is False


def test_request_and_check() -> None:
    reg = InterruptRegistry()
    reg.request_interrupt("session-1")
    assert reg.should_interrupt("session-1") is True
    assert reg.should_interrupt("session-2") is False


def test_clear_removes_flag() -> None:
    reg = InterruptRegistry()
    reg.request_interrupt("s1")
    cleared = reg.clear("s1")
    assert cleared is True
    assert reg.should_interrupt("s1") is False


def test_clear_idempotent() -> None:
    reg = InterruptRegistry()
    reg.request_interrupt("s1")
    reg.clear("s1")
    cleared_again = reg.clear("s1")
    assert cleared_again is False


def test_request_idempotent() -> None:
    """Повторный request_interrupt — не растит set."""
    reg = InterruptRegistry()
    reg.request_interrupt("s1")
    reg.request_interrupt("s1")
    assert reg.active_count() == 1


def test_empty_session_id_noop() -> None:
    reg = InterruptRegistry()
    reg.request_interrupt("")
    assert reg.active_count() == 0
    assert reg.should_interrupt("") is False


def test_scope_clears_on_exit() -> None:
    reg = InterruptRegistry()

    with reg.scope("s1"):
        reg.request_interrupt("s1")
        assert reg.should_interrupt("s1") is True
    # После выхода из scope — флаг снят
    assert reg.should_interrupt("s1") is False


def test_scope_clears_even_on_exception() -> None:
    reg = InterruptRegistry()

    class _Boom(Exception):
        pass

    try:
        with reg.scope("s1"):
            reg.request_interrupt("s1")
            raise _Boom
    except _Boom:
        pass
    assert reg.should_interrupt("s1") is False


def test_thread_safety() -> None:
    reg = InterruptRegistry()

    def worker(sid: str) -> None:
        for _ in range(50):
            reg.request_interrupt(sid)
            reg.should_interrupt(sid)
            reg.clear(sid)

    threads = [threading.Thread(target=worker, args=(f"s{i}",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Не падает + конечный счёт чистый
    assert reg.active_count() == 0
