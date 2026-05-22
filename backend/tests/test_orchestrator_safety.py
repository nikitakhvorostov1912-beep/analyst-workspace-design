"""Тесты модуля orchestrator/safety.py — dangerous keywords + pending confirmation store."""

import asyncio

import pytest

from app.orchestrator.safety import (
    is_dangerous_tool,
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


# ===== W1.2: is_dangerous_tool + SQL DML расширение =====


def test_is_dangerous_tool_execute_code():
    """execute_code исторически опасен (W0) — должен сохранить статус."""
    assert is_dangerous_tool("execute_code") is True


def test_is_dangerous_tool_execute_query():
    """W1.2: execute_query тоже опасен — DML может попасть через MCP Toolkit raw SQL."""
    assert is_dangerous_tool("execute_query") is True


def test_is_dangerous_tool_safe_tools():
    """Read-only инструменты не должны блокироваться."""
    assert is_dangerous_tool("get_metadata") is False
    assert is_dangerous_tool("get_event_log") is False
    assert is_dangerous_tool("get_object_by_link") is False
    assert is_dangerous_tool("find_references_to_object") is False


def test_scan_finds_sql_insert():
    """W1.2: SQL DML — INSERT блокируется."""
    result = scan_for_dangerous({"query": "INSERT INTO users VALUES (1, 'evil')"})
    assert result is not None
    assert "Insert" in result or "insert" in result.lower()


def test_scan_finds_sql_update_set():
    """W1.2: SQL UPDATE ... SET блокируется (но НЕ BSL `Установить()` сам по себе)."""
    result = scan_for_dangerous({"query": "UPDATE users SET role='admin' WHERE id=1"})
    assert result is not None


def test_scan_finds_sql_alter():
    """W1.2: DDL — ALTER блокируется."""
    result = scan_for_dangerous({"query": "ALTER TABLE accounts ADD column hacked text"})
    assert result is not None
    assert "Alter" in result or "alter" in result.lower()


def test_scan_finds_sql_grant():
    """W1.2: Grant/Revoke (изменение прав в DB) блокируются."""
    assert scan_for_dangerous({"query": "GRANT ALL ON users TO public"}) is not None
    assert scan_for_dangerous({"query": "REVOKE SELECT ON sensitive FROM analyst"}) is not None


def test_scan_finds_sql_exec_xp():
    """W1.2: EXEC / sp_executesql (T-SQL вектор RCE) блокируются."""
    assert scan_for_dangerous({"query": "EXEC sp_addsrvrolemember 'attacker'"}) is not None
    assert scan_for_dangerous({"query": "sp_executesql N'DROP TABLE x'"}) is not None


def test_scan_allows_normal_query_1c():
    """W1.2: нормальный 1С-запрос (SELECT/UNION/ИЗ) не должен блокироваться."""
    result = scan_for_dangerous({
        "query": "ВЫБРАТЬ ПЕРВЫЕ 100 Ссылка ИЗ Документ.РеализацияТоваровУслуг ГДЕ Дата >= &Период"
    })
    assert result is None


def test_scan_allows_normal_query_select():
    """W1.2: чистый SELECT без DML — пропуск."""
    result = scan_for_dangerous({"query": "SELECT id, name FROM users WHERE active=1 LIMIT 100"})
    assert result is None


def test_scan_sql_injection_via_query():
    """W1.2: типичная SQL-inject полезная нагрузка — должна блокироваться."""
    result = scan_for_dangerous({
        "query": "SELECT * FROM users WHERE id=1; DROP TABLE users; --"
    })
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
