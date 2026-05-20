"""Tests for SkillUsageStore (Sprint 3 — Hermes A9)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.learning.skill_usage import USAGE_FILE_NAME, SkillUsageStore


def test_empty_store_returns_zero(tmp_path: Path) -> None:
    store = SkillUsageStore(tmp_path)
    stats = store.get("skill_001")
    assert stats.count == 0
    assert stats.last_used_iso is None


def test_increment_creates_file(tmp_path: Path) -> None:
    store = SkillUsageStore(tmp_path)
    new_count = store.increment("skill_001")
    assert new_count == 1
    assert (tmp_path / USAGE_FILE_NAME).exists()


def test_increment_multiple_times(tmp_path: Path) -> None:
    store = SkillUsageStore(tmp_path)
    for _ in range(5):
        store.increment("skill_001")
    stats = store.get("skill_001")
    assert stats.count == 5
    assert stats.last_used_iso is not None


def test_increment_separate_skills(tmp_path: Path) -> None:
    store = SkillUsageStore(tmp_path)
    store.increment("skill_a")
    store.increment("skill_a")
    store.increment("skill_b")
    assert store.get("skill_a").count == 2
    assert store.get("skill_b").count == 1


def test_all_stats(tmp_path: Path) -> None:
    store = SkillUsageStore(tmp_path)
    store.increment("a")
    store.increment("b")
    store.increment("b")
    all_data = store.all_stats()
    assert "a" in all_data and "b" in all_data
    assert all_data["a"].count == 1
    assert all_data["b"].count == 2


def test_remove(tmp_path: Path) -> None:
    store = SkillUsageStore(tmp_path)
    store.increment("skill_x")
    assert store.remove("skill_x") is True
    assert store.get("skill_x").count == 0
    # Повторный remove — False
    assert store.remove("skill_x") is False


def test_increment_empty_id_raises(tmp_path: Path) -> None:
    store = SkillUsageStore(tmp_path)
    with pytest.raises(ValueError):
        store.increment("")


def test_corrupted_file_is_recovered(tmp_path: Path) -> None:
    """Если .usage.json повреждён — store возвращает пустой dict, не падает."""
    (tmp_path / USAGE_FILE_NAME).write_text("not valid json", encoding="utf-8")
    store = SkillUsageStore(tmp_path)
    stats = store.get("anything")
    assert stats.count == 0
    # Increment работает — перезаписывает.
    store.increment("skill_y")
    data = json.loads((tmp_path / USAGE_FILE_NAME).read_text(encoding="utf-8"))
    assert "skill_y" in data
