"""Tests for insights engine (Sprint 4 — Hermes G8 lite)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import aiosqlite
import pytest

from app.orchestrator.insights import _period_cutoff, collect_insights


@pytest.fixture
async def db_with_sessions(tmp_path):
    """Создаёт мини-схему с messages + sessions для insights."""
    db_path = tmp_path / "insights.db"
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
            tool_calls TEXT,
            created_at TEXT
        );
        """
    )

    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)
    weeks_ago = now - timedelta(days=10)

    sessions = [
        ("s1", "Сессия 1", "ch-a", now.isoformat()),
        ("s2", "Сессия 2", "ch-a", yesterday.isoformat()),
        ("s3", "Сессия 3", "ch-b", weeks_ago.isoformat()),
    ]
    for s in sessions:
        await db.execute(
            "INSERT INTO sessions (id, title, channel_id, created_at) VALUES (?, ?, ?, ?)",
            s,
        )

    # Messages
    tc1 = json.dumps([
        {"name": "execute_query", "duration_ms": 50},
        {"name": "execute_query", "duration_ms": 30},
        {"name": "get_metadata", "duration_ms": 20, "error": "timeout"},
    ])
    msgs = [
        ("s1", "user", "вопрос", None, now.isoformat()),
        ("s1", "assistant", "ответ", tc1, now.isoformat()),
        ("s2", "user", "q2", None, yesterday.isoformat()),
        ("s2", "assistant", "a2", json.dumps([{"name": "execute_query", "duration_ms": 100}]), yesterday.isoformat()),
        ("s3", "user", "old", None, weeks_ago.isoformat()),
        ("s3", "assistant", "old answer", None, weeks_ago.isoformat()),
    ]
    for m in msgs:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, tool_calls, created_at) VALUES (?, ?, ?, ?, ?)",
            m,
        )
    await db.commit()
    yield db
    await db.close()


def test_period_cutoff_24h_returns_iso() -> None:
    cutoff = _period_cutoff("24h")
    assert cutoff is not None
    # Парсится как ISO
    parsed = datetime.fromisoformat(cutoff)
    assert parsed.tzinfo is not None


def test_period_cutoff_all_returns_none() -> None:
    assert _period_cutoff("all") is None


@pytest.mark.asyncio
async def test_collect_insights_all(db_with_sessions) -> None:
    report = await collect_insights(db_with_sessions, period="all")
    assert report.sessions == 3
    assert report.messages == 6
    assert report.tool_calls_total == 4
    assert report.tool_errors_total == 1


@pytest.mark.asyncio
async def test_collect_insights_24h_excludes_old(db_with_sessions) -> None:
    report = await collect_insights(db_with_sessions, period="24h")
    # s3 (10 дней назад) исключён, s2 (1 день назад) тоже на грани.
    # Минимум s1 (сейчас) точно есть.
    assert report.sessions >= 1
    assert report.sessions <= 2


@pytest.mark.asyncio
async def test_top_tools_sorted(db_with_sessions) -> None:
    report = await collect_insights(db_with_sessions, period="all")
    # execute_query вызывался чаще
    assert report.top_tools[0].name == "execute_query"
    assert report.top_tools[0].calls == 3


@pytest.mark.asyncio
async def test_error_rate_computed(db_with_sessions) -> None:
    report = await collect_insights(db_with_sessions, period="all")
    # get_metadata имел 1 error из 1 вызова
    for tool in report.top_tools:
        if tool.name == "get_metadata":
            assert tool.error_rate == 1.0


@pytest.mark.asyncio
async def test_top_channels_includes_both(db_with_sessions) -> None:
    report = await collect_insights(db_with_sessions, period="all")
    ch_ids = {c.channel_id for c in report.top_channels}
    assert "ch-a" in ch_ids
    assert "ch-b" in ch_ids


@pytest.mark.asyncio
async def test_avg_duration_computed(db_with_sessions) -> None:
    report = await collect_insights(db_with_sessions, period="all")
    # (50 + 30 + 20 + 100) / 4 = 50
    assert report.avg_duration_ms == 50


@pytest.mark.asyncio
async def test_empty_db_returns_zeros(tmp_path) -> None:
    db_path = tmp_path / "empty.db"
    db = await aiosqlite.connect(str(db_path))
    await db.executescript(
        """
        CREATE TABLE sessions (id TEXT PRIMARY KEY, title TEXT, channel_id TEXT, created_at TEXT);
        CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT, content TEXT, tool_calls TEXT, created_at TEXT);
        """
    )
    await db.commit()
    report = await collect_insights(db, period="all")
    assert report.sessions == 0
    assert report.messages == 0
    assert report.tool_calls_total == 0
    await db.close()
