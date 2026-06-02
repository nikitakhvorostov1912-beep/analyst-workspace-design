"""Тесты circuit-breaker / телеметрии buddy_monitor (#40)."""
from __future__ import annotations

import pytest

from app.knowledge import buddy_monitor as bm


@pytest.fixture(autouse=True)
def _reset():
    bm._reset_for_test()
    bm._state.enabled = True
    bm._state.endpoint = "http://127.0.0.1:6002/mcp"
    yield
    bm._reset_for_test()


def test_circuit_opens_after_3_consecutive_fails():
    bm._apply_check(False, now=1.0)
    bm._apply_check(False, now=2.0)
    assert not bm._state.degraded  # 2 фейла — ещё closed
    bm._apply_check(False, now=3.0)
    assert bm._state.degraded  # 3-й → open
    assert bm.snapshot()["status"] == "down"


def test_success_resets_and_closes_circuit():
    for t in (1.0, 2.0, 3.0):
        bm._apply_check(False, now=t)
    assert bm._state.degraded
    bm._apply_check(True, now=4.0)
    assert not bm._state.degraded
    assert bm._state.consecutive_fails == 0
    assert bm.snapshot()["status"] == "up"


def test_single_fail_does_not_open():
    bm._apply_check(True, now=1.0)
    bm._apply_check(False, now=2.0)
    assert not bm._state.degraded


def test_record_call_telemetry():
    bm.record_call(True)
    bm.record_call(True)
    bm.record_call(False)
    s = bm.snapshot()
    assert s["calls_total"] == 3
    assert s["calls_ok"] == 2
    assert s["calls_fail"] == 1


def test_snapshot_disabled():
    bm._state.enabled = False
    assert bm.snapshot()["status"] == "disabled"


@pytest.mark.asyncio
async def test_ping_down_endpoint_returns_false():
    # заведомо мёртвый порт
    assert await bm._ping("http://127.0.0.1:6599/mcp", timeout=1.0) is False
