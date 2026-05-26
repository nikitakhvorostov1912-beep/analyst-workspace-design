"""Тесты для backend/app/knowledge/its_loader.py (M-K2.7).

Покрытие:
- _slugify / _extract_doc_id для всех 5 категорий
- _extract_title — H1, fallback
- _strip_id_header — `###### #stdN`
- _should_skip_file — top-level navigation
- _detect_category — допустимые / отвергнутые верхушки
- parse_md_file — happy / skip / empty
- load_its_documents — recursive iteration, ошибки
- Migration v14 — its_chunks table + UNIQUE constraint
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from app.knowledge.its_loader import (
    ITSDocument,
    ITSLoaderError,
    _detect_category,
    _extract_doc_id,
    _extract_title,
    _should_skip_file,
    _slugify,
    _strip_id_header,
    load_its_documents,
    parse_md_file,
)
from app.storage.migrations import apply_migrations


# ---------- _slugify ----------


def test_slugify_lowercases_and_replaces_separators():
    assert _slugify("DRY") == "dry"
    assert _slugify("Rule Of Three") == "rule-of-three"
    assert _slugify("separation-of-concerns") == "separation-of-concerns"


def test_slugify_strips_md_suffix():
    assert _slugify("396.md") == "396"
    assert _slugify("abstract-factory.md") == "abstract-factory"


def test_slugify_collapses_multiple_separators():
    assert _slugify("foo___bar") == "foo-bar"
    assert _slugify("--leading-and-trailing--") == "leading-and-trailing"


# ---------- _extract_doc_id ----------


def test_extract_doc_id_std():
    rel = Path("std/396.md")
    assert _extract_doc_id(rel, "std") == "std396"


def test_extract_doc_id_metod():
    rel = Path("metod8dev/1590.md")
    assert _extract_doc_id(rel, "metod8dev") == "metod1590"


def test_extract_doc_id_pattern_group_index():
    rel = Path("patterns/engineering/index.md")
    assert _extract_doc_id(rel, "patterns") == "pattern-engineering"


def test_extract_doc_id_pattern_specific():
    rel = Path("patterns/engineering/dry/index.md")
    assert _extract_doc_id(rel, "patterns") == "pattern-engineering-dry"


def test_extract_doc_id_pattern_gof_specific():
    rel = Path("patterns/gof/abstract-factory/index.md")
    assert _extract_doc_id(rel, "patterns") == "pattern-gof-abstract-factory"


def test_extract_doc_id_diagnostics_subdir():
    rel = Path("diagnostics/bslls/canonical-spelling-keywords/index.md")
    assert _extract_doc_id(rel, "diagnostics") == "diag-bslls-canonical-spelling-keywords"


def test_extract_doc_id_diagnostics_subdir_index():
    rel = Path("diagnostics/bslls/index.md")
    assert _extract_doc_id(rel, "diagnostics") == "diag-bslls"


def test_extract_doc_id_lang_overview():
    rel = Path("lang/index.md")
    assert _extract_doc_id(rel, "lang") == "lang-overview"


# ---------- _extract_title ----------


def test_extract_title_finds_first_h1():
    body = "Some intro\n\n# My Title\n\nbody"
    assert _extract_title(body, "fallback") == "My Title"


def test_extract_title_strips_whitespace_around():
    body = "# Title with spaces around   \nbody"
    assert _extract_title(body, "fallback") == "Title with spaces around"


def test_extract_title_uses_fallback_when_no_h1():
    body = "No headers here just text"
    assert _extract_title(body, "filename") == "filename"


def test_extract_title_ignores_h2():
    body = "## Subtitle\n\n# Real Title\n\nbody"
    # H1 находится — берём его (regex matches first H1)
    assert _extract_title(body, "fallback") == "Real Title"


# ---------- _strip_id_header ----------


def test_strip_id_header_removes_std_marker():
    body = "###### #std396\n\n# Title\n\nbody"
    stripped = _strip_id_header(body)
    assert "#std396" not in stripped
    assert stripped.startswith("# Title")


def test_strip_id_header_noop_if_absent():
    body = "# Title\n\nbody"
    assert _strip_id_header(body) == body


# ---------- _should_skip_file ----------


def test_skip_top_level_navigation():
    assert _should_skip_file(Path("index.md"))
    assert _should_skip_file(Path("mcp.md"))
    assert _should_skip_file(Path("support.md"))
    assert _should_skip_file(Path("search-help.md"))


def test_dont_skip_nested_index():
    # patterns/engineering/index.md — это полезный overview
    assert not _should_skip_file(Path("patterns/engineering/index.md"))
    assert not _should_skip_file(Path("std/396.md"))


# ---------- _detect_category ----------


def test_detect_category_allowed():
    assert _detect_category(Path("std/396.md")) == "std"
    assert _detect_category(Path("patterns/engineering/dry/index.md")) == "patterns"
    assert _detect_category(Path("diagnostics/bslls/index.md")) == "diagnostics"
    assert _detect_category(Path("metod8dev/1590.md")) == "metod8dev"
    assert _detect_category(Path("lang/index.md")) == "lang"


def test_detect_category_rejects_assets_and_other():
    assert _detect_category(Path("assets/img/logo.png.md")) is None
    assert _detect_category(Path("docker-compose/somefile.md")) is None
    assert _detect_category(Path("tests/somefile.md")) is None


# ---------- parse_md_file ----------


def test_parse_md_file_happy(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    target = root / "std" / "396.md"
    target.write_text(
        "###### #std396\n\n# Обработчик события ОбработкаЗаполнения\n\nbody текст",
        encoding="utf-8",
    )

    doc = parse_md_file(target, root)
    assert doc is not None
    assert doc.doc_id == "std396"
    assert doc.title == "Обработчик события ОбработкаЗаполнения"
    assert "body текст" in doc.body
    assert "#std396" not in doc.body  # ID header stripped
    assert doc.category == "std"
    assert doc.source_path == "std/396.md"


def test_parse_md_file_skips_navigation(tmp_path: Path):
    root = tmp_path / "docs"
    root.mkdir()
    nav = root / "index.md"
    nav.write_text("# Nav\nlinks", encoding="utf-8")

    assert parse_md_file(nav, root) is None


def test_parse_md_file_skips_unknown_category(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "assets").mkdir(parents=True)
    not_a_doc = root / "assets" / "x.md"
    not_a_doc.write_text("# Asset", encoding="utf-8")

    assert parse_md_file(not_a_doc, root) is None


def test_parse_md_file_returns_none_for_empty(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    empty = root / "std" / "999.md"
    empty.write_text("   \n\n", encoding="utf-8")

    assert parse_md_file(empty, root) is None


def test_parse_md_file_returns_none_for_only_id_header(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    target = root / "std" / "888.md"
    target.write_text("###### #std888\n\n", encoding="utf-8")

    assert parse_md_file(target, root) is None


def test_parse_md_file_uses_filename_fallback_when_no_h1(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    target = root / "std" / "777.md"
    target.write_text("###### #std777\n\njust text no H1", encoding="utf-8")

    doc = parse_md_file(target, root)
    assert doc is not None
    assert doc.title == "777"  # fallback на stem


def test_parse_md_file_rejects_non_md(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    non_md = root / "std" / "notes.txt"
    non_md.write_text("text", encoding="utf-8")

    assert parse_md_file(non_md, root) is None


# ---------- load_its_documents ----------


def test_load_its_documents_walks_recursively(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "std").mkdir(parents=True)
    (root / "std" / "396.md").write_text(
        "###### #std396\n\n# Title 396\n\nbody",
        encoding="utf-8",
    )
    (root / "std" / "400.md").write_text(
        "###### #std400\n\n# Title 400\n\nbody",
        encoding="utf-8",
    )
    (root / "patterns" / "engineering" / "dry").mkdir(parents=True)
    (root / "patterns" / "engineering" / "dry" / "index.md").write_text(
        "# DRY Principle\n\nbody",
        encoding="utf-8",
    )
    # navigation skip
    (root / "index.md").write_text("# Nav", encoding="utf-8")
    # unknown category skip
    (root / "assets").mkdir()
    (root / "assets" / "x.md").write_text("# X", encoding="utf-8")

    docs = list(load_its_documents(root))
    doc_ids = {d.doc_id for d in docs}
    assert doc_ids == {"std396", "std400", "pattern-engineering-dry"}


def test_load_its_documents_raises_for_missing_root(tmp_path: Path):
    missing = tmp_path / "no-such-dir"
    with pytest.raises(ITSLoaderError, match="не найден"):
        list(load_its_documents(missing))


def test_load_its_documents_raises_for_non_dir(tmp_path: Path):
    f = tmp_path / "file.md"
    f.write_text("content", encoding="utf-8")
    with pytest.raises(ITSLoaderError, match="не каталог"):
        list(load_its_documents(f))


def test_load_its_documents_returns_dataclass_instances(tmp_path: Path):
    root = tmp_path / "docs"
    (root / "metod8dev").mkdir(parents=True)
    (root / "metod8dev" / "1590.md").write_text(
        "###### #metod1590\n\n# Метод 1590\n\nbody",
        encoding="utf-8",
    )

    docs = list(load_its_documents(root))
    assert len(docs) == 1
    assert isinstance(docs[0], ITSDocument)
    assert docs[0].category == "metod8dev"


# ---------- Migration v14 ----------


@pytest.mark.asyncio
async def test_migration_v14_creates_its_chunks_table():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='its_chunks'"
        )
        row = await cursor.fetchone()
        assert row is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v14_object_path_unique():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await conn.execute(
            "INSERT INTO its_chunks "
            "(object_path, doc_id, chunk_index, title, content, category, source_path, char_count, chunk_hash) "
            "VALUES ('its:std396#0', 'std396', 0, 'T', 'C', 'std', 'std/396.md', 1, 'h')"
        )
        await conn.commit()

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO its_chunks "
                "(object_path, doc_id, chunk_index, title, content, category, source_path, char_count, chunk_hash) "
                "VALUES ('its:std396#0', 'std396', 0, 'T', 'C', 'std', 'std/396.md', 1, 'h')"
            )
            await conn.commit()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v14_doc_index_unique():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await conn.execute(
            "INSERT INTO its_chunks "
            "(object_path, doc_id, chunk_index, title, content, category, source_path, char_count, chunk_hash) "
            "VALUES ('its:std396#0', 'std396', 0, 'T', 'C', 'std', 'std/396.md', 1, 'h')"
        )
        await conn.commit()

        # Тот же doc_id + chunk_index, другой object_path — должно упасть
        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO its_chunks "
                "(object_path, doc_id, chunk_index, title, content, category, source_path, char_count, chunk_hash) "
                "VALUES ('its:std396#0-other', 'std396', 0, 'T', 'C', 'std', 'std/396.md', 1, 'h')"
            )
            await conn.commit()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v14_indexes_created():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name IN ('idx_its_chunks_category', 'idx_its_chunks_doc')"
        )
        rows = await cursor.fetchall()
        names = {r[0] for r in rows}
        assert names == {"idx_its_chunks_category", "idx_its_chunks_doc"}
    finally:
        await conn.close()
