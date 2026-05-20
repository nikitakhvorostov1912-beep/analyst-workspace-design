"""Curator backup — pre-run tar.gz snapshot перед auto-archive/cleanup.

Sprint 3 (Hermes A7): двухступенчатый rollback — даже rollback undo-able.

Структура:
    <skills_dir>/.curator_backups/
    ├── 20260520T120015Z/
    │   ├── manifest.json   # { reason, count, ids }
    │   └── skills.tar.gz   # сжатые skills + .usage.json
    ├── 20260521T060000Z/
    │   └── ...
"""

from __future__ import annotations

import gzip
import json
import logging
import re
import shutil
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


BACKUPS_DIR = ".curator_backups"
MAX_BACKUPS = 10  # храним N последних, старше — удаляем


@dataclass(frozen=True)
class BackupManifest:
    timestamp: str          # UTC ISO
    reason: str             # e.g. "auto_archive_inactive"
    skill_count: int
    backup_dir: Path


def _utc_label() -> str:
    """Label с миллисекундной точностью — не коллапсирует при близких вызовах."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")


class CuratorBackup:
    """Снимок директории skills перед изменением.

    Args:
        skills_dir: per-channel skills/<channel_id>/.
    """

    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = Path(skills_dir)
        self._backups_root = self._skills_dir / BACKUPS_DIR

    @property
    def backups_root(self) -> Path:
        return self._backups_root

    def create(self, reason: str) -> BackupManifest:
        """Создаёт tar.gz snapshot активных и архивированных skills + manifest.json.

        Returns:
            BackupManifest с путём к каталогу backup.

        Raises:
            OSError при ошибке файловой системы.
        """
        if not self._skills_dir.exists():
            # Нечего бэкапить — создаём пустой manifest для трассировки попытки.
            self._backups_root.mkdir(parents=True, exist_ok=True)
            label = _utc_label()
            target = self._backups_root / label
            target.mkdir(parents=True, exist_ok=True)
            manifest = {
                "timestamp": label,
                "reason": reason,
                "skill_count": 0,
                "note": "skills_dir not present at backup time",
            }
            (target / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return BackupManifest(
                timestamp=label, reason=reason, skill_count=0, backup_dir=target
            )

        label = _utc_label()
        target = self._backups_root / label
        target.mkdir(parents=True, exist_ok=True)

        # Считаем количество skills
        skill_count = sum(1 for _ in self._skills_dir.glob("*.md")) + sum(
            1 for _ in (self._skills_dir / ".archive").glob("*.md")
            if (self._skills_dir / ".archive").exists()
        )

        # Создаём tar.gz: skills.tar.gz содержит все .md из skills_dir и .archive/,
        # плюс .usage.json если есть. .curator_backups/ исключаем.
        archive_path = target / "skills.tar.gz"
        with tarfile.open(archive_path, "w:gz") as tar:
            def _filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
                if BACKUPS_DIR in info.name.split("/"):
                    return None
                return info

            tar.add(self._skills_dir, arcname=self._skills_dir.name, filter=_filter)

        manifest = {
            "timestamp": label,
            "reason": reason,
            "skill_count": skill_count,
            "skills_dir": str(self._skills_dir),
        }
        (target / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self._rotate()
        return BackupManifest(
            timestamp=label, reason=reason, skill_count=skill_count, backup_dir=target
        )

    def _rotate(self) -> None:
        """Оставляем только MAX_BACKUPS самых свежих snapshots."""
        if not self._backups_root.exists():
            return
        entries = sorted(
            [p for p in self._backups_root.iterdir() if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        for old in entries[MAX_BACKUPS:]:
            try:
                shutil.rmtree(old, ignore_errors=True)
            except OSError as exc:
                logger.warning("Не удалось удалить старый backup %s: %s", old, exc)

    def list_backups(self) -> list[BackupManifest]:
        """Список всех snapshot'ов, новейшие первыми."""
        if not self._backups_root.exists():
            return []
        out: list[BackupManifest] = []
        for path in sorted(self._backups_root.iterdir(), reverse=True):
            if not path.is_dir():
                continue
            mp = path / "manifest.json"
            if not mp.exists():
                continue
            try:
                data = json.loads(mp.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            out.append(
                BackupManifest(
                    timestamp=data.get("timestamp") or path.name,
                    reason=data.get("reason") or "unknown",
                    skill_count=int(data.get("skill_count") or 0),
                    backup_dir=path,
                )
            )
        return out

    def restore(self, timestamp: str) -> bool:
        """Восстанавливает skills из snapshot.

        ВНИМАНИЕ: делает rollback-snapshot ПЕРЕД restore — на случай если
        пользователь захочет откатить откат.

        Args:
            timestamp: метка из .curator_backups/<label>/.

        Returns:
            True при успехе.
        """
        target = self._backups_root / timestamp
        archive_path = target / "skills.tar.gz"
        if not archive_path.exists():
            logger.warning("Backup %s не найден", timestamp)
            return False

        # 1) Сохраняем текущее состояние — на случай rollback rollback'а.
        self.create(reason=f"pre_restore_of_{timestamp}")

        # 2) Очищаем текущие skills (но НЕ .curator_backups).
        for entry in list(self._skills_dir.iterdir()):
            if entry.name == BACKUPS_DIR:
                continue
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                try:
                    entry.unlink()
                except OSError:
                    pass

        # 3) Распаковываем архив. archive хранит skills_dir/<channel>/ как top-level →
        # извлекаем в parent чтобы пути совпали.
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(self._skills_dir.parent)

        return True
