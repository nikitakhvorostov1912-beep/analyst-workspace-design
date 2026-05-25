"""Тесты ARCH-2 — contextvars для structured logging.

Контракт:
1. session_id_var / request_id_var изолированы per asyncio.Task.
2. ContextFilter правильно инжектирует значения в LogRecord.
3. Дефолтные значения '' не падают в formatter.
4. Параллельные tasks не пересекают context.
5. generate_request_id выдаёт уникальные значения.
"""

from __future__ import annotations

import asyncio
import logging
from io import StringIO

import pytest

from app.context import (
    ContextFilter,
    generate_request_id,
    get_request_id,
    get_session_id,
    request_id_var,
    session_id_var,
)


# ===== Базовые свойства =====


def test_defaults_are_empty_strings():
    assert get_session_id() == ""
    assert get_request_id() == ""


def test_generate_request_id_unique():
    ids = {generate_request_id() for _ in range(100)}
    assert len(ids) == 100


def test_generate_request_id_short():
    # 12 hex chars — компромисс между uniqueness (16^12 = 2.8e14) и краткостью в логах
    assert len(generate_request_id()) == 12


# ===== ContextFilter =====


def test_context_filter_injects_into_record():
    token_s = session_id_var.set("test-session-abc")
    token_r = request_id_var.set("req-xyz123")
    try:
        rec = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="x",
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        f = ContextFilter()
        result = f.filter(rec)
        assert result is True  # filter не отбрасывает
        assert rec.session_id == "test-session-abc"
        assert rec.request_id == "req-xyz123"
    finally:
        session_id_var.reset(token_s)
        request_id_var.reset(token_r)


def test_context_filter_with_empty_defaults():
    """Если контекст не установлен — filter ставит пустые строки, formatter не падает."""
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="x",
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    f = ContextFilter()
    f.filter(rec)
    # Должны быть атрибуты, даже если пустые
    assert hasattr(rec, "session_id")
    assert hasattr(rec, "request_id")
    assert rec.session_id == ""
    assert rec.request_id == ""


def test_formatter_works_with_context_filter():
    """Полный pipeline: установить context → log → проверить что в выводе есть значения."""
    log_buf = StringIO()
    handler = logging.StreamHandler(log_buf)
    handler.setFormatter(
        logging.Formatter(
            '{"session": "%(session_id)s", "request": "%(request_id)s", "msg": "%(message)s"}'
        )
    )
    handler.addFilter(ContextFilter())

    logger = logging.getLogger("test_context_pipeline")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    token_s = session_id_var.set("sess-42")
    token_r = request_id_var.set("req-99")
    try:
        logger.info("hello from session")
    finally:
        session_id_var.reset(token_s)
        request_id_var.reset(token_r)

    output = log_buf.getvalue()
    assert '"session": "sess-42"' in output
    assert '"request": "req-99"' in output
    assert '"msg": "hello from session"' in output


# ===== Per-task isolation =====


@pytest.mark.asyncio
async def test_contextvars_isolated_between_tasks():
    """Главное свойство ARCH-2: contextvars per asyncio.Task — 2 параллельных
    запроса не пересекают session_id."""
    results: dict[str, str] = {}

    async def task_a():
        session_id_var.set("session-A")
        await asyncio.sleep(0.01)  # дать task_b шанс установить своё
        results["a"] = get_session_id()

    async def task_b():
        session_id_var.set("session-B")
        await asyncio.sleep(0.005)
        results["b"] = get_session_id()

    await asyncio.gather(task_a(), task_b())

    assert results["a"] == "session-A"
    assert results["b"] == "session-B"


@pytest.mark.asyncio
async def test_context_set_doesnt_leak_to_parent_after_task():
    """После завершения task'а изменения context не должны утечь в parent."""
    # Parent context — пусто
    assert get_session_id() == ""

    async def child():
        session_id_var.set("child-sess")
        return get_session_id()

    child_value = await asyncio.create_task(child())
    assert child_value == "child-sess"
    # Parent после await — context не загрязнён
    assert get_session_id() == ""
