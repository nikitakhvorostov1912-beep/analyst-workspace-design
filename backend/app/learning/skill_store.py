"""SkillStore — read/write/list/archive skills как markdown с YAML front-matter.

Sprint 3: skills — это структурированная сущность над MEMORY.md/USER.md.
Если MEMORY.md — это сплошной markdown агента, то skill — это файл с
явным `id`, `tags`, `provenance`, `created_at`, `pinned`, `archived`.

Иерархия:
    <memory_root>/skills/<channel_id>/
    ├── skill_001.md
    ├── skill_002.md
    ├── .archive/
    │   └── skill_003.md          # архив, не инжектится в prompt
    ├── .usage.json               # SkillUsageStore (отдельный модуль)
    └── .curator_backups/<utc>/   # CuratorBackup

Формат файла:
    ---
    id: skill_001
    provenance: agent          # agent | user
    created_at: 2026-05-20T12:00:00Z
    updated_at: 2026-05-20T12:00:00Z
    tags: [query, opp]
    pinned: false
    archived: false
    ---

    # Когда аналитик спрашивает «покажи реализацию за <период> без шапки»
    ...

Минимально жизнеспособная реализация. Без YAML-зависимости — сами парсим
front-matter (это 4 свойства, не нужно тащить PyYAML).
"""

from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.learning.skill_provenance import current_provenance

logger = logging.getLogger(__name__)


# Safe sanitization для channel_id в path (см. memory/markdown_store.py).
_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]")
_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def sanitize_channel_id(channel_id: str) -> str:
    """Заменяет всё кроме [A-Za-z0-9._-] на '_'."""
    return _UNSAFE_CHARS_RE.sub("_", channel_id)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


_SENTINEL_TIMESTAMP = "__now__"


@dataclass
class Skill:
    """In-memory представление skill."""

    id: str
    body: str
    provenance: str = "user"              # "agent" | "user"
    tags: list[str] = field(default_factory=list)
    created_at: str = _SENTINEL_TIMESTAMP   # фиксируется в __post_init__
    updated_at: str = _SENTINEL_TIMESTAMP
    pinned: bool = False
    archived: bool = False
    chars: int = 0                        # вычисляется из len(body)

    def __post_init__(self) -> None:
        if not _SKILL_ID_RE.match(self.id):
            raise ValueError(
                f"Invalid skill id {self.id!r}: only [A-Za-z0-9_-], 1-64 chars"
            )
        # Если timestamps не заданы caller'ом — оба = текущее время (равные значения).
        # Это позволяет write() распознать «свежий skill» и обновить updated_at.
        if self.created_at == _SENTINEL_TIMESTAMP and self.updated_at == _SENTINEL_TIMESTAMP:
            now = _now_iso()
            self.created_at = now
            self.updated_at = now
        elif self.created_at == _SENTINEL_TIMESTAMP:
            self.created_at = self.updated_at
        elif self.updated_at == _SENTINEL_TIMESTAMP:
            self.updated_at = self.created_at
        self.chars = len(self.body)


def parse_skill_file(text: str, skill_id: str) -> Skill:
    """Парсит файл .md → Skill. Front-matter опционален.

    Args:
        text: содержимое файла.
        skill_id: id из имени файла (используется если в front-matter не задан).

    Returns:
        Skill.
    """
    body = text
    front_lines: list[str] = []
    if text.startswith("---\n"):
        # Ищем закрывающий "---" на отдельной строке
        end_marker = text.find("\n---\n", 4)
        if end_marker != -1:
            front_lines = text[4:end_marker].splitlines()
            body = text[end_marker + 5 :]

    meta: dict[str, str] = {}
    for line in front_lines:
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()

    def _to_bool(s: str) -> bool:
        return s.lower() in ("true", "yes", "1")

    def _to_tags(s: str) -> list[str]:
        # Поддерживаем "[a, b]" и "a, b"
        s = s.strip().strip("[]")
        if not s:
            return []
        return [t.strip().strip('"') for t in s.split(",") if t.strip()]

    return Skill(
        id=meta.get("id") or skill_id,
        body=body,
        provenance=meta.get("provenance") or "user",
        tags=_to_tags(meta.get("tags", "")),
        created_at=meta.get("created_at") or _now_iso(),
        updated_at=meta.get("updated_at") or _now_iso(),
        pinned=_to_bool(meta.get("pinned", "false")),
        archived=_to_bool(meta.get("archived", "false")),
    )


def serialize_skill(skill: Skill) -> str:
    """Превращает Skill → markdown с front-matter."""
    tags_str = "[" + ", ".join(skill.tags) + "]"
    return (
        f"---\n"
        f"id: {skill.id}\n"
        f"provenance: {skill.provenance}\n"
        f"created_at: {skill.created_at}\n"
        f"updated_at: {skill.updated_at}\n"
        f"tags: {tags_str}\n"
        f"pinned: {'true' if skill.pinned else 'false'}\n"
        f"archived: {'true' if skill.archived else 'false'}\n"
        f"---\n"
        f"{skill.body}"
    )


# Лимиты — защита от runaway.
MAX_SKILL_BYTES = 8_000
MAX_SKILLS_PER_CHANNEL = 200


class SkillStore:
    """Per-channel skill storage.

    Args:
        root: <memory_root>/skills/. Каналы — поддиректории.
        channel_id: идентификатор канала.
    """

    def __init__(self, root: Path, channel_id: str) -> None:
        safe = sanitize_channel_id(channel_id)
        if not safe:
            raise ValueError(f"channel_id sanitized to empty: {channel_id!r}")
        self._channel_id = channel_id
        self._dir = Path(root) / safe
        self._archive_dir = self._dir / ".archive"
        self._lock = threading.Lock()

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def directory(self) -> Path:
        return self._dir

    @property
    def archive_directory(self) -> Path:
        return self._archive_dir

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _skill_path(self, skill_id: str, archived: bool = False) -> Path:
        base = self._archive_dir if archived else self._dir
        return base / f"{skill_id}.md"

    def generate_skill_id(self) -> str:
        """Сгенерировать новый случайный id вида skill_<8hex>."""
        return f"skill_{uuid.uuid4().hex[:8]}"

    def write(self, skill: Skill) -> Skill:
        """Записывает skill в файл. provenance auto-set из ContextVar если не задан явно.

        Возвращает обновлённый Skill (с updated_at).

        Raises:
            ValueError: если body > MAX_SKILL_BYTES или превышен лимит skills.
        """
        if len(skill.body) > MAX_SKILL_BYTES:
            raise ValueError(
                f"Skill body too large: {len(skill.body)} > {MAX_SKILL_BYTES}"
            )

        with self._lock:
            self._ensure_dir()
            # Если файл новый и список skills уже на лимите — отказ.
            target = self._skill_path(skill.id, archived=skill.archived)
            if not target.exists():
                active_count = len(list(self._dir.glob("*.md")))
                if active_count >= MAX_SKILLS_PER_CHANNEL:
                    raise ValueError(
                        f"Skill limit reached: {active_count}/{MAX_SKILLS_PER_CHANNEL}. "
                        "Архивируйте старые skills."
                    )
            # Provenance: если в Skill default 'user' но контекст 'agent' — берём контекст.
            if skill.provenance == "user":
                ctx_prov = current_provenance()
                if ctx_prov == "agent":
                    skill.provenance = "agent"
            # updated_at управляется caller'ом. Default (через __post_init__) уже = now().
            # Сценарий UPDATE — caller обязан явно передать новое updated_at либо использовать
            # отдельный метод touch().
            skill.chars = len(skill.body)
            text = serialize_skill(skill)
            tmp = target.with_suffix(".md.tmp")
            if skill.archived:
                self._archive_dir.mkdir(parents=True, exist_ok=True)
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(target)
            return skill

    def read(self, skill_id: str) -> Skill | None:
        """Читает skill по id. None если не найден.

        Сначала ищем активный, потом архив.
        """
        with self._lock:
            for archived in (False, True):
                p = self._skill_path(skill_id, archived=archived)
                if p.exists():
                    try:
                        return parse_skill_file(p.read_text(encoding="utf-8"), skill_id)
                    except (OSError, ValueError) as exc:
                        logger.warning("Cannot read skill %s: %s", skill_id, exc)
                        return None
            return None

    def list_active(self) -> list[Skill]:
        """Возвращает все активные (не архивированные) skills, отсортированные по updated_at desc."""
        with self._lock:
            if not self._dir.exists():
                return []
            skills: list[Skill] = []
            for path in self._dir.glob("*.md"):
                try:
                    skills.append(
                        parse_skill_file(
                            path.read_text(encoding="utf-8"), path.stem
                        )
                    )
                except (OSError, ValueError):
                    continue
            skills.sort(key=lambda s: s.updated_at, reverse=True)
            return skills

    def list_archived(self) -> list[Skill]:
        with self._lock:
            if not self._archive_dir.exists():
                return []
            out: list[Skill] = []
            for path in self._archive_dir.glob("*.md"):
                try:
                    out.append(
                        parse_skill_file(
                            path.read_text(encoding="utf-8"), path.stem
                        )
                    )
                except (OSError, ValueError):
                    continue
            out.sort(key=lambda s: s.updated_at, reverse=True)
            return out

    def archive(self, skill_id: str) -> bool:
        """Перемещает skill из active в .archive/. Pinned skills не архивируются.

        Returns True если архивация выполнена.
        """
        with self._lock:
            src = self._skill_path(skill_id, archived=False)
            if not src.exists():
                return False
            try:
                skill = parse_skill_file(src.read_text(encoding="utf-8"), skill_id)
            except (OSError, ValueError):
                return False
            if skill.pinned:
                logger.info("Skill %s is pinned — пропускаем архивацию", skill_id)
                return False
            skill.archived = True
            skill.updated_at = _now_iso()
            self._archive_dir.mkdir(parents=True, exist_ok=True)
            dst = self._skill_path(skill_id, archived=True)
            dst.write_text(serialize_skill(skill), encoding="utf-8")
            src.unlink()
            return True

    def unarchive(self, skill_id: str) -> bool:
        """Возвращает skill из .archive/ в active."""
        with self._lock:
            src = self._skill_path(skill_id, archived=True)
            if not src.exists():
                return False
            try:
                skill = parse_skill_file(src.read_text(encoding="utf-8"), skill_id)
            except (OSError, ValueError):
                return False
            skill.archived = False
            skill.updated_at = _now_iso()
            self._ensure_dir()
            dst = self._skill_path(skill_id, archived=False)
            dst.write_text(serialize_skill(skill), encoding="utf-8")
            src.unlink()
            return True

    def delete(self, skill_id: str) -> bool:
        """Hard-delete skill (и из active и из archive). Pinned — нельзя."""
        with self._lock:
            existing = self.read(skill_id) if False else None  # placeholder
            removed = False
            for archived in (False, True):
                p = self._skill_path(skill_id, archived=archived)
                if p.exists():
                    try:
                        s = parse_skill_file(p.read_text(encoding="utf-8"), skill_id)
                        if s.pinned:
                            return False
                    except (OSError, ValueError):
                        pass
                    p.unlink()
                    removed = True
            return removed

    def render_for_prompt(self, max_chars: int = 4_000) -> str:
        """Собирает active skills в один блок для system prompt.

        - pinned первыми
        - после — обычные в порядке updated_at desc
        - cap на total bytes (max_chars)
        """
        skills = self.list_active()
        if not skills:
            return ""
        pinned = [s for s in skills if s.pinned]
        normal = [s for s in skills if not s.pinned]
        ordered = pinned + normal

        chunks: list[str] = []
        total = 0
        for s in ordered:
            tag_str = f" [{', '.join(s.tags)}]" if s.tags else ""
            block = f"## {s.id}{tag_str}\n{s.body.strip()}\n"
            if total + len(block) > max_chars:
                # Срезаем последний блок если выходит за лимит.
                remaining = max_chars - total
                if remaining > 100:  # Не вставляем огрызки <100 символов
                    chunks.append(block[:remaining] + "\n...[truncated]")
                break
            chunks.append(block)
            total += len(block)

        if not chunks:
            return ""
        return (
            "### Skills (накопленные подсказки)\n\n"
            + "\n".join(chunks)
        )
