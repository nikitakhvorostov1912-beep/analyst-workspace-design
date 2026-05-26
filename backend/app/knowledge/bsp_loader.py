"""BSP Loader — парсит экспортные методы CommonModules БСП (M-K2.8).

Knowledge Foundation Phase 8: загружает корпус Библиотеки Стандартных
Подсистем (БСП) — экспортные API общих модулей, для RAG-поиска LLM
по типу «методы БСП для длительных операций».

**Источник:**
- `tools/ssl_3_1/src/cf/CommonModules/*/Ext/Module.bsl` — БСП 3.1
- `tools/ssl_3_2/src/cf/CommonModules/*/Ext/Module.bsl` — БСП 3.2

Лицензия исходников БСП: CC-BY-4.0 (zeegin/ssl_3_* зеркала).

**Что индексируем:**
- Только Экспорт-методы внутри `#Область ПрограммныйИнтерфейс` (public API).
  Служебные интерфейсы и приватные методы пропускаем — они не для пользователя.
- Каждый метод → отдельный chunk (doc-комментарий + сигнатура + начало body).

**Парсер:**
- Регулярки + state machine (не AST). BSL грамматику ради этой задачи разбирать
  избыточно. Распознаём:
  - область `#Область ПрограммныйИнтерфейс` ... `#КонецОбласти`
  - doc-комментарий (consecutive `//` lines) перед сигнатурой
  - сигнатура `Процедура|Функция X(...) Экспорт`
  - тело до `КонецПроцедуры|КонецФункции`

**Что НЕ делает loader:**
- Не валидирует BSL синтаксис (если файл невалидный — пропускаем целиком).
- Не извлекает annotations `&НаСервере`, `&Перед` и т.п. (M-K3 если потребуется).
- Не парсит CommonForms / DataProcessors модули — только CommonModules.
"""

from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


BSPVersion = Literal["3.1", "3.2"]


# Регулярка для начала экспортного метода (на одной строке или с continuation).
# Например: "Функция ВыполнитьФункцию(Знач ПараметрыВыполнения, ИмяФункции, ...) Экспорт"
# Захватываем kind, name. Сигнатура (включая параметры) собирается отдельно.
_SIGNATURE_RE = re.compile(
    r"^\s*(Процедура|Функция)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)

# Регулярка для конца блока региона.
_REGION_START = re.compile(r"^\s*#Область\s+(\S+)", re.MULTILINE)
_REGION_END = re.compile(r"^\s*#КонецОбласти", re.MULTILINE)

# Конец метода
_METHOD_END = re.compile(r"^\s*(КонецПроцедуры|КонецФункции)\b", re.MULTILINE)

# Имя публичного интерфейса (что считаем public API).
_PUBLIC_REGION_NAMES = frozenset({"ПрограммныйИнтерфейс"})


@dataclass(frozen=True, slots=True)
class BSPMethod:
    """Один Экспорт-метод БСП готовый к store + embedding.

    Attrs:
        module_name: «ДлительныеОперации»
        method_name: «ВыполнитьФункцию»
        method_kind: «Процедура» | «Функция»
        signature: полная сигнатура одной строкой (после нормализации
                  whitespace), включая слово Экспорт
        doc_comment: многострочный текст doc-комментария (без `//`)
        body_excerpt: тело метода, обрезанное до MAX_BODY_CHARS (см. константу)
        version: «3.1» | «3.2»
        source_path: путь относительно корня репозитория ssl_3_*/
    """

    module_name: str
    method_name: str
    method_kind: str
    signature: str
    doc_comment: str
    body_excerpt: str
    version: BSPVersion
    source_path: str

    @property
    def object_path(self) -> str:
        """Стабильный путь для vec_objects: bsp:<ver>:<Mod>.<Method>."""
        return f"bsp:{self.version}:{self.module_name}.{self.method_name}"

    @property
    def content(self) -> str:
        """Текст для embedding: doc + signature + body_excerpt."""
        parts = []
        if self.doc_comment:
            parts.append(self.doc_comment)
        parts.append(self.signature)
        if self.body_excerpt:
            parts.append(self.body_excerpt)
        return "\n\n".join(parts)

    @property
    def content_hash(self) -> str:
        """SHA-256 hex от content для idempotent re-index."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class BSPLoaderError(Exception):
    """Ошибка loader — невалидный root, нечитаемый файл."""


# Максимум символов body — для длинных методов оставляем только начало
# (signature + первые ~2000 символов — достаточно для embed понимания цели).
MAX_BODY_CHARS = 2000

# Максимум общего размера chunk (для embedding окна 8K токенов).
MAX_CONTENT_CHARS = 4000


def _read_text(path: Path) -> str | None:
    """Безопасное чтение файла. Возвращает None при ошибке."""
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            logger.debug("BSP loader: read failed %s: %s", path, exc)
            return None
    logger.debug("BSP loader: encoding mismatch для %s", path)
    return None


def _extract_public_regions(text: str) -> list[tuple[int, int]]:
    """Возвращает [(start_offset, end_offset)] позиций ПрограммныйИнтерфейс регионов.

    Внутри одного модуля может быть только один ПрограммныйИнтерфейс
    (по соглашению БСП), но мы поддерживаем несколько на случай нестандарта.

    Если ни один регион не найден — возвращает [(0, len(text))], потому что
    некоторые мелкие модули не используют #Область совсем.
    """
    regions: list[tuple[int, int]] = []
    starts = list(_REGION_START.finditer(text))
    ends = list(_REGION_END.finditer(text))

    if not starts:
        return [(0, len(text))]

    # Простой алгоритм: для каждого start ищем ближайший след. end после него
    # (BSL #Область не вложенные на практике).
    used_end_indices: set[int] = set()
    for start_m in starts:
        region_name = start_m.group(1)
        if region_name not in _PUBLIC_REGION_NAMES:
            continue
        start_offset = start_m.end()
        end_offset = len(text)
        for i, end_m in enumerate(ends):
            if i in used_end_indices:
                continue
            if end_m.start() > start_m.start():
                end_offset = end_m.start()
                used_end_indices.add(i)
                break
        regions.append((start_offset, end_offset))

    if not regions:
        # ПрограммныйИнтерфейс не найден — модуль без public API.
        return []

    return regions


def _collect_doc_comment(text: str, signature_start: int) -> str:
    """Собирает doc-комментарий перед сигнатурой.

    Идём назад строка за строкой:
    - строка `// ...` → добавляем в doc
    - пустая → stop (между комментарием и методом часто пустая строка после
      БСП-конвенции «Пример: ...» — но обычно doc вплотную к сигнатуре)
    - non-comment → stop

    Возвращает «нормализованный» текст: без префиксов `//`, с переносами строк
    как в оригинале.
    """
    if signature_start <= 0:
        return ""
    before = text[:signature_start]
    lines = before.split("\n")
    # Идём с конца, пропускаем строки сигнатуры (могут быть пустые на отступе)
    # и собираем подряд идущие comment-lines.
    doc_lines: list[str] = []
    # Последняя строка перед сигнатурой может быть пустой (типичный pattern).
    # Дропаем trailing whitespace lines прежде чем собирать doc.
    while lines and not lines[-1].strip():
        lines.pop()
    while lines:
        line = lines[-1]
        stripped = line.strip()
        if not stripped:
            # Пустая строка ПОСЛЕ doc-комментариев — граница, останавливаемся
            break
        if not stripped.startswith("//"):
            break
        # Убираем префикс `//` и опциональный пробел после
        doc_lines.append(stripped[2:].lstrip(" "))
        lines.pop()
    doc_lines.reverse()
    return "\n".join(doc_lines).strip()


def _find_method_end(text: str, start: int, kind: str) -> int:
    """Возвращает offset после `КонецПроцедуры`/`КонецФункции`.

    Если не найден — возвращает len(text) (метод обрывается концом файла).
    """
    expected = "КонецПроцедуры" if kind == "Процедура" else "КонецФункции"
    pattern = re.compile(rf"^\s*{expected}\b", re.MULTILINE)
    match = pattern.search(text, start)
    if match:
        return match.end()
    return len(text)


def _find_matching_close_paren(chunk: str, open_pos: int) -> int:
    """Возвращает позицию `)` балансирующего `(` на open_pos. -1 если нет."""
    depth = 1
    i = open_pos + 1
    while i < len(chunk):
        c = chunk[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _collect_signature(text: str, start: int) -> tuple[str, int]:
    """Собирает сигнатуру (от `Процедура/Функция` до `Экспорт`).

    Сигнатура может быть многострочной из-за множества параметров.
    Учитываем nested parens (BSL допускает дефолтные значения с `(`).
    Возвращает (signature_normalized, end_offset_after_export).

    Если за закрывающей `)` сигнатуры не идёт `Экспорт` — возвращает («», 0).
    """
    chunk = text[start:start + 8000]
    open_pos = chunk.find("(")
    if open_pos < 0:
        return "", 0
    close_pos = _find_matching_close_paren(chunk, open_pos)
    if close_pos < 0:
        return "", 0
    # Что идёт после `)` — должен быть `Экспорт` (с разделителем-пробелом)
    after = chunk[close_pos:close_pos + 50]
    export_match = re.match(r"\)\s+Экспорт\b", after)
    if not export_match:
        return "", 0
    end_local = close_pos + export_match.end()
    signature_raw = chunk[:end_local]
    normalized = re.sub(r"\s+", " ", signature_raw).strip()
    return normalized, start + end_local


def _is_export_method(text: str, sig_start: int) -> bool:
    r"""True если непосредственно после балансирующей `)` сигнатуры стоит `Экспорт`.

    Раньше регулярка `\)\s+Экспорт\b` могла поймать Экспорт из следующего
    метода — теперь учитываем balanced parens.
    """
    sig, _ = _collect_signature(text, sig_start)
    return bool(sig)


def parse_module_methods(
    module_name: str,
    text: str,
    version: BSPVersion,
    source_path: str,
) -> Iterator[BSPMethod]:
    """Парсит один Module.bsl и yields все Экспорт-методы.

    Берёт методы только из `#Область ПрограммныйИнтерфейс`. Если регион
    не найден — берёт всё что в файле (на случай если модуль без #Область
    вообще).

    Args:
        module_name: имя CommonModule (название директории)
        text: содержимое Module.bsl
        version: «3.1» или «3.2»
        source_path: путь к файлу относительно корня репозитория ssl_*

    Yields:
        BSPMethod для каждого Экспорт-метода.
    """
    if not text or not text.strip():
        return

    regions = _extract_public_regions(text)
    if not regions:
        return

    for region_start, region_end in regions:
        region_text = text[region_start:region_end]
        # Ищем все Процедура|Функция в region
        for sig_match in _SIGNATURE_RE.finditer(region_text):
            local_start = sig_match.start()
            kind = sig_match.group(1)
            method_name = sig_match.group(2)

            # Проверяем что это именно Экспорт-метод
            if not _is_export_method(region_text, local_start):
                continue

            # Собираем сигнатуру
            signature, sig_end_local = _collect_signature(region_text, local_start)
            if not signature:
                continue

            # Doc-комментарий ДО сигнатуры
            doc_comment = _collect_doc_comment(region_text, local_start)

            # Тело: от sig_end до конца метода
            method_end_local = _find_method_end(region_text, sig_end_local, kind)
            body_full = region_text[sig_end_local:method_end_local].strip("\n")
            body_excerpt = body_full[:MAX_BODY_CHARS]

            method = BSPMethod(
                module_name=module_name,
                method_name=method_name,
                method_kind=kind,
                signature=signature,
                doc_comment=doc_comment,
                body_excerpt=body_excerpt,
                version=version,
                source_path=source_path,
            )

            # Cap общий size content (тело сильно урезано если очень большой
            # method, но doc + signature всегда сохраняются полностью).
            if len(method.content) > MAX_CONTENT_CHARS:
                # Урезаем body ещё сильнее
                allowed_body = MAX_CONTENT_CHARS - len(doc_comment) - len(signature) - 10
                if allowed_body < 100:
                    allowed_body = 100  # минимум
                method = BSPMethod(
                    module_name=method.module_name,
                    method_name=method.method_name,
                    method_kind=method.method_kind,
                    signature=method.signature,
                    doc_comment=method.doc_comment,
                    body_excerpt=method.body_excerpt[:allowed_body],
                    version=method.version,
                    source_path=method.source_path,
                )

            yield method


def _detect_version_from_root(root: Path) -> BSPVersion:
    """Определяет версию БСП по имени корневой папки.

    `ssl_3_1` → '3.1', `ssl_3_2` → '3.2'. По умолчанию '3.2' если
    не распознали.
    """
    name = root.name.lower()
    if "3_1" in name or "3.1" in name:
        return "3.1"
    return "3.2"


def load_bsp_modules(ssl_root: Path) -> Iterator[BSPMethod]:
    """Сканирует ssl_root/src/cf/CommonModules/* и yields все Экспорт-методы.

    Args:
        ssl_root: корневой каталог репозитория ssl_3_1 / ssl_3_2.
                  Должен содержать src/cf/CommonModules/.

    Raises:
        BSPLoaderError если ssl_root не существует или нет ожидаемой структуры.

    Yields:
        BSPMethod для каждого Экспорт-метода из всех CommonModules.
    """
    if not ssl_root.exists():
        raise BSPLoaderError(f"БСП root не найден: {ssl_root}")
    if not ssl_root.is_dir():
        raise BSPLoaderError(f"БСП root не каталог: {ssl_root}")

    common_modules_root = ssl_root / "src" / "cf" / "CommonModules"
    if not common_modules_root.is_dir():
        raise BSPLoaderError(
            f"Не найден src/cf/CommonModules/ в {ssl_root} — "
            "возможно структура отличается от стандартной выгрузки cf",
        )

    version = _detect_version_from_root(ssl_root)

    for module_dir in sorted(common_modules_root.iterdir()):
        if not module_dir.is_dir():
            continue
        module_bsl = module_dir / "Ext" / "Module.bsl"
        if not module_bsl.is_file():
            continue

        text = _read_text(module_bsl)
        if text is None:
            continue

        try:
            source_path = module_bsl.relative_to(ssl_root).as_posix()
        except ValueError:
            source_path = str(module_bsl)

        try:
            yield from parse_module_methods(
                module_name=module_dir.name,
                text=text,
                version=version,
                source_path=source_path,
            )
        except Exception:
            logger.exception(
                "BSP loader: parse_module_methods failed для %s — skip",
                module_bsl,
            )
            continue
