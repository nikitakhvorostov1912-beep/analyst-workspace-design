"""Тесты модуля orchestrator/safety.py — dangerous keywords + pending confirmation store."""

import asyncio

import pytest

from app.orchestrator.safety import (
    register_pending_confirmation,
    resolve_pending_confirmation,
    scan_for_dangerous,
    wait_for_confirmation,
)

# ===== Сброс глобального состояния между тестами =====


@pytest.fixture(autouse=True)
def clear_pending():
    """Очищаем _pending dict до и после каждого теста."""
    import app.orchestrator.safety as safety_mod

    safety_mod._pending.clear()
    yield
    safety_mod._pending.clear()


# ===== scan_for_dangerous =====


def test_scan_for_dangerous_finds_удалить():
    result = scan_for_dangerous({"code": "Контрагент.Удалить()"})
    assert result is not None
    assert "Удалить" in result


def test_scan_for_dangerous_finds_записать_paren():
    result = scan_for_dangerous({"code": "Объект.Записать(РежимЗаписи.Запись);"})
    assert result is not None
    assert "Записать(" in result or "Записать" in result


def test_scan_for_dangerous_finds_english_delete():
    result = scan_for_dangerous({"code": "DELETE FROM table"})
    assert result is not None
    assert "Delete" in result or "delete" in result.lower()


def test_scan_for_dangerous_finds_drop():
    result = scan_for_dangerous({"code": "DROP TABLE x"})
    assert result is not None
    assert "Drop" in result or "drop" in result.lower()


def test_scan_for_dangerous_no_match():
    result = scan_for_dangerous({"code": "SELECT * FROM РегистрСведений.КурсыВалют"})
    assert result is None


def test_scan_for_dangerous_case_insensitive():
    result = scan_for_dangerous({"code": "удалить"})
    assert result is not None


def test_scan_for_dangerous_word_boundary():
    # «Заполнитель» не должно ловиться, т.к. нет keyword из списка с word boundary
    result = scan_for_dangerous({"code": "Заполнитель = 1;"})
    assert result is None


def test_scan_for_dangerous_trucate():
    result = scan_for_dangerous({"code": "TRUNCATE users"})
    assert result is not None


# ===== register / resolve pending confirmation =====


def test_register_resolve_pending():
    ev = register_pending_confirmation("c1")
    assert ev is not None

    # resolve возвращает True (запись найдена)
    result = resolve_pending_confirmation("c1", True)
    assert result is True

    # повторный resolve → False (запись уже удалена через wait или timeout)
    # Но wait не был вызван — запись ещё в dict, но event уже set
    # Проверяем что повторный вызов без wait_for_confirmation работает без краша
    # Примечание: _pending не удаляет запись при resolve — только wait делает pop
    # Поэтому второй resolve возвращает True (запись есть, event уже set)
    # Но смысл теста: resolve unknown id → False
    result2 = resolve_pending_confirmation("unknown_id", False)
    assert result2 is False


@pytest.mark.asyncio
async def test_wait_for_confirmation_resolves():
    ev = register_pending_confirmation("c2")
    assert ev is not None

    async def _resolve():
        await asyncio.sleep(0.01)
        resolve_pending_confirmation("c2", True)

    asyncio.create_task(_resolve())
    result = await wait_for_confirmation("c2", timeout_s=2.0)
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_confirmation_timeout():
    register_pending_confirmation("c3")
    # timeout мал — никто не resolve
    result = await wait_for_confirmation("c3", timeout_s=0.05)
    assert result is None


@pytest.mark.asyncio
async def test_wait_for_confirmation_false():
    register_pending_confirmation("c4")

    async def _resolve():
        await asyncio.sleep(0.01)
        resolve_pending_confirmation("c4", False)

    asyncio.create_task(_resolve())
    result = await wait_for_confirmation("c4", timeout_s=2.0)
    assert result is False


def test_wait_for_unknown_id_returns_none_sync():
    # wait_for_confirmation("non_existent") should return None via asyncio.run
    async def _check():
        return await wait_for_confirmation("non_existent", timeout_s=0.01)

    result = asyncio.run(_check())
    assert result is None
