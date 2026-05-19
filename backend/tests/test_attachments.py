"""Тесты извлечения текста из прикреплённых документов."""

import base64
import io

import pytest


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def test_extract_unsupported_mime():
    from app.orchestrator.attachments import extract_attachment

    r = extract_attachment("a.bin", "application/octet-stream", _b64(b"x"))
    assert r.error is not None
    assert "не поддерживается" in r.error
    assert r.text == ""


def test_extract_text_plain_utf8():
    from app.orchestrator.attachments import extract_attachment

    content = "Тестовый русский текст\nВторая строка"
    r = extract_attachment("note.txt", "text/plain", _b64(content.encode("utf-8")))
    assert r.error is None
    assert "Тестовый русский текст" in r.text
    assert "Вторая строка" in r.text


def test_extract_text_cp1251_fallback():
    """Если UTF-8 не парсится, пробуем cp1251."""
    from app.orchestrator.attachments import extract_attachment

    content = "Русский cp1251"
    r = extract_attachment("note.txt", "text/plain", _b64(content.encode("cp1251")))
    assert r.error is None
    assert "Русский" in r.text


def test_extract_csv():
    from app.orchestrator.attachments import extract_attachment

    csv = "a,b,c\n1,2,3\n4,5,6"
    r = extract_attachment("data.csv", "text/csv", _b64(csv.encode("utf-8")))
    assert r.error is None
    assert "a,b,c" in r.text
    assert "1,2,3" in r.text


def test_extract_xlsx_simple():
    from openpyxl import Workbook

    from app.orchestrator.attachments import extract_attachment

    wb = Workbook()
    ws = wb.active
    ws.title = "Контрагенты"
    ws.append(["ИНН", "Наименование", "КПП"])
    ws.append(["7707083893", "Сбербанк", "770701001"])
    ws.append(["7728168971", "Газпром", "997250001"])
    buf = io.BytesIO()
    wb.save(buf)
    raw = buf.getvalue()

    r = extract_attachment(
        "контрагенты.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        _b64(raw),
    )
    assert r.error is None
    assert "Контрагенты" in r.text
    assert "Сбербанк" in r.text
    assert "7707083893" in r.text


def test_extract_docx_paragraphs():
    from docx import Document

    from app.orchestrator.attachments import extract_attachment

    doc = Document()
    doc.add_heading("Отчёт по контрагенту", level=1)
    doc.add_paragraph("Дата: 19.05.2026")
    doc.add_paragraph("Контрагент: ООО Ромашка")
    buf = io.BytesIO()
    doc.save(buf)

    r = extract_attachment(
        "report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _b64(buf.getvalue()),
    )
    assert r.error is None
    assert "Отчёт по контрагенту" in r.text
    assert "ООО Ромашка" in r.text


def test_extract_size_limit():
    from app.orchestrator.attachments import MAX_RAW_BYTES, extract_attachment

    big = b"x" * (MAX_RAW_BYTES + 1)
    r = extract_attachment("huge.txt", "text/plain", _b64(big))
    assert r.error is not None
    assert "слишком большой" in r.error


def test_extract_text_truncation():
    from app.orchestrator.attachments import MAX_TEXT_PER_FILE, extract_attachment

    content = "x" * (MAX_TEXT_PER_FILE + 100)
    r = extract_attachment("big.txt", "text/plain", _b64(content.encode("utf-8")))
    assert r.error is None
    assert r.truncated is True
    assert "обрезано" in r.text
    assert len(r.text) <= MAX_TEXT_PER_FILE + 50


def test_extract_invalid_base64():
    from app.orchestrator.attachments import extract_attachment

    # base64.b64decode validate=False допускает много, но пустые строки невалидны
    r = extract_attachment("a.txt", "text/plain", "!!! не base64 !!!")
    # либо вернёт error, либо мусорный текст — главное не падать
    assert r.error is not None or isinstance(r.text, str)


def test_extract_by_extension_when_mime_unknown():
    """Если mime пустой/неизвестен — определяем по расширению файла."""
    from app.orchestrator.attachments import extract_attachment

    csv = "a,b\n1,2"
    # mime пустой — но расширение .csv → должно сработать
    r = extract_attachment("data.csv", "", _b64(csv.encode("utf-8")))
    assert r.error is None
    assert "1,2" in r.text


def test_format_attachments_for_llm():
    from app.orchestrator.attachments import (
        ExtractedAttachment,
        format_attachments_for_llm,
    )

    atts = [
        ExtractedAttachment("a.txt", "text/plain", "Hello world", False),
        ExtractedAttachment("b.pdf", "application/pdf", "", False, error="не PDF"),
    ]
    result = format_attachments_for_llm(atts)
    assert "Прикреплён файл: a.txt" in result
    assert "Hello world" in result
    assert "Прикреплён файл: b.pdf" in result
    assert "не PDF" in result


def test_format_attachments_empty():
    from app.orchestrator.attachments import format_attachments_for_llm

    assert format_attachments_for_llm([]) == ""
