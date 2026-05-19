"""Извлечение текста из прикреплённых документов.

Поддерживается: PDF, DOCX, XLSX, plain text, CSV. Изображения пока не
обрабатываются (Phase 2 — multimodal через mimo-v2-omni).

Используется в orchestrator.run_chat_loop перед склейкой messages для LLM:
content прикреплённых файлов конкатенируется к user message с разделителем.

Cap: 50_000 символов на файл (DoS guard). Cap: 5 файлов на сообщение.
"""

import base64
import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Лимиты — защита от DoS / context overflow.
MAX_TEXT_PER_FILE = 50_000  # символов
MAX_ATTACHMENTS_PER_MESSAGE = 5
MAX_RAW_BYTES = 25 * 1024 * 1024  # 25 MB на файл (декодированных)


@dataclass
class ExtractedAttachment:
    """Результат обработки одного прикреплённого файла.

    Для текстовых документов — извлечённый текст в `text`.
    Для изображений (PNG/JPG/WebP) — `is_image=True`, `image_data_url` содержит
    data:URI для прямой подачи в multimodal LLM (mimo-v2-omni). `text` —
    placeholder для сохранения в БД (что-то вроде "[Картинка: name.png]").
    """

    name: str
    mime: str
    text: str
    truncated: bool
    error: str | None = None  # если не удалось извлечь
    is_image: bool = False
    image_data_url: str | None = None


# Image MIME types — обрабатываем без text extraction, отдаём в LLM как
# multimodal image_url. Требуется vision-модель (mimo-v2-omni / GPT-4V).
_IMAGE_MIMES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def is_image_mime(mime: str) -> bool:
    return (mime or "").lower() in _IMAGE_MIMES


def _cap(text: str) -> tuple[str, bool]:
    """Обрезает текст до MAX_TEXT_PER_FILE."""
    if len(text) <= MAX_TEXT_PER_FILE:
        return text, False
    return text[:MAX_TEXT_PER_FILE] + "\n…(обрезано)", True


def _extract_pdf(data: bytes) -> str:
    """Извлекает текст из PDF. Возвращает '' при ошибке (caller логирует)."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            pages.append(f"--- Страница {i + 1} ---\n{text}")
    return "\n\n".join(pages)


def _extract_docx(data: bytes) -> str:
    from docx import Document

    doc = Document(io.BytesIO(data))
    parts: list[str] = []
    # Параграфы
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    # Таблицы — простой текстовый рендер
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _extract_xlsx(data: bytes) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    parts: list[str] = []
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        parts.append(f"--- Лист «{sheet_name}» ---")
        rows_emitted = 0
        for row in sheet.iter_rows(values_only=True):
            cells = ["" if v is None else str(v) for v in row]
            if any(c.strip() for c in cells):
                parts.append("\t".join(cells))
                rows_emitted += 1
            # Cap per sheet to keep context manageable
            if rows_emitted >= 1000:
                parts.append("…(остальные строки листа обрезаны)")
                break
    wb.close()
    return "\n".join(parts)


def _extract_text(data: bytes) -> str:
    """Plain text / CSV — пытаемся UTF-8, потом cp1251."""
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# Mapping mime → extractor.
_EXTRACTORS = {
    "application/pdf": _extract_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _extract_docx,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": _extract_xlsx,
    "application/msword": _extract_docx,  # старый DOC иногда отдаёт это, попытка
    "text/plain": _extract_text,
    "text/csv": _extract_text,
    "application/json": _extract_text,
    "application/xml": _extract_text,
    "text/xml": _extract_text,
    "text/markdown": _extract_text,
}


def extract_attachment(
    name: str,
    mime: str,
    content_base64: str,
) -> ExtractedAttachment:
    """Декодирует base64, извлекает текст по mime-типу.

    Безопасно к ошибкам: при сбое возвращает Attachment с error и пустым text.
    Caller решает — включать в payload LLM или нет.
    """
    try:
        data = base64.b64decode(content_base64, validate=False)
    except Exception as e:
        return ExtractedAttachment(
            name=name, mime=mime, text="", truncated=False,
            error=f"не удалось декодировать base64: {e}"
        )

    if len(data) > MAX_RAW_BYTES:
        return ExtractedAttachment(
            name=name, mime=mime, text="", truncated=False,
            error=f"файл слишком большой ({len(data) // 1024 // 1024} MB), лимит 25 MB"
        )

    # Fuzzy mime detection по расширению — если MIME не известен
    mime_lower = (mime or "").lower()
    if mime_lower not in _EXTRACTORS and not is_image_mime(mime_lower):
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        ext_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "txt": "text/plain",
            "csv": "text/csv",
            "json": "application/json",
            "xml": "application/xml",
            "md": "text/markdown",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "gif": "image/gif",
        }
        if ext in ext_map:
            mime_lower = ext_map[ext]

    # Изображения — НЕ извлекаем текст, формируем data:URI для multimodal LLM.
    if is_image_mime(mime_lower):
        ext = _IMAGE_MIMES[mime_lower]
        size_kb = len(data) // 1024
        return ExtractedAttachment(
            name=name,
            mime=mime_lower,
            text=f"[Картинка: {name}, {size_kb} КБ]",
            truncated=False,
            is_image=True,
            image_data_url=f"data:{mime_lower};base64,{content_base64}",
        )

    extractor = _EXTRACTORS.get(mime_lower)
    if extractor is None:
        return ExtractedAttachment(
            name=name, mime=mime, text="", truncated=False,
            error=(
                f"тип «{mime}» не поддерживается. "
                "Поддерживаются: PDF, DOCX, XLSX, TXT, CSV, JSON, XML, MD."
            ),
        )

    try:
        raw_text = extractor(data)
    except Exception as e:
        logger.warning("Не удалось извлечь текст из %s (%s): %s", name, mime, e)
        return ExtractedAttachment(
            name=name, mime=mime, text="", truncated=False,
            error=f"ошибка чтения: {e}"
        )

    text, truncated = _cap(raw_text)
    return ExtractedAttachment(
        name=name, mime=mime, text=text, truncated=truncated
    )


def format_attachments_for_llm(attachments: list[ExtractedAttachment]) -> str:
    """Форматирует прикреплённые ТЕКСТОВЫЕ файлы для добавления к user message.

    Картинки (is_image=True) формируются отдельно в build_user_content() как
    multimodal image_url. Здесь — только text-блоки.
    """
    if not attachments:
        return ""
    blocks: list[str] = []
    for att in attachments:
        if att.is_image:
            # Картинки идут в multimodal content, тут просто placeholder.
            blocks.append(f"=== Прикреплена картинка: {att.name} (см. ниже) ===")
            continue
        if att.error:
            blocks.append(
                f"=== Прикреплён файл: {att.name} ({att.mime or '?'}) ===\n"
                f"Не удалось прочитать: {att.error}"
            )
            continue
        truncated_note = " [обрезано]" if att.truncated else ""
        blocks.append(
            f"=== Прикреплён файл: {att.name} ({att.mime or '?'}){truncated_note} ===\n"
            f"{att.text}"
        )
    return "\n\n".join(blocks)


def build_user_message_content(
    text: str,
    attachments: list[ExtractedAttachment],
) -> tuple[str | list[dict], bool]:
    """Строит content для user message в OpenAI chat-completions формате.

    Returns:
        (content, has_image):
        - has_image=False → content — обычная строка (text + блоки текстовых файлов)
        - has_image=True  → content — list[{type, text}|{type:image_url}], multimodal
        Caller использует has_image для выбора модели (vision vs text-only).
    """
    image_atts = [a for a in attachments if a.is_image and a.image_data_url]
    text_block = format_attachments_for_llm(attachments)
    full_text = text + ("\n\n" + text_block if text_block else "")
    full_text = full_text.strip()

    if not image_atts:
        return full_text, False

    parts: list[dict] = []
    if full_text:
        parts.append({"type": "text", "text": full_text})
    for img in image_atts:
        parts.append({
            "type": "image_url",
            "image_url": {"url": img.image_data_url},
        })
    return parts, True


def make_history_user_text(
    text: str,
    attachments: list[ExtractedAttachment],
) -> str:
    """Возвращает текст для сохранения в БД (history-friendly).

    Для картинок — placeholder с именем + размером (base64 в БД не лежит).
    Текстовое содержимое — полное (как в LLM).
    """
    block = format_attachments_for_llm(attachments)
    return (text + "\n\n" + block).strip() if block else text
