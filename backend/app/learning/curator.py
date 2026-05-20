"""Curator — inactivity-triggered автоматизация lifecycle skills.

Sprint 3 (Hermes A6 lite): только auto-archive по неактивности.
Сохранение skills через background_review происходит отдельно — Curator
работает с уже сохранёнными агентом skills и закрывает их жизненный цикл.

Strict invariants (из Hermes):
- Только agent-created skills → user-skills неприкосновенны.
- Never auto-delete — только archive (восстановимо).
- pinned skills всегда bypass.
- Pre-run backup → CuratorBackup.create() ОБЯЗАТЕЛЕН.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.learning.curator_backup import BackupManifest, CuratorBackup
from app.learning.skill_store import Skill, SkillStore
from app.learning.skill_usage import SkillUsageStore

logger = logging.getLogger(__name__)


# Auto-archive skill если:
# - provenance = "agent" (не пользовательский)
# - не pinned
# - usage.count = 0 ИЛИ last_used старше N дней
DEFAULT_INACTIVE_DAYS = 30
DEFAULT_MIN_AGE_DAYS = 7  # не трогать совсем свежие skills


@dataclass(frozen=True)
class CuratorReport:
    """Результат одного run'а."""

    inspected: int                 # сколько skill прошли через фильтр
    archived: list[str]            # ids архивированных
    skipped_pinned: list[str]
    skipped_user: list[str]
    skipped_recent: list[str]
    backup: BackupManifest | None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _is_stale(skill: Skill, usage_last_used: str | None, *, inactive_days: int, now: datetime) -> bool:
    """True если skill — кандидат на архивацию.

    Логика:
    - Если usage.count > 0 и last_used старше inactive_days → stale.
    - Если usage отсутствует (=0) и skill старше inactive_days по updated_at → stale.
    """
    cutoff = now - timedelta(days=inactive_days)

    last_used = _parse_iso(usage_last_used)
    if last_used is not None:
        return last_used < cutoff

    updated = _parse_iso(skill.updated_at)
    if updated is None:
        return False
    return updated < cutoff


class Curator:
    """Auto-archive inactive agent-created skills.

    Args:
        store: SkillStore для канала.
        usage: SkillUsageStore того же канала.
        backup: CuratorBackup того же канала.
        inactive_days: skill старше этого → кандидат.
        min_age_days: не трогать skills моложе этого (защита от ложного archive).
    """

    def __init__(
        self,
        *,
        store: SkillStore,
        usage: SkillUsageStore,
        backup: CuratorBackup,
        inactive_days: int = DEFAULT_INACTIVE_DAYS,
        min_age_days: int = DEFAULT_MIN_AGE_DAYS,
    ) -> None:
        self._store = store
        self._usage = usage
        self._backup = backup
        self._inactive_days = inactive_days
        self._min_age_days = min_age_days

    def run(self, *, dry_run: bool = False, now: datetime | None = None) -> CuratorReport:
        """Один проход auto-archive.

        Args:
            dry_run: True → ничего не меняет, только возвращает кандидатов.
            now: подменяемое время (для тестов).

        Returns:
            CuratorReport.
        """
        now = now or datetime.now(UTC)
        skills = self._store.list_active()
        usage_data = self._usage.all_stats()

        archived: list[str] = []
        skipped_pinned: list[str] = []
        skipped_user: list[str] = []
        skipped_recent: list[str] = []

        backup_manifest: BackupManifest | None = None

        # Список кандидатов для бэкапа: те, кого реально будем архивировать
        candidates: list[Skill] = []
        min_cutoff = now - timedelta(days=self._min_age_days)

        for skill in skills:
            if skill.pinned:
                skipped_pinned.append(skill.id)
                continue
            if skill.provenance != "agent":
                skipped_user.append(skill.id)
                continue

            created = _parse_iso(skill.created_at)
            if created and created > min_cutoff:
                skipped_recent.append(skill.id)
                continue

            usage = usage_data.get(skill.id)
            last_used = usage.last_used_iso if usage else None
            if _is_stale(
                skill, last_used, inactive_days=self._inactive_days, now=now
            ):
                candidates.append(skill)

        if candidates and not dry_run:
            backup_manifest = self._backup.create(reason="auto_archive_inactive")
            for skill in candidates:
                if self._store.archive(skill.id):
                    archived.append(skill.id)
                else:
                    logger.warning("Не удалось архивировать skill %s", skill.id)
        elif candidates and dry_run:
            archived = [s.id for s in candidates]

        return CuratorReport(
            inspected=len(skills),
            archived=archived,
            skipped_pinned=skipped_pinned,
            skipped_user=skipped_user,
            skipped_recent=skipped_recent,
            backup=backup_manifest,
        )
