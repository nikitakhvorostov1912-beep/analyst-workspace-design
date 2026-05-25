# ADR-005: Schema migrations — продолжить DDL (без alembic)

**Status:** Accepted
**Date:** 2026-05-25
**Deciders:** Никита, Claude
**Phase:** M-K1

## Context

Текущая схема SQLite управляется через `backend/app/storage/migrations.py`:
явные DDL-скрипты с `schema_version` колонкой в `app_meta` таблице,
последовательно применяются при `init_db()`.

После M6 handoff обсуждается миграция MCPConnection +5 полей (mode, configuration,
platform, ext_version, capabilities JSON). Handoff предполагает **alembic** для
этой миграции. Возникает выбор:
- (A) Перейти на alembic в M-K1
- (B) Продолжить DDL — как для остальных 10 миграций (v0..v10)

## Decision

**Продолжить прямые DDL** в `backend/app/storage/migrations.py`. Новая миграция
v11 добавит 5 полей в `mcp_connections` обычным `ALTER TABLE`.

```python
# backend/app/storage/migrations.py
async def _migrate_to_v11(conn: aiosqlite.Connection) -> None:
    """v11: M6 Phase 12 — capability-aware MCP connections.

    Добавляет mode/configuration/platform/ext_version/capabilities JSON
    для дискриминации EPF vs CFE vs raw MCP Toolkit.
    """
    await conn.execute("ALTER TABLE mcp_connections ADD COLUMN mode TEXT DEFAULT 'mcp_only'")
    await conn.execute("ALTER TABLE mcp_connections ADD COLUMN configuration TEXT")
    await conn.execute("ALTER TABLE mcp_connections ADD COLUMN platform TEXT")
    await conn.execute("ALTER TABLE mcp_connections ADD COLUMN ext_version TEXT")
    await conn.execute("ALTER TABLE mcp_connections ADD COLUMN capabilities TEXT")  # JSON
    await conn.execute("UPDATE app_meta SET value = '11' WHERE key = 'schema_version'")
```

## Consequences

### Положительные
- **Consistency**: 10 уже-существующих миграций v0..v10 в DDL стиле —
  не вводим parallel mechanism
- **Zero new deps**: alembic = +SQLAlchemy + Mako templates + jinja2 + ~30 MB
  в bundle. У нас raw aiosqlite, не SQLAlchemy
- **Простота**: 80% наших миграций — `ALTER TABLE ADD COLUMN` или `CREATE INDEX`,
  alembic over-engineering для этого
- **Readable diffs**: один Python файл, последовательное чтение «v0 → v1 → v2 → ...»
- **Совместимо с PyInstaller**: alembic + SQLAlchemy дополнительные hooks в spec файле
- **Электрон bundle не растёт**: критично, уже 105.9 MB

### Отрицательные
- **No autogenerate**: alembic умеет `alembic revision --autogenerate` против
  declarative моделей. У нас нет моделей (Pydantic ≠ SQLAlchemy declarative),
  поэтому нечего autogenerate-ить — это не потеря
- **No downgrade**: текущий `migrations.py` односторонний (forward-only). Для
  desktop приложения это OK — у пользователя одна БД и она upgrade-only
- **Ручное тестирование миграций** — нужно вручную убедиться что v0 → v11
  работает на старой БД от v1.0. Уже есть `test_migrations.py` (см. tests/)

### Нейтральные
- В будущем если БД станет heavy (> 100 таблиц) — можно мигрировать на alembic
  без потери истории (просто конвертация migrations.py → alembic versions)

## Alternatives considered

| Alt | Verdict | Reason |
|---|---|---|
| **alembic** | rejected | Requires SQLAlchemy, +30 MB bundle, overkill для 10 миграций |
| **yoyo-migrations** | rejected | Маленькая community, ещё одна зависимость без преимуществ |
| **sqlmigrate (Django-style)** | rejected | Tied to Django ORM, не наш стек |
| **Raw SQL files в migrations/ folder** | considered | Чище чем Python, но Python даёт условные миграции (например «если column уже есть — skip»). У нас есть кейсы условных миграций (data backfill в v8). Оставляем Python. |
| **Liquibase / Flyway** | rejected | Java runtime, не подходит для Electron Python backend |

## References

- Текущий `backend/app/storage/migrations.py` — 10 миграций v0..v10
- Тесты `backend/tests/test_migrations.py`
- Новая миграция v11 будет в M-K1.6 (см. M-K1-PLAN.md)
- SQLite ALTER TABLE: https://www.sqlite.org/lang_altertable.html — поддерживает
  ADD COLUMN без table rebuild
- См. ADR-004 (capability field, кладётся в JSON колонку этой миграцией)
