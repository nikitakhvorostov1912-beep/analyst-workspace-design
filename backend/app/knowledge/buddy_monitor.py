"""Healthcheck + circuit-breaker + usage-телеметрия для 1С:Напарник (buddy MCP).

R-06 (#40): фоновый периодический ping `buddy_mcp_endpoint`. N фейлов подряд →
circuit OPEN (degraded) → `/health` отдаёт это фронту (degraded-предупреждение).
При восстановлении — circuit CLOSED.

Плюс счётчики использования buddy.* инструментов (`record_call`) — данные для
lifecycle-решения «платить Напарнику vs свой RAG» к 01.10.2026.

Состояние — процесс-локальный синглтон (один backend = один монитор).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger("buddy_monitor")

_FAIL_THRESHOLD = 3  # фейлов подряд до circuit OPEN


@dataclass
class _State:
    endpoint: str = ""
    enabled: bool = False
    consecutive_fails: int = 0
    degraded: bool = False
    checks_total: int = 0
    last_ok_ts: float = 0.0
    last_check_ts: float = 0.0
    # usage-телеметрия вызовов buddy.* из оркестратора
    calls_total: int = 0
    calls_ok: int = 0
    calls_fail: int = 0


_state = _State()
_task: asyncio.Task | None = None


async def _ping(endpoint: str, timeout: float = 4.0) -> bool:
    """Доступен ли buddy. Любой HTTP-ответ = жив; connect-error/timeout = мёртв."""
    base = endpoint.rsplit("/mcp", 1)[0] or endpoint
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            await c.get(base)
        return True
    except Exception:  # noqa: BLE001 — любая сетевая ошибка = недоступен
        return False


def record_call(ok: bool) -> None:
    """Зафиксировать вызов buddy.* инструмента (для lifecycle-телеметрии)."""
    _state.calls_total += 1
    if ok:
        _state.calls_ok += 1
    else:
        _state.calls_fail += 1


def snapshot() -> dict:
    """Текущее состояние для /health и телеметрии."""
    if not _state.enabled:
        status = "disabled"
    elif _state.degraded:
        status = "down"
    elif _state.last_ok_ts:
        status = "up"
    else:
        status = "unknown"
    return {
        "enabled": _state.enabled,
        "status": status,
        "degraded": _state.degraded,
        "consecutive_fails": _state.consecutive_fails,
        "endpoint": _state.endpoint,
        "checks_total": _state.checks_total,
        "calls_total": _state.calls_total,
        "calls_ok": _state.calls_ok,
        "calls_fail": _state.calls_fail,
    }


def hide_buddy_tools_if_down(mcp_tools: list[dict], status: str) -> list[dict]:
    """Убирает buddy.* инструменты из списка, если Напарник недоступен (down).

    Корень жалобы «бот делает вид, что искал в ИТС»: Напарник (buddy MCP, :6002)
    лежит/без ключа, circuit breaker это знает (status="down"), но buddy.search_its
    всё равно отдавался модели — она звала мёртвый tool, получала «не настроен» и
    маскировала это. Когда down — не предлагаем buddy.* вовсе; при восстановлении
    (status="up") tools снова доступны.

    Фильтруем только при подтверждённом "down" (3+ фейла пинга). При "up"/
    "unknown"/"disabled" список не трогаем (консервативно — не прячем рабочее).
    """
    if status != "down":
        return mcp_tools
    return [t for t in mcp_tools if not t.get("name", "").startswith("buddy.")]


def _apply_check(ok: bool, *, now: float) -> None:
    """Обновить circuit-breaker по результату одного ping (чистая транзиция)."""
    _state.last_check_ts = now
    _state.checks_total += 1
    if ok:
        if _state.degraded:
            logger.info("buddy восстановлен → circuit CLOSED")
        _state.consecutive_fails = 0
        _state.degraded = False
        _state.last_ok_ts = now
    else:
        _state.consecutive_fails += 1
        if _state.consecutive_fails >= _FAIL_THRESHOLD and not _state.degraded:
            _state.degraded = True
            logger.warning(
                "buddy недоступен %d раз подряд (%s) → circuit OPEN (degraded)",
                _state.consecutive_fails, _state.endpoint,
            )


async def _loop(interval: int) -> None:
    while True:
        ok = await _ping(_state.endpoint)
        _apply_check(ok, now=time.monotonic())
        await asyncio.sleep(interval)


def start(endpoint: str, *, enabled: bool, interval: int) -> None:
    """Запустить фоновый монитор (idempotent). enabled=False — только фиксируем state."""
    global _task
    _state.endpoint = endpoint
    _state.enabled = enabled
    if not enabled:
        logger.info("buddy_monitor: disabled (buddy_mcp_enabled=false)")
        return
    if _task is not None and not _task.done():
        return
    _task = asyncio.create_task(_loop(interval))
    logger.info("buddy_monitor запущен: %s, ping каждые %ds", endpoint, interval)


async def stop() -> None:
    """Остановить монитор (для shutdown / тестов)."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None


def _reset_for_test() -> None:
    """Сброс синглтона между тестами."""
    global _state
    _state = _State()
