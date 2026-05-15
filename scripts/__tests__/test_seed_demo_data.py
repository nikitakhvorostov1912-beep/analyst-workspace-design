"""Тесты для scripts/seed-demo-data.py."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import pytest_asyncio

# Добавляем backend в path для app.storage.migrations
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

import aiosqlite

from app.storage.migrations import apply_migrations

# Имя файла содержит дефис — importlib.util необходим
_SEED_MODULE_PATH = Path(__file__).parent.parent / "seed-demo-data.py"
_spec = importlib.util.spec_from_file_location("seed_demo_data", _SEED_MODULE_PATH)
_seed_module = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_seed_module)  # type: ignore[union-attr]

DEMO_SESSIONS = _seed_module.DEMO_SESSIONS
seed = _seed_module.seed


@pytest_asyncio.fixture
async def empty_db(tmp_path):
    """Создаёт временную SQLite БД с применёнными миграциями."""
    db_path = str(tmp_path / "test.db")
    async with aiosqlite.connect(db_path) as db:
        await apply_migrations(db)
    return db_path


@pytest.mark.asyncio
async def test_seed_creates_6_sessions(empty_db):
    """Seed создаёт ровно 6 демо-сессий."""
    await seed(empty_db, clean=False)
    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall("SELECT COUNT(*) FROM sessions")
    assert rows[0][0] == 6


@pytest.mark.asyncio
async def test_seed_creates_messages_for_each_session(empty_db):
    """Каждая сессия имеет ровно 2 сообщения (user + assistant)."""
    await seed(empty_db, clean=False)
    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall(
            "SELECT session_id, COUNT(*) as cnt FROM messages GROUP BY session_id"
        )
    assert len(rows) == 6
    for row in rows:
        assert row[1] == 2, f"Session {row[0]} has {row[1]} messages, expected 2"


@pytest.mark.asyncio
async def test_seed_creates_log_card_state_when_card_id_present(empty_db):
    """LogCard сессия имеет card_state с tool_name=get_event_log."""
    await seed(empty_db, clean=False)
    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall(
            "SELECT tool_name FROM card_states WHERE tool_name = 'get_event_log'"
        )
    assert len(rows) == 1, "Ожидается 1 card_state для LogCard"
    assert rows[0][0] == "get_event_log"


@pytest.mark.asyncio
async def test_seed_clean_flag_wipes_previous_data(empty_db):
    """--clean очищает предыдущие данные перед вставкой."""
    # Первый запуск
    await seed(empty_db, clean=False)
    # Второй запуск с --clean
    await seed(empty_db, clean=True)

    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall("SELECT COUNT(*) FROM sessions")
    # После --clean должно быть ровно 6 (а не 12)
    assert rows[0][0] == 6


@pytest.mark.asyncio
async def test_seed_idempotent_without_clean(empty_db):
    """Повторный запуск без --clean не дублирует сессии (INSERT OR IGNORE)."""
    await seed(empty_db, clean=False)
    await seed(empty_db, clean=False)

    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall("SELECT COUNT(*) FROM sessions")
    assert rows[0][0] == 6


@pytest.mark.asyncio
async def test_seed_anon_session_has_anon_tokens_in_card_state(empty_db):
    """Анонимная сессия содержит anon_tokens в card_states."""
    await seed(empty_db, clean=False)
    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall(
            "SELECT anon_tokens FROM card_states WHERE anon_tokens IS NOT NULL"
        )
    assert len(rows) == 1, "Ожидается 1 card_state с anon_tokens"
    tokens = json.loads(rows[0][0])
    assert "[ORG-001]" in tokens
    assert "[INN-001]" in tokens


@pytest.mark.asyncio
async def test_seed_all_6_card_types_present(empty_db):
    """Все 6 типов карточек присутствуют в seed-данных."""
    await seed(empty_db, clean=False)
    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall(
            "SELECT cards FROM messages WHERE cards IS NOT NULL"
        )
    card_types = set()
    for row in rows:
        cards = json.loads(row[0])
        for card in cards:
            card_types.add(card["type"])

    expected = {"table", "log", "references", "metric", "code"}
    assert expected.issubset(card_types), f"Отсутствуют типы карточек: {expected - card_types}"


@pytest.mark.asyncio
async def test_seed_applies_migrations_idempotently(empty_db):
    """seed вызывает apply_migrations идемпотентно — не падает на уже созданной БД."""
    await seed(empty_db, clean=False)
    # Повторный вызов не должен падать
    await seed(empty_db, clean=False)
    async with aiosqlite.connect(empty_db) as db:
        rows = await db.execute_fetchall("SELECT MAX(version) FROM schema_version")
    assert rows[0][0] == 5
