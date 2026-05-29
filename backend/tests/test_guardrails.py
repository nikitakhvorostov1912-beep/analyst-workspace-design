"""Тесты response guardrails (M-K4 G2/G3)."""

from __future__ import annotations

import aiosqlite
import pytest

from app.knowledge.guardrails import GuardrailReport, evaluate_response
from app.storage.migrations import apply_migrations


async def _seed(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        "INSERT INTO bsp_chunks(object_path,module_name,method_name,method_kind,signature,"
        "doc_comment,content,version,source_path,char_count,chunk_hash) "
        "VALUES('bsp:3.2:ОбщегоНазначения.ЗначениеРеквизитаОбъекта','ОбщегоНазначения',"
        "'ЗначениеРеквизитаОбъекта','Функция','Функция ЗначениеРеквизитаОбъекта(Ссылка)',"
        "'doc','c','3.2','x',10,'h')"
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_real_method_with_retrieval_no_warning():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed(conn)
        report = await evaluate_response(
            conn,
            answer="Используйте ОбщегоНазначения.ЗначениеРеквизитаОбъекта(Ссылка, \"ИНН\").",
            retrieved_count=3,
        )
        assert isinstance(report, GuardrailReport)
        assert report.has_warning is False
        assert report.phantom_methods == ()
        assert report.unsupported_claim is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_phantom_method_flagged():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed(conn)
        report = await evaluate_response(
            conn,
            answer="Вызови ОбщегоНазначения.ПолучитьРеквизитМагия(Ссылка).",
            retrieved_count=2,
        )
        assert report.has_warning is True
        assert report.phantom_methods == ("ОбщегоНазначения.ПолучитьРеквизитМагия",)
        assert report.unsupported_claim is False
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_unsupported_claim_when_retrieval_empty():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed(conn)
        # retrieval пуст, но ответ уверенно ссылается на метод
        report = await evaluate_response(
            conn,
            answer="Просто вызови ОбщегоНазначения.ЗначениеРеквизитаОбъекта(Ссылка).",
            retrieved_count=0,
        )
        assert report.unsupported_claim is True
        assert report.has_warning is True
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_no_calls_no_warning_even_empty_retrieval():
    conn = await aiosqlite.connect(":memory:")
    try:
        await apply_migrations(conn)
        await _seed(conn)
        report = await evaluate_response(
            conn,
            answer="Информация по этому вопросу в базе знаний не найдена.",
            retrieved_count=0,
        )
        assert report.has_warning is False
        assert report.unsupported_claim is False
    finally:
        await conn.close()


def test_report_to_dict():
    report = GuardrailReport(phantom_methods=("М.Ф",), unsupported_claim=True)
    assert report.to_dict() == {"phantom_methods": ["М.Ф"], "unsupported_claim": True}
