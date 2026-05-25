"""Тесты SQL AST validator (P2.3, 2026-05-23).

Покрывает 3 группы кейсов:
- positive (read-only запросы): SELECT/ВЫБРАТЬ/WITH/EXPLAIN — должны пройти
- negative (DML/DDL): DELETE/UPDATE/INSERT/DROP/ALTER/... — должны быть BLOCKED
- bypass attempts: комментарий-обходка, encoded payload, мульти-statement —
  AST должен ловить даже если keyword regex промахнётся

Тесты пропускаются если sqlparse не установлен (CI без зависимости).
"""

from __future__ import annotations

import pytest

from app.orchestrator.sql_validator import (
    ValidationStatus,
    is_available,
    validate_query,
)

# Skip всего модуля если sqlparse не установлен (degrade-режим).
pytestmark = pytest.mark.skipif(
    not is_available(), reason="sqlparse не установлен — AST validator в degrade"
)


# ===== Positive: read-only запросы =====


class TestAllowedQueries:
    """SELECT/ВЫБРАТЬ/EXPLAIN/SHOW — должны проходить."""

    @pytest.mark.parametrize(
        "query",
        [
            "SELECT * FROM users",
            "SELECT id, name FROM accounts WHERE active = 1",
            "select * from users",  # lowercase
            "  SELECT 1  ",  # whitespace padding
            "SELECT u.id, c.name FROM users u JOIN companies c ON u.company_id = c.id",
            "SELECT COUNT(*) FROM orders WHERE date > '2026-01-01'",
            "SELECT * FROM (SELECT id FROM users WHERE active=1) sub",  # subquery OK
        ],
    )
    def test_select_passes(self, query: str) -> None:
        result = validate_query(query)
        assert result.status == ValidationStatus.OK, f"expected OK for {query!r}, got {result}"

    @pytest.mark.parametrize(
        "query",
        [
            "ВЫБРАТЬ * ИЗ Справочник.Контрагенты",
            "ВЫБРАТЬ Поле1 ИЗ Документ.Реализация ГДЕ Дата > &Дата",
            "выбрать первые 100 * из РегистрНакопления.ТоварыНаСкладах.Остатки",
        ],
    )
    def test_1c_select_passes(self, query: str) -> None:
        """Русский язык запросов 1С — ВЫБРАТЬ должен пройти."""
        result = validate_query(query)
        assert result.status == ValidationStatus.OK, f"expected OK for {query!r}, got {result}"

    @pytest.mark.parametrize(
        "query",
        [
            # SEC-4 (M-K0): WITH удалён из allow-list (см. ниже отдельный тест).
            "EXPLAIN SELECT * FROM users",
            "EXPLAIN ANALYZE SELECT id FROM accounts",
            "SHOW TABLES",
            "DESCRIBE users",
            "DESC users",
        ],
    )
    def test_other_readonly_passes(self, query: str) -> None:
        result = validate_query(query)
        assert result.status == ValidationStatus.OK, f"expected OK for {query!r}, got {result}"


# ===== SEC-4: CTE (WITH) теперь BLOCKED как первый токен =====


class TestSEC4WithCteBlocked:
    """SEC-4 (M-K0): WITH удалён из allow-list.

    Раньше `WITH cte AS (INSERT...RETURNING) SELECT * FROM cte` обходил
    first-token check. Решение: запретить WITH совсем (1С не использует;
    direct-SQL WITH+SELECT переписывается как обычный SELECT).

    Plus RETURNING добавлен в forbidden keywords для defence-in-depth.
    """

    def test_with_cte_select_blocked(self) -> None:
        """Даже легитимный read-only WITH...SELECT теперь BLOCKED."""
        result = validate_query(
            "WITH cte AS (SELECT * FROM users) SELECT * FROM cte"
        )
        assert result.status == ValidationStatus.BLOCKED
        assert "WITH" in result.reason or "не разрешён" in result.reason

    def test_with_cte_insert_returning_bypass_blocked(self) -> None:
        """Главная атака: WITH cte AS (INSERT...RETURNING) SELECT — bypass."""
        result = validate_query(
            "WITH cte AS (INSERT INTO users VALUES (1, 'evil') RETURNING id) "
            "SELECT * FROM cte"
        )
        assert result.status == ValidationStatus.BLOCKED

    def test_with_cte_update_returning_blocked(self) -> None:
        result = validate_query(
            "WITH cte AS (UPDATE users SET role='admin' WHERE id=1 RETURNING id) "
            "SELECT * FROM cte"
        )
        assert result.status == ValidationStatus.BLOCKED

    def test_with_cte_delete_returning_blocked(self) -> None:
        result = validate_query(
            "WITH cte AS (DELETE FROM users WHERE id=1 RETURNING id) "
            "SELECT * FROM cte"
        )
        assert result.status == ValidationStatus.BLOCKED

    def test_returning_in_plain_select_blocked(self) -> None:
        """RETURNING вне CTE — тоже сигнал DML, blocked."""
        # Селект не должен содержать RETURNING — это глагол DML.
        result = validate_query(
            "INSERT INTO users VALUES (1, 'evil') RETURNING id"
        )
        assert result.status == ValidationStatus.BLOCKED

    def test_lowercase_with_blocked(self) -> None:
        """Регистр-инсенситивно — WITH/with/With все BLOCKED."""
        for variant in ("with", "With", "WITH", "wItH"):
            result = validate_query(f"{variant} cte AS (SELECT 1) SELECT * FROM cte")
            assert result.status == ValidationStatus.BLOCKED, (
                f"variant {variant!r} прошёл (должен быть BLOCKED)"
            )


# ===== Negative: DML/DDL должны быть BLOCKED =====


class TestForbiddenQueries:
    """DELETE/UPDATE/INSERT/DROP/ALTER/... — должны быть BLOCKED."""

    @pytest.mark.parametrize(
        "query",
        [
            "DELETE FROM users",
            "delete from users where id = 1",
            "DROP TABLE accounts",
            "DROP DATABASE production",
            "TRUNCATE users",
            "INSERT INTO users VALUES (1, 'evil')",
            "UPDATE users SET role = 'admin' WHERE id = 1",
            "ALTER TABLE users ADD COLUMN backdoor TEXT",
            "ALTER USER analyst WITH SUPERUSER",
            "GRANT ALL ON users TO public",
            "REVOKE SELECT ON sensitive FROM analyst",
            "EXEC sp_addsrvrolemember 'attacker'",
            "EXECUTE sp_executesql N'DROP TABLE x'",
            "CREATE TABLE evil (id INT)",
            "RENAME TABLE users TO compromised",
            "REPLACE INTO users VALUES (1, 'compromised')",
            "MERGE INTO users USING source ON 1=1 WHEN MATCHED THEN UPDATE SET role='admin'",
            "CALL admin_proc()",
        ],
    )
    def test_dml_ddl_blocked(self, query: str) -> None:
        result = validate_query(query)
        assert result.status == ValidationStatus.BLOCKED, (
            f"expected BLOCKED for {query!r}, got {result}"
        )

    @pytest.mark.parametrize(
        "query",
        [
            "УДАЛИТЬ Справочник.Контрагенты",
            "удалить документ.реализация",
            "ИЗМЕНИТЬ Справочник.X",
            "ВСТАВИТЬ В Документ.X",
            "ОЧИСТИТЬ Регистр.X",
        ],
    )
    def test_1c_dml_blocked(self, query: str) -> None:
        """1С DML keywords (УДАЛИТЬ/ИЗМЕНИТЬ/...) — должны быть заблокированы."""
        result = validate_query(query)
        assert result.status == ValidationStatus.BLOCKED, (
            f"expected BLOCKED for {query!r}, got {result}"
        )


# ===== Bypass attempts =====


class TestBypassAttempts:
    """LLM может попытаться обойти keyword regex — AST должен ловить."""

    def test_comment_bypass_line(self) -> None:
        """`SELECT 1; -- DELETE FROM users` — strip убирает комментарий,
        но второй statement остаётся."""
        # После strip: "SELECT 1;   "
        # parsed: [SELECT 1, empty]
        # SELECT 1 → OK; empty statement пропускается
        result = validate_query("SELECT 1; -- DELETE FROM users")
        assert result.status == ValidationStatus.OK

    def test_comment_bypass_with_actual_dml_after(self) -> None:
        """`SELECT 1; /* harmless */ DELETE FROM users` — DELETE остаётся
        после strip block-комментария, должен быть BLOCKED."""
        result = validate_query("SELECT 1; /* harmless */ DELETE FROM users")
        assert result.status == ValidationStatus.BLOCKED

    def test_multi_statement_with_dml(self) -> None:
        """Несколько statement'ов через ; — каждый проверяется."""
        result = validate_query("SELECT * FROM users; DELETE FROM accounts")
        assert result.status == ValidationStatus.BLOCKED

    def test_inline_dml_in_subquery(self) -> None:
        """SELECT с inline DELETE (некоторые DBMS поддерживают) — BLOCKED."""
        # PostgreSQL DELETE RETURNING может быть в WITH:
        # WITH d AS (DELETE FROM users RETURNING id) SELECT * FROM d
        result = validate_query(
            "WITH d AS (DELETE FROM users RETURNING id) SELECT * FROM d"
        )
        # Первый токен WITH → ОК но _find_forbidden_token увидит DELETE → BLOCKED
        assert result.status == ValidationStatus.BLOCKED

    def test_leading_whitespace_does_not_help(self) -> None:
        """Большое количество whitespace перед DROP — не помогает обойти."""
        result = validate_query("\n\n\n   DROP TABLE users")
        assert result.status == ValidationStatus.BLOCKED

    def test_drop_with_trailing_comment(self) -> None:
        result = validate_query("DROP TABLE users -- innocent comment")
        assert result.status == ValidationStatus.BLOCKED


# ===== Edge cases =====


class TestEdgeCases:
    """Граничные случаи: пустой запрос, мусор, только комментарии."""

    def test_empty_string_invalid(self) -> None:
        result = validate_query("")
        assert result.status == ValidationStatus.INVALID

    def test_whitespace_only_invalid(self) -> None:
        result = validate_query("   \n\t  ")
        assert result.status == ValidationStatus.INVALID

    def test_only_comment_returns_invalid_or_ok(self) -> None:
        """Только комментарий → после strip пусто → INVALID."""
        result = validate_query("-- just a comment")
        assert result.status in {ValidationStatus.INVALID, ValidationStatus.OK}

    def test_random_garbage(self) -> None:
        """Не парсится / не SELECT → BLOCKED или INVALID."""
        result = validate_query("foobar barfoo qux")
        assert result.status in {ValidationStatus.BLOCKED, ValidationStatus.INVALID}

    def test_statement_with_only_semicolon(self) -> None:
        """`;` — пустой statement, не парсится осмысленно."""
        result = validate_query(";")
        assert result.status in {ValidationStatus.INVALID, ValidationStatus.OK}


# ===== Integration с safety.scan_query_ast =====


class TestSafetyIntegration:
    """scan_query_ast — обёртка которую вызывает loop.py."""

    def test_scan_query_ast_non_query_tool_returns_none(self) -> None:
        from app.orchestrator.safety import scan_query_ast

        # get_metadata не сканируем
        assert scan_query_ast("get_metadata", {"path": "Справочник"}) is None

    def test_scan_query_ast_no_query_arg(self) -> None:
        from app.orchestrator.safety import scan_query_ast

        # Если в args нет ключа `query` → пропускаем (keyword-scan защищает)
        assert scan_query_ast("execute_query", {"foo": "bar"}) is None

    def test_scan_query_ast_blocks_delete(self) -> None:
        from app.orchestrator.safety import scan_query_ast

        result = scan_query_ast(
            "execute_query", {"query": "DELETE FROM users WHERE id=1"}
        )
        assert result is not None
        assert "ast_blocked" in result

    def test_scan_query_ast_passes_select(self) -> None:
        from app.orchestrator.safety import scan_query_ast

        result = scan_query_ast(
            "execute_query",
            {"query": "ВЫБРАТЬ * ИЗ Справочник.Контрагенты"},
        )
        assert result is None

    def test_scan_query_ast_query_text_not_string(self) -> None:
        """Если query — не str (LLM передал int/list/None) → пропускаем."""
        from app.orchestrator.safety import scan_query_ast

        assert scan_query_ast("execute_query", {"query": 123}) is None
        assert scan_query_ast("execute_query", {"query": None}) is None
        assert scan_query_ast("execute_query", {"query": ["DELETE"]}) is None
