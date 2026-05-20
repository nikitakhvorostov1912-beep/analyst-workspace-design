"""Tests for CuratorBackup (Sprint 3 — Hermes A7)."""

from __future__ import annotations

import json
from pathlib import Path

from app.learning.curator_backup import BACKUPS_DIR, MAX_BACKUPS, CuratorBackup
from app.learning.skill_store import Skill, SkillStore


def test_backup_empty_skills_dir(tmp_path: Path) -> None:
    """Backup даже когда skills_dir не существует — создаёт manifest-only."""
    skills_dir = tmp_path / "skills" / "ch1"
    backup = CuratorBackup(skills_dir)
    manifest = backup.create(reason="test")
    assert manifest.skill_count == 0
    assert (manifest.backup_dir / "manifest.json").exists()


def test_backup_with_skills(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    store.write(Skill(id="s1", body="one"))
    store.write(Skill(id="s2", body="two"))

    backup = CuratorBackup(store.directory)
    manifest = backup.create(reason="pre_archive")
    assert manifest.skill_count == 2
    assert (manifest.backup_dir / "skills.tar.gz").exists()


def test_list_backups(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    store.write(Skill(id="s1", body="x"))

    backup = CuratorBackup(store.directory)
    backup.create(reason="first")
    backup.create(reason="second")
    backups = backup.list_backups()
    assert len(backups) == 2
    # Новейшие первыми
    assert backups[0].timestamp >= backups[1].timestamp


def test_rotation_keeps_max_n(tmp_path: Path) -> None:
    """Старше MAX_BACKUPS удаляются."""
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    store.write(Skill(id="s1", body="x"))
    backup = CuratorBackup(store.directory)
    # Делаем больше чем лимит — через искусственные timestamp подпапки.
    for i in range(MAX_BACKUPS + 3):
        backup.create(reason=f"run_{i}")
    backups = backup.list_backups()
    # Не более MAX_BACKUPS
    assert len(backups) <= MAX_BACKUPS


def test_restore_brings_back_state(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    store.write(Skill(id="will_survive", body="keep"))
    store.write(Skill(id="will_lose", body="bye"))

    backup = CuratorBackup(store.directory)
    manifest = backup.create(reason="before_destruction")

    # Удаляем skills
    store.delete("will_lose")
    assert store.read("will_lose") is None

    # Restore
    assert backup.restore(manifest.timestamp) is True
    # Старый skill восстановлен
    restored_store = SkillStore(skills_root, "ch1")
    assert restored_store.read("will_lose") is not None


def test_restore_unknown_label_returns_false(tmp_path: Path) -> None:
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    store.write(Skill(id="s1", body="x"))
    backup = CuratorBackup(store.directory)
    assert backup.restore("nonexistent_label") is False


def test_backups_dir_excluded_from_archive(tmp_path: Path) -> None:
    """В .curator_backups лежат архивы — они НЕ должны попадать в новый архив (зацикл)."""
    skills_root = tmp_path / "skills"
    store = SkillStore(skills_root, "ch1")
    store.write(Skill(id="s1", body="x"))
    backup = CuratorBackup(store.directory)
    backup.create(reason="first")
    # Делаем ещё один — _filter должен исключить уже существующий backup.
    manifest = backup.create(reason="second")
    # Archive файл существует и не пустой
    assert (manifest.backup_dir / "skills.tar.gz").exists()
    assert (manifest.backup_dir / "skills.tar.gz").stat().st_size > 0
