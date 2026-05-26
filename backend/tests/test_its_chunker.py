"""Тесты для backend/app/knowledge/its_chunker.py (M-K2.7).

Покрытие:
- _split_into_sections: вступление, заголовки, code blocks
- _aggregate_sections: малые секции склеиваются до max_chars
- _split_oversize_section: разбивка по \\n\\n, защита code-fence
- chunk_document: integration, stable hash, monotonic chunk_index
- ITSChunk.object_path формат
"""

from __future__ import annotations

import pytest

from app.knowledge.its_chunker import (
    DEFAULT_MAX_CHARS,
    ITSChunk,
    _aggregate_sections,
    _hash_content,
    _split_into_sections,
    _split_oversize_section,
    chunk_document,
)
from app.knowledge.its_loader import ITSDocument


def _make_doc(body: str, doc_id: str = "std396") -> ITSDocument:
    """Хелпер для тестов — минимальный ITSDocument."""
    return ITSDocument(
        doc_id=doc_id,
        title="Test Title",
        body=body,
        category="std",
        source_path=f"std/{doc_id[3:]}.md",
    )


# ---------- _split_into_sections ----------


def test_split_no_headers_returns_single_section():
    body = "Just plain text without any headers"
    result = _split_into_sections(body)
    assert len(result) == 1
    assert result[0][0] is None
    assert result[0][1] == body


def test_split_empty_returns_empty():
    assert _split_into_sections("") == []
    assert _split_into_sections("   \n\n  \n") == []


def test_split_with_intro_before_first_header():
    body = "Intro text\n\n# Title 1\n\nbody1"
    result = _split_into_sections(body)
    assert len(result) == 2
    assert result[0] == (None, "Intro text\n")
    assert result[1][0] == "Title 1"
    assert result[1][1].startswith("# Title 1")


def test_split_multiple_headers():
    body = "# H1\n\ncontent 1\n\n## H2\n\ncontent 2\n\n###### Subsection 3.1\n\ncontent 3"
    result = _split_into_sections(body)
    assert len(result) == 3
    assert result[0][0] == "H1"
    assert result[1][0] == "H2"
    assert result[2][0] == "Subsection 3.1"


def test_split_section_includes_header_line():
    body = "# Title\n\nbody"
    result = _split_into_sections(body)
    assert result[0][1].startswith("# Title")
    assert "body" in result[0][1]


# ---------- _aggregate_sections ----------


def test_aggregate_combines_small_sections():
    sections = [
        ("S1", "# S1\nsmall content 1"),
        ("S2", "# S2\nsmall content 2"),
        ("S3", "# S3\nsmall content 3"),
    ]
    result = list(_aggregate_sections(sections, max_chars=200))
    assert len(result) == 1
    assert result[0][0] == "S1"  # title первой
    assert "S1" in result[0][1] and "S2" in result[0][1] and "S3" in result[0][1]


def test_aggregate_splits_when_exceeds_limit():
    big = "x" * 100
    sections = [
        ("A", f"# A\n{big}"),
        ("B", f"# B\n{big}"),
        ("C", f"# C\n{big}"),
    ]
    # max_chars 200 — каждые 2 секции по ~104 = ~208 > 200, не помещаются
    result = list(_aggregate_sections(sections, max_chars=200))
    assert len(result) == 3
    titles = [r[0] for r in result]
    assert titles == ["A", "B", "C"]


def test_aggregate_empty():
    assert list(_aggregate_sections([], max_chars=100)) == []


def test_aggregate_single_oversize_passes_through():
    """Если одна секция > max_chars, _aggregate не пытается её резать (это работа _split_oversize_section)."""
    huge = "x" * 5000
    sections = [("Big", f"# Big\n{huge}")]
    result = list(_aggregate_sections(sections, max_chars=1000))
    assert len(result) == 1
    assert result[0][0] == "Big"
    assert len(result[0][1]) > 1000


# ---------- _split_oversize_section ----------


def test_split_oversize_returns_single_when_under_limit():
    content = "short content"
    result = _split_oversize_section("T", content, max_chars=100)
    assert result == [("T", content)]


def test_split_oversize_splits_by_paragraphs():
    p1 = "a" * 500
    p2 = "b" * 500
    p3 = "c" * 500
    content = f"# Section\n\n{p1}\n\n{p2}\n\n{p3}"
    result = _split_oversize_section("Section", content, max_chars=600)
    assert len(result) > 1
    # Первый part наследует title
    assert result[0][0] == "Section"
    # Последующие — None
    for part_title, _ in result[1:]:
        assert part_title is None


def test_split_oversize_preserves_code_fence():
    """Не должен разрезать ВНУТРИ ```bsl ... ``` блока."""
    code_block = "```bsl\n" + ("Сообщить(\"X\");\n" * 100) + "```"
    content = f"# Section\n\nintro\n\n{code_block}\n\noutro"
    result = _split_oversize_section("Section", content, max_chars=200)
    # Каждый part должен либо содержать code block целиком, либо вообще не
    # содержать ```
    for _, part in result:
        opens = part.count("```")
        # Если есть хоть одна метка — должна быть парная (open + close)
        assert opens % 2 == 0, f"Code fence несбалансирован в part: {part[:200]}"


# ---------- chunk_document ----------


def test_chunk_document_empty_body_yields_nothing():
    doc = _make_doc("")
    chunks = list(chunk_document(doc))
    assert chunks == []


def test_chunk_document_short_body_yields_one_chunk():
    doc = _make_doc("# Title\n\nshort content")
    chunks = list(chunk_document(doc))
    assert len(chunks) == 1
    assert isinstance(chunks[0], ITSChunk)
    assert chunks[0].chunk_index == 0
    assert chunks[0].doc_id == "std396"


def test_chunk_document_long_body_yields_multiple():
    long_body = "# Title\n\n"
    for i in range(20):
        long_body += f"###### {i}.\n\n{'x' * 200}\n\n"
    doc = _make_doc(long_body)
    chunks = list(chunk_document(doc, max_chars=500))
    assert len(chunks) > 1
    # chunk_index монотонно растёт от 0
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunk_document_hash_is_stable():
    """Один и тот же контент → один и тот же hash (для skip-already-indexed)."""
    doc = _make_doc("# T\n\nstable text")
    chunks1 = list(chunk_document(doc))
    chunks2 = list(chunk_document(doc))
    assert chunks1[0].content_hash == chunks2[0].content_hash


def test_chunk_document_object_path_format():
    doc = _make_doc("# T\n\nbody", doc_id="std396")
    chunks = list(chunk_document(doc))
    assert chunks[0].object_path == "its:std396#0"


def test_chunk_document_invalid_max_chars():
    doc = _make_doc("# T\n\nbody")
    with pytest.raises(ValueError, match="max_chars должен быть > 0"):
        list(chunk_document(doc, max_chars=0))
    with pytest.raises(ValueError):
        list(chunk_document(doc, max_chars=-1))


def test_chunk_document_default_max_chars_is_reasonable():
    """Дефолт DEFAULT_MAX_CHARS подходит под embedding окно."""
    assert 500 <= DEFAULT_MAX_CHARS <= 4000


def test_chunk_document_preserves_section_titles():
    body = "# H1\n\nbody1\n\n###### 1.\n\nbody2\n\n###### 2.\n\nbody3"
    doc = _make_doc(body)
    # max_chars 50 — каждая секция отдельным чанком
    chunks = list(chunk_document(doc, max_chars=50))
    titles = [c.section_title for c in chunks]
    # Первая секция — H1
    assert titles[0] == "H1"


def test_chunk_document_content_includes_header():
    body = "# Important Title\n\nthe body"
    doc = _make_doc(body)
    chunks = list(chunk_document(doc))
    assert "# Important Title" in chunks[0].content
    assert "the body" in chunks[0].content


def test_chunk_document_aggregates_small_sections():
    body = "# T\n\n" + "###### 1.\n\nshort\n\n" * 10
    doc = _make_doc(body)
    chunks = list(chunk_document(doc, max_chars=5000))
    # Огромный лимит — должно быть мало чанков (склейка)
    assert len(chunks) == 1


# ---------- _hash_content ----------


def test_hash_content_is_deterministic():
    assert _hash_content("foo") == _hash_content("foo")


def test_hash_content_differs_for_different_input():
    assert _hash_content("foo") != _hash_content("bar")


def test_hash_content_handles_unicode():
    h = _hash_content("кириллица")
    assert len(h) == 64  # SHA-256 = 64 hex
