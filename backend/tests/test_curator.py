"""Tests for Curator (Sprint 3 — Hermes A6 lite)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.learning.curator import Curator, _is_stale
from app.learning.curator_backup import CuratorBackup
from app.learning.skill_store import Skill, SkillStore
from app.learning.skill_usage import SkillUsageStore


def _make_curator(tmp_path: Path, *, inactive_days: int = 30, min_age_days: int = 7) -> tuple[Curator, SkillStore, SkillUsageStore]:
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    usage = SkillUsageStore(store.directory)
    backup = CuratorBackup(store.directory)
    curator = Curator(
        store=store, usage=usage, backup=backup,
        inactive_days=inactive_days, min_age_days=min_age_days,
    )
    return curator, store, usage


def test_no_skills_no_action(tmp_path: Path) -> None:
    curator, _, _ = _make_curator(tmp_path)
    report = curator.run()
    assert report.inspected == 0
    assert report.archived == []


def test_pinned_skill_skipped(tmp_path: Path) -> None:
    curator, store, _ = _make_curator(tmp_path)
    old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    store.write(Skill(id="pin", body="x", pinned=True, provenance="agent",
                       created_at=old_ts, updated_at=old_ts))
    report = curator.run()
    assert "pin" in report.skipped_pinned
    assert report.archived == []


def test_user_skill_skipped(tmp_path: Path) -> None:
    curator, store, _ = _make_curator(tmp_path)
    old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    store.write(Skill(id="userish", body="x", provenance="user",
                       created_at=old_ts, updated_at=old_ts))
    report = curator.run()
    assert "userish" in report.skipped_user
    assert report.archived == []


def test_recent_skill_skipped(tmp_path: Path) -> None:
    curator, store, _ = _make_curator(tmp_path, min_age_days=7)
    fresh_ts = datetime.now(UTC).isoformat()
    store.write(Skill(id="fresh", body="x", provenance="agent",
                       created_at=fresh_ts, updated_at=fresh_ts))
    report = curator.run()
    assert "fresh" in report.skipped_recent
    assert report.archived == []


def test_stale_agent_skill_archived(tmp_path: Path) -> None:
    curator, store, _ = _make_curator(tmp_path)
    old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    store.write(Skill(id="stale", body="x", provenance="agent",
                       created_at=old_ts, updated_at=old_ts))
    report = curator.run()
    assert "stale" in report.archived
    # backup был создан
    assert report.backup is not None


def test_dry_run_does_not_modify(tmp_path: Path) -> None:
    curator, store, _ = _make_curator(tmp_path)
    old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    store.write(Skill(id="stale", body="x", provenance="agent",
                       created_at=old_ts, updated_at=old_ts))
    report = curator.run(dry_run=True)
    assert report.archived == ["stale"]
    # Но реально не архивирован
    assert store.read("stale") is not None
    assert "stale" in [s.id for s in store.list_active()]


def test_is_stale_with_recent_usage(tmp_path: Path) -> None:
    """Если skill использовался недавно — не stale."""
    now = datetime.now(UTC)
    recent = (now - timedelta(days=5)).isoformat()
    skill = Skill(id="x", body="x", provenance="agent",
                  created_at=(now - timedelta(days=60)).isoformat(),
                  updated_at=(now - timedelta(days=60)).isoformat())
    assert _is_stale(skill, recent, inactive_days=30, now=now) is False


def test_is_stale_with_old_usage(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old = (now - timedelta(days=60)).isoformat()
    skill = Skill(id="x", body="x", provenance="agent",
                  created_at=old, updated_at=old)
    assert _is_stale(skill, old, inactive_days=30, now=now) is True


def test_usage_recency_protects_old_skill(tmp_path: Path) -> None:
    """Если skill старый, но юзается — Curator не трогает."""
    curator, store, usage = _make_curator(tmp_path)
    old_ts = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    store.write(Skill(id="popular", body="x", provenance="agent",
                       created_at=old_ts, updated_at=old_ts))
    usage.increment("popular")  # last_used = now
    report = curator.run()
    assert "popular" not in report.archived
