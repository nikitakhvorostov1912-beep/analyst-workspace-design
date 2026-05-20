"""Skill bundles — /<bundle-name> slash-команды для загрузки N skills.

Sprint 5 (Hermes A10): bundle = YAML файл со списком skill_id, который
аналитик может одной командой включить в SYSTEM_PROMPT.

Пример (`bundles/закрытие-месяца.yaml`):
    name: closing-month
    title: Закрытие месяца
    description: Подсказки по закрытию периода (проводки, акты, баланс)
    skills:
      - check-postings
      - reconcile-acts
      - balance-check

Команда `/closing-month` → backend подбирает active=True для этих skills.

Минимально жизнеспособная реализация: парсер YAML руками (без зависимости).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_SKILLS_PER_BUNDLE = 20


@dataclass
class Bundle:
    """Описание bundle."""

    name: str
    title: str
    description: str = ""
    skills: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name):
            raise ValueError(
                f"Bundle name '{self.name}' invalid: [A-Za-z0-9_-], 1-64 chars"
            )
        if len(self.skills) > MAX_SKILLS_PER_BUNDLE:
            raise ValueError(
                f"Bundle '{self.name}' содержит >{MAX_SKILLS_PER_BUNDLE} skills"
            )


def parse_bundle_yaml(text: str) -> Bundle:
    """Очень простой YAML парсер для bundle файлов.

    Поддерживает только верхнеуровневые ключи (name, title, description, skills)
    и list через ` - item ` синтаксис. Без зависимости PyYAML.
    """
    name = ""
    title = ""
    description = ""
    skills: list[str] = []
    in_skills = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if in_skills and line.startswith(" "):
            stripped = line.strip()
            if stripped.startswith("- "):
                skills.append(stripped[2:].strip().strip("\"'"))
                continue
            in_skills = False  # secondary key вышел

        if line.startswith("name:"):
            name = line.split(":", 1)[1].strip().strip("\"'")
            in_skills = False
        elif line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip("\"'")
            in_skills = False
        elif line.startswith("description:"):
            description = line.split(":", 1)[1].strip().strip("\"'")
            in_skills = False
        elif line.startswith("skills:"):
            tail = line.split(":", 1)[1].strip()
            if tail.startswith("[") and tail.endswith("]"):
                # Inline list: [a, b, c]
                inner = tail[1:-1]
                for part in inner.split(","):
                    p = part.strip().strip("\"'")
                    if p:
                        skills.append(p)
                in_skills = False
            else:
                in_skills = True

    if not name:
        raise ValueError("Bundle YAML: missing 'name'")
    return Bundle(
        name=name, title=title or name, description=description, skills=skills,
    )


class BundleRegistry:
    """In-memory registry загруженных bundle'ов."""

    def __init__(self) -> None:
        self._bundles: dict[str, Bundle] = {}

    def add(self, bundle: Bundle) -> None:
        self._bundles[bundle.name] = bundle

    def get(self, name: str) -> Bundle | None:
        return self._bundles.get(name)

    def list_all(self) -> list[Bundle]:
        return sorted(self._bundles.values(), key=lambda b: b.name)

    def remove(self, name: str) -> bool:
        return self._bundles.pop(name, None) is not None

    def clear(self) -> None:
        self._bundles.clear()


def load_bundles_from_dir(dir_path: Path) -> BundleRegistry:
    """Загружает все *.yaml/*.yml из dir_path → BundleRegistry."""
    registry = BundleRegistry()
    if not dir_path.exists():
        return registry
    for path in sorted(dir_path.iterdir()):
        if path.suffix not in (".yaml", ".yml"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
            bundle = parse_bundle_yaml(text)
            registry.add(bundle)
        except (OSError, ValueError) as exc:
            logger.warning("Не удалось загрузить bundle %s: %s", path, exc)
    return registry
