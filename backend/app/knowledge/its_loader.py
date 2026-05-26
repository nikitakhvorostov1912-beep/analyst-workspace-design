"""ITS Loader — парсинг markdown статей ИТС из tools/v8std/docs/ (M-K2.7).

Knowledge Foundation Phase 7: загружает корпус ИТС-стандартов 1С
(публичный зеркальный markdown zeegin/v8std, CC-BY-4.0) для последующего
chunking + embedding + индексации в vec_objects (channel_id="_its").

**Источник:** tools/v8std/docs/{std, patterns, diagnostics, metod8dev, lang}/

- std/<N>.md — нумерованные ИТС-стандарты (317 файлов)
- patterns/<group>/<slug>/index.md — паттерны проектирования (~48)
- metod8dev/<N>.md — методические статьи разработчика (~10)
- diagnostics/<subdir>/<file>.md — статьи по диагностикам BSL LS / acc
- lang/index.md — обзор языка

**Что НЕ загружаем (skip-list):**
- Top-level navigation: index.md, mcp.md, support.md, search-help.md
- Чисто навигационные группы без полезной информации

**Что НЕ делает M-K2.7 loader:**
- Не делает chunking (это `its_chunker.py`).
- Не нормализует admonitions `!!! example "..."` (оставляем как есть —
  embedding-модель не страдает от лишних маркеров).
- Не разворачивает cross-references `[#std499](499.md)` — оставляем как
  есть, LLM поймёт.
- Не пишет в БД (это `its_indexer.py`).

**Зависимости:** только pathlib + dataclasses. Pure-функции (легко тестировать).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


ITSCategory = Literal["std", "patterns", "diagnostics", "metod8dev", "lang"]


# Файлы которые на любом уровне игнорируем — это навигация, поиск, support.
# index.md встречается часто (в каждой группе patterns) — внутри groups он
# нужен (overview), а на корневом уровне docs/ — нет. Решаем через
# `_should_skip_file` с учётом глубины.
_TOP_LEVEL_NAV_FILES = frozenset({"index.md", "mcp.md", "support.md", "search-help.md"})


# Допустимые корневые категории. Если top-level dir не в этом списке —
# loader пропускает (например, assets/ — только картинки).
_ALLOWED_CATEGORIES: frozenset[ITSCategory] = frozenset(
    {"std", "patterns", "diagnostics", "metod8dev", "lang"}
)


# Регулярка для первого H1 заголовка `# Title`. ITS-документы используют
# `# Title` для основного заголовка (после opening `###### #std396` ID).
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)

# Открывающий ID-маркер `###### #std396` — выкидываем при titlestrip.
_ID_HEADER_RE = re.compile(r"^######\s+#\S+\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ITSDocument:
    """Один загруженный markdown-документ ИТС.

    Body — raw markdown, готовый к chunking. Title — извлечён из первого
    `# H1` или fallback на имя файла. doc_id — стабильный slug, по которому
    индексер строит `object_path = f"its:{doc_id}#{chunk_index}"`.

    Attrs:
        doc_id: стабильный slug (см. `_extract_doc_id`)
        title: первый H1 в файле (например, «Обработчик события ОбработкаЗаполнения»)
        body: markdown без ID-маркера, готов к chunking
        category: одна из 5 ITSCategory
        source_path: путь относительно docs/ root (например, "std/396.md")
    """

    doc_id: str
    title: str
    body: str
    category: ITSCategory
    source_path: str


class ITSLoaderError(Exception):
    """Ошибка loader — невалидный root, нечитаемый файл."""


def _slugify(text: str) -> str:
    """Превращает произвольный кусок имени файла/каталога в kebab-slug.

    Используется только для `patterns/*/*/...` где исходные пути латиницей
    и без пробелов — но на всякий случай прогоняем через нормализацию.
    Кириллицу не транслитерируем (в std/ и metod8dev/ её нет в именах).
    """
    text = text.lower().strip()
    # Убираем расширение если есть
    if text.endswith(".md"):
        text = text[:-3]
    # Заменяем не-alnum на дефис
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _extract_doc_id(rel_path: Path, category: ITSCategory) -> str:
    """Строит стабильный slug по relative path внутри docs/.

    Конвенция:
    - std/<N>.md         → "std{N}"          (std396, std400)
    - metod8dev/<N>.md   → "metod{N}"        (metod1590)
    - patterns/<g>/index.md       → "pattern-{g}"        (pattern-engineering)
    - patterns/<g>/<s>/index.md   → "pattern-{g}-{s}"    (pattern-engineering-dry)
    - patterns/index.md  → "pattern-overview"  (skip-list скрывает это)
    - diagnostics/<sub>/<f>.md    → "diag-{sub}-{stem}"  (diag-bslls-canonical-spelling)
    - diagnostics/<sub>/index.md  → "diag-{sub}"         (diag-bslls)
    - diagnostics/index.md → "diag-overview"   (skip-list скрывает это)
    - lang/index.md      → "lang-overview"
    """
    parts = rel_path.parts
    # parts[0] = category, остальное — внутри
    inside = parts[1:]
    if not inside:
        # Файл прямо в категории — невозможно (loader не дойдёт)
        return f"{category}-orphan-{_slugify(rel_path.stem)}"

    if category == "std":
        # std/<N>.md → "std{N}"
        return f"std{rel_path.stem}"

    if category == "metod8dev":
        return f"metod{rel_path.stem}"

    if category == "patterns":
        # Без последнего сегмента (имя файла, обычно index.md)
        dirs = [_slugify(p) for p in inside[:-1]]
        last = inside[-1]
        if last == "index.md":
            slug_parts = dirs
        else:
            # На случай patterns/<group>/<some-other>.md (нестандартно)
            slug_parts = dirs + [_slugify(last)]
        return "pattern-" + "-".join(slug_parts) if slug_parts else "pattern-overview"

    if category == "diagnostics":
        dirs = [_slugify(p) for p in inside[:-1]]
        last = inside[-1]
        if last == "index.md":
            slug_parts = dirs
        else:
            slug_parts = dirs + [_slugify(last)]
        return "diag-" + "-".join(slug_parts) if slug_parts else "diag-overview"

    if category == "lang":
        # lang/index.md → lang-overview
        if inside[-1] == "index.md" and len(inside) == 1:
            return "lang-overview"
        return "lang-" + "-".join(_slugify(p) for p in inside).replace("-index", "")

    # Defensive — невозможно по контракту _ALLOWED_CATEGORIES
    return f"{category}-{_slugify('-'.join(inside))}"


def _extract_title(body: str, fallback: str) -> str:
    """Возвращает первый H1 (`# Title`) или fallback (имя файла без расширения).

    ITS-стандарты начинаются с `###### #stdN` маркера и потом `# Title`.
    Если H1 нет — берём имя файла.
    """
    match = _H1_RE.search(body)
    if match:
        return match.group(1).strip()
    return fallback


def _strip_id_header(body: str) -> str:
    """Удаляет opening `###### #stdN` ID-маркер.

    Этот маркер дублирует имя файла и шумит при embedding'е (LLM может
    сфокусироваться на `#stdN` вместо смысла). Оставляем только тело.
    """
    return _ID_HEADER_RE.sub("", body, count=1).lstrip("\n")


def _should_skip_file(rel_path: Path) -> bool:
    """Решает, пропускать ли файл при load.

    Top-level navigation файлы (docs/index.md, docs/mcp.md, ...) — да.
    Внутри категорий index.md загружаем (overview) — это полезный контент.
    """
    if len(rel_path.parts) == 1 and rel_path.name in _TOP_LEVEL_NAV_FILES:
        return True
    return False


def _detect_category(rel_path: Path) -> ITSCategory | None:
    """Определяет category по первому сегменту пути.

    Возвращает None если top-level не в `_ALLOWED_CATEGORIES` (assets, docker и т.п.).
    """
    if not rel_path.parts:
        return None
    top = rel_path.parts[0]
    if top in _ALLOWED_CATEGORIES:
        # type: ignore — runtime check выше
        return top  # type: ignore[return-value]
    return None


def parse_md_file(
    abs_path: Path,
    docs_root: Path,
) -> ITSDocument | None:
    """Парсит один .md-файл в ITSDocument.

    Возвращает None если:
    - файл не относится к допустимым категориям
    - файл в skip-list
    - файл пустой или содержит только пробелы

    Args:
        abs_path: абсолютный путь к .md
        docs_root: корневой docs/ (для расчёта relative path)

    Raises:
        ITSLoaderError: при ошибке чтения файла.
    """
    if abs_path.suffix.lower() != ".md":
        return None

    try:
        rel_path = abs_path.relative_to(docs_root)
    except ValueError:
        return None

    if _should_skip_file(rel_path):
        return None

    category = _detect_category(rel_path)
    if category is None:
        return None

    try:
        raw = abs_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ITSLoaderError(f"Не удалось прочитать {abs_path}: {exc}") from exc

    if not raw.strip():
        logger.debug("ITS file is empty, skipping: %s", rel_path)
        return None

    body = _strip_id_header(raw)
    if not body.strip():
        # Файл содержал только ID-маркер — мусор
        return None

    title = _extract_title(body, fallback=abs_path.stem)
    doc_id = _extract_doc_id(rel_path, category)
    source_path = rel_path.as_posix()

    return ITSDocument(
        doc_id=doc_id,
        title=title,
        body=body,
        category=category,
        source_path=source_path,
    )


def load_its_documents(docs_root: Path) -> Iterator[ITSDocument]:
    """Рекурсивно проходит docs_root и yields все валидные ITSDocument.

    Порядок не гарантирован (зависит от FS). Идёт в одном проходе через
    `rglob('*.md')` — для текущего объёма (~1200 файлов) это быстро (< 1s
    на NVMe).

    Args:
        docs_root: корневой каталог `tools/v8std/docs/`.

    Raises:
        ITSLoaderError: если docs_root не существует или не каталог.

    Yields:
        ITSDocument для каждого валидного .md.
    """
    if not docs_root.exists():
        raise ITSLoaderError(f"ITS docs root не найден: {docs_root}")
    if not docs_root.is_dir():
        raise ITSLoaderError(f"ITS docs root не каталог: {docs_root}")

    for md_path in docs_root.rglob("*.md"):
        if not md_path.is_file():
            continue
        try:
            doc = parse_md_file(md_path, docs_root)
        except ITSLoaderError:
            logger.exception("Не смог разобрать %s — пропускаю", md_path)
            continue
        if doc is not None:
            yield doc
