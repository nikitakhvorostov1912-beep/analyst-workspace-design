"""MarkdownStore — MEMORY.md + USER.md provider.

Persistent storage в виде двух markdown файлов на диск per channel.
Schema-less, читаемо человеком, редактируемо в любом редакторе.

Layout:
    <root>/<channel_id>/MEMORY.md   — заметки агента (среда, конвенции,
                                       нюансы базы, паттерны решений)
    <root>/<channel_id>/USER.md     — что мы знаем о пользователе
                                       (предпочтения, домен, стиль)

Каждый файл — markdown с секциями `### <дата | заголовок>`. Append-only
с heuristic dedup (точное совпадение пропускается). Bounded growth через
MAX_TOKENS cap — старые секции обрезаются сверху.

Модель имеет два tool'а: `memory_append` (добавить факт) и `memory_remove`
(удалить по partial match). Tool calls идут через MemoryManager.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from .provider import MemoryProvider

logger = logging.getLogger(__name__)


class MarkdownStore(MemoryProvider):
    """Persistent .md storage для двух namespace: agent и user.

    Args:
        root: каталог хранения. Создаётся при initialize().
        channel_id: канал/база. Один файл MEMORY.md и один USER.md per channel.
        max_memory_chars: cap для MEMORY.md (~4000 tokens). По умолчанию 16 КБ.
        max_user_chars: cap для USER.md (~2000 tokens). По умолчанию 8 КБ.
    """

    name = "markdown_store"
    is_external = False

    # ~4000 tokens ≈ 16 KB символов для MEMORY.md
    DEFAULT_MAX_MEMORY_CHARS = 16_000
    # ~2000 tokens ≈ 8 KB символов для USER.md
    DEFAULT_MAX_USER_CHARS = 8_000

    def __init__(
        self,
        root: Path,
        channel_id: str,
        *,
        max_memory_chars: int = DEFAULT_MAX_MEMORY_CHARS,
        max_user_chars: int = DEFAULT_MAX_USER_CHARS,
    ) -> None:
        self.root = Path(root)
        # Sanitize channel_id для безопасного использования как имя каталога.
        # Запрещаем разделители путей и относительные ссылки.
        safe_channel = re.sub(r"[^A-Za-z0-9._-]", "_", channel_id) or "default"
        self.channel_id = safe_channel
        self.channel_dir = self.root / safe_channel
        self.memory_path = self.channel_dir / "MEMORY.md"
        self.user_path = self.channel_dir / "USER.md"
        self.max_memory_chars = max_memory_chars
        self.max_user_chars = max_user_chars

    def initialize(self) -> None:
        """Создаёт каталог канала и пустые файлы если их нет."""
        self.channel_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.memory_path, self.user_path):
            if not path.exists():
                path.write_text("", encoding="utf-8")

    def system_prompt_block(self) -> str:
        """Block инжектится в SYSTEM_PROMPT. Возвращает пустую строку если оба файла пусты."""
        mem = self._read_capped(self.memory_path, self.max_memory_chars)
        usr = self._read_capped(self.user_path, self.max_user_chars)
        if not mem.strip() and not usr.strip():
            return ""

        mem_section = mem.strip() if mem.strip() else "_(пусто — записывай факты через `memory_append`)_"
        usr_section = usr.strip() if usr.strip() else "_(пусто)_"

        return (
            "## Постоянная память\n\n"
            "<persistent-memory>\n"
            "Эти заметки сохраняются между сессиями. Учитывай их при ответе.\n"
            "Если узнал важный факт о базе или предпочтениях пользователя — "
            "вызови `memory_append`. Если факт устарел — `memory_remove`.\n\n"
            "### MEMORY.md — заметки агента\n"
            f"{mem_section}\n\n"
            "### USER.md — что мы знаем о пользователе\n"
            f"{usr_section}\n"
            "</persistent-memory>"
        )

    def get_tool_schemas(self) -> list[dict]:
        """Два OpenAI-format function tools: append + remove."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "memory_append",
                    "description": (
                        "Append a durable fact to persistent memory. Use sparingly — "
                        "only facts worth remembering across sessions (project conventions, "
                        "user preferences, repeated patterns). Don't dump conversation details."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {
                                "type": "string",
                                "enum": ["agent", "user"],
                                "description": (
                                    "'agent' — заметки об окружении/базе/паттернах. "
                                    "'user' — про предпочтения и домен пользователя."
                                ),
                            },
                            "content": {
                                "type": "string",
                                "description": "Сам факт. 1-3 предложения. Чёткий и переиспользуемый.",
                            },
                            "section": {
                                "type": "string",
                                "description": "Опциональный заголовок секции (например, 'Конвенции базы').",
                            },
                        },
                        "required": ["namespace", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "memory_remove",
                    "description": (
                        "Remove sections matching the given substring (case-insensitive). "
                        "Use for outdated or wrong info."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "namespace": {"type": "string", "enum": ["agent", "user"]},
                            "match": {
                                "type": "string",
                                "description": "Подстрока для поиска секций. Удалятся ВСЕ секции содержащие её.",
                            },
                        },
                        "required": ["namespace", "match"],
                    },
                },
            },
        ]

    def handle_tool_call(self, name: str, args: dict) -> str:
        if name == "memory_append":
            return self._append(
                namespace=args["namespace"],
                content=args["content"],
                section=args.get("section"),
            )
        if name == "memory_remove":
            return self._remove(
                namespace=args["namespace"],
                match=args["match"],
            )
        raise ValueError(f"{self.name}: unknown tool {name!r}")

    # ------------------------------------------------------------------
    # Public helpers (used by /memory REST routes for UI editing)
    # ------------------------------------------------------------------

    def read_namespace(self, namespace: str) -> str:
        """Returns full text of MEMORY.md или USER.md. '' если пусто/нет."""
        path = self._path_for(namespace)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write_namespace(self, namespace: str, content: str) -> int:
        """Перезаписать MEMORY.md или USER.md содержимым. Возвращает длину в символах.

        Cap применяется — слишком длинный текст обрезается сверху.
        Используется UI-редактором (settings/memory page).
        """
        path = self._path_for(namespace)
        max_chars = self.max_memory_chars if namespace == "agent" else self.max_user_chars
        if len(content) > max_chars:
            # Обрезаем сверху, помечаем что было обрезано
            content = "[... earlier entries truncated by max-size cap ...]\n\n" + content[-max_chars:]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return len(content)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _path_for(self, namespace: str) -> Path:
        if namespace == "agent":
            return self.memory_path
        if namespace == "user":
            return self.user_path
        raise ValueError(f"namespace must be 'agent' or 'user', got {namespace!r}")

    def _read_capped(self, path: Path, max_chars: int) -> str:
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8")
        if len(content) > max_chars:
            content = "[... earlier entries truncated ...]\n\n" + content[-max_chars:]
        return content

    def _append(self, namespace: str, content: str, section: str | None) -> str:
        if not content.strip():
            return f"{namespace}: empty content, skipped"
        path = self._path_for(namespace)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""

        # Dedup heuristic: точное совпадение нормализованного содержания
        clean_content = content.strip()
        if clean_content in existing:
            return f"{namespace}: already present, skipped"

        # Заголовок секции — section или дата
        heading = (section or datetime.now(timezone.utc).strftime("%Y-%m-%d")).strip()
        block = f"\n### {heading}\n{clean_content}\n"

        new_text = existing + block
        # Применяем cap при append
        max_chars = self.max_memory_chars if namespace == "agent" else self.max_user_chars
        if len(new_text) > max_chars:
            new_text = "[... earlier entries truncated ...]\n\n" + new_text[-max_chars:]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
        return f"{namespace}: appended {len(clean_content)} chars under section {heading!r}"

    def _remove(self, namespace: str, match: str) -> str:
        if not match.strip():
            return f"{namespace}: empty match, skipped"
        path = self._path_for(namespace)
        if not path.exists():
            return f"{namespace}: file does not exist"
        text = path.read_text(encoding="utf-8")

        # Разбиваем на секции по `### ` (с MULTILINE)
        sections = re.split(r"(?=^### )", text, flags=re.MULTILINE)
        match_lower = match.lower()
        kept = [s for s in sections if match_lower not in s.lower()]
        removed = len(sections) - len(kept)
        if removed == 0:
            return f"{namespace}: no sections matched {match!r}"
        path.write_text("".join(kept), encoding="utf-8")
        return f"{namespace}: removed {removed} section(s) matching {match!r}"
