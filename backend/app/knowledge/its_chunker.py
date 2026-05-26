"""ITS Chunker — разбивка ITSDocument на embedding-friendly чанки (M-K2.7).

Knowledge Foundation Phase 7: получает на вход `ITSDocument` (из
`its_loader.py`), разбивает body по заголовкам markdown и агрегирует
секции до `max_chars` чтобы каждый чанк попадал в embedding-окно
без потери смысла.

**Стратегия разбивки:**

1. Парсим body на «секции» (заголовок + контент). Заголовок —
   любая строка с префиксом `^#+\\s`. Контент секции включает все
   строки до следующего заголовка.
2. Агрегируем последовательные секции пока суммарная длина <= max_chars.
3. Если одна секция > max_chars, разбиваем её по `\\n\\n` (параграфы),
   **с защитой fenced code blocks** (``` ... ```): не дробим внутри.
4. Если параграф ВНУТРИ кода всё ещё > max_chars — оставляем как есть
   (целостность кода важнее лимита, LLM-окна обычно > 8к токенов).

**Заголовок секции:** первая `^#+\\s.+` строка чанка. Если нет —
`None`. Используется UI для cite-back («std396: п.3.1»).

**Что НЕ делает chunker:**
- Не убирает admonitions `!!! example "Пример"` — это контекст.
- Не убирает `[#std499](499.md)` cross-refs — пускай LLM видит.
- Не делает overlap между чанками (sliding window). M-K3 при
  необходимости.
- Не считает токены (только символы) — оценка достаточная для
  text-embedding-3-small (≈ 4 chars/token).

**Дефолт max_chars=1800** — ~450 tokens, в 8k input-окне OpenAI
помещается ~17 чанков параллельно для batch embed.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass

from app.knowledge.its_loader import ITSDocument

logger = logging.getLogger(__name__)


# Дефолтный лимит размера чанка в символах. ≈ 450 токенов
# (text-embedding-3-small окно 8191 token).
DEFAULT_MAX_CHARS = 1800

# Если секция меньше этого порога — попытка склеить со следующей.
DEFAULT_MIN_CHARS = 300

# Регулярка для markdown-заголовков (1-6 хешей + пробел + текст).
# `^` + `re.MULTILINE` — заголовок только в начале строки.
_HEADER_RE = re.compile(r"^(#+)\s+(.+?)\s*$", re.MULTILINE)

# Регулярка для fenced code блоков ``` ... ``` (вкл. ```bsl, ```python etc.).
_FENCE_RE = re.compile(r"^```", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ITSChunk:
    """Один чанк ITSDocument готовый к embed/store.

    Attrs:
        doc_id: совпадает с ITSDocument.doc_id (для JOIN с метаданными)
        chunk_index: 0-based порядковый номер чанка в документе
        section_title: первый header в content (или None если только текст)
        content: markdown текст чанка (включает заголовок)
        char_count: len(content)
        content_hash: SHA-256 hex для idempotent re-index detection
    """

    doc_id: str
    chunk_index: int
    section_title: str | None
    content: str
    char_count: int
    content_hash: str

    @property
    def object_path(self) -> str:
        """Стабильный путь для vec_objects.object_path: `its:{doc_id}#{index}`."""
        return f"its:{self.doc_id}#{self.chunk_index}"


def _split_into_sections(body: str) -> list[tuple[str | None, str]]:
    """Делит body на список (section_title, content_block).

    Section_title — текст заголовка (без хешей). Content_block — весь
    текст от заголовка до СЛЕДУЮЩЕГО заголовка, ВКЛЮЧАЯ строку
    заголовка (чтобы chunk сохранял контекст).

    Если body не содержит заголовков — возвращает один элемент
    `[(None, body)]`.

    Если body начинается с текста до первого заголовка — этот «вступительный»
    кусок становится первой секцией с section_title=None.
    """
    matches = list(_HEADER_RE.finditer(body))
    if not matches:
        stripped = body.strip()
        return [(None, body)] if stripped else []

    sections: list[tuple[str | None, str]] = []

    # Вступление до первого заголовка
    first_start = matches[0].start()
    if first_start > 0:
        intro = body[:first_start]
        if intro.strip():
            sections.append((None, intro.rstrip() + "\n"))

    # Каждый заголовок + всё до следующего
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        section_start = match.start()
        section_end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[section_start:section_end]
        if content.strip():
            sections.append((title, content))

    return sections


def _aggregate_sections(
    sections: list[tuple[str | None, str]],
    max_chars: int,
) -> Iterator[tuple[str | None, str]]:
    """Склеивает соседние секции пока итоговая длина ≤ max_chars.

    Возвращает iterator (section_title, aggregated_content). Заголовок
    результата — заголовок ПЕРВОЙ склеенной секции.

    Если одна секция > max_chars — yield её отдельно (без агрегации).
    """
    if not sections:
        return

    current_title: str | None = None
    current_parts: list[str] = []
    current_len = 0
    first_in_group = True

    for title, content in sections:
        content_len = len(content)

        if first_in_group:
            current_title = title
            current_parts = [content]
            current_len = content_len
            first_in_group = False
            continue

        # Помещается?
        if current_len + content_len <= max_chars:
            current_parts.append(content)
            current_len += content_len
            continue

        # Не помещается — flush текущий + начинаем новый
        yield current_title, "".join(current_parts)
        current_title = title
        current_parts = [content]
        current_len = content_len

    # Хвост
    if current_parts:
        yield current_title, "".join(current_parts)


def _split_oversize_section(
    title: str | None,
    content: str,
    max_chars: int,
) -> list[tuple[str | None, str]]:
    """Разбивает одну oversize-секцию по параграфам с защитой code blocks.

    Возвращает list of (section_title, part_content). Первый part наследует
    title секции; последующие — None (нет нового заголовка, это всё та же
    секция, просто разрезанная).

    Если параграф внутри code block превышает max_chars — оставляем целиком,
    логируем warning. Код важнее лимита.
    """
    if len(content) <= max_chars:
        return [(title, content)]

    # Разбиваем по \n\n, но не внутри fenced code блоков.
    lines = content.split("\n")
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    in_fence = False

    for line in lines:
        is_fence = _FENCE_RE.match(line) is not None
        if is_fence:
            in_fence = not in_fence

        line_with_nl = line + "\n"
        line_len = len(line_with_nl)

        # Точка разреза — пустая строка вне code-fence И мы превысили half-max
        # (даём шанс собрать что-то осмысленное, не разрезаем при первой
        # пустой строке).
        if (
            not in_fence
            and line.strip() == ""
            and current_len + line_len > max_chars
            and current
        ):
            parts.append("".join(current))
            current = []
            current_len = 0
            continue

        current.append(line_with_nl)
        current_len += line_len

    if current:
        parts.append("".join(current))

    if not parts:
        return [(title, content)]

    # Любой part всё ещё > max_chars — оставляем целиком (code block внутри
    # обычно). Лог-варнинг для отладки.
    for part in parts:
        if len(part) > max_chars:
            logger.debug(
                "ITS chunk overflow: doc_section=%r part_len=%d max_chars=%d "
                "(code-block oversize, оставляю целиком)",
                title, len(part), max_chars,
            )

    return [(title if i == 0 else None, part) for i, part in enumerate(parts)]


def _hash_content(content: str) -> str:
    """SHA-256 hex чанка для idempotent re-index detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def chunk_document(
    doc: ITSDocument,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> Iterator[ITSChunk]:
    """Превращает ITSDocument в последовательность ITSChunk.

    Args:
        doc: загруженный документ ИТС
        max_chars: дефолт 1800 (~450 токенов). Меньше → больше чанков;
                  больше → меньше но возможно потеря контекста при матче.

    Yields:
        ITSChunk с chunk_index 0..N-1.

    Контракт: если body пуст — yield пустую последовательность. Не raises.
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars должен быть > 0, получено {max_chars}")

    sections = _split_into_sections(doc.body)
    if not sections:
        return

    # Agregate → maybe split oversize → emit
    chunk_index = 0
    for title, content in _aggregate_sections(sections, max_chars):
        parts = _split_oversize_section(title, content, max_chars)
        for part_title, part_content in parts:
            stripped = part_content.strip()
            if not stripped:
                continue
            yield ITSChunk(
                doc_id=doc.doc_id,
                chunk_index=chunk_index,
                section_title=part_title,
                content=part_content,
                char_count=len(part_content),
                content_hash=_hash_content(part_content),
            )
            chunk_index += 1
