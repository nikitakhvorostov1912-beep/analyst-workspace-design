"""Тесты phantom-method detector (M-K4 ИТС-KB, D1 анти-галлюцинация).

Покрытие:
- extract_bsl_calls: парсинг `Модуль.Метод(`, кириллица, dedup, нет вызовов
- check_phantom_methods: реальный метод OK, выдуманный → phantom,
  неизвестный модуль не флагается, пустой корпус → пусто, version_filter
"""

from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.phantom_check import (
    PhantomReport,
    check_phantom_methods,
    extract_bsl_calls,
)
from app.storage.migrations import apply_migrations


async def _seed_bsp(conn: aiosqlite.Connection) -> None:
    """Кладёт в корпус 2 реальных метода ОбщегоНазначения (3.2)."""
    rows = [
        ("bsp:3.2:ОбщегоНазначения.ЗначениеРеквизитаОбъекта", "ОбщегоНазначения",
         "ЗначениеРеквизитаОбъекта", "Функция",
         "Функция ЗначениеРеквизитаОбъекта(Ссылка, ИмяРеквизита, Тип)", "doc", "c", "3.2"),
        ("bsp:3.2:ОбщегоНазначения.ЗначенияРеквизитовОбъекта", "ОбщегоНазначения",
         "ЗначенияРеквизитовОбъекта", "Функция",
         "Функция ЗначенияРеквизитовОбъекта(Ссылка, Реквизиты)", "doc", "c", "3.2"),
    ]
    for object_path, mod, meth, kind, sig, doc, content, ver in rows:
        await conn.execute(
            "INSERT INTO bsp_chunks(object_path,module_name,method_name,method_kind,signature,"
            "doc_comment,content,version,source_path,char_count,chunk_hash) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (object_path, mod, meth, kind, sig, doc, content, ver, "x", 10, object_path[-8:]),
        )
    await conn.commit()


# ---------- extract_bsl_calls ----------


def test_extract_parses_cyrillic_call():
    calls = extract_bsl_calls("Вызов ОбщегоНазначения.ЗначениеРеквизитаОбъекта(Ссылка, Имя) тут")
    assert ("ОбщегоНазначения", "ЗначениеРеквизитаОбъекта") in calls


def test_extract_dedup_and_multiple():
    text = (
        "ДлительныеОперации.ВыполнитьФункцию(x); снова "
        "ДлительныеОперации.ВыполнитьФункцию(y); ОбщегоНазначения.МойМетод()"
    )
    calls = extract_bsl_calls(text)
    assert calls == [
        ("ДлительныеОперации", "ВыполнитьФункцию"),
        ("ОбщегоНазначения", "МойМетод"),
    ]


def test_extract_no_calls():
    assert extract_bsl_calls("просто текст без вызовов") == []
    assert extract_bsl_calls("") == []


def test_extract_ignores_leading_digit():
    # 1Сметод.Метод( не должен парситься как идентификатор (начинается с цифры)
    assert extract_bsl_calls("3.14(x)") == []


# ---------- check_phantom_methods ----------


@pytest.mark.asyncio
async def test_real_method_not_flagged():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed_bsp(conn)
        report = await check_phantom_methods(
            conn, "Используй ОбщегоНазначения.ЗначениеРеквизитаОбъекта(Ссылка, \"ИНН\", Тип)"
        )
        assert isinstance(report, PhantomReport)
        assert report.checked == ("ОбщегоНазначения.ЗначениеРеквизитаОбъекта",)
        assert report.phantom == ()
        assert report.has_phantom is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_phantom_method_flagged():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed_bsp(conn)
        # Модуль известен (ОбщегоНазначения), а метода ПолучитьЗначениеРеквизита нет
        report = await check_phantom_methods(
            conn, "Вызови ОбщегоНазначения.ПолучитьЗначениеРеквизита(Ссылка)"
        )
        assert report.has_phantom is True
        assert report.phantom == ("ОбщегоНазначения.ПолучитьЗначениеРеквизита",)
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_unknown_module_not_flagged():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed_bsp(conn)
        # НашМодуль нет в корпусе → кастомная конфигурация, не флагаем
        report = await check_phantom_methods(conn, "НашМодуль.КакойТоМетод(Параметр)")
        assert report.checked == ()
        assert report.phantom == ()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_empty_corpus_no_false_positive():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)  # bsp_chunks пуст
        report = await check_phantom_methods(
            conn, "ОбщегоНазначения.ЛюбойМетод(x)"
        )
        assert report.checked == ()
        assert report.phantom == ()
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_version_filter():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed_bsp(conn)  # только 3.2
        # При фильтре 3.1 модулей нет → ничего не проверяется
        report = await check_phantom_methods(
            conn, "ОбщегоНазначения.ЗначениеРеквизитаОбъекта(x)", version_filter="3.1"
        )
        assert report.checked == ()
    finally:
        await conn.close()
