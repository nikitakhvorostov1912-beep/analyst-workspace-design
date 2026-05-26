"""Тесты для backend/app/knowledge/bsp_loader.py (M-K2.8).

Покрытие:
- _extract_public_regions: с / без #Область
- _collect_doc_comment: один блок, multi-line, пустая строка как граница
- _collect_signature: одна строка, многострочная
- _find_method_end: КонецФункции / КонецПроцедуры / EOF
- _is_export_method: только Экспорт
- parse_module_methods: integration с разными вариантами
- load_bsp_modules: walks directory
- BSPMethod.object_path / content / content_hash
- Migration v15: bsp_chunks + UNIQUE
"""

from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from app.knowledge.bsp_loader import (
    MAX_CONTENT_CHARS,
    BSPLoaderError,
    BSPMethod,
    _collect_doc_comment,
    _collect_signature,
    _detect_version_from_root,
    _extract_public_regions,
    _find_method_end,
    _is_export_method,
    load_bsp_modules,
    parse_module_methods,
)
from app.storage.migrations import apply_migrations


def _ext_module(root: Path, module_name: str, content: str) -> Path:
    """Создаёт ssl_root/src/cf/CommonModules/<module_name>/Ext/Module.bsl."""
    target = root / "src" / "cf" / "CommonModules" / module_name / "Ext" / "Module.bsl"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


# ---------- _extract_public_regions ----------


def test_extract_no_region_returns_whole_text():
    text = "Просто текст без областей"
    regions = _extract_public_regions(text)
    assert regions == [(0, len(text))]


def test_extract_public_region_only():
    text = (
        "#Область ПрограммныйИнтерфейс\n"
        "// public method\n"
        "#КонецОбласти\n"
        "#Область СлужебныйПрограммныйИнтерфейс\n"
        "// internal\n"
        "#КонецОбласти\n"
    )
    regions = _extract_public_regions(text)
    assert len(regions) == 1
    public_text = text[regions[0][0]:regions[0][1]]
    assert "public method" in public_text
    assert "internal" not in public_text


def test_extract_returns_empty_when_no_public_region():
    """Если есть #Область но не ПрограммныйИнтерфейс — module без public API."""
    text = (
        "#Область СлужебныеПроцедурыИФункции\n"
        "// internal\n"
        "#КонецОбласти\n"
    )
    regions = _extract_public_regions(text)
    assert regions == []


# ---------- _collect_doc_comment ----------


def test_collect_doc_simple():
    text = (
        "// Описание метода.\n"
        "// Параметры:\n"
        "//   X - Число\n"
        "Функция МойМетод(X) Экспорт"
    )
    sig_start = text.index("Функция")
    doc = _collect_doc_comment(text, sig_start)
    assert "Описание метода." in doc
    assert "Параметры:" in doc
    assert "X - Число" in doc


def test_collect_doc_with_trailing_blank_before_sig():
    text = (
        "// Doc line\n"
        "\n"
        "Функция МойМетод() Экспорт"
    )
    sig_start = text.index("Функция")
    doc = _collect_doc_comment(text, sig_start)
    assert "Doc line" in doc


def test_collect_doc_stops_at_non_comment_line():
    text = (
        "Какой-то код выше\n"
        "// Doc для метода\n"
        "Функция МойМетод() Экспорт"
    )
    sig_start = text.index("Функция")
    doc = _collect_doc_comment(text, sig_start)
    assert "Doc для метода" in doc
    assert "Какой-то код выше" not in doc


def test_collect_doc_empty_when_no_comment():
    text = "Функция МойМетод() Экспорт"
    doc = _collect_doc_comment(text, 0)
    assert doc == ""


# ---------- _collect_signature ----------


def test_collect_signature_one_line():
    text = "Функция X(A, B) Экспорт\n  // body\nКонецФункции"
    sig, end = _collect_signature(text, 0)
    assert sig == "Функция X(A, B) Экспорт"
    assert end > 0


def test_collect_signature_multiline():
    text = (
        "Функция X(\n"
        "    A,\n"
        "    B,\n"
        "    C\n"
        ") Экспорт\n"
        "  // body"
    )
    sig, end = _collect_signature(text, 0)
    assert "Функция X" in sig
    assert "Экспорт" in sig
    assert end > 0


def test_collect_signature_no_export_returns_empty():
    text = "Функция Внутренний(A) \n  // body\nКонецФункции"
    sig, end = _collect_signature(text, 0)
    assert sig == ""
    assert end == 0


# ---------- _find_method_end ----------


def test_find_method_end_function():
    text = "Функция X() Экспорт\n  // body\nКонецФункции\nДругойКод"
    end = _find_method_end(text, 0, "Функция")
    assert end > 0
    assert "ДругойКод" not in text[:end]


def test_find_method_end_procedure():
    text = "Процедура X() Экспорт\nКонецПроцедуры\nХвост"
    end = _find_method_end(text, 0, "Процедура")
    assert "Хвост" not in text[:end]


def test_find_method_end_falls_back_to_eof():
    text = "Функция X() Экспорт\nКонец не написан"
    end = _find_method_end(text, 0, "Функция")
    assert end == len(text)


# ---------- _is_export_method ----------


def test_is_export_true():
    text = "Функция МойМетод(A, B) Экспорт"
    assert _is_export_method(text, 0)


def test_is_export_false():
    text = "Функция Приватный(A, B)\n  // body\nКонецФункции"
    assert not _is_export_method(text, 0)


# ---------- parse_module_methods ----------


def test_parse_simple_module():
    text = (
        "#Область ПрограммныйИнтерфейс\n"
        "\n"
        "// Делает что-то полезное\n"
        "Функция ВыполнитьЧтото(Параметр) Экспорт\n"
        "    Возврат Параметр;\n"
        "КонецФункции\n"
        "\n"
        "#КонецОбласти\n"
    )
    methods = list(parse_module_methods(
        "ДемоМодуль", text, "3.2", "src/cf/CommonModules/ДемоМодуль/Ext/Module.bsl"
    ))
    assert len(methods) == 1
    m = methods[0]
    assert m.module_name == "ДемоМодуль"
    assert m.method_name == "ВыполнитьЧтото"
    assert m.method_kind == "Функция"
    assert "Делает что-то полезное" in m.doc_comment
    assert "Экспорт" in m.signature
    assert m.version == "3.2"


def test_parse_skips_non_export_in_public_region():
    text = (
        "#Область ПрограммныйИнтерфейс\n"
        "Функция Приватный() \n"
        "КонецФункции\n"
        "Процедура ПубличныйЯвно() Экспорт\n"
        "КонецПроцедуры\n"
        "#КонецОбласти\n"
    )
    methods = list(parse_module_methods(
        "X", text, "3.2", "x.bsl"
    ))
    names = {m.method_name for m in methods}
    assert names == {"ПубличныйЯвно"}


def test_parse_skips_methods_outside_public_region():
    text = (
        "#Область СлужебныеПроцедурыИФункции\n"
        "Функция Внутренний() Экспорт\n"
        "КонецФункции\n"
        "#КонецОбласти\n"
    )
    methods = list(parse_module_methods("X", text, "3.2", "x.bsl"))
    assert methods == []


def test_parse_empty_text():
    assert list(parse_module_methods("X", "", "3.2", "x.bsl")) == []
    assert list(parse_module_methods("X", "   \n  ", "3.2", "x.bsl")) == []


def test_parse_module_without_regions_still_works():
    """Если #Область отсутствует — берём всё."""
    text = (
        "// Простой метод\n"
        "Процедура ОдинокийМетод() Экспорт\n"
        "КонецПроцедуры\n"
    )
    methods = list(parse_module_methods("X", text, "3.2", "x.bsl"))
    assert len(methods) == 1
    assert methods[0].method_name == "ОдинокийМетод"


def test_parse_multiple_methods_in_region():
    text = (
        "#Область ПрограммныйИнтерфейс\n"
        "// Метод 1\n"
        "Функция М1() Экспорт\n"
        "КонецФункции\n"
        "\n"
        "// Метод 2\n"
        "Процедура М2(А, Б) Экспорт\n"
        "КонецПроцедуры\n"
        "#КонецОбласти\n"
    )
    methods = list(parse_module_methods("X", text, "3.2", "x.bsl"))
    assert len(methods) == 2
    assert [m.method_name for m in methods] == ["М1", "М2"]


def test_parse_caps_oversize_body():
    huge_body = "Сообщить(\"X\");\n" * 500  # ~ 8K chars
    text = (
        "#Область ПрограммныйИнтерфейс\n"
        "// Доc\n"
        "Процедура Большая() Экспорт\n"
        f"{huge_body}\n"
        "КонецПроцедуры\n"
        "#КонецОбласти\n"
    )
    methods = list(parse_module_methods("X", text, "3.2", "x.bsl"))
    assert len(methods) == 1
    assert len(methods[0].content) <= MAX_CONTENT_CHARS


# ---------- BSPMethod properties ----------


def test_bsp_method_object_path():
    m = BSPMethod(
        module_name="ДлительныеОперации", method_name="ВыполнитьФункцию",
        method_kind="Функция",
        signature="Функция ВыполнитьФункцию() Экспорт",
        doc_comment="Doc", body_excerpt="body",
        version="3.2",
        source_path="src/cf/CommonModules/ДлительныеОперации/Ext/Module.bsl",
    )
    assert m.object_path == "bsp:3.2:ДлительныеОперации.ВыполнитьФункцию"


def test_bsp_method_content_includes_all_parts():
    m = BSPMethod(
        module_name="X", method_name="Y", method_kind="Функция",
        signature="Функция Y() Экспорт", doc_comment="doc 1\ndoc 2",
        body_excerpt="тело", version="3.2", source_path="x",
    )
    content = m.content
    assert "doc 1" in content
    assert "Функция Y()" in content
    assert "тело" in content


def test_bsp_method_hash_stable():
    m = BSPMethod(
        module_name="X", method_name="Y", method_kind="Функция",
        signature="Функция Y() Экспорт", doc_comment="doc",
        body_excerpt="body", version="3.2", source_path="x",
    )
    h1 = m.content_hash
    h2 = m.content_hash
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


# ---------- load_bsp_modules (FS integration) ----------


def test_load_walks_common_modules(tmp_path: Path):
    root = tmp_path / "ssl_3_2"
    _ext_module(root, "Модуль1",
        "#Область ПрограммныйИнтерфейс\n"
        "// Doc1\n"
        "Функция М1() Экспорт\nКонецФункции\n"
        "#КонецОбласти\n"
    )
    _ext_module(root, "Модуль2",
        "#Область ПрограммныйИнтерфейс\n"
        "// Doc2\n"
        "Процедура М2() Экспорт\nКонецПроцедуры\n"
        "#КонецОбласти\n"
    )

    methods = list(load_bsp_modules(root))
    by_module = {m.module_name for m in methods}
    assert by_module == {"Модуль1", "Модуль2"}


def test_load_raises_missing_root(tmp_path: Path):
    missing = tmp_path / "no-such"
    with pytest.raises(BSPLoaderError, match="не найден"):
        list(load_bsp_modules(missing))


def test_load_raises_when_no_common_modules(tmp_path: Path):
    root = tmp_path / "ssl_3_2"
    root.mkdir()
    with pytest.raises(BSPLoaderError, match="CommonModules"):
        list(load_bsp_modules(root))


def test_load_skips_module_without_bsl(tmp_path: Path):
    root = tmp_path / "ssl_3_2"
    # Создаём модуль БЕЗ Ext/Module.bsl
    (root / "src" / "cf" / "CommonModules" / "Пустой").mkdir(parents=True)
    _ext_module(root, "Полный",
        "#Область ПрограммныйИнтерфейс\n"
        "Функция М() Экспорт\nКонецФункции\n"
        "#КонецОбласти\n"
    )
    methods = list(load_bsp_modules(root))
    assert {m.module_name for m in methods} == {"Полный"}


def test_detect_version_from_root():
    assert _detect_version_from_root(Path("ssl_3_1")) == "3.1"
    assert _detect_version_from_root(Path("ssl_3_2")) == "3.2"
    assert _detect_version_from_root(Path("ssl_3.1")) == "3.1"
    assert _detect_version_from_root(Path("any-other")) == "3.2"  # default


# ---------- Migration v15 ----------


@pytest.mark.asyncio
async def test_migration_v15_creates_bsp_chunks_table():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='bsp_chunks'"
        )
        assert await cursor.fetchone() is not None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v15_object_path_unique():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await conn.execute(
            "INSERT INTO bsp_chunks (object_path, module_name, method_name, "
            "method_kind, signature, doc_comment, content, version, source_path, "
            "char_count, chunk_hash) VALUES "
            "('bsp:3.2:M.X', 'M', 'X', 'Функция', 'sig', 'doc', 'c', '3.2', 's', 1, 'h')"
        )
        await conn.commit()

        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO bsp_chunks (object_path, module_name, method_name, "
                "method_kind, signature, doc_comment, content, version, source_path, "
                "char_count, chunk_hash) VALUES "
                "('bsp:3.2:M.X', 'M', 'X', 'Функция', 'sig', 'doc', 'c', '3.2', 's', 1, 'h')"
            )
            await conn.commit()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v15_module_method_version_unique():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await conn.execute(
            "INSERT INTO bsp_chunks (object_path, module_name, method_name, "
            "method_kind, signature, doc_comment, content, version, source_path, "
            "char_count, chunk_hash) VALUES "
            "('bsp:3.2:M.X', 'M', 'X', 'Функция', 'sig', 'doc', 'c', '3.2', 's', 1, 'h')"
        )
        await conn.commit()

        # Тот же module+method+version, другой object_path — должно упасть
        with pytest.raises(aiosqlite.IntegrityError):
            await conn.execute(
                "INSERT INTO bsp_chunks (object_path, module_name, method_name, "
                "method_kind, signature, doc_comment, content, version, source_path, "
                "char_count, chunk_hash) VALUES "
                "('bsp:3.2:M.X-other', 'M', 'X', 'Функция', 'sig', 'doc', 'c', '3.2', 's', 1, 'h')"
            )
            await conn.commit()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_migration_v15_indexes_created():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name IN ('idx_bsp_chunks_module', 'idx_bsp_chunks_method', 'idx_bsp_chunks_version')"
        )
        rows = await cursor.fetchall()
        names = {r[0] for r in rows}
        assert names == {"idx_bsp_chunks_module", "idx_bsp_chunks_method", "idx_bsp_chunks_version"}
    finally:
        await conn.close()
