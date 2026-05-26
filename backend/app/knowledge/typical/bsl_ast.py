"""BSL AST parser через tree-sitter-bsl (production-grade, M-K2.5.1).

Использует community grammar `tree-sitter-bsl` 0.1.6 (1c-syntax). Парсит
BSL модуль в `BSLModule` со списком методов / регионов / директив
компиляции / doc-комментариев.

## Зачем tree-sitter а не regex

`bsp_loader.py` использует regex с балансировкой скобок — этого хватило
для plain БСП-методов, но ломается на:
- Доработках через `// Доработка START` маркеры
- Вложенных #Если внутри методов
- Строковых литералах с `Процедура` / `КонецФункции`
- Доллар-меточных строках (`Шаблон("Процедура Х(...)")` внутри)

Tree-sitter решает эти кейсы корректно за счёт полноценного AST.

## Производительность

- Lazy init parser (один Language объект на процесс).
- Парсинг ~10 МБ BSL → ~3-5 секунд (single-thread).
- Tree-sitter инкрементальный — re-parse изменённого файла мгновенный
  (Phase 8: индексация диффов).

## Что НЕ парсит

- Тела методов как AST (выдаёт raw text, тела разберёт Phase 2 query parser).
- `Перем X;` верхнего уровня модуля (Phase 4 graph builder).
- XDTO-схемы / СКД XML — там xml parser (Phase 3).
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any

import tree_sitter_bsl
from tree_sitter import Language, Node, Parser

from app.knowledge.typical.bsl_models import (
    BSLMethod,
    BSLMethodKind,
    BSLModule,
    BSLParameter,
    BSLRegion,
)

logger = logging.getLogger(__name__)


# ── Parser singleton ─────────────────────────────────────────────────


_parser_lock = threading.Lock()
_parser: Parser | None = None


def _get_parser() -> Parser:
    """Singleton парсер. Lazy init — Language создаётся один раз."""
    global _parser
    if _parser is not None:
        return _parser
    with _parser_lock:
        if _parser is None:
            lang = Language(tree_sitter_bsl.language())
            _parser = Parser(lang)
    return _parser


# ── Customization markers (CFE) ──────────────────────────────────────


# `// Доработка START <текст>` / `// Доработка END` — конвенция CFE.
# Используется для compare_with_typical (Phase 6 LLM tool).
# Применяется к УЖЕ очищенному doc_comment (без `//` префикса).
_CUSTOMIZATION_MARKER_RE = re.compile(
    r"Доработка(?:\s+(?:START|END|НАЧАЛО|КОНЕЦ))?\s*(.*)",
    re.IGNORECASE,
)


def _extract_customization_marker(doc_comment: str | None) -> str | None:
    """Ищет в doc_comment маркер доработки. Возвращает текст после маркера
    или пустую строку (если маркер без текста) или None если нет.
    """
    if not doc_comment:
        return None
    for line in doc_comment.splitlines():
        match = _CUSTOMIZATION_MARKER_RE.search(line)
        if match:
            return match.group(1).strip()
    return None


# ── Helpers для walk'а дерева ────────────────────────────────────────


def _node_text(node: Node, source: bytes) -> str:
    """Возвращает текст узла как UTF-8 строку."""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def _find_first_child(node: Node, type_name: str) -> Node | None:
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def _find_children(node: Node, type_name: str) -> list[Node]:
    return [c for c in node.children if c.type == type_name]


# ── Извлечение метода ────────────────────────────────────────────────


def _extract_parameters(params_node: Node, source: bytes) -> list[BSLParameter]:
    """Парсит `(А, Знач Б = 0, В = Неопределено)` → BSLParameter[]."""
    result: list[BSLParameter] = []
    for param_node in _find_children(params_node, "parameter"):
        result.append(_extract_one_parameter(param_node, source))
    return result


def _extract_one_parameter(param_node: Node, source: bytes) -> BSLParameter:
    """Один параметр: [Знач] identifier [= default_expression]."""
    by_value = False
    name = ""
    default: str | None = None

    # tree-sitter-bsl: VAL_KEYWORD = «Знач»
    # children: [VAL_KEYWORD?, identifier, ('=' default)?]
    seen_eq = False
    default_parts: list[str] = []

    for child in param_node.children:
        if child.type == "VAL_KEYWORD":
            by_value = True
        elif child.type == "identifier" and not name:
            name = _node_text(child, source)
        elif child.type == "=":
            seen_eq = True
        elif seen_eq:
            # Всё после `=` — выражение default-значения
            default_parts.append(_node_text(child, source))

    if default_parts:
        default = " ".join(default_parts).strip()

    return BSLParameter(name=name, by_value=by_value, default=default)


def _extract_method(
    node: Node,
    source: bytes,
    *,
    doc_comment: str | None,
    compile_directive: str | None,
    region: str | None,
) -> BSLMethod:
    """Превращает function_definition / procedure_definition в BSLMethod.

    Сохраняет body_source как сырой текст всего узла (включая сигнатуру
    и КонецФункции/КонецПроцедуры). Это удобно для:
    - LLM-карточек (Phase 5)
    - Query parser-а на телах (Phase 2)
    """
    kind = (
        BSLMethodKind.FUNCTION.value
        if node.type == "function_definition"
        else BSLMethodKind.PROCEDURE.value
    )

    name_node = _find_first_child(node, "identifier")
    name = _node_text(name_node, source) if name_node else ""

    params_node = _find_first_child(node, "parameters")
    parameters = (
        _extract_parameters(params_node, source) if params_node is not None else []
    )

    is_exported = _find_first_child(node, "EXPORT_KEYWORD") is not None

    body_source = _node_text(node, source)

    return BSLMethod(
        name=name,
        kind=kind,
        parameters=tuple(parameters),
        is_exported=is_exported,
        doc_comment=doc_comment,
        compile_directive=compile_directive,
        region=region,
        line_start=node.start_point[0] + 1,
        line_end=node.end_point[0] + 1,
        body_source=body_source,
        customization_marker=_extract_customization_marker(doc_comment),
    )


# ── Препроцессорные узлы (#Область / #КонецОбласти / #Если) ──────────


def _is_region_start(preproc: Node) -> bool:
    return _find_first_child(preproc, "PREPROC_REGION_KEYWORD") is not None


def _is_region_end(preproc: Node) -> bool:
    return _find_first_child(preproc, "PREPROC_ENDREGION_KEYWORD") is not None


def _is_if_directive(preproc: Node) -> bool:
    """`#Если ... #Тогда`, `#ИначеЕсли`, `#Иначе`, `#КонецЕсли`."""
    keywords = {c.type for c in preproc.children}
    return bool(
        keywords & {
            "PREPROC_IF_KEYWORD",
            "PREPROC_ELSIF_KEYWORD",
            "PREPROC_ELSE_KEYWORD",
            "PREPROC_ENDIF_KEYWORD",
        }
    )


def _is_compile_annotation(preproc: Node) -> bool:
    """`&НаСервере` / `&НаКлиенте` / `&НаСервереБезКонтекста` /
    `&ИзменениеИКонтроль("X")` — в tree-sitter-bsl парсится как
    `preprocessor` с child `annotation`.
    """
    return _find_first_child(preproc, "annotation") is not None


def _region_name(preproc: Node, source: bytes) -> str:
    ident = _find_first_child(preproc, "identifier")
    return _node_text(ident, source) if ident else ""


# ── Doc-комментарии ──────────────────────────────────────────────────


def _flush_doc_comment(lines: list[str]) -> str | None:
    """Превращает накопленные `// ...` строки в единый doc-блок.

    Возвращает None если список пуст. Каждая строка очищается от
    префикса `//` и leading/trailing whitespace.
    """
    if not lines:
        return None
    cleaned: list[str] = []
    for raw in lines:
        text = raw.lstrip()
        if text.startswith("//"):
            text = text[2:]
        cleaned.append(text.rstrip())
    return "\n".join(cleaned) if cleaned else None


# ── Compile directives (&НаСервере, &НаКлиенте, ...) ─────────────────


# В tree-sitter-bsl директивы могут идти как top-level узел `annotation`
# или как child внутри function_definition. На smoke-тесте видно что
# для `&НаСервере` парсер делает отдельный top-level узел до метода.
# Унифицированный набор имён которые точно являются директивами:
_DIRECTIVE_NODE_TYPES = {
    "compiler_directive",
    "compile_directive",
    "annotation",
    "compilation_directive",
}


def _is_directive_node(node: Node) -> bool:
    if node.type in _DIRECTIVE_NODE_TYPES:
        return True
    # Эвристика: top-level узел начинается с `&` — это directive
    if node.start_byte < node.end_byte:
        return False  # точную проверку делает caller через текст


# ── Main parsing entrypoint ──────────────────────────────────────────


def parse_module(
    source: str | bytes,
    module_path: str | None = None,
) -> BSLModule:
    """Парсит BSL модуль в BSLModule.

    `source` — UTF-8 строка или bytes. `module_path` — для трассировки
    в логах / errors (`backend/app/knowledge/typical/bsl_ast.py` может
    не знать путь, если парсит inline source).

    Не поднимает исключения на синтаксисе — `has_errors` отмечает
    наличие проблем. Это даёт graceful degradation: даже на ломаном
    модуле большинство методов извлекутся корректно.
    """
    if isinstance(source, str):
        source_bytes = source.encode("utf-8")
    else:
        source_bytes = source

    total_lines = source_bytes.count(b"\n") + 1

    parser = _get_parser()
    tree = parser.parse(source_bytes)
    root = tree.root_node

    methods: list[BSLMethod] = []
    regions: list[BSLRegion] = []
    has_preprocessor_branches = False

    # State машины walk'а:
    #   - region_stack: стек активных #Область (name, start_line, parent)
    #   - pending_doc_lines: накопленные // строки (для doc_comment)
    #   - pending_directive: текст последней & директивы (для compile_directive)
    region_stack: list[tuple[str, int, str | None]] = []
    pending_doc_lines: list[str] = []
    pending_directive: str | None = None

    def _reset_pending() -> None:
        nonlocal pending_directive
        pending_doc_lines.clear()
        pending_directive = None

    for child in root.children:
        text = _node_text(child, source_bytes).strip()

        if child.type == "line_comment":
            # Накапливаем — может стать doc_comment для следующего метода
            pending_doc_lines.append(_node_text(child, source_bytes))
            continue

        if child.type == "preprocessor":
            # Compile directive? `&НаСервере` / `&НаКлиенте` / etc
            # Это разные виды preprocessor — annotation внутри.
            if _is_compile_annotation(child):
                pending_directive = _node_text(child, source_bytes).strip()
                continue
            # Регион?
            if _is_region_start(child):
                name = _region_name(child, source_bytes)
                parent = region_stack[-1][0] if region_stack else None
                region_stack.append((name, child.start_point[0] + 1, parent))
                continue
            if _is_region_end(child):
                if region_stack:
                    name, start_line, parent = region_stack.pop()
                    regions.append(
                        BSLRegion(
                            name=name,
                            parent=parent,
                            line_start=start_line,
                            line_end=child.end_point[0] + 1,
                        )
                    )
                continue
            if _is_if_directive(child):
                # `#Если ... #Тогда` — пометим что в модуле есть условные ветки
                has_preprocessor_branches = True
                continue
            # Прочий preprocessor — сбрасываем pending doc/directive
            _reset_pending()
            continue

        # Compile directive: &НаСервере / &НаКлиенте / &ИзменениеИКонтроль / ...
        # tree-sitter-bsl на 0.1.6 может выдавать их как отдельный узел
        # или как часть function_definition.children. Поддерживаем оба.
        if child.type in _DIRECTIVE_NODE_TYPES or text.startswith("&"):
            pending_directive = text
            continue

        if child.type in ("function_definition", "procedure_definition"):
            # Если внутри function_definition есть directive — он перебивает
            # pending (на случай когда tree-sitter положил directive внутрь).
            inner_directive = pending_directive
            for inner in child.children:
                inner_text = _node_text(inner, source_bytes).strip()
                if inner.type in _DIRECTIVE_NODE_TYPES or (
                    inner.is_named and inner_text.startswith("&")
                ):
                    inner_directive = inner_text
                    break

            doc = _flush_doc_comment(pending_doc_lines)
            region_name_for_method = (
                region_stack[-1][0] if region_stack else None
            )
            method = _extract_method(
                child,
                source_bytes,
                doc_comment=doc,
                compile_directive=inner_directive,
                region=region_name_for_method,
            )
            methods.append(method)
            _reset_pending()
            continue

        # Любой иной non-trivial узел — сбрасываем pending doc/directive
        # (т.к. они "приклеиваются" только к ближайшему методу).
        if child.is_named:
            _reset_pending()

    # Закрытие незакрытых regions (для broken-syntax файлов)
    while region_stack:
        name, start_line, parent = region_stack.pop()
        regions.append(
            BSLRegion(
                name=name,
                parent=parent,
                line_start=start_line,
                line_end=total_lines,
            )
        )

    parse_errors: tuple[str, ...] = ()
    if root.has_error:
        parse_errors = (_collect_first_errors(root, source_bytes, limit=5),)

    return BSLModule(
        module_path=module_path,
        methods=tuple(methods),
        regions=tuple(regions),
        has_errors=root.has_error,
        parse_errors=parse_errors,
        has_preprocessor_branches=has_preprocessor_branches,
        total_lines=total_lines,
    )


def _collect_first_errors(root: Node, source: bytes, *, limit: int = 5) -> str:
    """Собирает первые N ERROR-узлов в человекочитаемый список."""
    errors: list[str] = []
    cursor = root.walk()
    visited = False
    while True:
        if not visited:
            node = cursor.node
            if node.type == "ERROR" or node.is_missing:
                snippet = _node_text(node, source)[:80].replace("\n", " ")
                errors.append(
                    f"line {node.start_point[0] + 1}: {node.type}"
                    + (f" ('{snippet}')" if snippet else "")
                )
                if len(errors) >= limit:
                    break
        if cursor.goto_first_child():
            visited = False
            continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return "; ".join(errors) if errors else ""
            visited = True
    return "; ".join(errors) if errors else ""


def parse_file(path: str | Path) -> BSLModule:
    """Читает файл (UTF-8 или cp1251 fallback) и парсит как BSL модуль."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        logger.warning(f"UTF-8 read failed for {p}, falling back to cp1251")
        source = p.read_text(encoding="cp1251")
    return parse_module(source, module_path=str(p))


def parse_string(source: str) -> BSLModule:
    """Удобная обёртка для парсинга inline-строки без указания пути."""
    return parse_module(source, module_path=None)
