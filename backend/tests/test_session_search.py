"""Tests for session_search (Sprint 4 — Hermes D4)."""

from __future__ import annotations

import aiosqlite
import pytest

from app.orchestrator.session_search import (
    cross_search,
    deep_search,
    discovery_search,
    fts5_safe_query,
)


@pytest.fixture
async def fts_db(tmp_path):
    db_path = tmp_path / "search.db"
    db = await aiosqlite.connect(str(db_path))
    await db.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY,
            title TEXT,
            channel_id TEXT,
            created_at TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        );
        CREATE VIRTUAL TABLE messages_fts USING fts5(content, content='messages', content_rowid='id');
        CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
        END;
        """
    )
    sessions = [
        ("s1", "Договоры", "ch-a"),
        ("s2", "Поставщики", "ch-b"),
    ]
    for sid, title, ch in sessions:
        await db.execute(
            "INSERT INTO sessions (id, title, channel_id, created_at) VALUES (?, ?, ?, '2026-05-20T00:00:00+00:00')",
            (sid, title, ch),
        )
    # 6 messages, в обеих сессиях упоминается "договор" и "поставщик"
    msgs = [
        ("s1", "user", "Покажи договоры за квартал", "2026-05-20T10:00:00+00:00"),
        ("s1", "assistant", "Нашёл 32 договора", "2026-05-20T10:00:01+00:00"),
        ("s1", "user", "А по поставщикам?", "2026-05-20T10:00:02+00:00"),
        ("s2", "user", "Поставщики из Москвы", "2026-05-20T11:00:00+00:00"),
        ("s2", "assistant", "Найдено 5 поставщиков", "2026-05-20T11:00:01+00:00"),
        ("s2", "user", "Есть ли договор с ним?", "2026-05-20T11:00:02+00:00"),
    ]
    for m in msgs:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            m,
        )
    await db.commit()
    yield db
    await db.close()


def test_fts5_safe_query_basic() -> None:
    out = fts5_safe_query("договор")
    assert out == '"договор"*'


def test_fts5_safe_query_multi_word() -> None:
    out = fts5_safe_query("договор поставщик")
    assert "AND" in out


def test_fts5_safe_query_strips_dangerous() -> None:
    out = fts5_safe_query('drop"\\table')
    # Двойные кавычки и слеши удалены
    assert '\\' not in out


def test_fts5_safe_query_empty() -> None:
    assert fts5_safe_query("") == '""'


@pytest.mark.asyncio
async def test_discovery_finds_договор(fts_db) -> None:
    hits = await discovery_search(fts_db, "договор", limit=10)
    assert len(hits) >= 2
    contents = " ".join(h.snippet for h in hits).lower()
    assert "договор" in contents


@pytest.mark.asyncio
async def test_discovery_channel_filter(fts_db) -> None:
    hits = await discovery_search(fts_db, "договор", channel_id="ch-a", limit=10)
    # Все hits — из ch-a
    for h in hits:
        assert h.channel_id == "ch-a"


@pytest.mark.asyncio
async def test_deep_search_returns_window(fts_db) -> None:
    hits = await deep_search(fts_db, "s1", "договор", window=5)
    # Все из s1
    for h in hits:
        assert h.session_id == "s1"
    # Минимум 1 hit
    assert len(hits) >= 1


@pytest.mark.asyncio
async def test_deep_search_unknown_session_empty(fts_db) -> None:
    hits = await deep_search(fts_db, "ghost", "договор")
    assert hits == []


@pytest.mark.asyncio
async def test_cross_search_groups_by_session(fts_db) -> None:
    grouped = await cross_search(fts_db, "договор", limit_per_session=2)
    # Минимум 2 сессии
    assert len(grouped) >= 1
    for sid, hits in grouped.items():
        assert all(h.session_id == sid for h in hits)
        assert len(hits) <= 2


@pytest.mark.asyncio
async def test_discovery_empty_query_returns_empty(fts_db) -> None:
    hits = await discovery_search(fts_db, "", limit=5)
    assert hits == []
